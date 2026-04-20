# Static Routing Using SDN Controller

**Student Name:** Tarun Jaganathan  
**SRN:** PES1UG24AM304

This project demonstrates static routing in Software Defined Networking (SDN) using a Ryu controller and a custom Mininet topology. The controller installs explicit OpenFlow 1.3 flow rules to force traffic over a predefined path instead of relying on learning-switch behavior.

## Problem Statement

Implement static routing paths using controller-installed flow rules.

Project goals:

- define routing paths explicitly
- install flow rules manually from the controller
- validate packet delivery with `ping` and `iperf`
- document routing behavior
- perform regression testing to confirm the path remains unchanged after rule reinstall

## Topology

The project uses a diamond topology with one source host, one destination host, and an alternate unused path.

```text
h1 --- s1 --- s2 --- s4 --- h4
         \\           /
          \\- s3 ----/
```

Topology diagram: [docs/topology.svg](docs/topology.svg)

Primary static route:

- `h1 -> s1 -> s2 -> s4 -> h4`
- reverse traffic uses `h4 -> s4 -> s2 -> s1 -> h1`

Alternate path available but intentionally unused:

- `s1 -> s3 -> s4`

## Repository Structure

- `src/static_routing_controller.py`: Ryu controller that installs route flows and handles `packet_in`
- `src/static_routing_topology.py`: Mininet topology and automated validation runner
- `scripts/run_demo.sh`: end-to-end demo runner
- `scripts/regression_test.sh`: clears route rules and verifies reinstall preserves the same path
- `docs/report.md`: project write-up
- `docs/proof/`: screenshot placeholders and capture guidance

## Requirements

Recommended execution environment:

- Ubuntu 20.04 or 22.04
- Python 3.8+
- Mininet
- Open vSwitch
- Ryu
- `iperf`

Install Python dependency:

```bash
pip3 install -r requirements.txt
```

## How To Run

Start the controller in one terminal:

```bash
ryu-manager src/static_routing_controller.py
```

Start the Mininet topology in another terminal:

```bash
sudo python3 src/static_routing_topology.py
```

Or run the automated demo wrapper:

```bash
chmod +x scripts/run_demo.sh scripts/regression_test.sh
./scripts/run_demo.sh
```

## Validation Steps

Inside the Mininet CLI, verify:

```bash
h1 ping -c 4 h4
h4 ping -c 4 h1
iperf h1 h4
sh ovs-ofctl -O OpenFlow13 dump-flows s1
sh ovs-ofctl -O OpenFlow13 dump-flows s2
sh ovs-ofctl -O OpenFlow13 dump-flows s4
```

Expected behavior:

- `h1` reaches `h4` successfully
- traffic follows `s1 -> s2 -> s4`
- `s3` does not receive static forwarding rules for the selected route
- reinstalling rules preserves the same route

Run the regression test:

```bash
./scripts/regression_test.sh
```

This script:

1. starts the controller
2. launches Mininet in automated mode
3. captures baseline flow tables
4. deletes only controller-installed static route rules
5. triggers traffic to reinstall the rules through `packet_in`
6. verifies the same switches and output ports are used again

## Routing Behavior Summary

- The controller keeps a fixed route database for known host pairs.
- On switch connection, it installs:
  - a table-miss rule to send unknown packets to the controller
  - an ARP rule to send ARP traffic to the controller
  - static IPv4 route rules for the configured path
- If static route rules are cleared, the next IPv4 packet triggers `packet_in`.
- The controller recognizes the flow and reinstalls the same route rules.

## Proof Of Execution

The PDF requires proof of execution such as flow-table screenshots and `ping` or `iperf` results. This repository includes:

- placeholder image slots in `docs/proof/`
- automated artifact capture into `artifacts/`
- a checklist for the screenshots required in the final submission

Open the proof guide here: [docs/proof/README.md](docs/proof/README.md)

Note:

This Mac workspace does not include Mininet/Open vSwitch/Ryu, so authentic runtime screenshots must be captured in a Linux environment where the project is executed.

## References

- Mininet documentation: [https://mininet.org/](https://mininet.org/)
- Ryu SDN framework: [https://ryu-sdn.org/](https://ryu-sdn.org/)
- OpenFlow Switch Specification 1.3.1: [https://opennetworking.org/sdn-resources/openflow-switch-specification/](https://opennetworking.org/sdn-resources/openflow-switch-specification/)
