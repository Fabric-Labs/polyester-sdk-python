#!/usr/bin/env bash
# Run unit tests, then optional live tiers based on env flags.
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

echo "==> unit (${PYTEST[*]})"
"${PYTEST[@]}" tests/unit -q

if [[ -z "${POLYESTER_API_KEY_ID:-}" || -z "${POLYESTER_API_PRIVATE_KEY:-}" ]]; then
  echo "Skipping live tests (set POLYESTER_API_KEY_ID and POLYESTER_API_PRIVATE_KEY in .env)"
  exit 0
fi

echo "==> integration (API-key read-only)"
"${PYTEST[@]}" tests/integration tests/e2e -m "integration and not mutation and not funded and not jwt_session and not realtime" -v

if [[ "${POLYESTER_TEST_REALTIME:-1}" =~ ^(1|true|yes)$ ]]; then
  echo "==> realtime (Centrifugo subscriptions, ~35s heartbeat)"
  "${PYTEST[@]}" tests/integration/test_realtime.py -m "integration and realtime" -v
fi

if [[ "${POLYESTER_TEST_MUTATION:-}" =~ ^(1|true|yes)$ ]]; then
  echo "==> mutation"
  "${PYTEST[@]}" tests/ -m mutation -v
fi

if [[ "${POLYESTER_TEST_FUNDED:-}" =~ ^(1|true|yes)$ ]]; then
  echo "==> funded"
  "${PYTEST[@]}" tests/e2e/funded tests/integration -m "(integration or funded) and not realtime" -v
fi

if [[ "${POLYESTER_TEST_TREASURY:-}" =~ ^(1|true|yes)$ ]]; then
  echo "==> treasury"
  "${PYTEST[@]}" tests/ -m treasury -v
fi
