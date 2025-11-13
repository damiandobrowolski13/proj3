import socket
import os
import sys
import struct
import time
import select
import binascii

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


def receive_one_ping(mySocket, ID, timeout, destAddr):
    while 1:
        what_ready = select.select([mySocket], [], [], timeout)
        if what_ready[0] == []:  # Timeout
            return "Request timed out."
        recPacket, addr = mySocket.recvfrom(1024)

        # TODO: read the packet and parse the source IP address, you will need this part for traceroute
        src_ip = addr[0]
        # 1st B of IPv4 head = v.(4b) + head_len(4b)
        ip_head_len = (recPacket[0] & 0x0F) * 4
        # 8th B of IPv4 head = TTL(8b)
        ttl = recPacket[8]
        # ICMP starts @ offset ip_head_len (b/c it's the IP payload)
        icmp_off = ip_head_len
        # icmp header is 1st 8 Bs of icmp pkt
        icmp_head = recPacket[icmp_off:icmp_off+8]
        icmp_type, icmp_code, icmp_cksum, icmp_id, icmp_seq = struct.unpack("bbHHh", icmp_head)

        # TODO: calculate and return the round trip time for this ping
        # TODO: handle different response type and error code, display error message to the user
        
        # case 1: Echo Reply (type 0) - payload has timestamp
        if icmp_type == 0 and icmp_id == ID:
            payload = recPacket[icmp_off + 8:]
            if len(payload) >= 8:
                try:
                    ts_sent = struct.unpack("d", payload[:8])[0]
                    rtt = time.time() - ts_sent
                    return rtt 
                except struct.error:
                    return "Bad payload"
            else:
                return "No timestamp in payload"
            
        # case 2: Time Exceeded (11) or Dest Unreachable (3)
        # routers incl original IP head + 1st 8 Bs of original payload
        if icmp_type in (11, 3):
            inner_off = icmp_off + 8
            # make sure inner IP head present
            if len(recPacket) >= inner_off + 20:
                inner_ip_head_len = (recPacket[inner_off] & 0x0F) & 4
                inner_icmp_off = inner_off + inner_ip_head_len
                # ensure inner ICMP head + 8 Bs of inner payload present
                if len(recPacket) >= inner_icmp_off + 16:
                    try:
                        _, _, _, inner_id = struct.unpack("bbHHh", recPacket[inner_icmp_off:inner_icmp_off+8])
                    except struct.error:
                        return "Bad inner ICMP"
                    # if inner_id matches our ID, extract original timestamp & compute RTT
                    if inner_id == ID:
                        inner_payload = recPacket[inner_icmp_off + 8:inner_icmp_off + 16]
                        try: 
                            ts_sent = struct.unpack("d", inner_payload)[0]
                            rtt = time.time() - ts_sent
                            return rtt  
                        except struct.error:
                            return None
            # return descriptive error msgs
            if icmp_type == 3:
                return f"Destination unreachable (code={icmp_code}) from {src_ip}"
            else:
                # time exceeded w/out matching inner packet
                return f"Time exceeded from {src_ip}"
            
        # for other cases of ICMP types, ignore/wait for timeout

def send_one_ping(mySocket, destAddr, ID):
    # Header is type (8), code (8), checksum (16), id (16), sequence (16)
    myChecksum = 0
    # Make a dummy header with a 0 checksum

    # struct -- Interpret strings as packed binary data
    header = struct.pack("bbHHh", ICMP_ECHO_REQUEST, 0, myChecksum, ID, 1)
    data = struct.pack("d", time.time())
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


def do_one_ping(destAddr, timeout):
    icmp = socket.getprotobyname("icmp")
    # SOCK_RAW is a powerful socket type. For more details: http://sock- raw.org/papers/sock_raw
    mySocket = socket.socket(socket.AF_INET, socket.SOCK_RAW, icmp)
    # Return the current process i
    myID = os.getpid() & 0xFFFF
    send_one_ping(mySocket, destAddr, myID)
    delay = receive_one_ping(mySocket, myID, timeout, destAddr)

    mySocket.close()
    return delay


def ping(host, timeout=1):
    # timeout=1 means: If one second goes by without a reply from the server,
    # the client assumes that either the client's ping or the server's pong is lost
    dest = socket.gethostbyname(host)
    print("Pinging " + dest + " using Python:")
    print("")
    # Send ping requests to a server separated by approximately one second
    while 1:
        delay = do_one_ping(dest, timeout)
        print(delay)
        time.sleep(1)  # one second
    return delay


ping("google.com")
