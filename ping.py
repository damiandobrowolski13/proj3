import socket
import os
import sys
import struct
import time
import select
import binascii
import random

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

# EXAMPLE FIELDS FOR RESPONSE
# {"tool":"ping","ts_send":..., "ts_recv":..., "dst":"example.com","dst_ip":"93.184.216.34",
# "seq":12,"ttl_reply":55,"rtt_ms":23.4,"icmp_type":0,"icmp_code":0,"err":null}

def receive_one_ping(mySocket, ID, timeout, destAddr, sendTime):
    response = {
        "ts_send": sendTime,
        "dst_ip": destAddr,
        "id": ID,
        "size": 0, #TODO implement this IF needed
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
        response["ttl_reply"] = recPacket[8]
        # ICMP starts @ offset ip_head_len (b/c it's the IP payload)
        icmp_off = ip_head_len
        # icmp header is 1st 8 Bs of icmp pkt
        icmp_head = recPacket[icmp_off:icmp_off+8]
        icmp_type, icmp_code, icmp_cksum, icmp_id, icmp_seq = struct.unpack("bbHHh", icmp_head)
        
        # case 1: Echo Reply (type 0) - payload has timestamp
        if icmp_type == 0 and icmp_id == ID:
            receiveTime = time.time()
            response["rtt_ms"] = (receiveTime - sendTime) / 1000

            payload = recPacket[icmp_off + 8:]
            if len(payload) >= 8:
                try:
                    ts_sent = struct.unpack("d", payload[:8])[0]
                    rtt = time.time() - ts_sent
                    print(f"Received RTT: {rtt:.3f}ms, calculated RTT: {response['rtt_ms']:.3f}ms")
                    # TODO decide what sendTime to use, in packet or from arguments
                except struct.error:
                    response["err"] =  "Bad payload"
                    return response
            else:
                response["err"] = "No timestamp in payload"
                return response

        # TODO: handle different response type and error code, display error message to the user
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
                        _, _, _, inner_id = struct.unpack("bbHHh", recPacket[inner_icmp_off:inner_icmp_off+8])
                    except struct.error:
                        response["err"] = "Bad inner ICMP"
                        return response
                    # if inner_id matches our ID, extract original timestamp & compute RTT
                    if inner_id == ID:
                        inner_payload = recPacket[inner_icmp_off + 8:inner_icmp_off + 16]
                        try: 
                            ts_sent = struct.unpack("d", inner_payload)[0]
                            response["rtt_ms"] = time.time() - ts_sent # TODO: do we care about non-EchoReply RTTs?
                            return response
                        except struct.error:
                            response["err"] = "Unable to unpack payload into ts_send"
                            return response
            # return descriptive error msgs
            if icmp_type == 3:
                response["err"] =  f"Destination unreachable (code={icmp_code}) from {src_ip}"
                return response
            else:
                # time exceeded w/out matching inner packet
                response["err"] =  f"Time exceeded from {src_ip}"
                return response
            
        # for other cases of ICMP types, ignore/wait for timeout

def send_one_ping(mySocket, destAddr, ID):
    timestamp = time.time()
    # Header is type (8), code (8), checksum (16), id (16), sequence (16)
    myChecksum = 0
    # Make a dummy header with a 0 checksum

    # struct -- Interpret strings as packed binary data
    header = struct.pack("bbHHh", ICMP_ECHO_REQUEST, 0, myChecksum, ID, 1)
    data = struct.pack("d", timestamp)
    # Calculate the checksum on the data and the dummy header.
    myChecksum = checksum(str(header + data))
    # Get the right checksum, and put in the header
    if sys.platform == 'darwin':
        # Convert 16-bit integers from host to network byte order
        myChecksum = socket.htons(myChecksum) & 0xffff
    else:
        myChecksum = socket.htons(myChecksum)

    header = struct.pack("bbHHh", ICMP_ECHO_REQUEST, 0, myChecksum, ID, 1)
    packet = header + data
    # AF_INET address must be tuple, not str # Both LISTS and TUPLES consist of a number of objects
    mySocket.sendto(packet, (destAddr, 1))
    # which can be referenced by their position number within the object.
    return timestamp

def do_one_ping(destAddr, timeout):
    icmp = socket.getprotobyname("icmp")
    # SOCK_RAW is a powerful socket type. For more details: http://sock- raw.org/papers/sock_raw
    mySocket = socket.socket(socket.AF_INET, socket.SOCK_RAW, icmp)
    # use RNG for ID
    myID = random.randint(0,0xFFFF)
    send_time = send_one_ping(mySocket, destAddr, myID)
    delay = receive_one_ping(mySocket, myID, timeout, destAddr, send_time) # TODO needs more than just delay

    mySocket.close()
    return delay


def ping(host, timeout=1):
    dummy_RTT = random.randint(0,100) #TODO: remove when actual ping is implemented
    # return {'rtt': dummy_RTT}

    # timeout=1 means: If one second goes by without a reply from the server,
    # the client assumes that either the client's ping or the server's pong is lost
    dest = socket.gethostbyname(host)
    return do_one_ping(dest, timeout)

