"""
packet_logger.py — SDN Packet Logger (POX Controller Component)
Course  : COMPUTER NETWORKS — UE24CS252B
Project : SDN Mininet-based Simulation (Orange Problem)

Place this file in:  ~/pox/ext/packet_logger.py

Run:
    cd ~/pox
    python3 pox.py log.level --DEBUG packet_logger

Test topology (separate terminal):
    sudo mn --topo tree,depth=2,fanout=2 \
            --controller remote,ip=127.0.0.1,port=6633 \
            --switch ovsk,protocols=OpenFlow10
"""

from pox.core import core
import pox.openflow.libopenflow_01 as of
from pox.lib.packet import ethernet, ipv4, arp, tcp, udp, icmp
from pox.lib.util import dpid_to_str
from pox.lib.addresses import EthAddr

import datetime
import csv
import os

log = core.getLogger()

LOG_FILE = "packet_log.csv"
LOG_FIELDS = ["timestamp", "switch_dpid", "in_port", "eth_src", "eth_dst",
              "eth_type", "protocol", "ip_src", "ip_dst",
              "src_port", "dst_port", "pkt_size", "action"]


class PacketLogger(object):
    """
    Per-switch packet logger handler.
    Instantiated once per switch connection.
    """

    def __init__(self, connection):
        self.connection = connection
        self.dpid = dpid_to_str(connection.dpid)
        self.mac_to_port = {}

        # Listen to this switch's events
        connection.addListeners(self)
        log.info("[switch] Connected: dpid=%s", self.dpid)

        # Install table-miss rule: send all unmatched packets to controller
        msg = of.ofp_flow_mod()
        msg.priority = 0
        msg.actions.append(of.ofp_action_output(port=of.OFPP_CONTROLLER))
        connection.send(msg)

    # ------------------------------------------------------------------
    # packet_in handler
    # ------------------------------------------------------------------
    def _handle_PacketIn(self, event):
        pkt      = event.parsed          # parsed packet
        in_port  = event.port
        dpid     = dpid_to_str(event.connection.dpid)

        if not pkt.parsed:
            log.warning("Incomplete packet, ignoring")
            return

        # --- Layer 2 learning ---
        self.mac_to_port[pkt.src] = in_port

        if pkt.dst in self.mac_to_port:
            out_port = self.mac_to_port[pkt.dst]
            action_str = "FORWARD"
        else:
            out_port = of.OFPP_FLOOD
            action_str = "FLOOD"

        # --- Install flow rule if destination is known ---
        if out_port != of.OFPP_FLOOD:
            msg = of.ofp_flow_mod()
            msg.match = of.ofp_match.from_packet(pkt, in_port)
            msg.priority = 1
            msg.idle_timeout = 30
            msg.hard_timeout = 0
            msg.actions.append(of.ofp_action_output(port=out_port))
            msg.data = event.ofp          # include buffered packet
            event.connection.send(msg)
        else:
            # Just flood this packet
            msg = of.ofp_packet_out()
            msg.data = event.ofp
            msg.actions.append(of.ofp_action_output(port=of.OFPP_FLOOD))
            event.connection.send(msg)

        # --- Parse upper layers for logging ---
        proto_name = "OTHER"
        ip_src = ip_dst = src_port = dst_port = "-"
        eth_type = hex(pkt.type)
        pkt_size = len(event.data)

        ip_pkt  = pkt.find("ipv4")
        arp_pkt = pkt.find("arp")

        if arp_pkt:
            proto_name = "ARP"
            ip_src = str(arp_pkt.protosrc)
            ip_dst = str(arp_pkt.protodst)

        elif ip_pkt:
            ip_src = str(ip_pkt.srcip)
            ip_dst = str(ip_pkt.dstip)

            tcp_pkt  = pkt.find("tcp")
            udp_pkt  = pkt.find("udp")
            icmp_pkt = pkt.find("icmp")

            if tcp_pkt:
                src_port = tcp_pkt.srcport
                dst_port = tcp_pkt.dstport
                proto_name = "HTTP" if dst_port in (80, 8080, 8000) else "TCP"
            elif udp_pkt:
                src_port = udp_pkt.srcport
                dst_port = udp_pkt.dstport
                proto_name = "UDP"
            elif icmp_pkt:
                proto_name = "ICMP"
            else:
                proto_name = "IP"

        # --- Console log ---
        ts = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
        log.info("[%s] dpid=%s port=%s | %-5s | %s -> %s | %s",
                 ts, dpid, in_port, proto_name, ip_src, ip_dst, action_str)

        # --- CSV log ---
        _write_csv({
            "timestamp":   ts,
            "switch_dpid": dpid,
            "in_port":     in_port,
            "eth_src":     str(pkt.src),
            "eth_dst":     str(pkt.dst),
            "eth_type":    eth_type,
            "protocol":    proto_name,
            "ip_src":      ip_src,
            "ip_dst":      ip_dst,
            "src_port":    src_port,
            "dst_port":    dst_port,
            "pkt_size":    pkt_size,
            "action":      action_str,
        })

        # Update global stats
        _update_stats(dpid, proto_name, action_str, pkt_size)


# ------------------------------------------------------------------
# Controller-level: listen for new switch connections
# ------------------------------------------------------------------
class PacketLoggerController(object):

    def __init__(self):
        core.openflow.addListeners(self)
        log.info("=== POX Packet Logger Controller Started ===")
        log.info("CSV log: %s", os.path.abspath(LOG_FILE))
        _init_csv()

    def _handle_ConnectionUp(self, event):
        PacketLogger(event.connection)


# ------------------------------------------------------------------
# Global stats
# ------------------------------------------------------------------
_stats = {}

def _update_stats(dpid, proto, action, size):
    if dpid not in _stats:
        _stats[dpid] = dict(total=0, tcp=0, udp=0, icmp=0,
                            arp=0, http=0, other=0, bytes=0, drop=0)
    s = _stats[dpid]
    s["total"] += 1
    s["bytes"] += size
    if proto == "TCP":   s["tcp"]  += 1
    elif proto == "UDP": s["udp"]  += 1
    elif proto == "ICMP":s["icmp"] += 1
    elif proto == "ARP": s["arp"]  += 1
    elif proto == "HTTP":s["http"] += 1
    else:                s["other"]+= 1
    if action == "DROP": s["drop"] += 1

    if s["total"] % 20 == 0:
        _print_stats()

def _print_stats():
    print("\n" + "="*60)
    print(f"{'DPID':<20} {'TOTAL':>6} {'TCP':>5} {'UDP':>5} "
          f"{'ICMP':>5} {'ARP':>5} {'BYTES':>9}")
    print("-"*60)
    for dpid, s in _stats.items():
        print(f"{dpid:<20} {s['total']:>6} {s['tcp']:>5} {s['udp']:>5} "
              f"{s['icmp']:>5} {s['arp']:>5} {s['bytes']:>9}")
    print("="*60 + "\n")


# ------------------------------------------------------------------
# CSV helpers
# ------------------------------------------------------------------
def _init_csv():
    with open(LOG_FILE, "w", newline="") as f:
        csv.DictWriter(f, fieldnames=LOG_FIELDS).writeheader()

def _write_csv(row):
    with open(LOG_FILE, "a", newline="") as f:
        csv.DictWriter(f, fieldnames=LOG_FIELDS).writerow(row)


# ------------------------------------------------------------------
# POX entry point
# ------------------------------------------------------------------
def launch():
    core.registerNew(PacketLoggerController)
