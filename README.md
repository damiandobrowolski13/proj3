# proj3

## File
- `ping.py` — low-level ICMP send/receive: build/send Echo Request, verify replies, compute RTT, checksum handling
- `traceroute.py` — TTL-based probing: build ICMP probes, set socket TTL, parse Time Exceeded / Echo Reply, extract inner packet timestamp when present
- `myping.py` / `mytrace.py` — CLI frontends: parse args, enforce qps/interval, create JsonlLogger, call ping()/get_route()
- `jsonhelper.py` — JSONL writer (`jwrite`), `OnlineStats` (Welford), and summarizers for ping and traceroute JSONL
- `example_*.jsonl` — per-probe logs produced during runs

## Data flow
1. User runs `myping.py` / `mytrace.py` (CLI flags: count/probes, timeout, qps, `--json`, `-n`/`--rdns`, `--flow-id`)
2. CLI calls `ping()` / `get_route()`, which open raw sockets and send ICMP packets
3. Each probe result is appended as one JSON object to a JSONL file via `jwrite`
4. `jsonhelper.py` reads JSONL files and computes summaries (min/avg/max/stddev, loss; per-hop mean/stddev)

## Key behaviors & implementation notes
- Raw sockets require elevated privileges (run with `sudo`)
- ICMP header packing/unpacking uses network byte order (`struct` with `"!"` formats)
- RTT is recorded in a unified `"rtt"` field (milliseconds) across ping and traceroute logs
- Traceroute supports Paris-style `--flow-id` (ICMP identifier) to reduce ECMP artifacts
- Reverse DNS: optional `--rdns` with a 200 ms per-hop budget, implemented via `ThreadPoolExecutor` and a small cache
- QPS limiting: per-probe sleep based on `qps_limit`, with a safeguard against QPS > 1 unless acknowledged
- Truncated inner payloads in Time Exceeded replies are treated as valid replies (timestamp optional)

## Logging & measurement pipeline
- Each probe appends one JSON object to JSONL (one-line JSONL per probe)
- `jsonhelper.py` summarizes:
  - Ping: count sent/received, loss%, RTT min/avg/max/stddev
  - Traceroute: per-hop mean RTT, stddev, and loss%
- Measurement: 20 pings per target, traceroute with 3 probes/hop, repeated at a second time of day for comparison
### Time of Day Comparison:
(Run (night test)------

sudo python3 myping.py example.com --count 20 --interval 1 --timeout 1 --json example_ping_run2.jsonl

sudo python3 mytrace.py example.com --probes 3 --max-ttl 30 --timeout 2 --rdns --json example_trace_run2.jsonl


[for summaries]

python3 jsonhelper.py --ping example_ping.jsonl example_ping_run2.jsonl

python3 jsonhelper.py --trace example_trace.jsonl example_trace_run2.jsonl

[briefly compare]
blah blah blah
------)
