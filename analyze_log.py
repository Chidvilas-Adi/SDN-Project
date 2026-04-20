"""
analyze_log.py — Packet Log Analyser
Course  : COMPUTER NETWORKS — UE24CS252B

Reads packet_log.csv produced by packet_logger.py and prints:
    - Protocol distribution
    - Top source/destination IPs
    - Per-switch packet counts
    - Timeline summary (packets per second)
    - Dropped packet report

Run:
    python3 analyze_log.py
    python3 analyze_log.py --file my_custom_log.csv
"""

import csv
import sys
import argparse
from collections import defaultdict, Counter


def load_log(path):
    rows = []
    try:
        with open(path, newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                rows.append(row)
    except FileNotFoundError:
        print(f"[ERROR] Log file not found: {path}")
        sys.exit(1)
    return rows


def bar(value, total, width=30):
    filled = int(width * value / total) if total else 0
    return "[" + "#" * filled + "." * (width - filled) + f"] {value:>5}"


def analyze(rows):
    total = len(rows)
    if total == 0:
        print("Log file is empty — run some traffic first.")
        return

    print(f"\n{'='*58}")
    print(f"  PACKET LOG ANALYSIS  ({total} packets total)")
    print(f"{'='*58}")

    # --- Protocol distribution ---
    proto_count = Counter(r["protocol"] for r in rows)
    print("\n Protocol Distribution:")
    for proto, count in proto_count.most_common():
        print(f"   {proto:<8} {bar(count, total)}  ({count/total*100:.1f}%)")

    # --- Action breakdown ---
    action_count = Counter(r["action"] for r in rows)
    print("\n Action Breakdown:")
    for action, count in action_count.most_common():
        print(f"   {action:<10} {bar(count, total)}  ({count/total*100:.1f}%)")

    # --- Top source IPs ---
    src_count = Counter(r["ip_src"] for r in rows if r["ip_src"] != "—")
    print("\n Top Source IPs (top 5):")
    for ip, count in src_count.most_common(5):
        print(f"   {ip:<18} {count:>5} packets")

    # --- Top destination IPs ---
    dst_count = Counter(r["ip_dst"] for r in rows if r["ip_dst"] != "—")
    print("\n Top Destination IPs (top 5):")
    for ip, count in dst_count.most_common(5):
        print(f"   {ip:<18} {count:>5} packets")

    # --- Top destination ports ---
    dport_count = Counter(r["dst_port"] for r in rows
                          if r["dst_port"] not in ("—", "0", ""))
    if dport_count:
        print("\n Top Destination Ports (top 5):")
        for port, count in dport_count.most_common(5):
            svc = {
                "80": "HTTP", "443": "HTTPS", "22": "SSH",
                "53": "DNS",  "3306": "MySQL", "8080": "HTTP-alt"
            }.get(port, "")
            print(f"   port {port:<8} {svc:<8} {count:>5} packets")

    # --- Per-switch breakdown ---
    dpid_count = Counter(r["switch_dpid"] for r in rows)
    print("\n Per-Switch Packet Count:")
    for dpid, count in sorted(dpid_count.items()):
        print(f"   dpid={dpid}   {count:>5} packets")

    # --- Byte total ---
    try:
        total_bytes = sum(int(r["pkt_size"]) for r in rows
                         if r["pkt_size"].isdigit())
        print(f"\n Total bytes captured : {total_bytes:,} B  "
              f"({total_bytes/1024:.1f} KB)")
    except Exception:
        pass

    # --- Dropped packets ---
    dropped = [r for r in rows if r["action"] == "DROP"]
    print(f"\n Dropped packets      : {len(dropped)} ({len(dropped)/total*100:.1f}%)")
    if dropped:
        print("   Sample drops (last 5):")
        for r in dropped[-5:]:
            print(f"   {r['timestamp']}  {r['protocol']:<5} "
                  f"{r['ip_src']} → {r['ip_dst']}")

    print(f"\n{'='*58}\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Analyse packet_log.csv")
    parser.add_argument("--file", default="packet_log.csv",
                        help="Path to the CSV log file")
    args = parser.parse_args()
    rows = load_log(args.file)
    analyze(rows)
