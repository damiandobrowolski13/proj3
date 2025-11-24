import socket
import os
import sys
import struct
import time
import select
import binascii

ICMP_ECHO_REQUEST = 8
MAX_HOPS = 30
TIMEOUT = 2.0
TRIES = 2
# The packet that we shall send to each router along the path is the ICMP echo # request packet, which is exactly what we had used in the ICMP ping exercise. # We shall use the same packet that we built in the Ping exercise


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


def build_packet():
    # In the sendOnePing() method of the ICMP Ping exercise ,firstly the header of our
    # packet to be sent was made, secondly the checksum was appended to the header and
    # then finally the complete packet was sent to the destination.
    # Make the header in a similar way to the ping exercise.
    # Append checksum to the header.
    # So the function ending should look like this
    ID = os.getpid() & 0xFFFF
    header = struct.pack("bbHHh", ICMP_ECHO_REQUEST, 0, 0, ID, 1)
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
    return packet


def get_route(hostname):
    icmp = socket.getprotobyname("icmp")
    timeLeft = TIMEOUT
    
    for ttl in range(1, MAX_HOPS):
        for tries in range(TRIES):
            send_sock = None
            recv_sock = None
            try:
                # create sockets & set TTL/timeout
                dest_ip = socket.gethostbyname(hostname)
                send_sock = socket.socket(socket.AF_INET, socket.SOCK_RAW, icmp)
                recv_sock = socket.socket(socket.AF_INET, socket.SOCK_RAW, icmp)
                # recv timeout for this attempt
                recv_sock.settimeout(timeLeft)
                send_sock.setsockopt(socket.SOL_IP, socket.IP_TTL, ttl)

                # build ICMP packet & send
                pkt = build_packet()
                send_time = time.time()
                send_sock.sendto(pkt, (dest_ip, 0))

                # blocking recv w/ timeout on recv_sock
                recPacket, addr = recv_sock.recvfrom(4096)
                recv_time = time.time()
                # update remaining timeLeft
                timeLeft = max(0.0, timeLeft - (recv_time - send_time))

            except socket.timeout:
                # timed out for this probe, print star * continue tries
                print(f"{ttl:2d} *")
                continue
            else:
                # parse & handle different response types 
                try:
                    src = addr[0]
                    if len(recPacket) < 20:
                        print(f"{ttl:2d} {src} (short pkt)")
                        continue

                    ihl = (recPacket[0] & 0x0F) * 4
                    if len(recPacket) < ihl + 8:
                        print(f"{ttl:2d} {src} (short icmp)")
                        continue

                    icmp_off = ihl
                    try:
                        r_type, r_code, r_cksum, r_id, r_seq = struct.unpack("bbHHh", recPacket[icmp_off:icmp_off + 8])
                    except struct.error:
                        print(f"{ttl:2d} {src} (unpack error)")
                        continue

                    if r_type == 0:
                        # echo reply (dest reached)
                        payload = recPacket[icmp_off + 8:]
                        if len(payload) >= 8:
                            try:
                                ts_sent = struct.unpack("d", payload[:8])[0]
                                rtt = (recv_time - ts_sent) * 1000.0
                            except Exception:
                                rtt = (recv_time - send_time) * 1000.0
                        else:
                            rtt = (recv_time - send_time) * 1000.0
                        print(f"{ttl:2d} {src} {rtt:.3f}ms")
                        return

                    if r_type in (11, 3):
                        # Time exceeded or dest unreachable: parse inner packet
                        inner_off = icmp_off + 8
                        if len(recPacket) >= inner_off + 20:
                            inner_ihl = (recPacket[inner_off] & 0x0F) * 4
                            inner_icmp_off = inner_off + inner_ihl
                            if len(recPacket) >= inner_icmp_off + 16:
                                try:
                                    _, _, _, inner_id, inner_seq = struct.unpack("bbHHh", recPacket[inner_icmp_off:inner_icmp_off + 8])
                                    inner_payload = recPacket[inner_icmp_off + 8:inner_icmp_off + 16]
                                    if len(inner_payload) >= 8:
                                        try:
                                            ts_sent = struct.unpack("d", inner_payload[:8])[0]
                                            rtt = (recv_time - ts_sent) * 1000.0
                                        except Exception:
                                            rtt = (recv_time - send_time) * 1000.0
                                    else:
                                        rtt = (recv_time - send_time) * 1000.0
                                    print(f"{ttl:2d} {src} {rtt:.3f} ms")
                                except struct.error:
                                    print(f"{ttl:2d} {src} *")
                            else:
                                print(f"{ttl:2d} {src} *")
                        else:
                            print(f"{ttl:2d} {src} *")
                    else:
                        print(f"{ttl:2d} {src} (type={r_type} code={r_code})")
                except Exception:
                    print(f"{ttl:2d} *")
            finally:
                # close sockets
                try:
                    if send_sock:
                        send_sock.close()
                except:
                    pass
                try:
                    if recv_sock:
                        recv_sock.close()
                except:
                    pass

get_route("google.com")
