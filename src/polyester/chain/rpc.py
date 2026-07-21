"""Minimal JSON-RPC helpers for chain RPC / bundler / paymaster."""

from __future__ import annotations

from typing import Any

import httpx


class JsonRpcError(RuntimeError):
    def __init__(self, message: str, *, code: int | None = None, data: Any = None) -> None:
        super().__init__(message)
        self.code = code
        self.data = data


class JsonRpcClient:
    def __init__(self, url: str, *, timeout: float = 60.0) -> None:
        self._url = url
        self._timeout = timeout
        self._id = 0

    def request(self, method: str, params: list[Any] | None = None) -> Any:
        self._id += 1
        payload = {
            "jsonrpc": "2.0",
            "id": self._id,
            "method": method,
            "params": params or [],
        }
        with httpx.Client(timeout=self._timeout) as client:
            response = client.post(self._url, json=payload)
            response.raise_for_status()
            body = response.json()
        if "error" in body and body["error"] is not None:
            err = body["error"]
            raise JsonRpcError(
                str(err.get("message", err)),
                code=err.get("code"),
                data=err.get("data"),
            )
        return body.get("result")

    async def arequest(self, method: str, params: list[Any] | None = None) -> Any:
        self._id += 1
        payload = {
            "jsonrpc": "2.0",
            "id": self._id,
            "method": method,
            "params": params or [],
        }
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(self._url, json=payload)
            response.raise_for_status()
            body = response.json()
        if "error" in body and body["error"] is not None:
            err = body["error"]
            raise JsonRpcError(
                str(err.get("message", err)),
                code=err.get("code"),
                data=err.get("data"),
            )
        return body.get("result")
