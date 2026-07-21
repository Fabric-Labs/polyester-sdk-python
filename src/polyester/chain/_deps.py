"""Lazy optional dependency gate for the chain extra."""

from __future__ import annotations


def require_eth_abi():
    try:
        import eth_abi  # noqa: F401
        from eth_utils import function_signature_to_4byte_selector  # noqa: F401
    except ImportError as exc:  # pragma: no cover - exercised when extra missing
        raise ImportError(
            "On-chain Funding helpers require the chain extra. "
            "Install with: pip install polyester-sdk[chain]"
        ) from exc
