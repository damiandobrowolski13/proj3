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

## Test Results

### 4 Global Server Ping Results:
Quad9 DNS – Chicago POP
📍 Chicago, Illinois
**IP: 149.112.112.112**
```
--- 149.112.112.112 ping statistics ---
20 packets transmitted, 20 received, 0.0% packet loss
RTT min: 4.104ms avg: 6.537ms max:8.710ms stddev:1.819ms
```


Google DNS – Ashburn, VA POP
📍 Ashburn, Virginia
**IP: 8.8.8.8**

```
--- 8.8.8.8 ping statistics ---
20 packets transmitted, 20 received, 0.0% packet loss
RTT min: 4.185ms avg: 6.668ms max:10.580ms stddev:2.423ms
```


Cloudflare DNS – Frankfurt, Germany
Frankfurt, DE
**IP: 1.1.1.1**

```
--- 1.1.1.1 ping statistics ---
20 packets transmitted, 20 received, 0.0% packet loss
RTT min: 5.033ms avg: 6.749ms max:9.728ms stddev:1.683ms
```


Cloudflare DNS – Johannesburg, South Africa
📍 Johannesburg, ZA
**IP: 1.0.0.1**

```
--- 1.0.0.1 ping statistics ---
20 packets transmitted, 20 received, 0.0% packet loss
RTT min: 4.094ms avg: 6.914ms max:9.625ms stddev:2.082ms
```


### 4 Global Server Traceroute Results:
Quad9 DNS – Chicago POP
📍 Chicago, Illinois
**IP: 149.112.112.112**
```
Traceroute to 149.112.112.112 (149.112.112.112) with max-ttl=30, probes=3, timeout=2.0s, qps=1.0, flow_id=0, no_resolve=False, rdns=False
 1 192.168.12.1 7.244 ms
 1 192.168.12.1 7.522 ms
 1 192.168.12.1 3.498 ms
 2 100.109.144.1 7.830 ms
 2 100.109.144.1 7.537 ms
 2 100.109.144.1 7.752 ms
 3 10.255.34.65 8.488 ms
 3 10.255.34.65 4.233 ms
 3 10.255.34.65 4.040 ms
 4 10.255.34.81 8.407 ms
 4 10.255.34.81 8.317 ms
 4 10.255.34.81 9.055 ms
 5 10.255.15.33 4.031 ms
 5 10.255.15.33 7.932 ms
 5 10.255.15.33 7.345 ms
 6 10.255.15.17 11.170 ms
 6 10.255.15.17 14.692 ms
 6 10.255.15.17 10.365 ms
 7 10.255.27.17 18.624 ms
 7 10.255.27.17 10.164 ms
 7 10.255.27.17 19.059 ms
 8 10.255.10.14 8.141 ms
 8 10.255.10.14 4.423 ms
 8 10.255.10.14 8.360 ms
 9 206.41.110.42 18.611 ms
 9 206.41.110.42 9.242 ms
 9 206.41.110.42 8.829 ms
10 149.112.112.112 4.287 ms

Summary statistics:
TTL 1: min = 3.498 avg = 6.088 max = 7.522 stddev = 2.247 ms, Loss = 0.0%
TTL 2: min = 7.537 avg = 7.706 max = 7.830 stddev = 0.152 ms, Loss = 0.0%
TTL 3: min = 4.040 avg = 5.587 max = 8.488 stddev = 2.514 ms, Loss = 0.0%
TTL 4: min = 8.317 avg = 8.593 max = 9.055 stddev = 0.402 ms, Loss = 0.0%
TTL 5: min = 4.031 avg = 6.436 max = 7.932 stddev = 2.103 ms, Loss = 0.0%
TTL 6: min = 10.365 avg = 12.076 max = 14.692 stddev = 2.301 ms, Loss = 0.0%
TTL 7: min = 10.164 avg = 15.949 max = 19.059 stddev = 5.015 ms, Loss = 0.0%
TTL 8: min = 4.423 avg = 6.975 max = 8.360 stddev = 2.212 ms, Loss = 0.0%
TTL 9: min = 8.829 avg = 12.227 max = 18.611 stddev = 5.532 ms, Loss = 0.0%
TTL 10: min = 4.287 avg = 4.287 max = 4.287 stddev = 0.000 ms, Loss = 0.0%
```


Google DNS – Ashburn, VA POP
📍 Ashburn, Virginia
**IP: 8.8.8.8**

```
Traceroute to 8.8.8.8 (8.8.8.8) with max-ttl=30, probes=3, timeout=2.0s, qps=1.0, flow_id=0, no_resolve=False, rdns=False
 1 192.168.12.1 15.430 ms
 1 192.168.12.1 3.679 ms
 1 192.168.12.1 3.689 ms
 2 100.109.144.1 3.980 ms
 2 100.109.144.1 4.698 ms
 2 100.109.144.1 3.857 ms
 3 10.255.34.65 4.412 ms
 3 10.255.34.65 8.437 ms
 3 10.255.34.65 8.517 ms
 4 10.255.34.81 7.188 ms
 4 10.255.34.81 4.730 ms
 4 10.255.34.81 8.632 ms
 5 10.255.15.33 8.841 ms
 5 10.255.15.33 5.455 ms
 5 10.255.15.33 7.975 ms
 6 10.255.15.17 7.579 ms
 6 10.255.15.17 11.186 ms
 6 10.255.15.17 8.589 ms
 7 10.255.27.17 7.354 ms
 7 10.255.27.17 18.540 ms
 7 10.255.27.17 18.571 ms
 8 10.255.10.14 4.659 ms
 8 10.255.10.14 8.412 ms
 8 10.255.10.14 9.117 ms
 9 204.14.39.95 4.529 ms
 9 204.14.39.95 4.202 ms
 9 204.14.39.95 4.135 ms
10 142.250.209.169 4.999 ms
10 142.250.209.169 6.392 ms
10 142.250.209.169 8.361 ms
11 142.251.60.15 4.281 ms
11 142.251.60.15 4.519 ms
11 142.251.60.15 4.639 ms
12 8.8.8.8 4.436 ms

Summary statistics:
TTL 1: min = 3.679 avg = 7.599 max = 15.430 stddev = 6.781 ms, Loss = 0.0%
TTL 2: min = 3.857 avg = 4.178 max = 4.698 stddev = 0.454 ms, Loss = 0.0%
TTL 3: min = 4.412 avg = 7.122 max = 8.517 stddev = 2.347 ms, Loss = 0.0%
TTL 4: min = 4.730 avg = 6.850 max = 8.632 stddev = 1.973 ms, Loss = 0.0%
TTL 5: min = 5.455 avg = 7.424 max = 8.841 stddev = 1.759 ms, Loss = 0.0%
TTL 6: min = 7.579 avg = 9.118 max = 11.186 stddev = 1.861 ms, Loss = 0.0%
TTL 7: min = 7.354 avg = 14.822 max = 18.571 stddev = 6.467 ms, Loss = 0.0%
TTL 8: min = 4.659 avg = 7.396 max = 9.117 stddev = 2.396 ms, Loss = 0.0%
TTL 9: min = 4.135 avg = 4.289 max = 4.529 stddev = 0.211 ms, Loss = 0.0%
TTL 10: min = 4.999 avg = 6.584 max = 8.361 stddev = 1.689 ms, Loss = 0.0%
TTL 11: min = 4.281 avg = 4.480 max = 4.639 stddev = 0.182 ms, Loss = 0.0%
TTL 12: min = 4.436 avg = 4.436 max = 4.436 stddev = 0.000 ms, Loss = 0.0%
```


Cloudflare DNS – Frankfurt, Germany
Frankfurt, DE
**IP: 1.1.1.1**

```
Traceroute to 1.1.1.1 (1.1.1.1) with max-ttl=30, probes=3, timeout=2.0s, qps=1.0, flow_id=0, no_resolve=False, rdns=False
 1 192.168.12.1 7.259 ms
 1 192.168.12.1 3.832 ms
 1 192.168.12.1 3.636 ms
 2 100.109.144.1 7.850 ms
 2 100.109.144.1 7.900 ms
 2 100.109.144.1 7.254 ms
 3 10.255.34.65 4.497 ms
 3 10.255.34.65 4.395 ms
 3 10.255.34.65 5.966 ms
 4 10.255.34.81 4.811 ms
 4 10.255.34.81 8.619 ms
 4 10.255.34.81 4.228 ms
 5 10.255.15.33 5.485 ms
 5 10.255.15.33 7.821 ms
 5 10.255.15.33 3.934 ms
 6 10.255.15.17 4.046 ms
 6 10.255.15.17 7.029 ms
 6 10.255.15.17 4.609 ms
 7 10.255.27.17 15.449 ms
 7 10.255.27.17 14.700 ms
 7 10.255.27.17 21.935 ms
 8 10.255.10.14 8.562 ms
 8 10.255.10.14 5.968 ms
 8 10.255.10.14 8.143 ms
 9 * (timeout)
 9 * (timeout)
 9 157.238.230.234 8.494 ms
10 * (timeout)
10 * (timeout)
10 * (timeout)
11 129.250.4.23 8.539 ms
11 129.250.4.23 3.915 ms
11 129.250.4.23 4.100 ms
12 128.241.14.134 4.655 ms
12 128.241.14.134 8.567 ms
12 128.241.14.134 4.347 ms
13 141.101.73.93 13.162 ms
13 141.101.73.93 16.077 ms
13 141.101.73.93 12.274 ms
14 1.1.1.1 9.531 ms

Summary statistics:
TTL 1: min = 3.636 avg = 4.909 max = 7.259 stddev = 2.038 ms, Loss = 0.0%
TTL 2: min = 7.254 avg = 7.668 max = 7.900 stddev = 0.359 ms, Loss = 0.0%
TTL 3: min = 4.395 avg = 4.953 max = 5.966 stddev = 0.879 ms, Loss = 0.0%
TTL 4: min = 4.228 avg = 5.886 max = 8.619 stddev = 2.385 ms, Loss = 0.0%
TTL 5: min = 3.934 avg = 5.747 max = 7.821 stddev = 1.957 ms, Loss = 0.0%
TTL 6: min = 4.046 avg = 5.228 max = 7.029 stddev = 1.585 ms, Loss = 0.0%
TTL 7: min = 14.700 avg = 17.361 max = 21.935 stddev = 3.979 ms, Loss = 0.0%
TTL 8: min = 5.968 avg = 7.557 max = 8.562 stddev = 1.393 ms, Loss = 0.0%
TTL 9: min = 8.494 avg = 8.494 max = 8.494 stddev = 0.000 ms, Loss = 66.7%
TTL 10: Loss = 100.0%
TTL 11: min = 3.915 avg = 5.518 max = 8.539 stddev = 2.618 ms, Loss = 0.0%
TTL 12: min = 4.347 avg = 5.856 max = 8.567 stddev = 2.353 ms, Loss = 0.0%
TTL 13: min = 12.274 avg = 13.838 max = 16.077 stddev = 1.989 ms, Loss = 0.0%
TTL 14: min = 9.531 avg = 9.531 max = 9.531 stddev = 0.000 ms, Loss = 0.0%
```


Cloudflare DNS – Johannesburg, South Africa
📍 Johannesburg, ZA
**IP: 1.0.0.1**

```
Traceroute to 1.0.0.1 (1.0.0.1) with max-ttl=30, probes=3, timeout=2.0s, qps=1.0, flow_id=0, no_resolve=False, rdns=False
 1 192.168.12.1 7.210 ms
 1 192.168.12.1 3.536 ms
 1 192.168.12.1 3.929 ms
 2 100.109.144.1 3.968 ms
 2 100.109.144.1 3.543 ms
 2 100.109.144.1 4.185 ms
 3 10.255.34.65 4.477 ms
 3 10.255.34.65 8.232 ms
 3 10.255.34.65 4.059 ms
 4 10.255.34.81 4.078 ms
 4 10.255.34.81 5.029 ms
 4 10.255.34.81 3.760 ms
 5 10.255.15.33 3.539 ms
 5 10.255.15.33 3.688 ms
 5 10.255.15.33 7.703 ms
 6 10.255.15.17 17.619 ms
 6 10.255.15.17 10.699 ms
 6 10.255.15.17 16.148 ms
 7 10.255.27.17 21.889 ms
 7 10.255.27.17 18.610 ms
 7 10.255.27.17 53.417 ms
 8 10.255.10.14 3.939 ms
 8 10.255.10.14 8.093 ms
 8 10.255.10.14 4.591 ms
 9 157.238.230.234 4.562 ms
 9 157.238.230.234 5.725 ms
 9 * (timeout)
10 * (timeout)
10 * (timeout)
10 * (timeout)
11 129.250.4.23 5.037 ms
11 129.250.4.23 4.573 ms
11 129.250.4.23 4.809 ms
12 140.174.28.242 8.943 ms
12 140.174.28.242 27.784 ms
12 140.174.28.242 9.770 ms
13 141.101.73.220 14.608 ms
13 141.101.73.220 37.459 ms
13 141.101.73.220 5.450 ms
14 1.0.0.1 9.291 ms

Summary statistics:
TTL 1: min = 3.536 avg = 4.892 max = 7.210 stddev = 2.017 ms, Loss = 0.0%
TTL 2: min = 3.543 avg = 3.899 max = 4.185 stddev = 0.326 ms, Loss = 0.0%
TTL 3: min = 4.059 avg = 5.589 max = 8.232 stddev = 2.298 ms, Loss = 0.0%
TTL 4: min = 3.760 avg = 4.289 max = 5.029 stddev = 0.660 ms, Loss = 0.0%
TTL 5: min = 3.539 avg = 4.977 max = 7.703 stddev = 2.362 ms, Loss = 0.0%
TTL 6: min = 10.699 avg = 14.822 max = 17.619 stddev = 3.646 ms, Loss = 0.0%
TTL 7: min = 18.610 avg = 31.305 max = 53.417 stddev = 19.219 ms, Loss = 0.0%
TTL 8: min = 3.939 avg = 5.541 max = 8.093 stddev = 2.234 ms, Loss = 0.0%
TTL 9: min = 4.562 avg = 5.143 max = 5.725 stddev = 0.822 ms, Loss = 33.3%
TTL 10: Loss = 100.0%
TTL 11: min = 4.573 avg = 4.806 max = 5.037 stddev = 0.232 ms, Loss = 0.0%
TTL 12: min = 8.943 avg = 15.499 max = 27.784 stddev = 10.647 ms, Loss = 0.0%
TTL 13: min = 5.450 avg = 19.172 max = 37.459 stddev = 16.486 ms, Loss = 0.0%
TTL 14: min = 9.291 avg = 9.291 max = 9.291 stddev = 0.000 ms, Loss = 0.0%
```

### Time of Day Ping Comparison:
#### 7pm Test
```bash
sudo python3 myping.py www.cam.ac.uk --count 20 --interval 1 --timeout 1
```
```
Reply from 23.185.0.3: bytes=36 time=3.885ms TTL=51
Reply from 23.185.0.3: bytes=36 time=8.400ms TTL=51
Reply from 23.185.0.3: bytes=36 time=8.885ms TTL=51
Reply from 23.185.0.3: bytes=36 time=4.701ms TTL=51
Reply from 23.185.0.3: bytes=36 time=6.636ms TTL=51
Reply from 23.185.0.3: bytes=36 time=8.602ms TTL=51
Reply from 23.185.0.3: bytes=36 time=9.091ms TTL=51
Reply from 23.185.0.3: bytes=36 time=8.359ms TTL=51
Reply from 23.185.0.3: bytes=36 time=8.648ms TTL=51
Reply from 23.185.0.3: bytes=36 time=8.485ms TTL=51
Reply from 23.185.0.3: bytes=36 time=10.488ms TTL=51
Reply from 23.185.0.3: bytes=36 time=4.525ms TTL=51
Reply from 23.185.0.3: bytes=36 time=4.274ms TTL=51
Reply from 23.185.0.3: bytes=36 time=8.500ms TTL=51
Reply from 23.185.0.3: bytes=36 time=5.407ms TTL=51
Reply from 23.185.0.3: bytes=36 time=5.323ms TTL=51
Reply from 23.185.0.3: bytes=36 time=8.590ms TTL=51
Reply from 23.185.0.3: bytes=36 time=4.702ms TTL=51
Reply from 23.185.0.3: bytes=36 time=5.590ms TTL=51
Reply from 23.185.0.3: bytes=36 time=8.866ms TTL=51

--- www.cam.ac.uk ping statistics ---
20 packets transmitted, 20 received, 0.0% packet loss
RTT min: 3.885ms avg: 7.098ms max:10.488ms stddev:2.062ms
```
#### 10pm Test
```bash
sudo python3 myping.py www.cam.ac.uk --count 20 --interval 1 --timeout 1
```
```
Pinging www.cam.ac.uk with count=20, interval=1.0s
Reply from 23.185.0.3: bytes=36 time=3.950ms TTL=51
Reply from 23.185.0.3: bytes=36 time=4.514ms TTL=51
Reply from 23.185.0.3: bytes=36 time=4.549ms TTL=51
Reply from 23.185.0.3: bytes=36 time=4.235ms TTL=51
Reply from 23.185.0.3: bytes=36 time=4.340ms TTL=51
Reply from 23.185.0.3: bytes=36 time=3.398ms TTL=51
Reply from 23.185.0.3: bytes=36 time=4.055ms TTL=51
Reply from 23.185.0.3: bytes=36 time=4.267ms TTL=51
Reply from 23.185.0.3: bytes=36 time=5.371ms TTL=51
Reply from 23.185.0.3: bytes=36 time=5.182ms TTL=51
Reply from 23.185.0.3: bytes=36 time=4.155ms TTL=51
Reply from 23.185.0.3: bytes=36 time=5.092ms TTL=51
Reply from 23.185.0.3: bytes=36 time=4.648ms TTL=51
Reply from 23.185.0.3: bytes=36 time=4.557ms TTL=51
Reply from 23.185.0.3: bytes=36 time=4.388ms TTL=51
Reply from 23.185.0.3: bytes=36 time=4.504ms TTL=51
Reply from 23.185.0.3: bytes=36 time=4.282ms TTL=51
Reply from 23.185.0.3: bytes=36 time=4.404ms TTL=51
Reply from 23.185.0.3: bytes=36 time=5.804ms TTL=51
Reply from 23.185.0.3: bytes=36 time=4.324ms TTL=51

--- www.cam.ac.uk ping statistics ---
20 packets transmitted, 20 received, 0.0% packet loss
RTT min: 3.398ms avg: 4.501ms max:5.804ms stddev:0.532ms
```

#### Results
The average RTT difference between the two tests 7.098ms (7pm CST) and  4.501ms (10pm CST)
indicates a significant difference in network latency across different times of day.
One hypothesis for this is that network usage earlier in the day is greater both in Chicago and Cambridge
(server location) so later in the day we see greatly improved performance.