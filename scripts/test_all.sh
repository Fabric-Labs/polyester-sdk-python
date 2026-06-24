#!/usr/bin/env bash
# Run unit tests, then optional live tiers based on env flags.
set -euo pipefail
cd "$(dirname "$0")/.."

if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

echo "==> unit"
pytest tests/unit -q

if [[ -z "${POLYESTER_API_KEY_ID:-}" || -z "${POLYESTER_API_PRIVATE_KEY:-}" ]]; then
  echo "Skipping live tests (set POLYESTER_API_KEY_ID and POLYESTER_API_PRIVATE_KEY in .env)"
  exit 0
fi

echo "==> integration (API-key read-only)"
pytest tests/integration tests/e2e -m "integration and not mutation and not funded and not jwt_session" -v

if [[ "${POLYESTER_TEST_MUTATION:-}" =~ ^(1|true|yes)$ ]]; then
  echo "==> mutation"
  pytest tests/ -m mutation -v
fi

if [[ "${POLYESTER_TEST_FUNDED:-}" =~ ^(1|true|yes)$ ]]; then
  echo "==> funded"
  pytest tests/e2e/funded tests/integration -m "integration or funded" -v
fi

if [[ "${POLYESTER_TEST_TREASURY:-}" =~ ^(1|true|yes)$ ]]; then
  echo "==> treasury"
  pytest tests/ -m treasury -v
fi
