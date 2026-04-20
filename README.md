# SDN Packet Logger — UE24CS252B

**Course:** Computer Networks — UE24CS252B  
**Project:** SDN Mininet-based Simulation (Orange Problem)  
**Topic:** Packet Logger using SDN Controller

---

## Problem Statement

Implement an SDN-based packet logger using **Mininet** and the **Ryu OpenFlow controller** that:

- Captures every packet traversing the network via `packet_in` controller events
- Identifies and classifies protocol types (ARP, ICMP, TCP, UDP, HTTP)
- Logs packet headers, ports, actions and sizes to a structured CSV file
- Demonstrates a **learning switch** with proactive flow rule installation
- Validates behaviour with at least two distinct test scenarios

---

## Project Structure

```
sdn_packet_logger/
├── packet_logger.py    # Ryu controller (OpenFlow 1.3)
├── topology.py         # Custom Mininet tree topology
├── test_scenarios.py   # Automated test scenarios (pingall, iperf, HTTP)
├── analyze_log.py      # Post-run CSV log analyser
├── packet_log.csv      # Generated at runtime by the controller
└── README.md
```

---

## Topology

```
         [ c0  Ryu controller  127.0.0.1:6633 ]
                       |  (OpenFlow 1.3)
                    [ s1 ]
                  /        \
             [ s2 ]        [ s3 ]
            /     \        /     \
          h1      h2     h3      h4
       10.0.0.1 10.0.0.2 10.0.0.3 10.0.0.4
```

| Node | Type    | IP / DPID               |
|------|---------|-------------------------|
| c0   | Controller | 127.0.0.1:6633       |
| s1   | OVS switch | dpid=0000000000000001 |
| s2   | OVS switch | dpid=0000000000000002 |
| s3   | OVS switch | dpid=0000000000000003 |
| h1   | Host    | 10.0.0.1/24             |
| h2   | Host    | 10.0.0.2/24             |
| h3   | Host    | 10.0.0.3/24             |
| h4   | Host    | 10.0.0.4/24             |

---

## Prerequisites

Ubuntu 20.04 / 22.04 with:

```
- Mininet (sudo apt install mininet -y)
- Open vSwitch (installed with Mininet)
- Ryu SDN framework (pip install ryu)
- Python 3.8+
- iperf (sudo apt install iperf -y)
- curl (sudo apt install curl -y)
```

---

## Setup & Installation

### Step 1 — Update the system

```bash
sudo apt update && sudo apt upgrade -y
```

### Step 2 — Install Mininet

```bash
sudo apt install mininet -y
# Verify
sudo mn --version
```

### Step 3 — Install Ryu

```bash
pip install ryu
# Verify
ryu-manager --version
```

> If you get an `eventlet` error, pin it:
> ```bash
> pip install eventlet==0.30.2
> pip install ryu
> ```

### Step 4 — Install test tools

```bash
sudo apt install iperf curl -y
```

### Step 5 — Clone / copy project files

```bash
# If from GitHub:
git clone https://github.com/<your-username>/sdn-packet-logger.git
cd sdn-packet-logger

# Or place all files in one folder and cd into it
cd sdn_packet_logger
```

---

## Running the Project

You need **two separate terminal windows**.

---

### Terminal 1 — Start the Ryu controller

```bash
ryu-manager packet_logger.py --observe-links
```

Expected output:
```
loading app packet_logger.py
loading app ryu.controller.ofp_handler
=== Packet Logger Controller Started ===
CSV log: /path/to/packet_log.csv
```

Leave this running.

---

### Terminal 2 — Start the Mininet topology

```bash
sudo python3 topology.py
```

Or using the built-in `mn` command directly:

```bash
sudo mn \
  --topo tree,depth=2,fanout=2 \
  --controller remote,ip=127.0.0.1,port=6633 \
  --switch ovsk,protocols=OpenFlow13 \
  --link tc
```

Expected output:
```
*** Network started
*** Switches: s1, s2, s3
*** Hosts: h1(10.0.0.1) h2(10.0.0.2) h3(10.0.0.3) h4(10.0.0.4)
*** Controller: c0 at 127.0.0.1:6633
*** Running connectivity test...
h1 -> h2 h3 h4
h2 -> h1 h3 h4
h3 -> h1 h2 h4
h4 -> h1 h2 h3
*** Results: 0% dropped (12/12 received)
mininet>
```

---

## Test Scenarios

### Scenario 1 — Connectivity (pingAll)

Inside the Mininet CLI:

```
mininet> pingall
```

Expected: **0% packet loss** across all 4 hosts.

---

### Scenario 2 — Latency measurement

```
mininet> h1 ping -c 10 h3
```

Observe RTT in Terminal 1 (controller log). Expected: ~4–6 ms (2 ms per hop × 2 hops).

---

### Scenario 3 — Throughput with iperf (TCP)

```
mininet> h3 iperf -s &
mininet> h1 iperf -c 10.0.0.3 -t 10
mininet> h3 kill %iperf
```

---

### Scenario 4 — Throughput with iperf (UDP)

```
mininet> h4 iperf -s -u &
mininet> h2 iperf -c 10.0.0.4 -u -b 5m -t 10
mininet> h4 kill %iperf
```

---

### Scenario 5 — HTTP traffic

```
mininet> h3 python3 -m http.server 8080 &
mininet> h1 curl http://10.0.0.3:8080/
mininet> h3 kill %python3
```

---

### Run all scenarios automatically

```bash
# With network already running (from topology.py):
mininet> py exec(open('test_scenarios.py').read()); run_all_scenarios(net)
```

---

## Inspect Flow Tables

While Mininet is running:

```
mininet> sh ovs-ofctl -O OpenFlow13 dump-flows s1
mininet> sh ovs-ofctl -O OpenFlow13 dump-flows s2
mininet> sh ovs-ofctl -O OpenFlow13 dump-flows s3
```

To see switch port mappings:

```
mininet> net
mininet> nodes
mininet> dump
```

---

## Analyse the Packet Log

After running traffic, stop Mininet (`exit`) and run:

```bash
python3 analyze_log.py
```

Sample output:

```
===========================================================
  PACKET LOG ANALYSIS  (142 packets total)
===========================================================

 Protocol Distribution:
   ARP      [#####..........................]    18  (12.7%)
   TCP      [##############................]    67  (47.2%)
   ICMP     [#######........................]    32  (22.5%)
   UDP      [####...........................]    25  (17.6%)

 Action Breakdown:
   FORWARD  [##############################]   138  (97.2%)
   FLOOD    [..............................]     4  (2.8%)

 Top Source IPs (top 5):
   10.0.0.1           42 packets
   10.0.0.3           38 packets
   ...

 Total bytes captured : 18,432 B  (18.0 KB)
 Dropped packets      : 0 (0.0%)
```

---

## OpenFlow Logic Summary

### Table-miss rule (installed at switch connect)

```
priority=0  match=*  action=CONTROLLER
```

Every unmatched packet is sent to the controller as a `packet_in` event.

### Learned forwarding rule (installed after first packet)

```
priority=1  match=(in_port=X, eth_src=M, eth_dst=N)  action=output:Y
idle_timeout=30s
```

After the controller learns which port a MAC address is reachable on, it installs this rule so subsequent packets in the same flow are forwarded directly without hitting the controller.

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `ryu-manager: command not found` | `pip install ryu` or use `python3 -m ryu.cmd.manager` |
| `eventlet` import error | `pip install eventlet==0.30.2 && pip install ryu` |
| Switches won't connect to controller | Check port 6633 is free: `sudo lsof -i :6633` |
| `sudo mn` fails | Clean up: `sudo mn -c` then retry |
| OVS not running | `sudo service openvswitch-switch start` |
| 100% packet loss in pingAll | Ensure controller started BEFORE topology |

---

## Cleanup

```bash
# Inside Mininet CLI
mininet> exit

# Clean up OVS state
sudo mn -c

# Stop Ryu (Ctrl+C in Terminal 1)
```

---

## References

1. Mininet overview — https://mininet.org/overview/
2. Mininet walkthrough — https://mininet.org/walkthrough/
3. Ryu documentation — https://ryu.readthedocs.io/en/latest/
4. OpenFlow 1.3 spec — https://opennetworking.org/wp-content/uploads/2014/10/openflow-spec-v1.3.0.pdf
5. Ryu simple switch example — https://github.com/faucetsdn/ryu/blob/master/ryu/app/simple_switch_13.py
6. PES University installation guide — `Mininet_Installation_Guide_on_UBUNTU_docx.pdf`
