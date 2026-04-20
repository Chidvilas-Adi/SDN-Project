"""
topology.py — Custom Mininet Tree Topology
Course  : COMPUTER NETWORKS — UE24CS252B
Project : SDN Mininet-based Simulation (Orange Problem)

Topology (tree, depth=2, fanout=2):

              [ c0  controller ]
                     |
                  [ s1 ]
                /        \
           [ s2 ]        [ s3 ]
           /    \         /    \
         h1     h2      h3     h4

IP Addresses:
    h1 = 10.0.0.1   h2 = 10.0.0.2
    h3 = 10.0.0.3   h4 = 10.0.0.4

Run:
    sudo python3 topology.py
"""

from mininet.net import Mininet
from mininet.node import RemoteController, OVSSwitch
from mininet.topo import Topo
from mininet.log import setLogLevel, info
from mininet.cli import CLI
from mininet.link import TCLink


class TreeTopo(Topo):
    """Tree topology: 1 root switch, 2 access switches, 4 hosts."""

    def build(self):
        # Root switch
        s1 = self.addSwitch("s1", protocols="OpenFlow13")

        # Access switches
        s2 = self.addSwitch("s2", protocols="OpenFlow13")
        s3 = self.addSwitch("s3", protocols="OpenFlow13")

        # Links: root → access (100 Mbps, 2 ms delay)
        self.addLink(s1, s2, bw=100, delay="2ms", loss=0)
        self.addLink(s1, s3, bw=100, delay="2ms", loss=0)

        # Hosts under s2
        h1 = self.addHost("h1", ip="10.0.0.1/24", mac="00:00:00:00:00:01")
        h2 = self.addHost("h2", ip="10.0.0.2/24", mac="00:00:00:00:00:02")
        self.addLink(h1, s2, bw=10, delay="1ms")
        self.addLink(h2, s2, bw=10, delay="1ms")

        # Hosts under s3
        h3 = self.addHost("h3", ip="10.0.0.3/24", mac="00:00:00:00:00:03")
        h4 = self.addHost("h4", ip="10.0.0.4/24", mac="00:00:00:00:00:04")
        self.addLink(h3, s3, bw=10, delay="1ms")
        self.addLink(h4, s3, bw=10, delay="1ms")


def run():
    setLogLevel("info")
    topo = TreeTopo()

    net = Mininet(
        topo=topo,
        switch=OVSSwitch,
        controller=None,   # Remote controller (Ryu)
        link=TCLink,
        autoSetMacs=False,
        autoStaticArp=False,
    )

    # Connect to the Ryu controller running on localhost:6633
    c0 = net.addController(
        "c0",
        controller=RemoteController,
        ip="127.0.0.1",
        port=6633,
    )

    net.start()

    info("\n*** Network started\n")
    info("*** Switches: s1, s2, s3\n")
    info("*** Hosts: h1(10.0.0.1) h2(10.0.0.2) h3(10.0.0.3) h4(10.0.0.4)\n")
    info("*** Controller: c0 at 127.0.0.1:6633\n")
    info("\n*** Running connectivity test...\n")
    net.pingAll()

    info("\n*** Opening Mininet CLI (type 'exit' to quit)\n")
    CLI(net)

    net.stop()


if __name__ == "__main__":
    run()
