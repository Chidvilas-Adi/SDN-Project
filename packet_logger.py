"""
packet_logger.py — SDN Packet Logger Controller
Course  : COMPUTER NETWORKS — UE24CS252B
Project : SDN Mininet-based Simulation (Orange Problem)
Author  : <Your Name> | <SRN>

Description:
    A Ryu OpenFlow 1.3 controller that:
      1. Handles packet_in events from every connected switch
      2. Learns MAC-to-port mappings (learning switch)
      3. Installs proactive flow rules after the first packet
      4. Logs every captured packet with full header details
      5. Maintains per-switch statistics (packet count, byte count, protocol breakdown)
      6. Writes a structured log file: packet_log.csv

Run:
    ryu-manager packet_logger.py --observe-links

Test topology (separate terminal):
    sudo mn --topo tree,depth=2,fanout=2 --controller remote,ip=127.0.0.1,port=6633 --switch ovsk,protocols=OpenFlow13
"""

from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER, set_ev_cls
from ryu.ofproto import ofproto_v1_3
from ryu.lib.packet import packet, ethernet, ipv4, ipv6, arp, tcp, udp, icmp
from ryu.lib.packet import ether_types

import datetime
import csv
import os
import logging

LOG_FILE = "packet_log.csv"
LOG_FIELDS = ["timestamp", "switch_dpid", "in_port", "eth_src", "eth_dst",
              "eth_type", "protocol", "ip_src", "ip_dst", "src_port",
              "dst_port", "pkt_size", "action"]


class PacketLogger(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(PacketLogger, self).__init__(*args, **kwargs)

        # mac_to_port[dpid][mac] = port_number
        self.mac_to_port = {}

        # stats[dpid] = { 'total': int, 'tcp': int, 'udp': int, 'icmp': int,
        #                  'arp': int, 'http': int, 'other': int, 'bytes': int }
        self.stats = {}

        # Setup console logger
        logging.basicConfig(level=logging.INFO,
                            format="%(asctime)s [%(levelname)s] %(message)s",
                            datefmt="%H:%M:%S")
        self.logger = logging.getLogger("PacketLogger")

        # Initialise CSV log file
        self._init_csv()
        self.logger.info("=== Packet Logger Controller Started ===")
        self.logger.info("CSV log: %s", os.path.abspath(LOG_FILE))

    # ------------------------------------------------------------------
    # Helper: CSV
    # ------------------------------------------------------------------
    def _init_csv(self):
        with open(LOG_FILE, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=LOG_FIELDS)
            writer.writeheader()

    def _write_csv(self, row):
        with open(LOG_FILE, "a", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=LOG_FIELDS)
            writer.writerow(row)

    # ------------------------------------------------------------------
    # Helper: stats
    # ------------------------------------------------------------------
    def _ensure_stats(self, dpid):
        if dpid not in self.stats:
            self.stats[dpid] = dict(total=0, tcp=0, udp=0, icmp=0,
                                    arp=0, http=0, other=0, bytes=0)

    def _print_stats(self):
        print("\n" + "="*58)
        print(f"{'SWITCH':<12} {'TOTAL':>7} {'TCP':>6} {'UDP':>6} "
              f"{'ICMP':>6} {'ARP':>6} {'HTTP':>6} {'BYTES':>10}")
        print("-"*58)
        for dpid, s in self.stats.items():
            print(f"{dpid:<12} {s['total']:>7} {s['tcp']:>6} {s['udp']:>6} "
                  f"{s['icmp']:>6} {s['arp']:>6} {s['http']:>6} {s['bytes']:>10}")
        print("="*58 + "\n")

    # ------------------------------------------------------------------
    # OpenFlow helpers
    # ------------------------------------------------------------------
    def _add_flow(self, datapath, priority, match, actions,
                  idle_timeout=30, hard_timeout=0):
        """Install a flow rule on the given switch."""
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS, actions)]
        mod = parser.OFPFlowMod(
            datapath=datapath,
            priority=priority,
            match=match,
            instructions=inst,
            idle_timeout=idle_timeout,
            hard_timeout=hard_timeout
        )
        datapath.send_msg(mod)

    def _send_packet_out(self, datapath, buffer_id, in_port, actions, data=None):
        """Forward the buffered or raw packet."""
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        out = parser.OFPPacketOut(
            datapath=datapath,
            buffer_id=buffer_id,
            in_port=in_port,
            actions=actions,
            data=data
        )
        datapath.send_msg(out)

    # ------------------------------------------------------------------
    # Event: Switch connected — install table-miss entry
    # ------------------------------------------------------------------
    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        datapath = ev.msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        dpid = datapath.id

        self._ensure_stats(dpid)
        self.mac_to_port.setdefault(dpid, {})

        # Table-miss: send every unmatched packet to the controller
        match = parser.OFPMatch()
        actions = [parser.OFPActionOutput(ofproto.OFPP_CONTROLLER,
                                          ofproto.OFPCML_NO_BUFFER)]
        self._add_flow(datapath, priority=0, match=match, actions=actions)

        self.logger.info("[switch] Connected — dpid=%016x", dpid)

    # ------------------------------------------------------------------
    # Event: Packet-in — log, learn, forward
    # ------------------------------------------------------------------
    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def packet_in_handler(self, ev):
        msg = ev.msg
        datapath = msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        dpid = datapath.id
        in_port = msg.match["in_port"]

        self._ensure_stats(dpid)

        # Parse the packet
        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocols(ethernet.ethernet)[0]

        # Ignore LLDP (link-layer discovery)
        if eth.ethertype == ether_types.ETH_TYPE_LLDP:
            return

        # --- Layer 2 learning ---
        dst_mac = eth.dst
        src_mac = eth.src
        self.mac_to_port[dpid][src_mac] = in_port

        out_port = (self.mac_to_port[dpid].get(dst_mac)
                    if dst_mac in self.mac_to_port[dpid]
                    else ofproto.OFPP_FLOOD)

        actions = [parser.OFPActionOutput(out_port)]

        # Install a flow rule if we know the destination (avoid flooding next time)
        if out_port != ofproto.OFPP_FLOOD:
            match = parser.OFPMatch(in_port=in_port, eth_dst=dst_mac,
                                    eth_src=src_mac)
            if msg.buffer_id != ofproto.OFP_NO_BUFFER:
                self._add_flow(datapath, priority=1, match=match,
                               actions=actions, idle_timeout=30)
                # Packet is already buffered; no need to send data
                self._send_packet_out(datapath, msg.buffer_id,
                                      in_port, actions)
            else:
                self._add_flow(datapath, priority=1, match=match,
                               actions=actions, idle_timeout=30)
                self._send_packet_out(datapath, ofproto.OFP_NO_BUFFER,
                                      in_port, actions, msg.data)
        else:
            # Flood: packet not yet in MAC table
            if msg.buffer_id != ofproto.OFP_NO_BUFFER:
                self._send_packet_out(datapath, msg.buffer_id,
                                      in_port, actions)
            else:
                self._send_packet_out(datapath, ofproto.OFP_NO_BUFFER,
                                      in_port, actions, msg.data)

        # --- Parse upper layers for logging ---
        proto_name = "OTHER"
        ip_src = ip_dst = src_port = dst_port = "—"
        action_str = "FLOOD" if out_port == ofproto.OFPP_FLOOD else "FORWARD"
        eth_type_str = hex(eth.ethertype)
        pkt_size = len(msg.data)

        ip_pkt = pkt.get_protocol(ipv4.ipv4)
        arp_pkt = pkt.get_protocol(arp.arp)
        ip6_pkt = pkt.get_protocol(ipv6.ipv6)

        if arp_pkt:
            proto_name = "ARP"
            ip_src = arp_pkt.src_ip
            ip_dst = arp_pkt.dst_ip
            self.stats[dpid]["arp"] += 1

        elif ip_pkt:
            ip_src = ip_pkt.src
            ip_dst = ip_pkt.dst

            tcp_pkt = pkt.get_protocol(tcp.tcp)
            udp_pkt = pkt.get_protocol(udp.udp)
            icmp_pkt = pkt.get_protocol(icmp.icmp)

            if tcp_pkt:
                src_port = tcp_pkt.src_port
                dst_port = tcp_pkt.dst_port
                proto_name = "HTTP" if dst_port in (80, 8080, 8000) else "TCP"
                self.stats[dpid]["tcp"] += 1
                if proto_name == "HTTP":
                    self.stats[dpid]["http"] += 1
            elif udp_pkt:
                src_port = udp_pkt.src_port
                dst_port = udp_pkt.dst_port
                proto_name = "UDP"
                self.stats[dpid]["udp"] += 1
            elif icmp_pkt:
                proto_name = "ICMP"
                self.stats[dpid]["icmp"] += 1
            else:
                self.stats[dpid]["other"] += 1

        elif ip6_pkt:
            proto_name = "IPv6"
            ip_src = ip6_pkt.src
            ip_dst = ip6_pkt.dst
            self.stats[dpid]["other"] += 1
        else:
            self.stats[dpid]["other"] += 1

        # Update totals
        self.stats[dpid]["total"] += 1
        self.stats[dpid]["bytes"] += pkt_size

        # Console log
        ts = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
        self.logger.info(
            "[%s] dpid=%016x port=%s | %-5s | %s → %s | sport=%s dport=%s | %dB | %s",
            ts, dpid, in_port, proto_name, ip_src, ip_dst,
            src_port, dst_port, pkt_size, action_str
        )

        # Print stats every 20 packets
        if self.stats[dpid]["total"] % 20 == 0:
            self._print_stats()

        # CSV log
        self._write_csv({
            "timestamp": ts,
            "switch_dpid": format(dpid, "016x"),
            "in_port": in_port,
            "eth_src": src_mac,
            "eth_dst": dst_mac,
            "eth_type": eth_type_str,
            "protocol": proto_name,
            "ip_src": ip_src,
            "ip_dst": ip_dst,
            "src_port": src_port,
            "dst_port": dst_port,
            "pkt_size": pkt_size,
            "action": action_str,
        })
