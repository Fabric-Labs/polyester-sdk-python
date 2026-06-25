#!/usr/bin/env bash
# Offline realtime unit tests + live Centrifugo heartbeat check (network required).
set -euo pipefail
cd "$(dirname "$0")/.."

# shellcheck disable=SC1091
source "$(dirname "$0")/lib.sh"
resolve_pytest

if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

echo "==> realtime unit tests (${PYTEST[*]})"
"${PYTEST[@]}" tests/unit/test_realtime_client.py -q

echo "==> live Centrifugo heartbeat (public trades, ~35s)"
"${PYTEST[@]}" tests/integration/test_realtime.py::test_public_trades_subscription_survives_centrifugo_ping -v

echo "Realtime smoke passed."
