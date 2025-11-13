#!/usr/bin/env python3
import argparse
import json
import time
import os

from ping import ping


def main():
    parser = argparse.ArgumentParser(description="ICMP Ping")
    parser.add_argument("target", help="Hostname or IP to ping")
    parser.add_argument("--count", type=int, default=4, help="Number of probes to send")
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
    print(f"JSON == {args.json}")
    logger = JsonlLogger(file_name=args.json)
    results = []

    for i in range(args.count):
        ping_result = ping(args.target, args.timeout)
        results.append(ping_result)
        logger.jsonl_write(ping_result)
        time.sleep(args.interval)

    print(f"Finished Pinging, results: {results}")

class JsonlLogger:
    def __init__(self, file_name=None):
        self.file_name = file_name
        if file_name is not None:
            self.path = os.getcwd() + file_name

    def jsonl_write(self, obj):
        if self.file_name is None:
            return

        obj.setdefault("ts", time.time())
        with open(self.path, "a") as f:
            f.write(json.dumps(obj) + "\n")

if __name__ == "__main__":
    main()
