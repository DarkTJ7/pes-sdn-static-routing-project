# Proof Capture Guide

The assignment asks for proof of execution in the GitHub repository. Add the following screenshots after running the project in a Linux environment with Mininet and Ryu installed.

## Required Screenshots

1. `01-controller-log.png`
   - show switch connection logs and static route installation messages
2. `02-s1-flow-table.png`
   - show `ovs-ofctl -O OpenFlow13 dump-flows s1`
3. `03-s2-flow-table.png`
   - show `ovs-ofctl -O OpenFlow13 dump-flows s2`
4. `04-s4-flow-table.png`
   - show `ovs-ofctl -O OpenFlow13 dump-flows s4`
5. `05-ping-result.png`
   - show successful `h1 ping -c 4 h4`
6. `06-iperf-result.png`
   - show throughput between `h1` and `h4`
7. `07-regression-result.png`
   - show that the same path is preserved after route rule reinstall

## Quick Capture Workflow

Run:

```bash
./scripts/run_demo.sh
./scripts/regression_test.sh
```

Useful commands for screenshots:

```bash
cat artifacts/demo_run/controller.log
cat artifacts/demo_run/s1_flows.txt
cat artifacts/demo_run/s2_flows.txt
cat artifacts/demo_run/s4_flows.txt
cat artifacts/demo_run/ping_h1_to_h4.txt
cat artifacts/demo_run/iperf_h1_h4.txt
```

## Placeholder Images

The files below are placeholders so the repository already includes the proof section structure:

- `flow-table-placeholder.svg`
- `ping-iperf-placeholder.svg`
- `regression-placeholder.svg`

Replace them with real screenshots before final submission.
