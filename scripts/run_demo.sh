#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ARTIFACT_DIR="$ROOT_DIR/artifacts/demo_run"
CONTROLLER_LOG="$ARTIFACT_DIR/controller.log"

mkdir -p "$ARTIFACT_DIR"

cleanup() {
  if [[ -n "${CTRL_PID:-}" ]]; then
    kill "$CTRL_PID" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT

sudo mn -c >/dev/null 2>&1 || true

cd "$ROOT_DIR"
ryu-manager src/static_routing_controller.py >"$CONTROLLER_LOG" 2>&1 &
CTRL_PID=$!

sleep 4
sudo python3 src/static_routing_topology.py --test --output-dir "$ARTIFACT_DIR"

echo "Artifacts saved in $ARTIFACT_DIR"
