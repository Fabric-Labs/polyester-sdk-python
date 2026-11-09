"""The logger the SDK gives websockets, with credential headers redacted."""

from __future__ import annotations

import logging
import re
from typing import Any

REDACTED = "[REDACTED]"
# A handshake header line that carries credentials, as websockets logs it at
# DEBUG: ``> Authorization: Basic <base64 user:password>``. websockets builds
# that header from a WebSocket URL's userinfo; base64 decodes to the password.
_CREDENTIAL_HEADER = re.compile(r"([<>]\s*(?:proxy-)?authorization\s*:)", re.IGNORECASE)


class _RedactingLogger(logging.LoggerAdapter[logging.Logger]):
    """Log as websockets does, through ``websockets.client``, but never the
    value of a credential header. The header itself still goes on the wire."""

    def log(self, level: int, msg: object, *args: Any, **kwargs: Any) -> None:
        if not self.isEnabledFor(level):
            return
        if isinstance(msg, str):
            try:
                line = msg % args if args else msg
            except (TypeError, ValueError, KeyError):
                line = msg
            header = _CREDENTIAL_HEADER.match(line)
            if header is not None:
                msg, args = "%s %s", (header.group(1), REDACTED)
        super().log(level, msg, *args, **kwargs)

    def process(self, msg: Any, kwargs: Any) -> tuple[Any, Any]:
        # Keep the caller's ``extra``; this adapter adds none.
        return msg, kwargs


WS_CLIENT_LOGGER = _RedactingLogger(logging.getLogger("websockets.client"))
