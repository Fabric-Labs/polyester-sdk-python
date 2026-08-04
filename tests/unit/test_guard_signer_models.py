from __future__ import annotations

from polyester.models.guard_signer import ExportGuardSignerWalletResult


def test_export_guard_signer_wallet_result_repr_redacts_private_key() -> None:
    secret = "0x" + ("ab" * 32)
    result = ExportGuardSignerWalletResult(private_key=secret)
    rendered = repr(result)
    assert "[REDACTED]" in rendered
    assert secret not in rendered
    assert "ab" * 8 not in rendered
