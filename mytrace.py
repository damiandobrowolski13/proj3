#!/usr/bin/env python3
import argparse
import json
import time
import os

import traceroute as tr


def main():
    parser = argparse.ArgumentParser(description="ICMP Traceroute")
    parser.add_argument("target", help="Hostname or IP to trace")
    parser.add_argument("--max-ttl", type=int, default=30, help="Maximum TTL (hops)")
    parser.add_argument("--probes", type=int, default=3, help="Probes per hop")
    parser.add_argument("--timeout", type=float, default=2.0, help="Per-probe timeout (s)")
    parser.add_argument("-n", action="store_true", help="Do not resolve hostnames (show IP only)")
    parser.add_argument("--rdns", action="store_true", help="Enable reverse DNS (200 ms budget per hop)")
    parser.add_argument("--flow-id", type=int, default=0,
                        help="Flow ID to keep probes consistent (Paris-style)")
    parser.add_argument("--json", type=str, help="Write per-probe results to JSONL file")
    parser.add_argument("--qps-limit", type=float, default=1.0,
                        help="Max probe rate (queries per second)")
    args = parser.parse_args()

    do_traceroute(args)

def do_traceroute(args):
    logger = JsonlLogger(file_name=args.json)

    tr.get_route(args.target, args.max_ttl, args.timeout, args.probes, args.qps_limit, logger)

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
