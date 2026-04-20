<div align="center">

```
╔═══════════════════════════════════════════════════════════════╗
║                                                               ║
║        ███████╗██████╗ ███╗   ██╗                            ║
║        ██╔════╝██╔══██╗████╗  ██║                            ║
║        ███████╗██║  ██║██╔██╗ ██║                            ║
║        ╚════██║██║  ██║██║╚██╗██║                            ║
║        ███████║██████╔╝██║ ╚████║                            ║
║        ╚══════╝╚═════╝ ╚═╝  ╚═══╝                            ║
║                                                               ║
║         P A C K E T   L O G G E R                            ║
║         Software Defined Networking — UE24CS252B              ║
║                                                               ║
╚═══════════════════════════════════════════════════════════════╝
```

<img src="https://img.shields.io/badge/OpenFlow-1.0-blue?style=for-the-badge&logo=cisco&logoColor=white"/>
<img src="https://img.shields.io/badge/Controller-POX-purple?style=for-the-badge"/>
<img src="https://img.shields.io/badge/Mininet-2.3-green?style=for-the-badge"/>
<img src="https://img.shields.io/badge/Python-3.x-yellow?style=for-the-badge&logo=python&logoColor=white"/>
<img src="https://img.shields.io/badge/OVS-OpenVSwitch-orange?style=for-the-badge"/>

> **Every packet has a story. This controller reads them all.**

</div>

---

## What is this?

A fully functional **Software Defined Network** running on a single machine — four virtual hosts, three OpenFlow switches, one controller brain — and every single packet that moves across this network gets **captured, classified, and logged** in real time.

When `h1` pings `h3`, the switch doesn't just forward it. It asks the controller: *"What do I do with this?"* The controller learns, decides, installs a rule, and writes the event to a CSV log with the protocol type, source, destination, ports, size, and action taken.

That's SDN. That's this project.

---

## Architecture

```
                    ┌─────────────────────────┐
                    │     POX Controller      │
                    │   packet_logger.py      │
                    │   127.0.0.1 : 6633      │
                    └────────────┬────────────┘
                                 │  OpenFlow 1.0
                    ┌────────────▼────────────┐
                    │          s1             │
                    │     (root switch)       │
                    └──────┬──────────┬───────┘
                           │          │
              ┌────────────▼──┐  ┌────▼────────────┐
              │      s2       │  │       s3         │
              │ (access sw)   │  │  (access sw)     │
              └──┬────────┬───┘  └───┬──────────┬──┘
                 │        │          │           │
           ┌─────▼─┐  ┌───▼──┐  ┌───▼──┐  ┌────▼──┐
           │  h1   │  │  h2  │  │  h3  │  │  h4   │
           │.0.0.1 │  │.0.0.2│  │.0.0.3│  │ .0.0.4│
           └───────┘  └──────┘  └──────┘  └───────┘
```

| Node | Role | Address |
|------|------|---------|
| `c0` | POX Controller | `127.0.0.1:6633` |
| `s1` | Root OVS Switch | dpid `00:00:00:00:00:01` |
| `s2` | Access Switch | dpid `00:00:00:00:00:02` |
| `s3` | Access Switch | dpid `00:00:00:00:00:03` |
| `h1` | Host | `10.0.0.1/24` |
| `h2` | Host | `10.0.0.2/24` |
| `h3` | Host | `10.0.0.3/24` |
| `h4` | Host | `10.0.0.4/24` |

---

## Project Files

```
SDN-Project/
│
├── packet_logger.py      ← POX controller component
│                           Handles packet_in events
│                           MAC learning + flow rule installation
│                           Protocol classification + CSV logging
│
├── topology.py           ← Custom Mininet topology
│                           tree depth=2 fanout=2
│                           Connects to remote POX controller
│
├── test_scenarios.py     ← Automated test runner
│                           pingall, iperf TCP, iperf UDP, HTTP, netcat
│
├── analyze_log.py        ← Post-run CSV analyser
│                           Protocol distribution, top IPs, stats
│
└── README.md             ← You are here
```

---

## How the Controller Works

### 1. Table-miss → packet_in

Every switch starts with one rule: *"if nothing matches, send to controller."*

```
priority = 0   match = *   action = CONTROLLER
```

### 2. Controller receives packet_in

The `_handle_PacketIn` function fires. It:
- Reads the Ethernet frame
- Learns `src_mac → in_port` mapping
- Looks up `dst_mac` in the table

### 3. Classify the protocol

```
Ethernet
├── ethertype 0x0806  →  ARP
└── ethertype 0x0800  →  IPv4
    ├── protocol 1    →  ICMP
    ├── protocol 6    →  TCP
    │   └── dst_port 80/8080/8000  →  HTTP
    └── protocol 17   →  UDP
```

### 4. Forward + install flow rule

```
If dst_mac is known  →  FORWARD to specific port + install flow rule
If dst_mac unknown   →  FLOOD to all ports
```

The installed flow rule:
```
priority = 1
match    = (in_port=X, eth_src=M, eth_dst=N)
action   = output:Y
timeout  = 30s idle
```

After this, subsequent packets in the same flow bypass the controller entirely — the switch handles them at line rate.

### 5. Log everything

Every `packet_in` event writes one row to `packet_log.csv`:

```
timestamp, switch_dpid, in_port, eth_src, eth_dst, eth_type,
protocol, ip_src, ip_dst, src_port, dst_port, pkt_size, action
```

---

## Setup

### Prerequisites

```bash
# Arch Linux
sudo pacman -S openvswitch python git iperf openbsd-netcat

# Start OVS (required before mn)
sudo systemctl start ovsdb-server
sudo systemctl start ovs-vswitchd

# Clone POX (no pip needed — pure Python)
git clone https://github.com/noxrepo/pox.git ~/pox

# Install Mininet from source
git clone https://github.com/mininet/mininet.git ~/mininet
cd ~/mininet && sudo python3 setup.py install && sudo make install
```

### Install this project

```bash
git clone https://github.com/Chidvilas-Adi/SDN-Project.git
cp SDN-Project/packet_logger.py ~/pox/ext/
```

---

## Running

Two terminals. Always start the controller first.

**Terminal 1 — Controller**
```bash
cd ~/pox
python3 pox.py log.level --DEBUG packet_logger
```

**Terminal 2 — Network**
```bash
sudo mn --topo tree,depth=2,fanout=2 \
        --controller remote,ip=127.0.0.1,port=6633 \
        --switch ovsk,protocols=OpenFlow10
```

---

## Test Scenarios

### Scenario 1 — Connectivity (ICMP / ARP)
```
mininet> pingall
# Expected: 0% packet loss
# POX log: ARP floods first, then ICMP forwards
```

### Scenario 2 — Latency measurement
```
mininet> h1 ping -c 10 h3
# First ping ~20ms (ARP + flow install), rest <1ms (rule hit)
```

### Scenario 3 — TCP throughput
```
mininet> h3 iperf -s &
mininet> h1 iperf -c 10.0.0.3 -t 10
mininet> h3 kill %iperf
```

### Scenario 4 — UDP throughput
```
mininet> h4 iperf -s -u &
mininet> h2 iperf -c 10.0.0.4 -u -b 10m -t 10
mininet> h4 kill %iperf
```

### Scenario 5 — HTTP traffic
```
mininet> h3 python3 -m http.server 80 &
mininet> h1 curl http://10.0.0.3/
# Logged as HTTP (dst_port=80), not TCP
```

### Scenario 6 — Raw TCP / UDP (netcat)
```
mininet> h2 nc -l -p 9999 &
mininet> h1 sh -c 'echo "hello" | nc 10.0.0.2 9999'

mininet> h2 nc -u -l -p 5005 &
mininet> h1 sh -c 'echo "udp" | nc -u -w1 10.0.0.2 5005'
```

---

## Reading the Output

### POX Console (Terminal 1)
```
[12:01:03.421] dpid=00-00-00-00-00-01 port=1 | ARP   | 10.0.0.1 -> 10.0.0.3 | FLOOD
[12:01:03.445] dpid=00-00-00-00-00-01 port=3 | ICMP  | 10.0.0.3 -> 10.0.0.1 | FORWARD
[12:01:04.100] dpid=00-00-00-00-00-02 port=1 | HTTP  | 10.0.0.1 -> 10.0.0.3 | FORWARD
[12:01:04.910] dpid=00-00-00-00-00-03 port=2 | UDP   | 10.0.0.2 -> 10.0.0.4 | FORWARD
```

| Field | Meaning |
|-------|---------|
| `dpid` | Which switch handled the packet |
| `port` | Which port it arrived on |
| `ICMP / TCP / UDP / HTTP / ARP` | Detected protocol |
| `FORWARD` | Sent to a known port (MAC learned) |
| `FLOOD` | Sent to all ports (MAC unknown — first packet) |

### CSV Log
```bash
tail -20 ~/pox/packet_log.csv        # last 20 entries
grep "HTTP" ~/pox/packet_log.csv     # filter by protocol
grep "FLOOD" ~/pox/packet_log.csv    # see all floods
python3 analyze_log.py --file ~/pox/packet_log.csv
```

---

## Inspect Flow Tables

```
mininet> sh ovs-ofctl dump-flows s1
mininet> sh ovs-ofctl dump-flows s2
mininet> sh ovs-ofctl dump-flows s3
mininet> net       # topology connections
mininet> dump      # all node details
```

---

## Cleanup

```bash
mininet> exit
sudo mn -c          # clean OVS state
# Ctrl+C in Terminal 1 to stop POX
```

---

## References

1. [Mininet](http://mininet.org) — network emulator
2. [POX Controller](https://github.com/noxrepo/pox) — SDN framework
3. [OpenFlow 1.0 Spec](https://opennetworking.org/wp-content/uploads/2013/04/openflow-spec-v1.0.0.pdf)
4. [Open vSwitch](https://www.openvswitch.org)
5. PES University — Computer Networks UE24CS252B course materials

---

<div align="center">

```
built with POX · OpenFlow · Mininet · Python
PES University — UE24CS252B — Computer Networks
```

</div>
