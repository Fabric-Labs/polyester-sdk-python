from __future__ import annotations

import asyncio
import contextlib
from collections.abc import Awaitable, Callable
from typing import Generic, TypeVar

from polyester.realtime.client import AsyncRealtimeClient, AsyncSubscription

TSnapshot = TypeVar("TSnapshot")
TPublication = TypeVar("TPublication")


class AsyncSnapshotThenStreamSubscription(Generic[TSnapshot, TPublication]):
  """Fetch a snapshot, buffer publications until ready, and refresh on disconnect."""

  def __init__(
      self,
      *,
      realtime: AsyncRealtimeClient,
      channel: str,
      decode: Callable[[bytes], TPublication],
      fetch_snapshot: Callable[[], Awaitable[TSnapshot]],
      read_publication: Callable[[TPublication], list[TPublication]],
      apply_snapshot: Callable[[TSnapshot, list[TPublication]], None],
      apply_live_publications: Callable[[list[TPublication]], None],
      max_buffered_publications: int = 200,
      on_open: Callable[[], None] | None = None,
      on_close: Callable[[], None] | None = None,
      on_error: Callable[[Exception], None] | None = None,
      on_reconnect: Callable[[], None] | None = None,
      on_snapshot_refresh: Callable[[], None] | None = None,
  ) -> None:
      self._realtime = realtime
      self._channel = channel
      self._decode = decode
      self._fetch_snapshot = fetch_snapshot
      self._read_publication = read_publication
      self._apply_snapshot = apply_snapshot
      self._apply_live_publications = apply_live_publications
      self._max_buffered_publications = max_buffered_publications
      self._on_open = on_open
      self._on_close = on_close
      self._on_error = on_error
      self._on_reconnect = on_reconnect
      self._on_snapshot_refresh = on_snapshot_refresh

      self._ready = False
      self._disposed = False
      self._generation = 0
      self._pending: list[TPublication] = []
      self._lock = asyncio.Lock()
      self._ws_sub: AsyncSubscription[TPublication] | None = None
      self._runner_task: asyncio.Task[None] | None = None

  async def start(self) -> None:
      if self._runner_task is not None:
          return
      self._runner_task = asyncio.create_task(self._run_ws_loop())
      await self.refresh_snapshot()

  def is_ready(self) -> bool:
      return self._ready

  def is_disposed(self) -> bool:
      return self._disposed

  async def refresh_snapshot(self) -> None:
      async with self._lock:
          generation = self._generation + 1
          self._generation = generation
          self._ready = False
          self._pending.clear()
          try:
              snapshot = await self._fetch_snapshot()
          except Exception as exc:
              if not self._disposed:
                  self._report_snapshot_error(exc)
              return
          if self._disposed or generation != self._generation:
              return
          buffered = self._take_pending()
          self._apply_snapshot(snapshot, buffered)
          if self._disposed or generation != self._generation:
              return
          self._ready = True
          if self._on_snapshot_refresh is not None:
              self._on_snapshot_refresh()

  async def aclose(self) -> None:
      self._disposed = True
      self._generation += 1
      self._pending.clear()
      if self._runner_task is not None and not self._runner_task.done():
          self._runner_task.cancel()
          with contextlib.suppress(asyncio.CancelledError, Exception):
              await asyncio.wait_for(self._runner_task, timeout=2.0)
      if self._ws_sub is not None:
          await self._ws_sub.aclose()

  def _take_pending(self) -> list[TPublication]:
      buffered = self._pending
      self._pending = []
      return buffered

  def _handle_publication(self, message: TPublication) -> None:
      publications = self._read_publication(message)
      if not publications:
          return
      if not self._ready:
          self._pending.extend(publications)
          if len(self._pending) > self._max_buffered_publications:
              self._pending = self._pending[-self._max_buffered_publications :]
          return
      self._apply_live_publications(publications)

  async def _run_ws_loop(self) -> None:
      first = True
      while not self._disposed:
          try:
              # Disable transport auto-reconnect so this loop can refresh
              # REST snapshot state between reconnect attempts.
              sub = await self._realtime.subscribe_proto(
                  self._channel,
                  decode=self._decode,
                  auto_reconnect=False,
              )
              if self._disposed:
                  await sub.aclose()
                  break
              self._ws_sub = sub
              if self._on_open is not None:
                  self._on_open()
              if not first:
                  if self._on_reconnect is not None:
                      self._on_reconnect()
                  await self.refresh_snapshot()
              first = False
              async for message in sub:
                  if self._disposed:
                      break
                  self._handle_publication(message)
              if sub.error is not None and self._on_error is not None:
                  self._on_error(sub.error)
          except asyncio.CancelledError:
              break
          except Exception as exc:
              if not self._disposed and self._on_error is not None:
                  self._on_error(exc)
          finally:
              self._ws_sub = None
          if self._disposed:
              break
          if self._on_close is not None:
              self._on_close()
          await asyncio.sleep(1.0)

  def _report_snapshot_error(self, error: Exception) -> None:
      if self._on_error is not None:
          self._on_error(error)
