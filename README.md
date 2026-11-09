# Smart CDN: Content Delivery with Software-Defined Networking

Six clients. Four content servers. One service address.

This project demonstrates how an SDN controller can choose a content server, route requests through a network, and keep new downloads working when a server or link fails. Clients connect to `10.0.0.100:5000`; the controller chooses a healthy replica using measured server load and network utilization.

The lab uses **Mininet, Open vSwitch, OpenFlow 1.3, OS-Ken, and Python TCP sockets**. It includes an automated demo, checksum-verified downloads, failure experiments, graphs, and a presentation guide.

## Start here

- **Run the project:** follow [Setup and execution](#setup-and-execution).
- **Present the final demo:** use [DEMO.md](DEMO.md) and [VIVA.md](VIVA.md).
- **Review recorded evidence:** open the [sample results](docs/sample-results/README.md).
- **Understand the implementation:** read the architecture and controller sections below.

## What the demo shows

| Experiment | What happens | What to inspect |
| --- | --- | --- |
| Normal delivery | Six clients download through one virtual address | Verified transfers and server choices |
| Congestion | Background downloads create real traffic | Measured utilization and new selections |
| Server failure | `srv1` stops, then returns | New requests avoid the failed replica |
| Link failure | A used network link goes down, then returns | New requests follow available paths |
| Restoration | Requests run after the faults are removed | Successful downloads and acceptance checks |

The saved run contains **78 successful requests, zero request failures, and 11 passing acceptance checks**. This is evidence from one recorded VM run, not a performance guarantee. See [validation details](VALIDATION.md) for what was rerun during repository preparation.

## Architecture

```mermaid
flowchart TD
    C["OS-Ken controller: virtual service 10.0.0.100"]
    C -. OpenFlow 1.3 .-> s1
    C -. OpenFlow 1.3 .-> s2
    C -. OpenFlow 1.3 .-> s3
    C -. OpenFlow 1.3 .-> s4
    C -. OpenFlow 1.3 .-> s5
    C -. OpenFlow 1.3 .-> s6
    s1 ---|50 Mbps| s2
    s1 ---|30 Mbps| s3
    s1 ---|30 Mbps| s4
    s2 ---|40 Mbps| s5
    s2 ---|40 Mbps| s6
    s3 ---|20 Mbps| s5
    s4 ---|20 Mbps| s6
    s3 ---|10 Mbps| s4
    s5 ---|10 Mbps| s6
    s3 --- S12[srv1 .11 / srv2 .12]
    s4 --- S34[srv3 .13 / srv4 .14]
    s5 --- C123[c1 .21 / c2 .22 / c3 .23]
    s6 --- C456[c4 .24 / c5 .25 / c6 .26]
```

All addresses use `10.0.0.0/24`. Host links are 100 Mbps/2 ms; inter-switch links have 5 ms delay. The original six switches, ten hosts and nineteen links are retained. TCLink applies bandwidth and delay. Static adjacency and MAC addresses are shared in `network_config.py`; tests verify these against Mininet ports.

## Setup and execution

Use a dedicated Kali/Debian Linux VM with sudo access. Install system dependencies and create the controller environment after cloning the repository:

```bash
sudo apt update
sudo apt install -y git python3 python3-venv python3-pip mininet openvswitch-switch python3-matplotlib
git clone <YOUR_GITHUB_REPOSITORY_URL> smart-cdn
cd smart-cdn
python3 -m venv sdn-env
./sdn-env/bin/python -m pip install -r requirements-controller.txt
```

The controller dependency is pinned to the locally installed OS-Ken 4.2.2. Mininet and plotting run with system Python; the controller runs in `sdn-env`. The existing development VM uses Python 3.14.7. If reusing that VM, keep its working environment and skip installation.

```bash
cd /path/to/smart-cdn
python3 -c 'import mininet, matplotlib'
./sdn-env/bin/python -c 'import os_ken'
sudo systemctl start openvswitch-switch
./demo.sh
```

Run `demo.sh` as your normal user. It asks sudo permission for Mininet; the controller stays unprivileged. Do not run multiple demos concurrently. The script generates sample files, starts OS-Ken, starts Mininet and four servers, performs experiments, plots available measurements, and terminates its processes. The default is `--scenario all`.

```bash
./demo.sh --scenario normal
./demo.sh --scenario congestion
./demo.sh --scenario server-failure
./demo.sh --scenario link-failure
./demo.sh --scenario cli
```

Each scenario first performs baseline connectivity and content tests. `cli` leaves the topology and servers running until you enter `exit`. Ctrl-C requests shutdown. After an abnormal crash on a dedicated Mininet VM, `sudo mn -c` removes stale Mininet resources (including other Mininet experiments).

To start the controller alone:

```bash
./sdn-env/bin/python -B sdn_launcher.py --results results/manual
# In another terminal, for the same output directory:
sudo python3 -B experiment.py --results results/manual --scenario cli
```

The experiment runner requires generated `content/`; run `python3 generate_content.py` first when using these separate commands.

## TCP communication

Servers listen on TCP port 5000. A newline-delimited JSON request names the desired file. The response header contains size, server identity and SHA-256, followed by exactly that many binary bytes. Buffered header parsing tolerates TCP fragmentation. Clients detect truncated transfers and checksum mismatches, use timeouts, write a temporary file, and commit only verified downloads. Missing files and traversal requests are rejected.

`generate_content.py` produces deterministic synthetic binary fixtures named `video.mp4`, `image.jpg`, `document.pdf` and `music.mp3`. They test binary delivery and are **not playable media or valid document encodings**. Every server serves the same immutable files.

## Controller and selection algorithm

Clients request `10.0.0.100:5000`. The controller answers ARP for the VIP and all known hosts. It never floods broadcasts. Generic IPv4 connectivity uses computed paths; unsupported L2 protocols and unknown destinations are dropped.

For a new TCP SYN, healthy reachable servers are ranked by:

```
link utilization = max(measured forward Mbps, measured reverse Mbps) / link capacity
link cost = 5 + 100 / max(0.1, capacity * (1 - min(0.99, utilization)))
server score = shortest-path cost + 20 * (active transfers + recent reservations)
               + 2 * measured server Mbps
```

Dijkstra computes paths. Recent two-second reservations help distribute simultaneous arrivals before the next load sample. Active transfers and server throughput come from server counters, not invented values. Weights are explanatory lab heuristics, not a production optimizer.

The controller installs connection-specific rules matching client IP, TCP source port and service port. At client ingress it translates VIP to the chosen physical server IP and destination MAC. On the reverse path, the client edge translates the server source back to the VIP and virtual MAC. OVS updates packet checksums. Established connections stay assigned to their server; changed network conditions affect new selections. Route entries expire after 30 seconds idle; session records expire after five minutes without a controller-observed packet.

## Monitoring and availability

OpenFlow port counters are sampled approximately once per second, converted to actual Mbps using elapsed time, and saved with utilization. Flow byte/packet counters are also collected. A process in c1 probes every server over the actual SDN network, retrieves active transfers and cumulative transmitted bytes, and atomically publishes health telemetry through the lab's shared filesystem. The controller treats telemetry older than four seconds as unavailable.

This intentionally simple lab telemetry channel avoids an additional management network. Loss of c1 or its telemetry process makes all service replicas unavailable to new selections; restart the demo to restore it. Server health probes themselves contribute a small amount of traffic.

## Failures and congestion

The server-failure experiment stops srv1, waits for both the health probe and controller to observe the failure, tests new requests against remaining servers, and restarts srv1. The link-failure experiment disables an inter-switch link used by a prior selected path, waits for OpenFlow port-state detection, tests alternate-path delivery, and restores the link.

Port changes invalidate application routes so subsequent packets cause path recomputation. The redundant topology remains intact. Existing connections to a failed server must reconnect; there is no state migration. Link changes can cause transient packet loss and TCP retransmission; new connections are the automated recovery acceptance target.

Congestion uses twelve simultaneous real video downloads to srv1 while six clients request the VIP, using the original limited-bandwidth links. This creates real server/network load. Decisions use measured load and bidirectional utilization. Saturation intensity depends on the VM; inspect `ports.csv` rather than assuming every run saturates a particular link. This basic experiment does not promise equal distribution or automatic migration of established sessions.

## Measurements and testing

Results go to `results/<timestamp>/`:

- `requests.csv`: completion time, per-request throughput, success, error, client and selected server.
- `decisions.csv`: server score, path and measured load at selection.
- `ports.csv`: actual transmit/receive Mbps and utilization.
- `flows.csv`: OpenFlow packet/byte counts and matches.
- `recovery.csv`: observed time from failure command to successful new transfer, including detection and transfer time.
- `connectivity.json`: controller-managed pingAll loss.
- `acceptance.json`: automated checks; false values make the demo exit nonzero.
- `summary.csv`, `graphs/`: averages and performance, per-client, distribution, link throughput and recovery plots.
- `controller.log`, `srv*.log`, `health.log`: implementation logs.

Replot existing measurements with `python3 plot_results.py results/<timestamp>`. An existing recorded demo run is included in `docs/sample-results/`; see its README for provenance and scope. Failure timing is an end-to-end observed recovery measure, not isolated controller processing latency. Average throughput is mean per-request throughput, not aggregate link capacity.

```bash
./sdn-env/bin/python -B -m unittest discover -s tests -v
```

Tests include selection policy, alternate paths, actual OS-Ken message serialization, bidirectional VIP rules, proxy ARP, binary transfer, six concurrent local clients, missing content and integrity failure. Socket tests skip only when the environment denies socket creation. Run the full demo to verify the actual controller/OVS/Mininet integration.

Implementation-environment status is recorded in `VALIDATION.md`. A saved live run is included; rerun integration on your VM with working sudo to validate your installation.

## Limitations and future improvements

This is a basic static IPv4 lab, not a production CDN. It does not implement discovery, IPv6, TLS, authentication, arbitrary host mobility, persistent connection migration, distributed telemetry, or automatic server process supervision. Replica restart is part of the experiment. Flow changes across switches are asynchronous, so TCP retransmissions can occur during rule setup. Session expiry is appropriate for these short lab transfers, not long-lived production sockets. Future work includes LLDP discovery, barrier-coordinated updates, durable connection tracking, HTTP delivery and repeated statistically controlled experiments.

## Repository guide

| File | Purpose |
| --- | --- |
| `demo.sh` | Start controller, run scenarios, and plot results |
| `topology.py`, `network_config.py` | Mininet topology and shared addressing/ports |
| `simple_switch_13.py`, `routing.py` | OpenFlow controller and path selection |
| `sdn_launcher.py`, `run_controller.py` | Controller entry points |
| `server.py`, `client.py`, `protocol.py` | Binary content protocol and integrity checks |
| `telemetry_agent.py` | Network health probes and load telemetry |
| `experiment.py`, `presentation.py` | Automated scenarios and readable demo output |
| `generate_content.py`, `plot_results.py` | Synthetic fixtures and measured plots |
| `tests/` | Controller, routing, protocol, and transfer checks |
| [DEMO.md](DEMO.md) | Live walkthrough and troubleshooting |
| [VIVA.md](VIVA.md) | Presentation script and likely questions |
| [VALIDATION.md](VALIDATION.md) | Verification evidence and environment limitations |
| [Sample results](docs/sample-results/README.md) | Saved acceptance checks, measurements, and graphs |

Generated content, local environments, working backups, and full experiment downloads are excluded from Git. `demo.sh` recreates the required fixtures.

## Troubleshooting

| Symptom | Check |
| --- | --- |
| `No module named os_ken` | Install `requirements-controller.txt` using `./sdn-env/bin/python -m pip`. |
| `No module named mininet` or `matplotlib` | Install the system packages from the setup instructions; the experiment uses system Python. |
| Switches do not connect | Start `openvswitch-switch`, check `controller.log`, and confirm port 6653 is free with `ss -ltnp`. |
| Interfaces remain after a crashed run | On the dedicated lab VM, run `sudo mn -c` before restarting. |
| Four transfer tests are skipped | Run the suite in a VM terminal that permits local sockets; see `VALIDATION.md`. |
| A demo acceptance check is false | Inspect that run's `acceptance.json`, request errors, controller log, and health log. |

## License

A license has not yet been selected by the author.
