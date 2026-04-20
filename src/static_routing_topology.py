#!/usr/bin/env python3

import argparse
import os
import subprocess
import time
from pathlib import Path

from mininet.cli import CLI
from mininet.link import TCLink
from mininet.log import setLogLevel
from mininet.net import Mininet
from mininet.node import OVSSwitch, RemoteController
from mininet.topo import Topo


class StaticRoutingTopo(Topo):
    def build(self):
        h1 = self.addHost("h1", ip="10.0.0.1/24", mac="00:00:00:00:00:01")
        h2 = self.addHost("h2", ip="10.0.0.2/24", mac="00:00:00:00:00:02")
        h3 = self.addHost("h3", ip="10.0.0.3/24", mac="00:00:00:00:00:03")
        h4 = self.addHost("h4", ip="10.0.0.4/24", mac="00:00:00:00:00:04")

        s1 = self.addSwitch("s1", protocols="OpenFlow13")
        s2 = self.addSwitch("s2", protocols="OpenFlow13")
        s3 = self.addSwitch("s3", protocols="OpenFlow13")
        s4 = self.addSwitch("s4", protocols="OpenFlow13")

        self.addLink(h1, s1, port2=1, cls=TCLink, bw=10, delay="5ms")
        self.addLink(h2, s2, port2=1, cls=TCLink, bw=10, delay="5ms")
        self.addLink(h3, s3, port2=1, cls=TCLink, bw=10, delay="5ms")
        self.addLink(h4, s4, port2=1, cls=TCLink, bw=10, delay="5ms")

        self.addLink(s1, s2, port1=2, port2=2, cls=TCLink, bw=20, delay="2ms")
        self.addLink(s1, s3, port1=3, port2=2, cls=TCLink, bw=20, delay="2ms")
        self.addLink(s2, s4, port1=3, port2=2, cls=TCLink, bw=20, delay="2ms")
        self.addLink(s3, s4, port1=3, port2=3, cls=TCLink, bw=20, delay="2ms")


def write_text(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(content)


def dump_flows(output_dir, switch_names):
    for switch in switch_names:
        result = subprocess.run(
            ["sudo", "ovs-ofctl", "-O", "OpenFlow13", "dump-flows", switch],
            check=False,
            capture_output=True,
            text=True,
        )
        write_text(os.path.join(output_dir, f"{switch}_flows.txt"), result.stdout + result.stderr)


def delete_static_route_flows(switch_names):
    for switch in switch_names:
        subprocess.run(
            [
                "sudo",
                "ovs-ofctl",
                "-O",
                "OpenFlow13",
                "--strict",
                "del-flows",
                switch,
                "cookie=0x1/-1,priority=100",
            ],
            check=False,
            capture_output=True,
            text=True,
        )


def normalize_route_flows(flow_file):
    normalized = []
    for line in Path(flow_file).read_text(encoding="utf-8").splitlines():
        if "cookie=0x1" not in line:
            continue
        _, remainder = line.split("priority=100", 1)
        normalized.append("priority=100" + remainder.strip())
    return sorted(normalized)


def run_automated_tests(net, output_dir):
    h1 = net.get("h1")
    h4 = net.get("h4")

    os.makedirs(output_dir, exist_ok=True)
    time.sleep(3)

    ping_forward = h1.cmd("ping -c 4 10.0.0.4")
    ping_reverse = h4.cmd("ping -c 4 10.0.0.1")
    iperf_result = net.iperf((h1, h4))

    write_text(os.path.join(output_dir, "ping_h1_to_h4.txt"), ping_forward)
    write_text(os.path.join(output_dir, "ping_h4_to_h1.txt"), ping_reverse)
    write_text(
        os.path.join(output_dir, "iperf_h1_h4.txt"),
        f"server_throughput={iperf_result[0]}\nclient_throughput={iperf_result[1]}\n",
    )

    dump_flows(output_dir, ["s1", "s2", "s3", "s4"])


def run_regression_tests(net, output_dir):
    baseline_dir = os.path.join(output_dir, "baseline")
    reinstall_dir = os.path.join(output_dir, "reinstall")
    os.makedirs(baseline_dir, exist_ok=True)
    os.makedirs(reinstall_dir, exist_ok=True)

    run_automated_tests(net, baseline_dir)
    delete_static_route_flows(["s1", "s2", "s3", "s4"])
    time.sleep(1)

    h1 = net.get("h1")
    h4 = net.get("h4")
    reinstall_ping_forward = h1.cmd("ping -c 4 10.0.0.4")
    reinstall_ping_reverse = h4.cmd("ping -c 4 10.0.0.1")
    write_text(os.path.join(reinstall_dir, "ping_h1_to_h4.txt"), reinstall_ping_forward)
    write_text(os.path.join(reinstall_dir, "ping_h4_to_h1.txt"), reinstall_ping_reverse)

    time.sleep(1)
    dump_flows(reinstall_dir, ["s1", "s2", "s3", "s4"])

    comparisons = []
    for switch in ["s1", "s2", "s4"]:
        baseline = normalize_route_flows(os.path.join(baseline_dir, f"{switch}_flows.txt"))
        reinstall = normalize_route_flows(os.path.join(reinstall_dir, f"{switch}_flows.txt"))
        comparisons.append((switch, baseline == reinstall, baseline, reinstall))

    passed = all(item[1] for item in comparisons)
    summary_lines = []
    for switch, is_same, baseline, reinstall in comparisons:
        summary_lines.append(f"{switch}: {'MATCH' if is_same else 'MISMATCH'}")
        summary_lines.append(f"baseline={baseline}")
        summary_lines.append(f"reinstall={reinstall}")
        summary_lines.append("")
    final_line = (
        "Regression test passed: static route path remained unchanged after rule reinstall."
        if passed
        else "Regression test failed: route entries changed after reinstall."
    )
    summary_lines.append(final_line)
    write_text(os.path.join(output_dir, "regression_summary.txt"), "\n".join(summary_lines))

    if not passed:
        raise SystemExit(1)


def build_network(controller_ip, controller_port):
    topo = StaticRoutingTopo()
    net = Mininet(
        topo=topo,
        controller=None,
        switch=OVSSwitch,
        autoSetMacs=False,
        autoStaticArp=False,
    )
    net.addController("c0", controller=RemoteController, ip=controller_ip, port=controller_port)
    net.start()
    return net


def main():
    parser = argparse.ArgumentParser(description="Static routing SDN topology")
    parser.add_argument("--controller-ip", default="127.0.0.1")
    parser.add_argument("--controller-port", type=int, default=6653)
    parser.add_argument("--test", action="store_true", help="run automated tests and exit")
    parser.add_argument("--regression", action="store_true", help="run regression validation and exit")
    parser.add_argument("--output-dir", default="artifacts/latest")
    args = parser.parse_args()

    net = build_network(args.controller_ip, args.controller_port)
    try:
        if args.regression:
            run_regression_tests(net, args.output_dir)
        elif args.test:
            run_automated_tests(net, args.output_dir)
        else:
            CLI(net)
    finally:
        net.stop()


if __name__ == "__main__":
    setLogLevel("info")
    main()
