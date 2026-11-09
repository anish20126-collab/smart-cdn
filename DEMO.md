# Basic live demonstration

Run from your **Kali VM terminal**, where sudo works:

```bash
cd /path/to/smart-cdn
sudo systemctl start openvswitch-switch
./sdn-env/bin/python -B -m unittest discover -s tests -v
./demo.sh
```

Enter your VM password when sudo asks. The script runs the controller as your normal user and uses sudo for the Mininet process. Allow several minutes for actual transfers and experiments.

Expected observations (these are expectations, not previously recorded results):

1. Six switches connect to OS-Ken on port 6653.
2. Controller-managed pingAll reports zero packet loss.
3. All six clients receive content, with SHA-256 verified before files are committed.
4. Requests to the same VIP use more than one server. Selected servers appear in terminal output and `decisions.csv`.
5. Congestion starts twelve real background transfers. Port statistics and server counters change; subsequent VIP selections incorporate those measurements.
6. srv1 is stopped, marked unavailable, and new requests use srv2–srv4. srv1 is restarted afterward.
7. An actually used inter-switch link goes down, the controller invalidates routes, and new requests take alternate paths. The link is restored.
8. The script prints acceptance checks and a results directory. Inspect any false acceptance check; it is not silently treated as success.

```bash
ls -td results/*/
# Replace <run> with the directory printed by demo.sh:
cat results/<run>/acceptance.json
cat results/<run>/summary.csv
cat results/<run>/recovery.csv
cat results/<run>/decisions.csv
ls results/<run>/graphs/
```

For interactive evaluation:

```bash
./demo.sh --scenario cli
```

At `mininet>`:

```text
net
nodes
pingall
c1 python3 client.py 10.0.0.100 video.mp4 --output /tmp/c1-video.bin
c2 python3 client.py 10.0.0.100 document.pdf --output /tmp/c2-document.bin
sh ovs-ofctl -O OpenFlow13 dump-flows s5
sh ovs-ofctl -O OpenFlow13 dump-ports s3
link s3 s5 down
c1 python3 client.py 10.0.0.100 image.jpg
link s3 s5 up
exit
```

For focused automated scenarios, use `./demo.sh --scenario server-failure`, `link-failure`, or `congestion`. Failure recovery measurements apply to new connections. A connection whose server dies must reconnect.

If the controller does not connect, inspect the printed run's `controller.log`, check that 6653 is free (`ss -ltnp`), and confirm OVS is running. If stale Mininet interfaces remain after a crash, run `sudo mn -c` on this dedicated lab VM before retrying. Do not run two demos at once.

## Teacher-facing output

The same `./demo.sh` command now prints a compact topology, numbered stages, controller health snapshots, per-client PASS/FAIL with SHA-256 verification, controller-selected switch routes, measured selection inputs, fault detection and recovery explanations, and a final readable checklist. The raw CSV and acceptance JSON outputs remain available.

Read `VIVA.md` for a short presentation script, explanations of each stage, and likely teacher questions with answers. Route output is matched to the request using its actual TCP source port; unavailable route evidence is reported rather than guessed.
