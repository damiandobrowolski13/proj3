import socket
import os
import sys
import struct
import time
import concurrent.futures

# from mytrace import JsonlLogger
from ping import calculate_icmp_checksum

# simple per-process cache for reverse lookups
_RDNS_CACHE = {}

def reverse_lookup(ip, timeout_ms=200):
    """return PTR name for ip or None on timeout/error, using cache"""
    if ip in _RDNS_CACHE:
        return _RDNS_CACHE[ip]
    if timeout_ms <= 0:
        try:
            name = socket.gethostbyaddr(ip)[0]
            _RDNS_CACHE[ip] = name
            return name
        except Exception:
            _RDNS_CACHE[ip] = None
            return None
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
        fut = ex.submit(socket.gethostbyaddr, ip)
        try:
            name = fut.result(timeout=timeout_ms / 1000.0)[0]
            _RDNS_CACHE[ip] = name
            return name
        except Exception:
            _RDNS_CACHE[ip] = None
            return None

ICMP_ECHO_REQUEST = 8

def build_packet(flow_id=0):
    # In the sendOnePing() method of the ICMP Ping exercise ,firstly the header of our
    # packet to be sent was made, secondly the checksum was appended to the header and
    # then finally the complete packet was sent to the destination.
    # Make the header in a similar way to the ping exercise.
    # Append checksum to the header.
    # Paris-style: use flow_id as identifier if provided, otherwise use PID
    ID = flow_id if flow_id != 0 else (os.getpid() & 0xFFFF)
    header = struct.pack("!BBHHH", ICMP_ECHO_REQUEST, 0, 0, ID, 1)
    data = struct.pack("d", time.time())
    # Calculate the checksum on the data and the dummy header.
    # Note: calculate_icmp_checksum already handles htons conversion
    myChecksum = calculate_icmp_checksum(header + data)

    header = struct.pack("!BBHHH", ICMP_ECHO_REQUEST, 0, myChecksum, ID, 1)
    packet = header + data
    return packet


# def get_route(hostname, max_ttl, timeout, probes, qps_limit, flow_id, logger: JsonlLogger):
def get_route(hostname, max_ttl, timeout, probes, qps_limit, flow_id, logger=None, no_resolve=False, rdns=False):
    dest_ip = socket.gethostbyname(hostname)
    icmp = socket.getprotobyname("icmp")
    responses = []

    print(f"Traceroute to {hostname} ({dest_ip}) with max-ttl={max_ttl}, probes={probes}, timeout={timeout}s, qps={qps_limit}, flow_id={flow_id}, no_resolve={no_resolve}, rdns={rdns}")

    done = False

    for ttl in range(1, max_ttl + 1):
        for tries in range(probes):
            probe_num = tries + 1
            send_sock = None
            recv_sock = None
            # naïve QPS limit (avoid div-by-zero)
            sleep_interval = (1.0 / qps_limit) if qps_limit > 0 else 0.0
            time.sleep(sleep_interval)

            try:
                # create sockets & set TTL/timeout
                send_sock = socket.socket(socket.AF_INET, socket.SOCK_RAW, icmp)
                recv_sock = socket.socket(socket.AF_INET, socket.SOCK_RAW, icmp)
                # recv timeout for this attempt
                recv_sock.settimeout(timeout)
                send_sock.setsockopt(socket.SOL_IP, socket.IP_TTL, ttl)

                # build ICMP packet & send
                pkt = build_packet(flow_id)
                send_time = time.time()
                send_sock.sendto(pkt, (dest_ip, 0))

                # blocking recv w/ timeout on recv_sock
                recPacket, addr = recv_sock.recvfrom(4096)
                recv_time = time.time()

            except socket.timeout:
                response_record = {
                    "ttl": ttl,
                    "err": "timeout"
                }
                print_response(response_record)
                responses.append(response_record)
                if logger:
                    logger.jsonl_write(response_record)
                continue
            else:
                rtt = (recv_time - send_time) * 1000.0
                src = addr[0]
                icmp_type, icmp_code, payload_timestamp, error = parse_response(recPacket)

                response_record = {
                    "dst": hostname,
                    "dst_ip": dest_ip,
                    "ttl": ttl,
                    "probe": probe_num,
                    "flow_id": flow_id,
                    "ts_send": send_time,
                    "ts_recv": recv_time,
                    "src": src,
                    "router_ip": src,
                    "router_name": None,
                    "rtt": rtt,
                    "payload_ts": payload_timestamp,
                    "type": icmp_type,
                    "code": icmp_code,
                    "err": error
                }
                # responses.append(response_record)
                # logger.jsonl_write(response_record)


                # perform reverse DNS if requested and not disabled
                if rdns and not no_resolve:
                    name = reverse_lookup(src, timeout_ms=200)
                    if name:
                        response_record["router_name"] = name

                responses.append(response_record)
                if logger:
                    logger.jsonl_write(response_record)
                print_response(response_record)

                # stop early if destination replied
                if icmp_type == 0 and src == dest_ip:
                    done = True
                    break

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

        if done:
            break

    summarize_responses(responses)

def summarize_responses(responses):
    print("\nSummary statistics:")
    stats = {}
    for resp in responses:
        ttl = resp['ttl']
        if ttl not in stats:
            stats[ttl] = {'rtts': [], 'total': 0}
        stats[ttl]['total'] += 1
        if 'rtt' in resp:
            stats[ttl]['rtts'].append(resp['rtt'])

    for ttl in sorted(stats.keys()):
        data = stats[ttl]
        rtts = data['rtts']
        total = data['total']
        loss_pct = (total - len(rtts)) / total * 100.0

        if rtts:
            min_rtt = min(rtts)
            max_rtt = max(rtts)
            avg_rtt = sum(rtts) / len(rtts)

            stddev = 0.0
            if len(rtts) > 1:
                variance = sum((x - avg_rtt) ** 2 for x in rtts) / (len(rtts) - 1)
                stddev = variance ** 0.5

            print(f"TTL {ttl}: min = {min_rtt:.3f} avg = {avg_rtt:.3f} max = {max_rtt:.3f} stddev = {stddev:.3f} ms, Loss = {loss_pct:.1f}%")
        else:
            print(f"TTL {ttl}: Loss = {loss_pct:.1f}%")


def parse_response(recPacket):
    icmp_type = None
    icmp_code = None
    payload_timestamp = None
    error = None

    try:
        if len(recPacket) < 20:
            return icmp_type, icmp_code, payload_timestamp, "short packet"

        internet_header_length = (recPacket[0] & 0x0F) * 4
        if len(recPacket) < internet_header_length + 8:
            return icmp_type, icmp_code, payload_timestamp, "short ICMP"

        icmp_offset = internet_header_length
        try:
            r_type, r_code, r_cksum, r_id, r_seq = struct.unpack("!BBHHH", recPacket[icmp_offset:icmp_offset + 8])
        except struct.error:
            return icmp_type, icmp_code, payload_timestamp, "unpack error"

        icmp_type = r_type
        icmp_code = r_code

        if icmp_type == 0:
            # echo reply (dest reached)
            payload = recPacket[icmp_offset + 8:]
            if len(payload) >= 8:
                try:
                    payload_timestamp = struct.unpack("d", payload[:8])[0]
                except Exception:
                    pass

        if r_type in (11, 3):
            # Time exceeded or dest unreachable: parse inner packet
            inner_off = icmp_offset + 8
            if len(recPacket) >= inner_off + 20:
                inner_ihl = (recPacket[inner_off] & 0x0F) * 4
                inner_icmp_off = inner_off + inner_ihl
                                # inner packet: try to parse inner ICMP header if at least 8 bytes present
                if len(recPacket) >= inner_icmp_off + 8:
                    try:
                        _, _, _, inner_id, inner_seq = struct.unpack("!BBHHH", recPacket[inner_icmp_off:inner_icmp_off + 8])
                        # inner payload may be truncated; try to extract timestamp if available
                        inner_payload = recPacket[inner_icmp_off + 8:inner_icmp_off + 16]
                        if len(inner_payload) >= 8:
                            try:
                                payload_timestamp = struct.unpack("d", inner_payload[:8])[0]
                            except Exception:
                                error = "timestamp unpack error"
                        else:
                            # truncated payload is OK: not a fatal error for traceroute stats
                            error = None
                    except struct.error:
                        error = "unpack error"
                else:
                    error = "packet too small"
            else:
                error = "packet too small"
    except Exception:
        error = "parsing Exception"

    return icmp_type, icmp_code, payload_timestamp, error


def print_response(response):
    msg = ""

    if response.get('ttl'):
        msg += f"{response['ttl']:2d}"

    if response.get('router_ip'):
        ip = response['router_ip']
        name = response.get('router_name')
        if name:
            msg += f" {name} ({ip})"
        else:
            msg += f" {ip}"
    else:
        msg += " *"

    rtt_val = response.get('rtt')
    if rtt_val is not None:
        msg += f" {rtt_val:.3f} ms"

    if response.get('err'):
        msg += f" ({response['err']})"

    print(msg)

