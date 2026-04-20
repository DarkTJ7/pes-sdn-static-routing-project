# SDN Mininet Based Simulation Project Report

**Project Title:** Static Routing using SDN Controller  
**Student Name:** Tarun Jaganathan  
**SRN:** PES1UG24AM304

## Objective

The objective of this project is to implement static routing in an SDN environment using Mininet and a Ryu OpenFlow controller. The controller installs explicit forwarding rules so that packets between selected hosts follow a predefined route.

## Problem Understanding

Traditional routing relies on distributed control inside routers. In SDN, the controller can centrally program forwarding behavior. This project demonstrates how OpenFlow rules can be used to enforce a fixed path even when an alternate path exists in the topology.

## Topology Design

The network uses four OpenFlow switches and four hosts in a diamond topology. Host `h1` communicates with host `h4` through the path `s1 -> s2 -> s4`. Switch `s3` provides an alternate physical path but is not selected by the controller for the static route.

## Controller Logic

The controller performs the following tasks:

- installs a table-miss rule on every switch
- sends ARP traffic to the controller for visibility and controlled flooding
- installs static IPv4 route rules for the configured host pair
- listens for `packet_in` events
- reinstalls the same static route if the route rules are deleted

## Match-Action Rules

The main static forwarding entries match:

- `in_port`
- `eth_type = IPv4`
- `ipv4_src`
- `ipv4_dst`

The corresponding actions:

- set destination MAC address
- output to the correct port for the chosen route

## Validation

The intended validation steps are:

- `ping` from `h1` to `h4`
- reverse `ping` from `h4` to `h1`
- `iperf` throughput measurement between `h1` and `h4`
- `ovs-ofctl dump-flows` on switches `s1`, `s2`, and `s4`

Expected observation:

- connectivity succeeds between `h1` and `h4`
- forwarding entries appear only on the selected path
- the alternate path through `s3` remains unused for the static route

## Regression Testing

Regression validation is done by removing controller-installed route rules and sending traffic again. The controller receives `packet_in`, reinstalls the same route, and the resulting flow tables should remain identical to the baseline route selection.

## Performance Observation

The project supports the following observations:

- latency from `ping`
- throughput from `iperf`
- flow table contents from `ovs-ofctl dump-flows`
- controller logs showing switch interaction and route installation

## Conclusion

This project shows that an SDN controller can enforce deterministic routing behavior through explicit flow installation. It also demonstrates that the same path can be restored after a rule reinstall, which satisfies the static routing regression requirement.
