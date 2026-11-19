import datetime

from polyester.gen.buf.validate import validate_pb2 as _validate_pb2
from polyester.gen.gnostic.openapi.v3 import annotations_pb2 as _annotations_pb2
from google.protobuf import timestamp_pb2 as _timestamp_pb2
from polyester.gen.polyester.api import options_pb2 as _options_pb2
from polyester.gen.polyester.type.v1 import depth_tier_pb2 as _depth_tier_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class GetOrderBookRequest(_message.Message):
    __slots__ = ("symbol_id", "depth")
    SYMBOL_ID_FIELD_NUMBER: _ClassVar[int]
    DEPTH_FIELD_NUMBER: _ClassVar[int]
    symbol_id: int
    depth: _depth_tier_pb2.DepthTier
    def __init__(self, symbol_id: _Optional[int] = ..., depth: _Optional[_Union[_depth_tier_pb2.DepthTier, str]] = ...) -> None: ...

class PriceLevel(_message.Message):
    __slots__ = ("price_ticks", "qty_scaled")
    PRICE_TICKS_FIELD_NUMBER: _ClassVar[int]
    QTY_SCALED_FIELD_NUMBER: _ClassVar[int]
    price_ticks: int
    qty_scaled: int
    def __init__(self, price_ticks: _Optional[int] = ..., qty_scaled: _Optional[int] = ...) -> None: ...

class GetOrderBookResponse(_message.Message):
    __slots__ = ("symbol_id", "book_seq", "bids", "asks", "ts", "available", "book_epoch", "depth")
    SYMBOL_ID_FIELD_NUMBER: _ClassVar[int]
    BOOK_SEQ_FIELD_NUMBER: _ClassVar[int]
    BIDS_FIELD_NUMBER: _ClassVar[int]
    ASKS_FIELD_NUMBER: _ClassVar[int]
    TS_FIELD_NUMBER: _ClassVar[int]
    AVAILABLE_FIELD_NUMBER: _ClassVar[int]
    BOOK_EPOCH_FIELD_NUMBER: _ClassVar[int]
    DEPTH_FIELD_NUMBER: _ClassVar[int]
    symbol_id: int
    book_seq: int
    bids: _containers.RepeatedCompositeFieldContainer[PriceLevel]
    asks: _containers.RepeatedCompositeFieldContainer[PriceLevel]
    ts: _timestamp_pb2.Timestamp
    available: bool
    book_epoch: int
    depth: _depth_tier_pb2.DepthTier
    def __init__(self, symbol_id: _Optional[int] = ..., book_seq: _Optional[int] = ..., bids: _Optional[_Iterable[_Union[PriceLevel, _Mapping]]] = ..., asks: _Optional[_Iterable[_Union[PriceLevel, _Mapping]]] = ..., ts: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., available: _Optional[bool] = ..., book_epoch: _Optional[int] = ..., depth: _Optional[_Union[_depth_tier_pb2.DepthTier, str]] = ...) -> None: ...

class OrderBookDelta(_message.Message):
    __slots__ = ("symbol_id", "book_seq_start", "book_seq_end", "bids", "asks", "reset", "ts")
    SYMBOL_ID_FIELD_NUMBER: _ClassVar[int]
    BOOK_SEQ_START_FIELD_NUMBER: _ClassVar[int]
    BOOK_SEQ_END_FIELD_NUMBER: _ClassVar[int]
    BIDS_FIELD_NUMBER: _ClassVar[int]
    ASKS_FIELD_NUMBER: _ClassVar[int]
    RESET_FIELD_NUMBER: _ClassVar[int]
    TS_FIELD_NUMBER: _ClassVar[int]
    symbol_id: int
    book_seq_start: int
    book_seq_end: int
    bids: _containers.RepeatedCompositeFieldContainer[PriceLevel]
    asks: _containers.RepeatedCompositeFieldContainer[PriceLevel]
    reset: bool
    ts: _timestamp_pb2.Timestamp
    def __init__(self, symbol_id: _Optional[int] = ..., book_seq_start: _Optional[int] = ..., book_seq_end: _Optional[int] = ..., bids: _Optional[_Iterable[_Union[PriceLevel, _Mapping]]] = ..., asks: _Optional[_Iterable[_Union[PriceLevel, _Mapping]]] = ..., reset: _Optional[bool] = ..., ts: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...
