from __future__ import annotations

from polyester.codecs.decode.auth import profile_from_proto, username_history_from_proto
from polyester.codecs.realtime_decode import decode_account_identity_bytes
from polyester.gen.auth.v1.profile_connect import ProfileServiceClient
from polyester.gen.auth.v1.profile_pb2 import (
    GetProfileRequest,
    GetUsernameHistoryRequest,
    UserProfilePatch,
)
from polyester.models.auth import AccountIdentity, UsernameHistoryList, UserProfile
from polyester.realtime.client import AsyncRealtimeClient, AsyncSubscription
from polyester.services._base import BaseService
from polyester.services._generated import unary_auth_decoded
from polyester.services._realtime_subscribe import subscribe_public_proto


class AsyncProfileService(BaseService):
    def __init__(self, transport, *, realtime: AsyncRealtimeClient | None = None) -> None:
        super().__init__(transport)
        self._realtime = realtime

    async def get(self) -> UserProfile:
        return await unary_auth_decoded(
            self._transport,
            ProfileServiceClient,
            lambda client, req: client.get_profile(req),
            GetProfileRequest(),
            profile_from_proto,
        )

    async def update(
        self,
        *,
        username: str = "",
        bio: str = "",
        website: str = "",
        twitter: str = "",
        avatar_url: str = "",
    ) -> UserProfile:
        request = UserProfilePatch(
            username=username,
            bio=bio,
            website=website,
            twitter=twitter,
            avatar_url=avatar_url,
        )
        return await unary_auth_decoded(
            self._transport,
            ProfileServiceClient,
            lambda client, req: client.update_profile(req),
            request,
            profile_from_proto,
        )

    async def get_username_history(self) -> UsernameHistoryList:
        return await unary_auth_decoded(
            self._transport,
            ProfileServiceClient,
            lambda client, req: client.get_username_history(req),
            GetUsernameHistoryRequest(),
            username_history_from_proto,
        )

    async def subscribe_identity(self) -> AsyncSubscription[AccountIdentity]:
        return await subscribe_public_proto(
            self._realtime,
            channel="public:identity:updates:proto",
            decode=decode_account_identity_bytes,
        )
