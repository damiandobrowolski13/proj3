import socket
import os
import sys
import struct
import time
import select

ICMP_ECHO_REQUEST = 8


def checksum(string):
    csum = 0
    countTo = (len(string) // 2) * 2
    count = 0

    while count < countTo:
        thisVal = ord(string[count+1]) * 256 + ord(string[count])
        csum = csum + thisVal
        csum = csum & 0xffffffff
        count = count + 2

    if countTo < len(string):
        csum = csum + ord(string[len(string) - 1])
        csum = csum & 0xffffffff

    csum = (csum >> 16) + (csum & 0xffff)
    csum = csum + (csum >> 16)
    answer = ~csum
    answer = answer & 0xffff
    answer = answer >> 8 | (answer << 8 & 0xff00)

    return answer

def calculate_icmp_checksum(packet):
    """
    Calculate the checksum for an ICMP packet.
        packet: ICMP header bytes with checksum field set to 0 + payload
    """
    # checksum() expects str, keep existing decode to avoid larger refactor
    myChecksum = checksum(packet.decode('latin-1'))
    # return raw 16-bit checksum (do not htons here), struct with "!" will emit network order
    return myChecksum & 0xffff

def verify_icmp_checksum(packet):
    """
    Verify the checksum of a received ICMP packet.
        packet: The ICMP packet bytes (header + data)
    """
    # Extract the received checksum (bytes 2-3 of ICMP header)
    received_checksum = struct.unpack("!H", packet[2:4])[0]

    # Zero out the checksum field for recalculation
    packet_with_zero_checksum = packet[:2] + b'\x00\x00' + packet[4:]

    # Calculate what the checksum should be
    calculated_checksum = calculate_icmp_checksum(packet_with_zero_checksum)

    return received_checksum == calculated_checksum

# EXAMPLE FIELDS FOR RESPONSE
# {"tool":"ping","ts_send":..., "ts_recv":..., "dst":"example.com","dst_ip":"93.184.216.34",
# "seq":12,"ttl_reply":55,"rtt_ms":23.4,"icmp_type":0,"icmp_code":0,"err":null}

def receive_one_ping(mySocket, ID, timeout, destAddr, sendTime, seq_num):
    response = {
        "ts_send": sendTime,
        "dst_ip": destAddr,
        "id": ID
    }

    while 1:
        what_ready = select.select([mySocket], [], [], timeout)
        if what_ready[0] == []:  # Timeout
            response["err"] = f"Request timed out. after: {timeout}s"
            return response

        recPacket, addr = mySocket.recvfrom(1024)

        src_ip = addr[0]
        # 1st B of IPv4 head = v.(4b) + head_len(4b)
        ip_head_len = (recPacket[0] & 0x0F) * 4
        # 8th B of IPv4 head = TTL(8b)
        response_ttl = recPacket[8]
        # ICMP starts @ offset ip_head_len (b/c it's the IP payload)
        icmp_off = ip_head_len
        # Extract the entire ICMP packet (header + payload)
        icmp_packet = recPacket[icmp_off:]

        # Verify the checksum of the received ICMP packet
        if not verify_icmp_checksum(icmp_packet):
            print(f"Invalid checksum from {src_ip}")
            continue # ignore invalid checksum packets

        # icmp header is 1st 8 Bs of icmp pkt
        icmp_head = icmp_packet[:8]
        # network (big-endian) order: type(1), code(1), checksum(2), id(2), seq(2)
        icmp_type, icmp_code, icmp_cksum, icmp_id, icmp_seq = struct.unpack("!BBHHH", icmp_head)

        if icmp_seq != seq_num:
            continue # ignore packets with wrong sequence number

        response["icmp_type"] = icmp_type
        response["icmp_code"] = icmp_code

        # case 1: Echo Reply (type 0) - payload has timestamp
        if icmp_type == 0 and icmp_id == ID:
            receiveTime = time.time()
            payload = icmp_packet[8:]
            response["ttl_reply"] = response_ttl
            response["size"] = len(recPacket)
            if len(payload) >= 8:
                try:
                    ts_sent_payload = struct.unpack("d", payload[:8])[0]
                    # compute RTT from payload timestamp (ms)
                    # ignore late/other replies (use timestamp to match)
                    if ts_sent_payload != sendTime:
                        print(f"Warning: Timestamp mismatch: payload_ts: {ts_sent_payload} != send_ts: {sendTime}")
                    response["rtt"] = (receiveTime - sendTime) * 1000.0
                except struct.error:
                    response["err"] = "Bad payload"
                    return response
            else:
                response["err"] = "No timestamp in payload"
                return response
            return response

        # case 2: Time Exceeded (11) or Dest Unreachable (3)
        # routers incl original IP head + 1st 8 Bs of original payload
        if icmp_type in (11, 3):
            inner_off = icmp_off + 8
            # make sure inner IP head present
            if len(recPacket) >= inner_off + 20:
                inner_ip_head_len = (recPacket[inner_off] & 0x0F) * 4
                inner_icmp_off = inner_off + inner_ip_head_len
                # ensure inner ICMP head + 8 Bs of inner payload present
                if len(recPacket) >= inner_icmp_off + 16:
                    try:
                        # unpack inner icmp head into fields (network order)
                        _, _, _, inner_id, _ = struct.unpack("!BBHHH", recPacket[inner_icmp_off:inner_icmp_off+8])
                    except struct.error:
                        response["err"] = "Bad inner ICMP"
                        return response
                    # if inner_id matches our ID, extract original timestamp & compute RTT
                    if inner_id == ID:
                        response["rtt"] = (receiveTime - sendTime) * 1000.0
                        return response
            # return descriptive error msgs
            if icmp_type == 3:
                response["err"] = f"Destination unreachable (code={icmp_code}) from {src_ip}"
            else:
                # time exceeded w/out matching inner packet
                response["err"] = f"Time exceeded from {src_ip}"
            return response
            
        # for other cases of ICMP types, ignore/wait for timeout

def send_one_ping(mySocket, destAddr, ID, seq_num):
    timestamp = time.time()
    seq_num = seq_num & 0xFFFF # handle unlikely case you ping more than 65K times :P

    # Header is type (8), code (8), checksum (16), id (16), sequence (16)
    # Make a dummy header with a 0 checksum
    header = struct.pack("!BBHHH", ICMP_ECHO_REQUEST, 0, 0, ID, seq_num)
    data = struct.pack("d", timestamp)

    # Calculate the checksum using the helper function
    myChecksum = calculate_icmp_checksum(header + data)

    # Rebuild header with the correct checksum
    header = struct.pack("!BBHHH", ICMP_ECHO_REQUEST, 0, myChecksum, ID, seq_num)
    packet = header + data

    # AF_INET address must be tuple, not str # Both LISTS and TUPLES consist of a number of objects
    mySocket.sendto(packet, (destAddr, 1))
    # which can be referenced by their position number within the object.
    return timestamp

def do_one_ping(destAddr, timeout, seq_num):
    icmp = socket.getprotobyname("icmp")
    # SOCK_RAW is a powerful socket type. For more details: http://sock- raw.org/papers/sock_raw
    mySocket = socket.socket(socket.AF_INET, socket.SOCK_RAW, icmp)
    # use RNG for ID
    myID = os.getpid() & 0xFFFF
    send_time = send_one_ping(mySocket, destAddr, myID, seq_num)
    ping_response = receive_one_ping(mySocket, myID, timeout, destAddr, send_time, seq_num)

    mySocket.close()
    return ping_response


def ping(host, timeout, seq_num):
    # timeout=1 means: If one second goes by without a reply from the server,
    # the client assumes that either the client's ping or the server's pong is lost
    dest = socket.gethostbyname(host)
    # print(f"Pinging {host} with Address: {dest} with Timeout: {timeout}s")
    return do_one_ping(dest, timeout, seq_num)

