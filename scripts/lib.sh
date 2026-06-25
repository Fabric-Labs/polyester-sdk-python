#!/usr/bin/env bash
# Shared helpers for SDK test scripts.
resolve_pytest() {
  if [[ -n "${VIRTUAL_ENV:-}" && -x "${VIRTUAL_ENV}/bin/python" ]]; then
    PYTEST=("${VIRTUAL_ENV}/bin/python" -m pytest)
  elif [[ -x .venv/bin/python ]]; then
    PYTEST=(.venv/bin/python -m pytest)
  else
    PYTEST=(python3 -m pytest)
  fi
}
