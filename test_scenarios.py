"""
test_scenarios.py — Validation & Test Scenarios
Course  : COMPUTER NETWORKS — UE24CS252B
Project : SDN Mininet-based Simulation (Orange Problem)

Run INSIDE the Mininet CLI (after topology.py is running):
    mininet> py execfile('test_scenarios.py')

OR as a standalone script with the net object:
    sudo python3 test_scenarios.py

Scenarios:
    1. Normal vs Blocked  — ping between all host pairs, observe forwarding
    2. Throughput test    — iperf between h1→h3 (TCP) and h2→h4 (UDP)
    3. Flow table check   — dump flow entries on all switches
    4. Latency test       — ping with 10 packets to measure RTT
"""

import subprocess
import sys
import time


# ── Scenario helpers ────────────────────────────────────────────────────────

def separator(title):
    print("\n" + "="*60)
    print(f"  SCENARIO: {title}")
    print("="*60)


def run_cmd(net, host_name, cmd):
    """Run a command on a Mininet host and print output."""
    host = net.get(host_name)
    print(f"\n[{host_name}]$ {cmd}")
    result = host.cmd(cmd)
    print(result)
    return result


def dump_flows(net, switch_name):
    """Dump the OpenFlow flow table of a switch."""
    sw = net.get(switch_name)
    print(f"\n--- Flow table: {switch_name} ---")
    result = sw.cmd("ovs-ofctl -O OpenFlow13 dump-flows", sw.name)
    print(result)


# ── Scenario 1: Normal connectivity (ping all pairs) ────────────────────────

def scenario1_connectivity(net):
    separator("1 — Normal Connectivity (pingAll)")
    print("Testing full-mesh ping across h1, h2, h3, h4 ...")
    print("Expected: 0% packet loss\n")
    net.pingAll()


# ── Scenario 2: Selective ping + latency measurement ────────────────────────

def scenario2_latency(net):
    separator("2 — Latency Measurement (ping -c 10)")

    pairs = [("h1", "h2"), ("h1", "h3"), ("h2", "h4"), ("h3", "h4")]
    for src, dst in pairs:
        dst_host = net.get(dst)
        run_cmd(net, src, f"ping -c 10 {dst_host.IP()}")
        time.sleep(0.5)


# ── Scenario 3: Throughput test with iperf ──────────────────────────────────

def scenario3_throughput(net):
    separator("3 — Throughput (iperf h1→h3 TCP, h2→h4 UDP)")

    h1 = net.get("h1")
    h3 = net.get("h3")
    h2 = net.get("h2")
    h4 = net.get("h4")

    # TCP: h1 (client) → h3 (server)
    print("\n[iperf TCP] h3 starting server ...")
    h3.cmd("iperf -s &")
    time.sleep(1)
    print("[iperf TCP] h1 → h3 for 10 seconds ...")
    result = h1.cmd(f"iperf -c {h3.IP()} -t 10")
    print(result)
    h3.cmd("kill %iperf")

    # UDP: h2 (client) → h4 (server)
    print("\n[iperf UDP] h4 starting UDP server ...")
    h4.cmd("iperf -s -u &")
    time.sleep(1)
    print("[iperf UDP] h2 → h4 for 10 seconds ...")
    result = h2.cmd(f"iperf -c {h4.IP()} -u -b 5m -t 10")
    print(result)
    h4.cmd("kill %iperf")


# ── Scenario 4: Flow table inspection ────────────────────────────────────────

def scenario4_flow_tables(net):
    separator("4 — Flow Table Inspection")
    for sw_name in ["s1", "s2", "s3"]:
        dump_flows(net, sw_name)


# ── Scenario 5: HTTP simulation (wget between hosts) ─────────────────────────

def scenario5_http(net):
    separator("5 — HTTP Traffic (Python HTTP server h3 → h1 fetches)")

    h3 = net.get("h3")
    h1 = net.get("h1")

    # Start a simple HTTP server on h3
    print("[h3] Starting HTTP server on port 8080 ...")
    h3.cmd("python3 -m http.server 8080 &")
    time.sleep(1)

    print(f"[h1] Fetching from h3 ({h3.IP()}:8080) ...")
    result = h1.cmd(f"curl -s -o /dev/null -w '%{{http_code}} %{{time_total}}s' http://{h3.IP()}:8080/")
    print(f"[h1] HTTP response: {result}")

    h3.cmd("kill %python3")


# ── Main ─────────────────────────────────────────────────────────────────────

def run_all_scenarios(net):
    """Call this from within Mininet CLI or after net.start()."""
    scenario1_connectivity(net)
    scenario2_latency(net)
    scenario3_throughput(net)
    scenario4_flow_tables(net)
    scenario5_http(net)
    print("\n*** All scenarios complete. Check packet_log.csv for logs. ***\n")


if __name__ == "__main__":
    # For standalone use, import and start the topology
    from mininet.net import Mininet
    from mininet.node import RemoteController, OVSSwitch
    from mininet.link import TCLink
    from mininet.log import setLogLevel
    from topology import TreeTopo

    setLogLevel("warning")
    topo = TreeTopo()
    net = Mininet(topo=topo, switch=OVSSwitch,
                  controller=None, link=TCLink)
    net.addController("c0", controller=RemoteController,
                      ip="127.0.0.1", port=6633)
    net.start()
    run_all_scenarios(net)
    net.stop()
