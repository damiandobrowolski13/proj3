#!/usr/bin/env python3
import argparse
import json
import time
import os

from ping import ping


def main():
    parser = argparse.ArgumentParser(description="ICMP Ping")
    parser.add_argument("target", help="Hostname or IP to ping")
    parser.add_argument("--count", type=int, default=1, help="Number of probes to send")
    parser.add_argument("--interval", type=float, default=1.0, help="Interval between probes (s)")
    parser.add_argument("--timeout", type=float, default=1.0, help="Per-probe timeout (s)")
    parser.add_argument("--json", type=str, help="Write per-probe results to JSONL file")
    parser.add_argument("--qps-limit", type=float, default=1.0,
                        help="Max probe rate (queries per second)") #TODO: implement this limit later
    parser.add_argument("--no-color", action="store_true", help="Disable color in output") #TODO: NEEDED?
    args = parser.parse_args()

    print(f"Pinging {args.target} with count={args.count}, interval={args.interval}s")
    do_pinging(args)

def do_pinging(args):
    logger = JsonlLogger(file_name=args.json)
    results = []

    for i in range(args.count):
        last_ping_ts = time.time()
        ping_result = ping(args.target, args.timeout)
        results.append(ping_result)
        logger.jsonl_write(ping_result)
        time.sleep(args.interval)

        time_since_last_ping = time.time() - last_ping_ts
        time_to_next_ping = args.interval - time_since_last_ping
        if time_to_next_ping > 0:
            time.sleep(time_to_next_ping)


    # Compute and print summary metrics
    print_summary(args.target, results)

def print_ping_result(result):
    """Print a single ping result to stdout."""
    # example ping output: Reply from 142.251.214.142: bytes=32 time=15ms TTL=58

    if result.get("err") is not None:
        print(f"Error: {result['err']}")
    else:
        print(f"Reply from {result['dst_ip']}: bytes={result['size']} time={result['rtt_ms']}ms TTL={result['ttl_reply']}")

def print_summary(target, results):
    """Print end-of-run summary like standard ping: min/avg/max/stddev RTT and loss %."""
    total = len(results)
    if total == 0:
        print("No packets sent.")
        return

    # Extract successful RTTs (where rtt_ms exists and is not None, and no error)
    rtts = []
    for r in results:
        rtt = r.get("rtt_ms")
        err = r.get("err")
        if rtt is not None and err is None:
            rtts.append(rtt)

    # Calculate Loss %
    received = len(rtts)
    lost = total - received
    loss_pct = (lost / total) * 100

    print(f"\n--- {target} ping statistics ---")
    print(f"{total} packets transmitted, {received} received, {loss_pct:.1f}% packet loss")

    if received > 0:
        min_rtt = min(rtts)
        max_rtt = max(rtts)
        avg_rtt = sum(rtts) / received

        # Calculate stddev TODO: review this logic
        if received > 1:
            variance = sum((x - avg_rtt) ** 2 for x in rtts) / (received - 1)
            stddev_rtt = variance ** 0.5
        else:
            stddev_rtt = 0.0

        print(f"RTT min: {min_rtt:.3f}ms avg: {avg_rtt:.3f}ms max:{max_rtt:.3f}ms stddev:{stddev_rtt:.3f}ms")

# example JSONL record from requirements:
# {"tool":"ping","ts_send":..., "ts_recv":..., "dst":"example.com","dst_ip":"93.184.216.34",
#  "seq":12,"ttl_reply":55,"rtt_ms":23.4,"icmp_type":0,"icmp_code":0,"err":null}
class JsonlLogger:
    def __init__(self, file_name=None):
        self.file_name = file_name
        if file_name is not None:
            self.path = os.path.join(os.getcwd(), file_name)

    def jsonl_write(self, obj):
        if self.file_name is None:
            return

        obj.setdefault("ts", time.time())
        with open(self.path, "a") as f:
            f.write(json.dumps(obj) + "\n")

if __name__ == "__main__":
    main()
