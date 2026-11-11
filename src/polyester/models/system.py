from __future__ import annotations

import msgspec


class ServerVersion(msgspec.Struct, kw_only=True, omit_defaults=True):
    """The build an environment serves (``system.v1.SystemService/GetVersion``).

    ``version`` is ``MAJOR.MINOR.PATCH`` for a release, such as ``0.10.0``. A
    build made after a release, which devnet may run, appends the number of
    source revisions since that release and ``g`` with the first 12 hexadecimal
    digits of its own revision: ``0.10.0-12-g4e21a2f09670``. It is not a
    semantic version: compare :attr:`release` to tell which release a build
    follows. ``commit`` is the full source revision of the build.
    ``environment`` names the environment that answered, such as ``devnet``,
    ``testnet``, ``mainnet`` or ``local``; it is a plain string, so a name this
    SDK does not know yet still reads.
    """

    version: str = ""
    commit: str = ""
    environment: str = ""

    @property
    def release(self) -> str:
        """The release a build follows: ``version`` up to its first ``-``."""
        return self.version.split("-", 1)[0]
