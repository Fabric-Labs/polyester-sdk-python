from __future__ import annotations

import msgspec

from polyester.models.secret import Secret, as_secret


class GuardSignerStatus(msgspec.Struct, kw_only=True, omit_defaults=True):
    signer_address: str = ""
    onchain_signer_address: str = ""
    initialized: bool = False
    nonce: str = ""
    nonce_space: str = "0"


class GuardApproval(msgspec.Struct, kw_only=True, omit_defaults=True):
    nonce_space: str = "0"
    deadline_unix: str = "0"
    signature: str = ""


class CreateGuardSignerWalletResult(msgspec.Struct, kw_only=True, omit_defaults=True):
    signer_address: str = ""


class RotateGuardSignerWalletResult(msgspec.Struct, kw_only=True, omit_defaults=True):
    new_signer_address: str = ""
    approval: GuardApproval | None = None


class ExportGuardSignerWalletResult(msgspec.Struct, kw_only=True, omit_defaults=True):
    """``private_key`` is the exported private key as a ``Secret``; read it with
    ``result.private_key.reveal()``. Printing, Rich, pickling and msgspec
    encoding never reveal it. A plain ``str`` passed in is wrapped."""

    private_key: Secret[str] = Secret("")

    def __post_init__(self) -> None:
        self.private_key = as_secret(self.private_key)


class BatchSignProtectedActionsResult(msgspec.Struct, kw_only=True, omit_defaults=True):
    approvals: list[GuardApproval]
