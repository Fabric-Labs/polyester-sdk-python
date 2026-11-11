from __future__ import annotations

from polyester.gen.system.v1 import system_pb2
from polyester.gen.system.v1.system_connect import SystemServiceClient
from polyester.models.system import ServerVersion
from polyester.services._base import BaseService
from polyester.services._generated import unary_public_decoded


def server_version_from_proto(msg: system_pb2.GetVersionResponse) -> ServerVersion:
    return ServerVersion(
        version=msg.version,
        commit=msg.commit,
        environment=msg.environment,
    )


class AsyncSystemService(BaseService):
    """The environment's build. Needs no API key; calls count against the
    public per-IP read budget."""

    async def get_version(self) -> ServerVersion:
        return await unary_public_decoded(
            self._transport,
            SystemServiceClient,
            lambda client, req: client.get_version(req),
            system_pb2.GetVersionRequest(),
            server_version_from_proto,
        )
