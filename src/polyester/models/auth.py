from __future__ import annotations

from datetime import datetime
from typing import Any

import msgspec

from polyester.models.secret import Secret, as_secret


class MeResult(msgspec.Struct, kw_only=True, omit_defaults=True):
    account_id: str = ""
    api_key_id: str = ""
    username: str = ""
    root_smart_account_address: str = ""
    session: dict[str, Any] | None = None


class UserProfile(msgspec.Struct, kw_only=True, omit_defaults=True):
    username: str = ""
    bio: str = ""
    website: str = ""
    twitter: str = ""
    twitter_verified: bool = False
    discord: str = ""
    discord_verified: bool = False
    avatar_url: str = ""
    created_at: datetime | None = None
    next_username_change_at: datetime | None = None
    vip_tier: int = 0
    username_unlocked: bool = False


class UsernameHistoryEntry(msgspec.Struct, kw_only=True, omit_defaults=True):
    username: str = ""
    set_at: datetime | None = None


class UsernameHistoryList(msgspec.Struct, kw_only=True, omit_defaults=True):
    history: list[UsernameHistoryEntry] = msgspec.field(default_factory=list)


class AccountIdentity(msgspec.Struct, kw_only=True, omit_defaults=True):
    account_id: str = ""
    username: str = ""
    avatar_url: str = ""
    root_smart_account_address: str = ""


class Ed25519Keypair(msgspec.Struct, kw_only=True):
    """A locally generated API key pair.

    The private key is held as ``Secret`` values, so printing, Rich, pickling
    and msgspec encoding never reveal it. Read it with
    ``keypair.secret_key_hex.reveal()`` (64 hex characters, the form
    ``api_private_key`` takes) or ``keypair.secret_key.reveal()`` (the 32-byte
    seed). Plain values passed in are wrapped."""

    public_key_hex: str
    public_key: bytes
    secret_key_hex: Secret[str]
    secret_key: Secret[bytes]

    def __post_init__(self) -> None:
        self.secret_key_hex = as_secret(self.secret_key_hex)
        self.secret_key = as_secret(self.secret_key)
