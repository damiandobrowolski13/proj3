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


def receive_one_ping(mySocket, ID, timeout, destAddr):
    while 1:
        what_ready = select.select([mySocket], [], [], timeout)
        if what_ready[0] == []:  # Timeout
            return "Request timed out."
        recPacket, addr = mySocket.recvfrom(1024)

        # TODO: read the packet and parse the source IP address, you will need this part for traceroute

        # TODO: calculate and return the round trip time for this ping

        # TODO: handle different response type and error code, display error message to the user


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


# EXAMPLE FIELDS FOR RESPONSE
# {"tool":"ping","ts_send":..., "ts_recv":..., "dst":"example.com","dst_ip":"93.184.216.34",
# "seq":12,"ttl_reply":55,"rtt_ms":23.4,"icmp_type":0,"icmp_code":0,"err":null}
def ping(host, timeout=1):
    return random.randint(0,100) #TODO: remove when actual ping is implemented

    # timeout=1 means: If one second goes by without a reply from the server,
    # the client assumes that either the client's ping or the server's pong is lost
    dest = socket.gethostbyname(host)
    print("Pinging " + dest + " using Python:")
    print("")
    delay = do_one_ping(dest, timeout)
    return delay

