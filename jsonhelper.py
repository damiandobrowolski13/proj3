# ...existing code...
#!/usr/bin/env python3
import json
import time
import os
import math
import argparse
from collections import defaultdict

# jwrite: safe JSONL append helper
# path: target file path (if None, function is a no-op)
# obj: dictionary to serialize as JSON on one line
# default_fields: dict of fields to set if missing (e.g., {"tool":"ping"})
def jwrite(path, obj, default_fields=None):
    """
    Append one JSON object to path. Adds ts if missing and merges default_fields.
    If path is None, does nothing.
    """
    if path is None:
        return
    default_fields = default_fields or {}
    # ensure defaults are present but donot override any explicit values
    for k, v in default_fields.items():
        obj.setdefault(k, v)
    # add timestamp if caller didn't provide 
    obj.setdefault("ts", time.time())
    # ensure directory exists when given nested path
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)
    # write one JSON object per line
    with open(path, "a") as f:
        f.write(json.dumps(obj) + "\n")

# OnlineStats: Welford's algorithm for online mean/stddev, plus min/max
class OnlineStats:
    def __init__(self):
        self.n = 0
        self.mean = 0.0
        self.M2 = 0.0
        self.min = float('inf')
        self.max = float('-inf')

    def add(self, x):
        self.n += 1
        d = x - self.mean
        self.mean += d / self.n
        self.M2 += d * (x - self.mean)
        if x < self.min: self.min = x
        if x > self.max: self.max = x

    def summary(self):
        var = self.M2 / (self.n - 1) if self.n > 1 else 0.0
        return {"count": self.n,
                "min": (self.min if self.n>0 else None),
                "avg": (self.mean if self.n>0 else None),
                "max": (self.max if self.n>0 else None),
                "stddev": math.sqrt(var)}

# summarize_ping: read a ping JSONL and print RTT stats and loss
def summarize_ping(jsonl_path):
    sent = 0
    recv = 0
    stats = OnlineStats()
    with open(jsonl_path) as f:
        for line in f:
            try:
                obj = json.loads(line)
            except Exception:
                # skip bad lines
                continue
            sent += 1
            # accept either unified "rtt" or legacy "rtt_ms"
            rtt = obj.get("rtt", obj.get("rtt_ms"))
            # only count RTTs for successful probes (no error)
            if rtt is not None and obj.get("err") is None:
                stats.add(float(rtt))
                recv += 1
    loss = (sent - recv) / sent * 100.0 if sent>0 else None
    s = stats.summary()
    print(f"Ping summary for {jsonl_path}: sent={sent}, recv={recv}, loss={loss:.1f}%")
    if s["count"]>0:
        print(f" RTT ms: min={s['min']:.3f}, avg={s['avg']:.3f}, max={s['max']:.3f}, stddev={s['stddev']:.3f}")
    else:
        print(" No successful RTT samples.")

# summarize_trace: aggregate traceroute JSONL by TTL/hop and print per-hop statistics
def summarize_trace(jsonl_path):
    # hops: map ttl -> {"stats": OnlineStats(), "total": probe_count_at_this_ttl}
    hops = defaultdict(lambda: {"stats": OnlineStats(), "total": 0})
    with open(jsonl_path) as f:
        for line in f:
            try:
                obj = json.loads(line)
            except Exception:
                continue
            # accept either "ttl" or "hop" field
            ttl = obj.get("ttl") or obj.get("hop")
            if ttl is None:
                continue
            hops[ttl]["total"] += 1
            # accept either unified "rtt" or legacy "rtt_ms"
            rtt = obj.get("rtt", obj.get("rtt_ms"))
            # treat any non-timeout probe with an RTT as a valid reply
            if rtt is not None and obj.get("err") != "timeout":
                hops[ttl]["stats"].add(float(rtt))
    print(f"Traceroute summary for {jsonl_path}:")
    for ttl in sorted(hops.keys()):
        data = hops[ttl]
        s = data["stats"].summary()
        total = data["total"]
        replies = s["count"]
        loss = (total - replies) / total * 100.0 if total>0 else 100.0
        if replies > 0:
            print(f" TTL {ttl}: replies={replies}/{total}, loss={loss:.1f}%, mean={s['avg']:.3f} ms, stddev={s['stddev']:.3f}")
        else:
            print(f" TTL {ttl}: 0 replies / {total} probes (loss=100.0%)")

# CLI entrypoint to run summaries from the terminal
def main():
    p = argparse.ArgumentParser()
    p.add_argument("--ping", nargs='*', help="ping JSONL files to summarize")
    p.add_argument("--trace", nargs='*', help="trace JSONL files to summarize")
    args = p.parse_args()
    if args.ping:
        for path in args.ping:
            summarize_ping(path)
            print()
    if args.trace:
        for path in args.trace:
            summarize_trace(path)
            print()

if __name__ == "__main__":
    main()