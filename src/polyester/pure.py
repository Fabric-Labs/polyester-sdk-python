"""Polyester request builders for a restricted Python runtime with no C extensions.

The SDK builds its order, trigger and OCO requests with this file; its README
("Request builders for restricted runtimes") documents it. Its one top-level
name is ``polyester``. Formatted with
``ruff format --config indent-width=2 --line-length 120``.
"""


# Builtins bound at load: code loaded later into the same namespace can't rebind them.
def polyester(
  AttributeError=AttributeError,
  OverflowError=OverflowError,
  ValueError=ValueError,
  abs=abs,
  all=all,
  bool=bool,
  dict=dict,
  divmod=divmod,
  float=float,
  format=format,
  getattr=getattr,
  int=int,
  isinstance=isinstance,
  len=len,
  locals=locals,
  range=range,
  repr=repr,
  setattr=setattr,
  sorted=sorted,
  str=str,
  type=type,
):
  import re as _re
  from dataclasses import dataclass as _dataclass
  from datetime import datetime as _datetime
  from datetime import timedelta as _timedelta
  from datetime import timezone as _timezone
  from decimal import Decimal as _Decimal
  from decimal import InvalidOperation as _InvalidOperation

  _VERSION = "0.33.0"

  _UINT64_MAX = 18446744073709551615
  _UINT32_MAX = 4294967295
  _INT64_MAX = 9223372036854775807
  _INT64_MIN = -9223372036854775808
  _PRICE_SCALE = 9
  _MAX_SCALE = 36
  _MAX_SCALED_DIGITS = 75  # digits of 2**128 - 1 (39) plus the largest scale
  _MAX_SHOWN = 64
  _HUGE = 1 << 512
  _MAX_BPS = 10000
  _MAX_SELL_BPS = 9999  # 100% leaves no price to sell at
  _CLIENT_ID_MAX_LEN = 36
  _REQUEST_ID_MAX_LEN = 64
  # The contract's buf.validate limits; a test holds them to the contract.
  _CLIENT_TRIGGER_ID_MAX_BYTES = 36
  _CLIENT_LIST_ID_MAX_LEN = 36
  _TWAP_DURATION_MS = (1000, _INT64_MAX)
  _TWAP_SLICE_INTERVAL_MS = (100, _INT64_MAX)
  _LADDER_LEVELS = (2, 100)

  _STRICT_DECIMAL = _re.compile(r"^[0-9]+(?:\.[0-9]+)?$")
  _DECIMAL_INTEGER = _re.compile(r"[0-9]+")
  _B58 = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
  _UTC = _timezone.utc

  _BAD_PRICE = "ERROR_CODE_BAD_PRICE"
  _CLIENT_LIST_ID_INVALID = "ERROR_CODE_CLIENT_LIST_ID_INVALID"
  _CLIENT_TRIGGER_ID_INVALID = "ERROR_CODE_CLIENT_TRIGGER_ID_INVALID"
  _FEE_ASSET_NOT_ALLOWED = "ERROR_CODE_FEE_ASSET_NOT_ALLOWED"
  _LADDER_LEVELS_INVALID = "ERROR_CODE_LADDER_LEVELS_INVALID"
  _MAX_SLIPPAGE_INVALID = "ERROR_CODE_MAX_SLIPPAGE_INVALID"
  _SLIPPAGE_BPS_INVALID = "ERROR_CODE_SLIPPAGE_BPS_INVALID"
  _SLIPPAGE_TICKS_INVALID = "ERROR_CODE_SLIPPAGE_TICKS_INVALID"
  _TRAILING_DISTANCE_INVALID = "ERROR_CODE_TRAILING_DISTANCE_INVALID"
  _TRIGGER_PATCH_EMPTY = "ERROR_CODE_TRIGGER_PATCH_EMPTY"
  _ACTIVATION_PRICE_INVALID = "ERROR_CODE_TRIGGER_ACTIVATION_PRICE_INVALID"
  _TRIGGER_PRICE_INVALID = "ERROR_CODE_TRIGGER_PRICE_INVALID"
  _TRIGGER_QTY_INVALID = "ERROR_CODE_TRIGGER_QTY_INVALID"
  _TWAP_DURATION_INVALID = "ERROR_CODE_TWAP_DURATION_INVALID"
  _TWAP_INTERVAL_INVALID = "ERROR_CODE_TWAP_INTERVAL_INVALID"
  _BUY_REQUIRES_LIMIT = "ERROR_CODE_TRIGGER_BUY_REQUIRES_LIMIT"
  _QTY_STEP_SIZE = "ERROR_CODE_QTY_STEP_SIZE"
  _PRICE_TICK_SIZE = "ERROR_CODE_PRICE_TICK_SIZE"
  _GRID_RULES = {
    _QTY_STEP_SIZE: ("step_size", "quantity does not align with the pair step size"),
    _PRICE_TICK_SIZE: ("tick_size", "price does not align with the pair tick size"),
  }

  _SIDES = {"buy": "BUY", "sell": "SELL"}
  _ORDER_TYPES = {"limit": "LIMIT", "market": "MARKET"}
  _TIFS = {"gtc": "GTC", "ioc": "IOC", "fok": "FOK", "gtd": "GTD"}
  _TIF_VALUES = "gtc', 'ioc', 'fok', 'gtd"
  _FEE_ASSETS = {"quote": "QUOTE", "base": "BASE"}
  _PEG_REFERENCES = {"best_bid": "BEST_BID", "best_ask": "BEST_ASK"}
  _MODIFY_BEHAVIORS = {
    "amend_or_replace": "AMEND_OR_REPLACE",
    "amend_only": "AMEND_ONLY",
    "replace_only": "REPLACE_ONLY",
  }
  _STP_MODES = {
    "expire_taker": "EXPIRE_TAKER",
    "expire_maker": "EXPIRE_MAKER",
    "expire_both": "EXPIRE_BOTH",
    "decrement": "DECREMENT",
  }
  _PRICE_SOURCES = {
    "last": "LAST_PRICE",
    "last_price": "LAST_PRICE",
    "index": "INDEX_PRICE",
    "index_price": "INDEX_PRICE",
  }
  _TRIGGER_TYPES = {
    "stop_loss": "STOP_LOSS",
    "take_profit": "TAKE_PROFIT",
    "trailing_stop": "TRAILING_STOP",
    "twap": "TWAP",
    "ladder": "LADDER",
  }

  def _err(message, code=None, violations=None, fractional=False):
    exc = ValueError(message)
    _tag(exc, code, violations, fractional)
    return exc

  def _tag(exc, code=None, violations=None, fractional=False):
    # CPython keeps the server's code, the field violations and whether a
    # digit fell past the scale; a runtime whose exceptions take no
    # attributes keeps the message only.
    try:
      if code is not None:
        setattr(exc, "code", code)  # noqa: B010
      if violations is not None:
        setattr(exc, "violations", violations)  # noqa: B010
      if fractional:
        setattr(exc, "fractional", True)  # noqa: B010
    except AttributeError:
      pass

  def _coded(code, fn, *args):
    try:
      return fn(*args)
    except ValueError as exc:
      if code is not None and getattr(exc, "code", None) is None:
        _tag(exc, code)
      raise

  def _grid(code, path, fn, *args):
    try:
      return fn(*args)
    except ValueError as exc:
      if not getattr(exc, "fractional", False):
        raise
      rule, message = _GRID_RULES[code]
      raise _err(str(exc), code, [_violation(path, rule, message)]) from None

  def _violation(path, rule, message):
    return {"field_path": path, "rule_id": rule, "message": message}

  def _type_name(value):
    return type(value).__name__

  def _int(value):
    # A plain int of the true value, as operator.index gives it: range()
    # reads an int subclass's own value, whatever it overrides.
    return value if type(value) is int else range(value).stop

  def _shown(text):
    return text if len(text) <= _MAX_SHOWN else f"{text[:_MAX_SHOWN]}... ({len(text)} characters)"

  def _scale(scale, field="scale"):
    if isinstance(scale, bool) or not isinstance(scale, int):
      raise _err(f"{field} must be an int")
    scale = _int(scale)
    if scale < 0:
      raise _err(f"{field} must be non-negative")
    if scale > _MAX_SCALE:
      raise _err(f"{field} {scale} exceeds maximum protocol scale {_MAX_SCALE}")
    return scale

  def _trim_zeros(text):
    if "." not in text:
      return text
    whole, _, frac = text.partition(".")
    frac = frac.rstrip("0")
    return f"{whole}.{frac}" if frac else whole or "0"

  def _check_decimal_size(raw, scale, field):
    # Before format(raw, "f"), which writes every digit an exponent implies.
    _, digits, exponent = raw.as_tuple()
    significant = len(digits)
    while significant > 1 and digits[significant - 1] == 0 and exponent < 0:
      significant -= 1
      exponent += 1
    shown = str(raw)
    if significant + abs(exponent) <= _MAX_SHOWN:
      shown = _trim_zeros(format(raw, "f"))
    if -exponent > scale:
      raise _err(f"{field} supports at most {scale} decimal places: {_shown(shown)}", fractional=True)
    if significant + exponent + scale > _MAX_SCALED_DIGITS:
      raise _err(f"{field} is too large: {_shown(shown)}")

  def _decimal_text(raw, field, scale):
    if isinstance(raw, (bool, float)):
      raise _err(f"{field} must be a decimal string or Decimal")
    if isinstance(raw, _Decimal):
      if not raw.is_finite():
        raise _err(f"{field} must be a finite decimal")
      if raw < 0:
        raise _err(f"{field} must be non-negative")
      if raw.is_zero():
        return "0"
      _check_decimal_size(raw, scale, field)
      text = format(raw, "f")
      if "." in text:
        text = text.rstrip("0").rstrip(".")
      return text or "0"
    if not isinstance(raw, str):
      raise _err(f"{field} must be a decimal string or Decimal")
    # Checked before trimming: str.strip() also strips non-ASCII spaces.
    if not raw.isascii():
      raise _err(f"{field} must be a valid decimal string")
    text = raw.strip()
    if not text or not _STRICT_DECIMAL.match(text):
      raise _err(f"{field} must be a valid decimal string")
    return text

  def _try_scaled(decimal, scale):
    if scale < 0 or scale > _MAX_SCALE:
      return False, None, "scale"
    raw = decimal.strip()
    if not decimal.isascii() or not _STRICT_DECIMAL.match(raw):
      return False, None, "invalid"
    whole, _, frac = _trim_zeros(raw).partition(".")
    if len(frac) > scale:
      return False, None, "precision"
    try:
      return True, int(whole + frac + "0" * (scale - len(frac)) or "0"), None
    except ValueError:  # more digits than int() reads
      return False, None, "invalid"

  def _to_scaled(raw, scale, field):
    _scale(scale, f"{field} scale")
    text = _decimal_text(raw, field, scale)
    ok, scaled, reason = _try_scaled(text, scale)
    if ok:
      return scaled
    if reason == "precision":
      raise _err(f"{field} supports at most {scale} decimal places: {_shown(text)}", fractional=True)
    raise _err(f"{field} must be a valid decimal string")

  def _parse_price_ticks(raw, field="price"):
    scaled = _to_scaled(raw, _PRICE_SCALE, field)
    if scaled > _INT64_MAX:
      raise _err(f"{field} exceeds int64 range")
    return scaled

  def _parse_qty_scaled(raw, scale, field="qty"):
    scaled = _to_scaled(raw, scale, field)
    if scaled <= 0:
      raise _err(f"{field} must be positive")
    # Scale 18 is a ledger amount, which may exceed int64 (U128 on the wire).
    if scale != 18 and scaled > _INT64_MAX:
      raise _err(f"{field} exceeds int64 range")
    return scaled

  def _format_scaled(value, scale):
    if scale < 0:
      raise _err("scale must be non-negative")
    if scale == 0:
      return str(int(value))
    digits = str(abs(int(value))).zfill(scale + 1)
    text = f"{digits[:-scale]}.{digits[-scale:]}".rstrip("0").rstrip(".") or "0"
    return f"-{text}" if value < 0 else text

  def _format_qty_scaled(scaled, scale):
    return _format_scaled(scaled, _scale(scale))

  def _ascii_int(value):
    if not value.isascii():
      raise ValueError("not an ASCII integer")
    return int(value)

  def _exact_integer(value, field, min_value, max_value, allow_str=False):
    expected = "an integer or a decimal-integer string" if allow_str else "an integer"
    if isinstance(value, bool):
      raise _err(f"{field} must be {expected}, not bool")
    if isinstance(value, str):
      if not allow_str or _DECIMAL_INTEGER.fullmatch(value) is None:
        raise _err(f"{field} must be {expected}, not {_shown(repr(value))}")
      digits = value.lstrip("0") or "0"
      if len(digits) > len(str(max_value)):
        raise _err(f"{field} {_shown(digits)} is outside {min_value}..{max_value}")
      parsed = int(digits)
    elif isinstance(value, int):
      parsed = _int(value)
    else:
      raise _err(f"{field} must be {expected}, not {_type_name(value)}")
    if parsed < min_value or parsed > max_value:
      # str() of a huge int is slow or refused, so it is not repeated.
      shown = f" {_shown(str(parsed))}" if -_HUGE < parsed < _HUGE else ""
      raise _err(f"{field}{shown} is outside {min_value}..{max_value}")
    return parsed

  def _small_int(value, field):
    if isinstance(value, bool) or not isinstance(value, (int, str)):
      raise _err(f"{field} must be an integer")
    try:
      return _int(value) if isinstance(value, int) else _ascii_int(value)
    except ValueError:
      raise _err(f"{field} must be an integer") from None

  def _tick_count(value, field, allow_zero=False):
    parsed = _small_int(value, field)
    if parsed < 0 or (parsed == 0 and not allow_zero):
      raise _err(f"{field} must be {'non-negative' if allow_zero else 'positive'}")
    if parsed > _INT64_MAX:
      raise _err(f"{field} exceeds int64 range")
    return parsed

  def _bps(value, field, allow_clear=False, max_value=_MAX_BPS):
    parsed = _small_int(value, field)
    if allow_clear and parsed == 0:
      return parsed
    if parsed < 1 or parsed > max_value:
      raise _err(f"{field} must be between 1 and {max_value}")
    return parsed

  def _max_slippage_bps_for_side(side):
    return _MAX_SELL_BPS if side == "sell" else _MAX_BPS

  def _slippage_bps(value, max_value, allow_clear=False):
    # Outside 1 to 10000 is SLIPPAGE_BPS_INVALID; 10000 where only 9999
    # applies is MAX_SLIPPAGE_INVALID, as the server answers them.
    parsed = _coded(_SLIPPAGE_BPS_INVALID, _bps, value, "max_slippage_bps", allow_clear)
    if parsed > max_value:
      raise _err(f"max_slippage_bps must be between 1 and {max_value}", _MAX_SLIPPAGE_INVALID)
    return parsed

  def _market_id(value, label):
    if isinstance(value, bool):
      raise _err(f"{label} must be an integer market ID, not bool")
    if not isinstance(value, int):
      raise _err(f"{label} must be an integer market ID, not {_type_name(value)}")
    parsed = _int(value)
    if parsed < 0 or parsed > _UINT32_MAX:
      raise _err(f"{label} {parsed} is outside 0..{_UINT32_MAX}")
    return parsed

  def _encode_id(value):
    text = ""
    while value:
      value, digit = divmod(value, 58)
      text = _B58[digit] + text
    return text or "1"

  def _parse_id(value, label):
    if isinstance(value, bool) or not isinstance(value, (int, str)):
      raise _err(f"{label} must be a base58 string or an integer ID")
    if isinstance(value, int):
      parsed = _int(value)
      if parsed < 0 or parsed > _UINT64_MAX:
        raise _err(f"{label} exceeds uint64 range")
      return parsed
    if not value:
      raise _err(f"{label} must be a base58 public ID, not empty")
    parsed = 0
    for char in value:
      digit = _B58.find(char)
      if digit < 0:
        raise _err(
          f"{label} must be a base58 public ID: {_shown(repr(value))} has "
          f"{char!r}, which is not base58; pass an integer ID as an int"
        )
      parsed = parsed * 58 + digit
      if parsed > _UINT64_MAX:
        raise _err(f"{label} exceeds uint64 range")
    if _encode_id(parsed) != value:
      if parsed == 0:
        raise _err(f"{label} must be a non-zero ID, not 0")
      raise _err(
        f"{label} must be a public ID in canonical form, as the SDK writes it "
        "(no leading 1); use the ID as the SDK or the app shows it, or pass the integer"
      )
    return parsed

  def _id_to_int(value, label="id"):
    parsed = _parse_id(value, label)
    if parsed == 0:
      raise _err(f"{label} must be a non-zero ID, not 0")
    return parsed

  def _check_correlation_id(value, field, max_len):
    if not value or len(value) > max_len:
      raise _err(f"{field} must be 1 to {max_len} characters")
    for char in value:
      if not (char.isascii() and (char.isalnum() or char in "._:/-")):
        raise _err(f"{field} contains invalid characters; allowed: A-Z a-z 0-9 . _ : / -")
    return value

  def _optional_client_id(value, field="client_order_id"):
    if value is None or not value.strip():
      return None
    return _check_correlation_id(value.strip(), field, _CLIENT_ID_MAX_LEN)

  def _required_client_id(value, field):
    return _check_correlation_id(value.strip(), field, _CLIENT_ID_MAX_LEN)

  def _optional_request_id(value):
    if value is None or not value.strip():
      return None
    return _check_correlation_id(value.strip(), "request_id", _REQUEST_ID_MAX_LEN)

  def _client_trigger_id(value):
    message = f"client_trigger_id must be 1 to {_CLIENT_TRIGGER_ID_MAX_BYTES} bytes of UTF-8"
    if not isinstance(value, str) or not value:
      raise _err(message, _CLIENT_TRIGGER_ID_INVALID)
    try:
      size = len(value.encode("utf-8"))
    except ValueError:
      raise _err(message, _CLIENT_TRIGGER_ID_INVALID) from None
    if size > _CLIENT_TRIGGER_ID_MAX_BYTES:
      raise _err(message, _CLIENT_TRIGGER_ID_INVALID)
    return value

  def _client_list_id(value, field="client_list_id"):
    if not isinstance(value, str):
      raise _err(f"{field} must be a string", _CLIENT_LIST_ID_INVALID)
    return _coded(_CLIENT_LIST_ID_INVALID, _check_correlation_id, value, field, _CLIENT_LIST_ID_MAX_LEN)

  def _aware(value, field):
    if isinstance(value, _datetime):
      if value.tzinfo is not None and value.utcoffset() is not None:
        try:
          value.astimezone(_UTC)
        except OverflowError:
          raise _err(f"{field} is outside the supported range (years 1 to 9999 in UTC)") from None
        return value
      received = "a naive datetime"
    else:
      received = "None" if value is None else _type_name(value)
    raise _err(f"{field} must be a timezone-aware datetime, not {received}")

  def _gtd_text(value):
    if value is None or isinstance(value, str):
      return value
    raise _err(f"expires_at must be an RFC3339 UTC timestamp string, not {_type_name(value)}")

  def _rfc3339(value):
    text = f"{value.year:04d}-{value.month:02d}-{value.day:02d}T{value.hour:02d}:{value.minute:02d}:{value.second:02d}"
    micros = value.microsecond
    if micros % 1000:
      text += f".{micros:06d}"
    elif micros:
      text += f".{micros // 1000:03d}"
    return text + "Z"

  def _gtd_expire_at(value, now):
    text = (_gtd_text(value) or "").strip()
    if not text:
      raise _err("tif='gtd' requires expires_at")
    if text.endswith("Z"):
      text = text[:-1] + "+00:00"
    try:
      parsed = _datetime.fromisoformat(text)
    except ValueError:
      raise _err("expires_at must be an RFC3339 UTC timestamp") from None
    if parsed.tzinfo is None:
      raise _err("expires_at must be timezone-aware UTC")
    parsed = _aware(parsed, "expires_at").astimezone(_UTC)
    if now is None:
      raise _err("tif='gtd' requires now, the current time, to check expires_at")
    delta = parsed - _aware(now, "now").astimezone(_UTC)
    if delta < _timedelta(seconds=1) or delta > _timedelta(days=30):
      raise _err("expires_at must be between 1 second and 30 days after validation")
    return _rfc3339(parsed)

  def _is(value, kind):
    # A price, quantity or transfer amount names its kind, so the SDK's slotted
    # types are read as this file's own.
    return getattr(value, "_polyester_kind", None) == kind

  def _require_scaled_int(value, field, allow_u128=False):
    if isinstance(value, bool):
      raise _err(f"{field} must not be a boolean")
    if not isinstance(value, int):
      raise _err(f"{field} must be an int")
    value = _int(value)
    if value < 0:
      raise _err(f"{field} must be non-negative")
    if not allow_u128 and value > _INT64_MAX:
      raise _err(f"{field} exceeds int64 range")
    return value

  def _typed_int(value, field):
    # A Price or Quantity built directly is unchecked: its value must be the int
    # the wire field takes; the field's own checks follow.
    if isinstance(value, bool) or not isinstance(value, int):
      raise _err(f"{field} must be an int")
    if value > _INT64_MAX:
      raise _err(f"{field} exceeds int64 range")
    return _int(value)

  def _price_from_ticks(ticks, *, symbol=None):
    return Price(_require_scaled_int(ticks, "ticks"), symbol)

  @_dataclass(frozen=True)
  class Price:
    """A price in ticks (1e-9 quote units); ``symbol`` binds it to a market."""

    ticks: int
    symbol: str | None = None
    _polyester_kind = "price"
    from_ticks = _price_from_ticks

    def as_decimal(self):
      return _Decimal(_format_scaled(self.ticks, _PRICE_SCALE))

    def format(self):
      return _format_scaled(self.ticks, _PRICE_SCALE)

    def compatible_with(self, *, symbol=None):
      _price_compatible(self, symbol)

  def _price_compatible(price, symbol):
    if price.symbol is not None and symbol is not None and price.symbol != symbol:
      raise _err(f"price symbol mismatch: value is for {price.symbol}, destination is {symbol}")

  def _quantity_from_scaled(scaled, *, scale=None, domain="order_base", symbol=None, symbol_id=None):
    value = _require_scaled_int(scaled, "scaled")
    if domain not in ("order_base", "order_quote"):
      raise _err("Quantity domain must be order_base or order_quote")
    if scale is not None:
      _scale(scale)
    return Quantity(value, scale, domain, symbol, symbol_id)

  def _quote_quantity_from_scaled(scaled, scale, *, symbol=None, symbol_id=None):
    return _quantity_from_scaled(scaled, scale=scale, domain="order_quote", symbol=symbol, symbol_id=symbol_id)

  def _quote_quantity_from_decimal(raw, scale, *, symbol=None, symbol_id=None):
    scaled = _parse_qty_scaled(raw, scale, "quote amount")
    return _quote_quantity_from_scaled(scaled, scale, symbol=symbol, symbol_id=symbol_id)

  @_dataclass(frozen=True)
  class Quantity:
    """An order or trigger quantity in scaled units (proto ``*_qty_scaled``)."""

    scaled: int
    scale: int | None = None
    domain: str = "order_base"
    symbol: str | None = None
    symbol_id: int | None = None
    _polyester_kind = "quantity"
    from_scaled = _quantity_from_scaled
    from_quote_scaled = _quote_quantity_from_scaled
    from_quote_decimal = _quote_quantity_from_decimal
    from_quote_decimal_str = _quote_quantity_from_decimal

    def as_decimal(self, scale=None):
      return _Decimal(_quantity_text(self, scale, "as_decimal"))

    def format(self, scale=None):
      return _quantity_text(self, scale, "format")

    def compatible_with(self, *, domain="order_base", scale=None, symbol=None, symbol_id=None):
      _quantity_compatible(self, domain, scale, symbol, symbol_id)

  def _quantity_text(qty, scale, name):
    resolved = scale if scale is not None else qty.scale
    if resolved is None:
      raise _err(f"{name} requires a known scale; pass scale= or construct with scale=")
    return _format_qty_scaled(qty.scaled, resolved)

  def _quantity_compatible(qty, domain, scale, symbol, symbol_id):
    if qty.domain != domain:
      raise _err(f"quantity domain mismatch: value is {qty.domain}, destination is {domain}")
    if qty.scale is not None and scale is not None and qty.scale != scale:
      raise _err(f"quantity scale mismatch: value scale is {qty.scale}, destination is {scale}")
    if qty.symbol is not None and symbol is not None and qty.symbol != symbol:
      raise _err(f"quantity symbol mismatch: value is for {qty.symbol}, destination is {symbol}")
    if qty.symbol_id is not None and symbol_id is not None and qty.symbol_id != symbol_id:
      raise _err(f"quantity symbol_id mismatch: value is for {qty.symbol_id}, destination is {symbol_id}")

  def _resolve_price_ticks(value, field="price", symbol=None, positive=False):
    if _is(value, "price"):
      _price_compatible(value, symbol)
      ticks = _typed_int(value.ticks, f"{field}.ticks")
    elif isinstance(value, (int, float, bool)):
      raise _err(f"{field} must be a decimal string, Decimal, or Price (use Price.from_ticks for scaled ints)")
    else:
      ticks = _parse_price_ticks(value, field)
    if positive and ticks <= 0:
      raise _err(f"{field} must be positive")
    return ticks

  def _resolve_qty(value, scale, field, symbol, symbol_id, quote):
    if _is(value, "quantity"):
      if quote and value.scale is None:
        raise _err("quote amount scale is required; use Quantity.from_quote_scaled/from_quote_decimal")
      domain = "order_quote" if quote else "order_base"
      _quantity_compatible(value, domain, scale, symbol, symbol_id)
      scaled = _typed_int(value.scaled, f"{field}.scaled")
      if scaled <= 0:
        raise _err(f"{field} must be positive")
      return scaled
    if _is(value, "asset_amount"):
      target = "order quote" if quote else "order/trigger"
      raise _err(f"{field} expects Quantity ({target}), not AssetAmount")
    if isinstance(value, (int, float, bool)):
      hint = "from_quote_scaled" if quote else "from_scaled"
      raise _err(f"{field} must be a decimal string, Decimal, or Quantity (use Quantity.{hint} for scaled ints)")
    scaled = _parse_qty_scaled(value, scale, field)
    if scaled > _INT64_MAX:
      raise _err(f"{field} exceeds int64 range")
    return scaled

  def _resolve_qty_scaled(value, scale, field="qty", symbol=None, symbol_id=None):
    return _resolve_qty(value, scale, field, symbol, symbol_id, False)

  def _resolve_quote_qty_scaled(value, scale, field="max_quote_debit", symbol=None, symbol_id=None):
    return _resolve_qty(value, scale, field, symbol, symbol_id, True)

  def _value_scale(scale, *values):
    for value in values:
      if _is(value, "quantity") and value.scale is not None and value.scale != scale:
        raise _err(f"quantity scale mismatch: value scale is {value.scale}, destination is {scale}")
    return scale

  def _quote_value_scale(scale, *values):
    present = [value for value in values if value is not None]
    for value in present:
      if _is(value, "quantity"):
        if value.scale is None:
          raise _err("quote amount scale is required; use Quantity.from_quote_scaled/from_quote_decimal")
        if value.scale != scale:
          raise _err(f"quantity scale mismatch: value scale is {value.scale}, destination is {scale}")
    return scale if present else 0

  def _codec_scale(value, quantity_scale):
    if quantity_scale is not None:
      return quantity_scale
    if _is(value, "quantity"):
      return value.scale if value.scale is not None else 0
    raise _err("decimal quantity encoding requires an explicit quantity_scale resolved from catalogs")

  def _spec_field(spec, snake, camel):
    value = spec.get(snake)
    return spec.get(camel) if value is None else value

  def _spec_int(spec, snake, camel, low, high, default=None):
    value = _spec_field(spec, snake, camel)
    if value is None:
      # Proto-JSON leaves a 0 out: a scale left out is 0.
      if default is None:
        raise _err(f"market {snake} is required")
      return default
    if isinstance(value, str) and _DECIMAL_INTEGER.fullmatch(value) is not None:
      if len(value) > 20:
        raise _err(f"market {snake} {_shown(value)} is outside {low}..{high}")
      value = int(value)
    if isinstance(value, bool) or not isinstance(value, int):
      raise _err(f"market {snake} must be an integer")
    value = _int(value)
    if value < low or value > high:
      raise _err(f"market {snake} {value} is outside {low}..{high}")
    return value

  @_dataclass(frozen=True)
  class Market:
    """A GetSpotConfig pair (other fields are ignored: the server enforces tick, step and
    minimums); binds prices and quantities to it."""

    symbol: str
    symbol_id: int
    base_quantity_scale: int
    quote_quantity_scale: int

    def price(self, value):
      return Price(_resolve_price_ticks(value, "price", self.symbol), self.symbol)

    def qty(self, value):
      scale = self.base_quantity_scale
      scaled = _resolve_qty_scaled(value, scale, "qty", self.symbol, self.symbol_id)
      return Quantity(scaled, scale, "order_base", self.symbol, self.symbol_id)

    def quote_qty(self, value):
      scale = self.quote_quantity_scale
      scaled = _resolve_quote_qty_scaled(value, scale, "quote_qty", self.symbol, self.symbol_id)
      return Quantity(scaled, scale, "order_quote", self.symbol, self.symbol_id)

  def _market(spec):
    if isinstance(spec, Market):
      return spec
    if not isinstance(spec, dict):
      raise _err(f"market must be a GetSpotConfig pair dict, not {_type_name(spec)}")
    symbol = spec.get("symbol")
    if not isinstance(symbol, str) or not symbol.strip():
      raise _err("market symbol must be a non-empty string")
    return Market(
      symbol,
      _spec_int(spec, "symbol_id", "symbolId", 1, _UINT32_MAX),
      _spec_int(spec, "base_quantity_scale", "baseQuantityScale", 0, _MAX_SCALE, 0),
      _spec_int(spec, "quote_quantity_scale", "quoteQuantityScale", 0, _MAX_SCALE, 0),
    )

  def _lookup(market):
    # (id of a name, name of an ID): the SDK's catalogs, or one market.
    return (
      lambda symbol: market.symbol_id if symbol == market.symbol else None,
      lambda symbol_id: market.symbol if symbol_id == market.symbol_id else None,
    )

  def _resolve_symbol_id(symbol, symbol_id, label, lookup):
    if symbol_id is not None:
      explicit = _market_id(symbol_id, f"{label} symbol_id")
      if explicit == 0:
        raise _err(f"{label} symbol_id must be non-zero when explicitly supplied")
      if symbol and lookup is not None:
        canonical, named = lookup[1](explicit), lookup[0](symbol)
        if (canonical is not None and symbol != canonical) or (named is not None and named != explicit):
          raise _err(
            f"{label} symbol mismatch: {symbol!r} does not match symbol_id {explicit}"
            + (f" ({canonical})" if canonical else "")
          )
      return explicit
    if symbol and lookup is not None:
      resolved = lookup[0](symbol)
      if resolved is not None:
        return resolved
    if symbol is None:
      raise _err(f"{label} requires symbol or symbol_id")
    raise _err(f"Unknown symbol {symbol!r}; call get_spot_config first or pass symbol_id")

  def _symbol_id_for(market, symbol, symbol_id, label):
    if symbol is None and symbol_id is None:
      return market.symbol_id
    return _resolve_symbol_id(symbol, symbol_id, label, _lookup(market))

  def _optional_symbol(symbol, label):
    if symbol is None:
      return None
    if not isinstance(symbol, str):
      raise _err(f"{label} must be a symbol string")
    if not symbol.strip():
      raise _err(f"{label} must not be blank; leave it out to match every market")
    return symbol.strip()

  def _control_symbol_id(symbol, symbol_id, label, lookup):
    symbol = _optional_symbol(symbol, f"{label} symbol")
    if symbol is None and symbol_id is None:
      return 0
    return _resolve_symbol_id(symbol, symbol_id, label, lookup)

  def _bound_market(symbol_id, prices, lookup, label):
    bound = [price for price in prices if _is(price, "price") and price.symbol is not None]
    if not symbol_id or not bound:
      return None
    name = lookup[1](symbol_id) if lookup is not None else None
    if name is None:
      raise _err(
        f"{label} cannot check a price bound to {bound[0].symbol} against symbol_id "
        f"{symbol_id}: the market is not in the catalogs; hydrate catalogs or pass an "
        "unbound price"
      )
    return name

  def _account(request, sub_account_id):
    if sub_account_id is not None:
      request["subaccountId"] = str(_id_to_int(sub_account_id, "sub_account_id"))
    return request

  def _host_owned(**values):
    for name in values:
      if values[name] is not None:
        raise _err(f"{name} is assigned by the host; leave it out")

  def _first(data, *names):
    for name in names:
      if name in data and data[name] is not None:
        return data[name]
    return None

  def _has(data, *names):
    return len([name for name in names if name in data]) > 0

  def _reject_unknown(data, allowed, field):
    unknown = [str(key) for key in data if key not in allowed]
    if unknown:
      raise _err(f"{field} has unsupported fields: {', '.join(sorted(unknown))}")

  def _put(target, key, value):
    if value:
      target[key] = value
    return target

  def _camel(name):
    head, *rest = name.split("_")
    return head + "".join([part.capitalize() for part in rest])

  def _price_source(value, field="trigger_price_source"):
    if value is None or value == "":
      return ""
    key = value.strip().lower() if isinstance(value, str) else ""
    if key in ("mark", "mark_price"):
      raise _err(f"{field} mark is not supported on spot markets; use last or index")
    if key not in _PRICE_SOURCES:
      raise _err(f"{field} must be last or index")
    return _PRICE_SOURCES[key]

  def _stp_mode(value):
    key = value.lower() if isinstance(value, str) else ""
    if key not in _STP_MODES:
      raise _err("self_trade_prevention_mode must be expire_taker, expire_maker, expire_both, or decrement")
    return _STP_MODES[key]

  _CREATE_ORDER_FIELDS = (
    "symbol symbol_id side order_type tif qty max_quote_debit quote_proceeds price sub_account_id "
    "client_order_id post_only expires_at attached_risk market_client_ref_price fee_asset "
    "max_slippage_ticks max_slippage_bps self_trade_prevention_mode display_qty peg"
  ).split()
  _DECIMAL_FIELDS = "qty max_quote_debit quote_proceeds display_qty price market_client_ref_price"

  def _wire_int(value):
    return isinstance(value, int) and not isinstance(value, bool) and (_INT64_MIN <= value <= _UINT64_MAX)

  def _create_types_ok(data):
    for name in ("side", "order_type"):
      if not isinstance(data.get(name), str):
        return False
    for name in "symbol tif client_order_id expires_at fee_asset self_trade_prevention_mode".split():
      if data.get(name) is not None and not isinstance(data[name], str):
        return False
    for name in ("symbol_id", "max_slippage_ticks", "max_slippage_bps"):
      if data.get(name) is not None and not _wire_int(data[name]):
        return False
    account = data.get("sub_account_id")
    if account is not None and not isinstance(account, str) and not _wire_int(account):
      return False
    return "post_only" not in data or isinstance(data["post_only"], bool)

  def _normalize_create(data):
    unknown = sorted([str(key) for key in data if key not in _CREATE_ORDER_FIELDS])
    if unknown:
      raise _err("unsupported create order argument(s): " + ", ".join(unknown))
    _gtd_text(data.get("expires_at"))
    if not _create_types_ok(data):
      raise _err("Invalid orders.create request")
    request = {name: data.get(name) for name in _CREATE_ORDER_FIELDS}
    request["post_only"] = bool(data.get("post_only", False))
    return _refuse_float_amounts(request)

  def _refuse_float_amounts(request):
    for name in _DECIMAL_FIELDS.split():
      if isinstance(request.get(name), float):
        raise _err(f"{name} must be a decimal string, Decimal, or typed scaled value (floats are not allowed)")
    return request

  def _order_intent(request, quantity_scale=None, quote_quantity_scale=None, now=None):
    symbol, symbol_id = request.get("symbol"), request.get("symbol_id")
    side, order_type, tif = request.get("side"), request.get("order_type"), request.get("tif")
    if symbol is None and symbol_id is None:
      raise _err("orders.create requires symbol or symbol_id")
    if side not in _SIDES:
      raise _err("side must be 'buy' or 'sell'")
    if order_type not in _ORDER_TYPES:
      raise _err("order_type must be 'limit' or 'market'")
    if tif is not None and tif not in _TIFS:
      raise _err(f"tif must be one of '{_TIF_VALUES}'")
    qty, debit, proceeds = [request.get(k) for k in ("qty", "max_quote_debit", "quote_proceeds")]
    if len([size for size in (qty, debit, proceeds) if size is not None]) != 1:
      raise _err("orders.create requires exactly one of qty, max_quote_debit or quote_proceeds")
    is_ioc = order_type == "market" or (tif or "gtc") == "ioc"
    if debit is not None and (side != "buy" or not is_ioc):
      raise _err("max_quote_debit is only valid for buy market or limit IOC orders")
    if proceeds is not None and (side != "sell" or not is_ioc):
      raise _err("quote_proceeds is only valid for sell market or limit IOC orders")
    if symbol_id is None or int(symbol_id) == 0:
      raise _err("orders.create requires a resolved symbol_id; pass symbol_id or wait for catalogs")
    intent = {"symbolId": int(symbol_id), "side": _SIDES[side]}
    if qty is not None:
      scale = _codec_scale(qty, quantity_scale)
      intent["baseQtyScaled"] = str(
        _grid(
          _QTY_STEP_SIZE,
          "order.base_qty_scaled",
          _resolve_qty_scaled,
          qty,
          scale,
          "qty",
          symbol,
          symbol_id,
        )
      )
    else:
      field = "max_quote_debit" if debit is not None else "quote_proceeds"
      if quote_quantity_scale is None:
        raise _err(
          f"quote quantity scale is required for {field}; await client.wait_for_catalogs() or pass quote_quantity_scale"
        )
      scaled = _resolve_quote_qty_scaled(
        debit if debit is not None else proceeds, quote_quantity_scale, field, symbol, symbol_id
      )
      intent["maxQuoteDebitScaled" if debit is not None else "quoteProceedsScaled"] = str(scaled)
    _put(intent, "clientOrderId", _optional_client_id(request.get("client_order_id")))
    fee_asset = request.get("fee_asset")
    if fee_asset is not None:
      fee_asset = fee_asset.lower()
      if fee_asset not in _FEE_ASSETS:
        raise _err("fee_asset must be quote or base")
      if side == "sell" and fee_asset != "quote":
        raise _err("sell orders must use fee_asset=quote", _FEE_ASSET_NOT_ALLOWED)
      intent["feeAsset"] = _FEE_ASSETS[fee_asset]
    if request.get("self_trade_prevention_mode") is not None:
      intent["selfTradePreventionMode"] = _stp_mode(request["self_trade_prevention_mode"])
    price, price_ticks = request.get("price"), None
    if price is not None:
      execution = {"gtd": "limit_gtd", "ioc": "limit_ioc", "fok": "limit_fok"}.get(tif, "limit_gtc")
      price_ticks = _grid(
        _PRICE_TICK_SIZE,
        f"order.{execution}.price_ticks",
        _resolve_price_ticks,
        price,
        "price",
        symbol,
        True,
      )
    tif = tif or "gtc"
    expires_at = request.get("expires_at")
    _gtd_text(expires_at)
    if expires_at and tif != "gtd":
      raise _err("expires_at is only valid for limit GTD orders")
    display = _display_qty_scaled(request, tif, quantity_scale)
    peg = _static_peg(request.get("peg"))
    if peg is not None:
      if order_type == "market":
        raise _err("peg is only valid for limit orders: a market order cannot carry a peg")
      if debit is not None or proceeds is not None:
        raise _err("peg is only valid with qty: quote sizing (max_quote_debit or quote_proceeds) cannot carry a peg")
      intent["peg"] = peg
    post_only = request.get("post_only")
    slip_ticks, slip_bps = request.get("max_slippage_ticks"), request.get("max_slippage_bps")
    ref_price = request.get("market_client_ref_price")
    if order_type == "market":
      # The only market execution is market_ioc; another tif is refused.
      if request.get("tif") is not None and request["tif"] != "ioc":
        raise _err(f"tif='{request['tif']}' is only valid for limit orders")
      if post_only:
        raise _err("post_only is only valid for limit GTC or GTD orders")
      if price is not None:
        raise _err("price is not valid for market orders; use market_client_ref_price for a reservation reference")
      market = {}
      if ref_price is not None:
        ticks = _resolve_price_ticks(ref_price, "market_client_ref_price", symbol)
        _put(market, "clientRefPriceTicks", str(ticks) if ticks else "")
      if slip_ticks is not None and slip_bps is not None:
        raise _err("market_ioc allows at most one of max_slippage_ticks or max_slippage_bps")
      if slip_ticks is not None:
        market["maxSlippageTicks"] = str(_tick_count(slip_ticks, "max_slippage_ticks"))
      elif slip_bps is not None:
        market["maxSlippageBps"] = _bps(slip_bps, "max_slippage_bps", False, _max_slippage_bps_for_side(side))
      intent["marketIoc"] = market
    else:
      if slip_ticks is not None or slip_bps is not None:
        raise _err("max_slippage_ticks and max_slippage_bps are only valid for market orders")
      if ref_price is not None:
        raise _err("market_client_ref_price is only valid for market orders")
      body = _put({}, "priceTicks", str(price_ticks) if price_ticks is not None else "")
      if tif in ("gtc", "gtd"):
        if tif == "gtd" and not expires_at:
          raise _err("tif='gtd' requires expires_at")
        _put(body, "postOnly", bool(post_only))
        if tif == "gtd":
          body["expireAt"] = _gtd_expire_at(expires_at, now)
        _put(body, "displayQtyScaled", str(display) if display else "")
      elif post_only:
        raise _err("post_only is only valid for limit GTC or GTD orders")
      intent["limit" + tif.capitalize()] = body
    risk = _risk_policy(request.get("attached_risk"), symbol, side)
    if risk is not None:
      if peg is not None:
        raise _err("peg cannot be combined with attached_risk")
      intent["attachedRisk"] = risk
    return intent

  def _display_qty_scaled(request, tif, quantity_scale):
    value = request.get("display_qty")
    if value is None:
      return 0
    if request.get("order_type") != "limit" or tif not in ("gtc", "gtd"):
      raise _err("display_qty is only valid for limit GTC or GTD orders: market, IOC and FOK orders have no display")
    return _resolve_qty_scaled(
      value,
      _codec_scale(value, quantity_scale),
      "display_qty",
      request.get("symbol"),
      request.get("symbol_id"),
    )

  def _static_peg(value):
    if value is None:
      return None
    if not isinstance(value, dict):
      raise _err("peg must be an OrderPeg or a dict")
    _reject_unknown(value, ("reference", "offset_ticks", "offsetTicks"), "peg")
    if "reference" not in value:
      raise _err("peg requires reference ('best_bid' or 'best_ask')")
    reference = value["reference"]
    offset = _first(value, "offset_ticks", "offsetTicks")
    offset = 0 if offset is None else offset
    key = reference.strip().lower() if isinstance(reference, str) else ""
    if key not in _PEG_REFERENCES:
      raise _err(f"peg reference must be 'best_bid' or 'best_ask' (got {reference!r})")
    if isinstance(offset, bool) or not isinstance(offset, int):
      raise _err("peg offset_ticks must be an integer")
    if not _INT64_MIN <= offset <= _INT64_MAX:
      raise _err("peg offset_ticks is outside int64 range")
    return _put({"reference": _PEG_REFERENCES[key]}, "offsetTicks", str(_int(offset)) if offset else "")

  _RISK_POLICY_KEYS = "take_profit takeProfit stop_loss stopLoss trailing_stop trailingStop oco".split()
  _RISK_LEG_KEYS = (
    "trigger_price triggerPrice order_type orderType limit_price limitPrice trigger_price_source "
    "triggerPriceSource trigger_price_ticks triggerPriceTicks child"
  ).split()
  _TRAILING_STOP_KEYS = (
    "trailing_distance_ticks trailingDistanceTicks trailing_distance_bps trailingDistanceBps "
    "distance_ticks distance_bps max_slippage_ticks maxSlippageTicks max_slippage_bps "
    "maxSlippageBps activation_price activationPrice activation_price_ticks activationPriceTicks "
    "limit_price limitPrice limit_price_ticks limitPriceTicks order_type orderType "
    "trigger_price_source triggerPriceSource"
  ).split()

  def _exit_price(value, field, symbol, path, positive=True):
    return _grid(_PRICE_TICK_SIZE, path, _resolve_price_ticks, value, field, symbol, positive)

  def _risk_child_friendly(order_type, limit_price, field, symbol, path, price_code):
    label = str(order_type).strip().lower() if order_type is not None else "market"
    if label in ("market", "market_ioc"):
      if limit_price is not None:
        raise _err(f"{field} MARKET child must not set limit_price")
      return {"marketIoc": {}}
    if label in ("limit", "limit_gtc"):
      if limit_price is None:
        raise _err(f"{field} LIMIT child requires limit_price", price_code)
      ticks = _coded(
        price_code,
        _exit_price,
        limit_price,
        f"{field}.limit_price",
        symbol,
        f"{path}.child.limit_gtc.price_ticks",
      )
      return {"limitGtc": {"priceTicks": str(ticks)}}
    raise _err(f"{field} order_type must be 'market' or 'limit' (got {order_type!r})")

  def _risk_child(child, field, symbol, path, price_code):
    if not isinstance(child, dict):
      raise _err(f"{field}.child must be an object")
    if "execution" in child:
      raise _err(
        f"{field}.child.execution is not a wire field; set child.market_ioc "
        "or child.limit_gtc (limit_ioc and limit_fok are not attached-risk children)"
      )
    _reject_unknown(child, ("market_ioc", "marketIoc", "limit_gtc", "limitGtc"), f"{field}.child")
    has_market = _has(child, "market_ioc", "marketIoc")
    if has_market and _has(child, "limit_gtc", "limitGtc"):
      raise _err(f"{field}.child must set exactly one of market_ioc or limit_gtc")
    if _has(child, "limit_gtc", "limitGtc"):
      limit = _first(child, "limit_gtc", "limitGtc")
      if not isinstance(limit, dict):
        raise _err(f"{field}.child.limit_gtc must be an object")
      _reject_unknown(limit, ("price_ticks", "priceTicks", "price"), f"{field}.child.limit_gtc")
      price, ticks = _first(limit, "price"), _first(limit, "price_ticks", "priceTicks")
      if price is not None and ticks is not None:
        raise _err(f"{field}.child.limit_gtc accepts price or price_ticks, not both")
      if price is not None:
        ticks = _coded(
          price_code,
          _exit_price,
          price,
          f"{field}.child.limit_gtc.price",
          symbol,
          f"{path}.child.limit_gtc.price_ticks",
        )
      elif ticks is not None:
        ticks = _coded(price_code, _tick_count, ticks, f"{field}.child.limit_gtc.price_ticks")
      else:
        raise _err(f"{field} LIMIT child requires limit_price", price_code)
      return {"limitGtc": {"priceTicks": str(ticks)}}
    if has_market:
      market = _first(child, "market_ioc", "marketIoc")
      if market is not None and market != {}:
        if not isinstance(market, dict):
          raise _err(f"{field}.child.market_ioc must be an object")
        raise _err(f"{field}.child.market_ioc does not accept extra fields")
    return {"marketIoc": {}}

  def _risk_leg(data, field, symbol, risk_field, trigger_code, limit_code):
    if not isinstance(data, dict):
      raise _err(f"{field} must be an object")
    _reject_unknown(data, _RISK_LEG_KEYS, field)
    source = _price_source(_first(data, "trigger_price_source", "triggerPriceSource"), f"{field}.trigger_price_source")
    path = f"{risk_field}.{field}"
    trigger_price = _first(data, "trigger_price", "triggerPrice")
    ticks = _first(data, "trigger_price_ticks", "triggerPriceTicks")
    if trigger_price is not None and ticks is not None:
      raise _err(f"{field} accepts trigger_price or trigger_price_ticks, not both")
    if trigger_price is not None:
      ticks = _coded(
        trigger_code,
        _exit_price,
        trigger_price,
        f"{field}.trigger_price",
        symbol,
        f"{path}.trigger_price_ticks",
      )
    elif ticks is not None:
      ticks = _coded(trigger_code, _tick_count, ticks, f"{field}.trigger_price_ticks")
    else:
      raise _err(f"{field} requires trigger_price")
    order_type = _first(data, "order_type", "orderType")
    limit_price = _first(data, "limit_price", "limitPrice")
    child = data.get("child")
    if child is not None and (order_type is not None or limit_price is not None):
      raise _err(f"{field} accepts friendly order_type/limit_price or child, not both")
    if child is not None:
      child = _risk_child(child, field, symbol, path, limit_code)
    else:
      child = _risk_child_friendly(order_type, limit_price, field, symbol, path, limit_code)
    return _put({"triggerPriceTicks": str(ticks), "child": child}, "triggerPriceSource", source)

  def _trailing_limit_error(message, code, rule, risk_field):
    path = f"{risk_field}.trailing_stop.limit_price_ticks"
    return _err(message, code, [_violation(path, rule, message)])

  def _trailing_stop(data, symbol, risk_field):
    field = "attached_risk.trailing_stop"
    if not isinstance(data, dict):
      raise _err(f"{field} must be an object")
    _reject_unknown(data, _TRAILING_STOP_KEYS, field)
    if _has(data, "order_type", "orderType"):
      raise _err(
        "attached trailing_stop takes no order_type: its child is a limit IOC at "
        "limit_price when the order sells, and a market order when it buys"
      )
    dist_ticks = _first(data, "trailing_distance_ticks", "trailingDistanceTicks", "distance_ticks")
    dist_bps = _first(data, "trailing_distance_bps", "trailingDistanceBps", "distance_bps")
    if dist_ticks is None and dist_bps is None:
      raise _err("trailing_stop requires trailing_distance_ticks or trailing_distance_bps")
    if dist_ticks is not None and dist_bps is not None:
      raise _err("trailing_stop requires exactly one of trailing_distance_ticks or trailing_distance_bps")
    stop = _put(
      {},
      "triggerPriceSource",
      _price_source(_first(data, "trigger_price_source", "triggerPriceSource"), f"{field}.trigger_price_source"),
    )
    # A refused value carries the code a standalone trailing stop answers.
    if dist_ticks is not None:
      stop["trailingDistanceTicks"] = str(
        _coded(_TRAILING_DISTANCE_INVALID, _tick_count, dist_ticks, "trailing_distance_ticks")
      )
    else:
      stop["trailingDistanceBps"] = _coded(_TRAILING_DISTANCE_INVALID, _bps, dist_bps, "trailing_distance_bps")
    slip_ticks = _first(data, "max_slippage_ticks", "maxSlippageTicks")
    slip_bps = _first(data, "max_slippage_bps", "maxSlippageBps")
    if slip_ticks is not None and slip_bps is not None:
      raise _err("trailing_stop allows at most one of max_slippage_ticks or max_slippage_bps")
    if slip_ticks is not None:
      stop["maxSlippageTicks"] = str(_coded(_SLIPPAGE_TICKS_INVALID, _tick_count, slip_ticks, "max_slippage_ticks"))
    if slip_bps is not None:
      stop["maxSlippageBps"] = _slippage_bps(slip_bps, _MAX_SELL_BPS)
    activation = _first(data, "activation_price", "activationPrice")
    active = _first(data, "activation_price_ticks", "activationPriceTicks")
    if activation is not None and active is not None:
      raise _err("trailing_stop accepts activation_price or activation_price_ticks, not both")
    if activation is not None:
      active = _coded(
        _ACTIVATION_PRICE_INVALID,
        _exit_price,
        activation,
        f"{field}.activation_price",
        symbol,
        f"{risk_field}.trailing_stop.activation_price_ticks",
      )
    elif active is not None:
      active = _coded(_ACTIVATION_PRICE_INVALID, _tick_count, active, "activation_price_ticks")
    active = active or 0
    _put(stop, "activationPriceTicks", str(active) if active else "")
    # The most a buy-back exit pays per unit; the order's side decides
    # whether it is required.
    limit = _first(data, "limit_price", "limitPrice")
    most = _first(data, "limit_price_ticks", "limitPriceTicks")
    if limit is not None and most is not None:
      raise _err("trailing_stop accepts limit_price or limit_price_ticks, not both")
    if limit is not None:
      most = _exit_price(
        limit,
        f"{field}.limit_price",
        symbol,
        f"{risk_field}.trailing_stop.limit_price_ticks",
        False,
      )
      if most <= 0:
        raise _trailing_limit_error(
          f"{field}.limit_price must be positive", _BUY_REQUIRES_LIMIT, "buy_required", risk_field
        )
    elif most is not None:
      most = _tick_count(most, "limit_price_ticks")
    most = most or 0
    if most and active > most:
      raise _trailing_limit_error(
        f"{field}.limit_price must be at least activation_price",
        _BAD_PRICE,
        "buy_at_least_activation",
        risk_field,
      )
    return _put(stop, "limitPriceTicks", str(most) if most else "")

  def _risk_policy(data, symbol=None, side=None, risk_field="order.attached_risk"):
    if data is None:
      return None
    if not isinstance(data, dict):
      raise _err("attached_risk must be an object or AttachedRisk")
    if not data:
      # Never dropped: the call would succeed and leave the legs as they were.
      # A batch item's refusal names the item (items[i].new_attached_risk).
      message = (risk_field if "[" in risk_field else "attached_risk") + " requires take_profit and/or a stop leg"
      if risk_field.endswith("new_attached_risk"):
        message += "; to remove the order's attached risk, pass clear_attached_risk=True"
      raise _err(message)
    _reject_unknown(data, _RISK_POLICY_KEYS, "attached_risk")
    take_profit = _first(data, "take_profit", "takeProfit")
    stop_loss = _first(data, "stop_loss", "stopLoss")
    trailing = _first(data, "trailing_stop", "trailingStop")
    if stop_loss is not None and trailing is not None:
      raise _err("attached_risk allows at most one of stop_loss or trailing_stop")
    if take_profit is None and stop_loss is None and trailing is None:
      raise _err("attached_risk requires take_profit and/or a stop leg")
    risk = {}
    if "oco" in data:
      oco = data.get("oco")
      if not isinstance(oco, bool):
        raise _err("attached_risk.oco must be a boolean")
      if oco and (take_profit is None or (stop_loss is None and trailing is None)):
        message = "oco requires take_profit and exactly one stop leg (stop_loss or trailing_stop)"
        rule = "risk_policy.oco_requires_tp_and_one_stop"
        raise _err(message, violations=[_violation(risk_field, rule, message)])
      _put(risk, "oco", oco)
    for key, leg in (("take_profit", take_profit), ("stop_loss", stop_loss)):
      if leg is not None:
        risk[_camel(key)] = _risk_leg(leg, key, symbol, risk_field, _TRIGGER_PRICE_INVALID, _BAD_PRICE)
    if trailing is not None:
      stop = _trailing_stop(trailing, symbol, risk_field)
      if side == "sell" and "limitPriceTicks" not in stop:
        raise _trailing_limit_error(
          "attached_risk.trailing_stop.limit_price is required when the order sells: "
          "the trailing stop buys back and pays at most this price",
          _BUY_REQUIRES_LIMIT,
          "buy_required",
          risk_field,
        )
      if side == "buy" and "limitPriceTicks" in stop:
        raise _trailing_limit_error(
          "attached_risk.trailing_stop.limit_price must be unset when the order buys",
          _BAD_PRICE,
          "sell_unset",
          risk_field,
        )
      risk["trailingStop"] = stop
    return risk

  def _replacement_risk(new_attached_risk, clear_attached_risk, symbol, risk_field="new_attached_risk"):
    # risk_field is the path refusals name: the field alone for a modify,
    # under the item's index (items[i].new_attached_risk) for a batch item.
    if not isinstance(clear_attached_risk, bool):
      raise _err("clear_attached_risk must be a bool")
    if clear_attached_risk:
      if new_attached_risk is not None:
        raise _err(f"pass {risk_field} or clear_attached_risk=True, not both")
      return {}
    # No side here: the server applies the trailing stop's side rule.
    return _risk_policy(new_attached_risk, symbol, None, risk_field)

  @_dataclass(frozen=True)
  class OrderId:
    """An exchange-assigned order ID (public base58 string or int)."""

    value: str | int
    _polyester_kind = "order_id"

  @_dataclass(frozen=True)
  class ClientOrderId:
    """A caller-supplied client order ID."""

    value: str
    _polyester_kind = "client_order_id"

  def _require_order_key(key, op):
    if _is(key, "order_id"):
      if key.value is None or (isinstance(key.value, str) and key.value.strip() == ""):
        raise _err(f"{op} requires a non-empty OrderId")
      return key
    if _is(key, "client_order_id"):
      if not str(key.value).strip():
        raise _err(f"{op} requires a non-empty ClientOrderId")
      return key
    raise _err(f"{op} requires an OrderKey (OrderId or ClientOrderId)")

  def _order_key(key, op):
    key = _require_order_key(key, op)
    if _is(key, "order_id"):
      return {"orderId": str(_id_to_int(key.value, "order_id"))}
    return {"clientOrderId": _required_client_id(key.value, "client_order_id")}

  def _non_positive_error(field):
    kept = "price" if field == "new_price" else "quantity"
    return _err(f"{field} must be positive; leave it None to keep the order's {kept}")

  def _refuse_non_positive(value, field):
    if isinstance(value, bool):
      return
    number = value
    if isinstance(value, str):
      try:
        number = _Decimal(value.strip())
      except _InvalidOperation:
        return
    if not isinstance(number, (int, float, _Decimal)):
      return
    try:
      non_positive = number <= 0
    except _InvalidOperation:  # Decimal NaN
      return
    if non_positive:
      raise _non_positive_error(field)

  def _positive(resolved, field):
    if resolved <= 0:
      raise _non_positive_error(field)
    return resolved

  def _new_price_ticks(value, symbol):
    _refuse_non_positive(value, "new_price")
    ticks = _grid(_PRICE_TICK_SIZE, "new_price_ticks", _resolve_price_ticks, value, "new_price", symbol)
    return _positive(ticks, "new_price")

  def _new_qty_scaled(value, quantity_scale, symbol, symbol_id):
    _refuse_non_positive(value, "new_qty")
    scale = _codec_scale(value, quantity_scale)
    scaled = _grid(
      _QTY_STEP_SIZE,
      "new_qty_scaled",
      _resolve_qty_scaled,
      value,
      scale,
      "new_qty",
      symbol,
      symbol_id,
    )
    return _positive(scaled, "new_qty")

  def _modify_order(
    symbol,
    symbol_id,
    key,
    sub_account_id=None,
    request_id=None,
    new_price=None,
    new_qty=None,
    new_attached_risk=None,
    behavior=None,
    new_client_order_id=None,
    quantity_scale=None,
    clear_attached_risk=False,
  ):
    if new_price is None and new_qty is None and new_attached_risk is None and clear_attached_risk is False:
      raise _err("modify requires new_price, new_qty, new_attached_risk, and/or clear_attached_risk")
    risk = _replacement_risk(new_attached_risk, clear_attached_risk, symbol)
    if symbol_id <= 0:
      raise _err("modify requires a resolved symbol_id")
    request = _put({}, "requestId", _optional_request_id(request_id))
    request["symbolId"] = int(symbol_id)
    request.update(_order_key(key, "modify"))
    _account(request, sub_account_id)
    if new_price is not None:
      request["newPriceTicks"] = str(_new_price_ticks(new_price, symbol))
    if new_qty is not None:
      request["newQtyScaled"] = str(_new_qty_scaled(new_qty, quantity_scale, symbol, symbol_id))
    if behavior:
      name = behavior.lower()
      if name not in _MODIFY_BEHAVIORS:
        raise _err("behavior must be amend_or_replace, amend_only, or replace_only")
      request["behavior"] = _MODIFY_BEHAVIORS[name]
    if new_client_order_id:
      request["newClientOrderId"] = _required_client_id(new_client_order_id, "new_client_order_id")
    if risk is not None:
      request["newAttachedRisk"] = risk
    return request

  def _trigger_type_key(trigger_type):
    key = trigger_type.lower().replace("-", "_") if isinstance(trigger_type, str) else ""
    if key not in _TRIGGER_TYPES:
      raise _err("trigger_type must be stop_loss, take_profit, trailing_stop, twap, or ladder")
    return key

  def _market_slippage(slip_ticks, slip_bps, max_bps):
    market = {}
    if slip_ticks is not None:
      market["maxSlippageTicks"] = str(_coded(_SLIPPAGE_TICKS_INVALID, _tick_count, slip_ticks, "max_slippage_ticks"))
    elif slip_bps is not None:
      market["maxSlippageBps"] = _slippage_bps(slip_bps, max_bps)
    return market

  def _child_price(limit_price, symbol):
    ticks = _coded(_BAD_PRICE, _resolve_price_ticks, limit_price, "limit_price", symbol, True)
    return {"priceTicks": str(ticks)}

  def _conditional_child(side, order_type, tif, limit_price, post_only, symbol, slip_ticks, slip_bps):
    if order_type == "market":
      if post_only:
        raise _err("post_only is only valid for limit GTC executions")
      if slip_ticks is not None and slip_bps is not None:
        raise _err("a market child allows at most one of max_slippage_ticks or max_slippage_bps")
      return {"marketIoc": _market_slippage(slip_ticks, slip_bps, _max_slippage_bps_for_side(side))}
    if slip_ticks is not None or slip_bps is not None:
      raise _err(
        "max_slippage_ticks and max_slippage_bps apply to a market child only; "
        "a limit child is capped by its limit price"
      )
    body = _child_price(limit_price, symbol) if limit_price is not None else {}
    tif = tif.lower()
    if tif not in ("gtc", "ioc", "fok"):
      raise _err("tif must be one of 'gtc', 'ioc', or 'fok'")
    if post_only:
      if tif != "gtc":
        raise _err("post_only is only valid for limit GTC executions")
      body["postOnly"] = True
    return {"limit" + tif.capitalize(): body}

  def _trigger_request(
    symbol,
    symbol_id,
    trigger_type,
    side,
    qty,
    quantity_scale,
    trigger_price=None,
    order_type=None,
    limit_price=None,
    trigger_price_source=None,
    tif=None,
    sub_account_id=None,
    client_trigger_id=None,
    post_only=False,
    fee_asset=None,
    self_trade_prevention_mode=None,
    trailing_distance_ticks=None,
    trailing_distance_bps=None,
    activation_price=None,
    max_slippage_ticks=None,
    max_slippage_bps=None,
    twap_duration_ms=None,
    twap_slice_interval_ms=None,
    ladder_price_min=None,
    ladder_price_max=None,
    ladder_levels=None,
    ladder_distribution=None,
  ):
    if symbol_id <= 0:
      raise _err("create trigger requires a resolved symbol_id")
    kind = _trigger_type_key(trigger_type)
    side = side.lower()
    if side not in ("buy", "sell"):
      raise _err("side must be buy or sell")
    if order_type is not None and not isinstance(order_type, str):
      raise _err("order_type must be limit or market")
    if kind == "ladder":
      # A ladder places limit GTC orders only: any other type is refused.
      if order_type is not None and order_type.lower() != "limit":
        raise _err(
          f"order_type={order_type!r} does not apply to a ladder: a ladder places "
          "limit GTC orders only; pass order_type='limit' or leave it out"
        )
      child_type = "limit"
    else:
      # Left out, a stop, trailing stop or TWAP child is a market order.
      child_type = (order_type if order_type is not None else "market").lower()
    if child_type not in ("limit", "market"):
      raise _err("order_type must be limit or market")
    # Another strategy's option never disappears silently, a 0 included.
    for option, value, supported in (
      ("trailing_distance_ticks", trailing_distance_ticks, ("trailing_stop",)),
      ("trailing_distance_bps", trailing_distance_bps, ("trailing_stop",)),
      ("activation_price", activation_price, ("trailing_stop",)),
      ("twap_duration_ms", twap_duration_ms, ("twap",)),
      ("twap_slice_interval_ms", twap_slice_interval_ms, ("twap",)),
      ("ladder_price_min", ladder_price_min, ("ladder",)),
      ("ladder_price_max", ladder_price_max, ("ladder",)),
      ("ladder_levels", ladder_levels, ("ladder",)),
      ("ladder_distribution", ladder_distribution, ("ladder",)),
      ("trigger_price", trigger_price, ("stop_loss", "take_profit")),
    ):
      if value is not None and kind not in supported:
        raise _err(f"{option} applies only to {' or '.join(supported)}")
    if post_only and kind in ("trailing_stop", "twap"):
      raise _err("post_only applies only to limit GTC stops or ladder")
    if limit_price is not None and (kind == "ladder" or (kind != "trailing_stop" and child_type == "market")):
      raise _err("limit_price applies only to limit children or a buy trailing_stop")
    sliced = kind == "ladder" or (kind == "twap" and child_type == "limit")
    if sliced and (max_slippage_ticks is not None or max_slippage_bps is not None):
      raise _err("max_slippage_ticks and max_slippage_bps apply only to market children or trailing_stop")
    if tif is not None and (not isinstance(tif, str) or tif.lower() not in ("gtc", "ioc", "fok")):
      raise _err("tif must be one of 'gtc', 'ioc', or 'fok'")
    tif = tif.lower() if tif is not None else None
    # A market child and a trailing stop execute IOC: they take ioc or no tif.
    if sliced:
      if tif not in (None, "gtc"):
        raise _err("tif must be gtc for ladder or twap limit slices")
    elif (kind == "trailing_stop" or child_type == "market") and tif not in (None, "ioc"):
      raise _err(f"tif={tif} applies only to limit children: a market child or a trailing_stop executes IOC")
    if kind == "trailing_stop" and side == "sell" and child_type == "limit":
      raise _err("order_type=limit applies only to buy trailing_stop children")
    wire_side = _SIDES[side]
    qty_scaled = _coded(_TRIGGER_QTY_INVALID, _resolve_qty_scaled, qty, quantity_scale, "qty", symbol, symbol_id)
    intent = {"symbolId": symbol_id, "qtyScaled": str(qty_scaled)}
    if client_trigger_id is not None:
      intent["clientTriggerId"] = _client_trigger_id(client_trigger_id)
    if fee_asset is not None:
      fee = fee_asset.lower()
      if fee not in _FEE_ASSETS:
        raise _err("fee_asset must be quote or base")
      if side == "sell" and fee != "quote":
        raise _err("a sell trigger must use fee_asset=quote", _FEE_ASSET_NOT_ALLOWED)
      intent["feeAsset"] = _FEE_ASSETS[fee]
    if self_trade_prevention_mode is not None:
      intent["selfTradePreventionMode"] = _stp_mode(self_trade_prevention_mode)
    source = _price_source(trigger_price_source)
    if source and kind in ("twap", "ladder"):
      raise _err("trigger_price_source applies to stop_loss, take_profit and trailing_stop only")
    if kind in ("stop_loss", "take_profit"):
      # Left out, it is 0 on the wire, which the contract refuses.
      if trigger_price is None:
        raise _err(f"trigger_price is required for a {kind}", _TRIGGER_PRICE_INVALID)
      ticks = _coded(_TRIGGER_PRICE_INVALID, _resolve_price_ticks, trigger_price, "trigger_price", symbol, True)
      strategy = {"triggerPriceTicks": str(ticks), "side": wire_side}
      strategy["child"] = _conditional_child(
        side,
        child_type,
        tif or "gtc",
        limit_price,
        post_only,
        symbol,
        max_slippage_ticks,
        max_slippage_bps,
      )
      _put(strategy, "triggerPriceSource", source)
    elif kind == "trailing_stop":
      strategy = _put({"side": wire_side}, "triggerPriceSource", source)
      _trailing_trigger(
        strategy,
        side,
        symbol,
        limit_price,
        trailing_distance_ticks,
        trailing_distance_bps,
        activation_price,
        max_slippage_ticks,
        max_slippage_bps,
      )
    elif kind == "twap":
      strategy = _twap(
        wire_side,
        side,
        child_type,
        symbol,
        limit_price,
        twap_duration_ms,
        twap_slice_interval_ms,
        max_slippage_ticks,
        max_slippage_bps,
      )
    else:
      strategy = _ladder(
        wire_side,
        symbol,
        ladder_price_min,
        ladder_price_max,
        ladder_levels,
        ladder_distribution,
        post_only,
      )
    intent[_camel(kind)] = strategy
    request = {"trigger": intent}
    _account(request, sub_account_id)
    return request

  def _trailing_trigger(stop, side, symbol, limit_price, dist_ticks, dist_bps, activation, slip_ticks, slip_bps):
    # A buy trailing stop needs its maximum price, the most its child pays
    # per unit; a sell one takes none.
    most = 0
    if side == "buy":
      if limit_price is None:
        raise _err("trailing_stop with side=buy requires limit_price (the maximum price)")
      most = _coded(_BAD_PRICE, _resolve_price_ticks, limit_price, "limit_price", symbol)
      if most <= 0:
        raise _err(
          "trailing_stop with side=buy: limit_price must be positive (the maximum price)",
          _BAD_PRICE,
        )
      stop["limitPriceTicks"] = str(most)
    elif limit_price is not None:
      raise _err("trailing_stop with side=sell does not take limit_price; the maximum price applies to buys only")
    if dist_ticks is not None and dist_bps is not None:
      raise _err("set at most one of trailing_distance_ticks or trailing_distance_bps")
    if slip_ticks is not None and slip_bps is not None:
      raise _err("set at most one of max_slippage_ticks or max_slippage_bps")
    if dist_ticks is not None:
      stop["trailingDistanceTicks"] = str(
        _coded(_TRAILING_DISTANCE_INVALID, _tick_count, dist_ticks, "trailing_distance_ticks")
      )
    if dist_bps is not None:
      stop["trailingDistanceBps"] = _coded(_TRAILING_DISTANCE_INVALID, _bps, dist_bps, "trailing_distance_bps")
    if activation is not None:
      active = _coded(
        _ACTIVATION_PRICE_INVALID,
        _resolve_price_ticks,
        activation,
        "activation_price",
        symbol,
        True,
      )
      stop["activationPriceTicks"] = str(active)
      if side == "buy" and most < active:
        raise _err("trailing_stop with side=buy requires limit_price at least activation_price")
    stop.update(_market_slippage(slip_ticks, None, _MAX_SELL_BPS))
    if slip_bps is not None:
      stop["maxSlippageBps"] = _slippage_bps(slip_bps, _MAX_SELL_BPS)

  def _twap(wire_side, side, child_type, symbol, limit_price, duration, interval, slip_ticks, slip_bps):
    # Left out, either is 0 on the wire, which the contract refuses.
    if duration is None:
      raise _err("twap_duration_ms is required for a twap", _TWAP_DURATION_INVALID)
    if interval is None:
      raise _err("twap_slice_interval_ms is required for a twap", _TWAP_INTERVAL_INVALID)
    duration = _coded(_TWAP_DURATION_INVALID, _exact_integer, duration, "twap_duration_ms", *_TWAP_DURATION_MS)
    interval = _coded(
      _TWAP_INTERVAL_INVALID,
      _exact_integer,
      interval,
      "twap_slice_interval_ms",
      *_TWAP_SLICE_INTERVAL_MS,
    )
    if interval > duration:
      raise _err("twap_slice_interval_ms must not exceed twap_duration_ms", _TWAP_INTERVAL_INVALID)
    twap = {"side": wire_side, "durationMs": str(duration), "sliceIntervalMs": str(interval)}
    if child_type == "limit":
      twap["limitGtc"] = _child_price(limit_price, symbol) if limit_price is not None else {}
      return twap
    if slip_ticks is not None and slip_bps is not None:
      raise _err("twap market_ioc allows at most one of max_slippage_ticks or max_slippage_bps")
    twap["marketIoc"] = _market_slippage(slip_ticks, slip_bps, _max_slippage_bps_for_side(side))
    return twap

  def _ladder(wire_side, symbol, price_min, price_max, levels, distribution, post_only):
    if distribution is not None and distribution.lower() != "linear":
      raise _err("ladder_distribution must be linear")
    bounds = []
    for name, price in (("ladder_price_min", price_min), ("ladder_price_max", price_max)):
      bounds.append(
        None if price is None else _coded(_TRIGGER_PRICE_INVALID, _resolve_price_ticks, price, name, symbol, True)
      )
    low, high = bounds
    # Both are required: a bound left out is 0 on the wire.
    if low is None or high is None:
      missing = "ladder_price_min" if low is None else "ladder_price_max"
      raise _err(f"{missing} is required for a ladder", _TRIGGER_PRICE_INVALID)
    if low >= high:
      raise _err("ladder_price_min must be strictly less than ladder_price_max", _TRIGGER_PRICE_INVALID)
    if levels is None:
      raise _err("ladder_levels is required for a ladder", _LADDER_LEVELS_INVALID)
    levels = _coded(_LADDER_LEVELS_INVALID, _exact_integer, levels, "ladder_levels", *_LADDER_LEVELS)
    ladder = {
      "side": wire_side,
      "priceMinTicks": str(low),
      "priceMaxTicks": str(high),
      "levels": levels,
    }
    return _put(ladder, "postOnly", bool(post_only))

  def _modify_trigger(
    trigger_id,
    symbol_id=0,
    symbol=None,
    sub_account_id=None,
    trigger_price=None,
    trailing_distance_ticks=None,
    trailing_distance_bps=None,
    activation_price=None,
    max_slippage_ticks=None,
    max_slippage_bps=None,
  ):
    patch = (
      trigger_price,
      trailing_distance_ticks,
      trailing_distance_bps,
      activation_price,
      max_slippage_ticks,
      max_slippage_bps,
    )
    if all([value is None for value in patch]):
      raise _err(
        "modify requires at least one of trigger_price, trailing_distance_ticks, "
        "trailing_distance_bps, activation_price, max_slippage_ticks, or "
        "max_slippage_bps",
        _TRIGGER_PATCH_EMPTY,
      )
    if symbol_id < 0:
      raise _err("modify trigger symbol_id must not be negative")
    if trailing_distance_ticks is not None and trailing_distance_bps is not None:
      raise _err("set at most one of trailing_distance_ticks or trailing_distance_bps")
    if max_slippage_ticks is not None and max_slippage_bps is not None:
      raise _err("set at most one of max_slippage_ticks or max_slippage_bps")
    request = _put({"triggerId": str(_id_to_int(trigger_id, "trigger_id"))}, "symbolId", int(symbol_id))
    _account(request, sub_account_id)
    if trigger_price is not None:
      request["triggerPriceTicks"] = str(
        _coded(_TRIGGER_PRICE_INVALID, _resolve_price_ticks, trigger_price, "trigger_price", symbol, True)
      )
    if trailing_distance_ticks is not None:
      request["trailingDistanceTicks"] = str(
        _coded(
          _TRAILING_DISTANCE_INVALID,
          _tick_count,
          trailing_distance_ticks,
          "trailing_distance_ticks",
        )
      )
    if trailing_distance_bps is not None:
      # 1 to 10000, as at create: the contract has no clearing zero.
      request["trailingDistanceBps"] = _coded(
        _TRAILING_DISTANCE_INVALID, _bps, trailing_distance_bps, "trailing_distance_bps"
      )
    if activation_price is not None:
      request["activationPriceTicks"] = str(
        _coded(
          _ACTIVATION_PRICE_INVALID,
          _resolve_price_ticks,
          activation_price,
          "activation_price",
          symbol,
        )
      )
    if max_slippage_ticks is not None:
      request["maxSlippageTicks"] = str(
        _coded(_SLIPPAGE_TICKS_INVALID, _tick_count, max_slippage_ticks, "max_slippage_ticks", True)
      )
    if max_slippage_bps is not None:
      request["maxSlippageBps"] = _slippage_bps(max_slippage_bps, _MAX_BPS, True)
    return request

  def _oco_request(
    symbol,
    symbol_id,
    side,
    qty,
    take_profit,
    stop_loss,
    quantity_scale,
    client_list_id=None,
    self_trade_prevention_mode=None,
    sub_account_id=None,
  ):
    if symbol_id <= 0:
      raise _err("create OCO requires a resolved symbol_id")
    side = side.lower() if isinstance(side, str) else ""
    if side not in ("buy", "sell"):
      raise _err("side must be buy or sell")
    qty_scaled = _coded(_TRIGGER_QTY_INVALID, _resolve_qty_scaled, qty, quantity_scale, "qty", symbol, symbol_id)
    intent = {"symbolId": symbol_id, "side": _SIDES[side], "qtyScaled": str(qty_scaled)}
    if client_list_id is not None:
      intent["clientListId"] = _client_list_id(client_list_id)
    if self_trade_prevention_mode is not None:
      mode = _stp_mode(self_trade_prevention_mode)
      if mode == "DECREMENT":
        raise _err(
          "self_trade_prevention_mode of an OCO must be expire_taker, expire_maker "
          "or expire_both; decrement is not supported on an OCO"
        )
      intent["selfTradePreventionMode"] = mode
    for key, leg in (("take_profit", take_profit), ("stop_loss", stop_loss)):
      intent[_camel(key)] = _risk_leg(leg, key, symbol, "oco", _TRIGGER_PRICE_INVALID, _BAD_PRICE)
    request = {"oco": intent}
    _account(request, sub_account_id)
    return request

  def _orders_create(market, now=None, **kwargs):
    """CreateOrderRequest proto-JSON for ``orders.create``'s arguments."""
    pair = _market(market)
    _host_owned(sub_account_id=kwargs.get("sub_account_id"), client_order_id=kwargs.get("client_order_id"))
    if isinstance(kwargs.get("expires_at"), _timedelta):
      kwargs["expires_at"] = _rfc3339(_aware(now, "now").astimezone(_UTC) + kwargs["expires_at"])
    request = _normalize_create(kwargs)
    symbol, symbol_id = request["symbol"], request["symbol_id"]
    resolved = _symbol_id_for(pair, symbol, symbol_id, "orders.create")
    if resolved != pair.symbol_id:
      raise _err(f"orders.create quantity scale is unavailable for symbol_id {resolved}; hydrate catalogs")
    if symbol is not None and symbol != pair.symbol:
      raise _err(f"orders.create symbol mismatch: {symbol!r} does not match symbol_id {resolved} ({pair.symbol})")
    scale = _value_scale(pair.base_quantity_scale, request["qty"], request["display_qty"])
    quote = _quote_value_scale(pair.quote_quantity_scale, request["max_quote_debit"], request["quote_proceeds"])
    request["symbol"], request["symbol_id"] = pair.symbol, resolved
    return {"order": _order_intent(request, scale, quote, now)}

  def _orders_modify(
    market,
    *,
    key,
    symbol=None,
    new_qty=None,
    sub_account_id=None,
    request_id=None,
    new_client_order_id=None,
    **changes,
  ):
    """ModifyOrderRequest proto-JSON for ``orders.modify``'s arguments."""
    pair = _market(market)
    _host_owned(sub_account_id=sub_account_id, request_id=request_id, new_client_order_id=new_client_order_id)
    symbol_id = _symbol_id_for(pair, symbol, None, "orders.modify")
    scale = _value_scale(pair.base_quantity_scale, new_qty)
    return _modify_order(pair.symbol, symbol_id, key, new_qty=new_qty, quantity_scale=scale, **changes)

  def _cancel_order(key, symbol_id=None, sub_account_id=None):
    request = _order_key(key, "cancel")
    if symbol_id is not None:
      _put(request, "symbolId", _market_id(symbol_id, "cancel symbol_id"))
    _account(request, sub_account_id)
    return request

  def _cancel_trigger(trigger_id, sub_account_id=None):
    request = {"triggerId": str(_id_to_int(trigger_id, "trigger_id"))}
    _account(request, sub_account_id)
    return request

  def _orders_cancel(market=None, *, key, symbol=None, symbol_id=None, sub_account_id=None):
    """CancelOrderRequest proto-JSON; with a market, ``symbolId`` names it."""
    _host_owned(sub_account_id=sub_account_id)
    if symbol is not None and symbol_id is not None:
      raise _err("cancel accepts only one of symbol or symbol_id")
    pair = None if market is None else _market(market)
    if symbol is not None:
      symbol_id = _resolve_symbol_id(symbol, None, "cancel", pair and _lookup(pair))
    elif symbol_id is None and pair is not None:
      symbol_id = pair.symbol_id
    return _cancel_order(key, symbol_id)

  def _triggers_create(
    market,
    *,
    trigger_type,
    side,
    qty,
    symbol=None,
    sub_account_id=None,
    client_trigger_id=None,
    **options,
  ):
    """CreateTriggerRequest proto-JSON for ``triggers.create``'s keyword
    arguments; the host fills ``clientTriggerId``."""
    pair = _market(market)
    _host_owned(sub_account_id=sub_account_id, client_trigger_id=client_trigger_id)
    symbol = pair.symbol if symbol is None else symbol
    symbol_id = _symbol_id_for(pair, symbol, None, "triggers.create")
    return _trigger_request(
      symbol,
      symbol_id,
      trigger_type,
      side,
      qty,
      _value_scale(pair.base_quantity_scale, qty),
      **options,
    )

  def _triggers_create_oco(
    market,
    *,
    side,
    qty,
    take_profit,
    stop_loss,
    symbol=None,
    self_trade_prevention_mode=None,
    sub_account_id=None,
    client_list_id=None,
  ):
    """CreateOcoRequest proto-JSON; the host fills ``clientListId``."""
    pair = _market(market)
    _host_owned(sub_account_id=sub_account_id, client_list_id=client_list_id)
    symbol = pair.symbol if symbol is None else symbol
    symbol_id = _symbol_id_for(pair, symbol, None, "triggers.create_oco")
    return _oco_request(
      symbol,
      symbol_id,
      side,
      qty,
      take_profit,
      stop_loss,
      _value_scale(pair.base_quantity_scale, qty),
      self_trade_prevention_mode=self_trade_prevention_mode,
    )

  def _triggers_cancel(market=None, *, trigger_id, sub_account_id=None):
    """CancelTriggerRequest proto-JSON; the request names no market."""
    _host_owned(sub_account_id=sub_account_id)
    if market is not None:
      _market(market)
    return _cancel_trigger(trigger_id)

  def _triggers_modify(market=None, *, trigger_id, symbol=None, symbol_id=None, sub_account_id=None, **patch):
    """ModifyTriggerRequest proto-JSON. ``symbolId`` names the market given, or
    ``symbol`` / ``symbol_id``; with neither the trigger's own market applies.
    A Price bound to another market is refused."""
    _host_owned(sub_account_id=sub_account_id)
    pair = None if market is None else _market(market)
    lookup = None if pair is None else _lookup(pair)
    if pair is not None and symbol is None and symbol_id is None:
      resolved = pair.symbol_id
    else:
      resolved = _control_symbol_id(symbol, symbol_id, "triggers.modify", lookup)
    prices = (patch.get("trigger_price"), patch.get("activation_price"))
    name = _bound_market(resolved, prices, lookup, "triggers.modify")
    return _modify_trigger(trigger_id, resolved, name, **patch)

  class _Orders:
    create = _orders_create
    modify = _orders_modify
    cancel = _orders_cancel

  class _Triggers:
    create = _triggers_create
    create_oco = _triggers_create_oco
    cancel = _triggers_cancel
    modify = _triggers_modify

  _types = (Price, Quantity, OrderId, ClientOrderId, Market)
  _scope = locals()

  class _Namespace:
    """The public namespace: builders named as the SDK's, and its types."""

    # Every rule, for the Python SDK, which builds its requests with them.
    _sdk = _scope
    VERSION = _VERSION
    ValidationError = ValueError
    Price = _types[0]
    Quantity = _types[1]
    OrderId = _types[2]
    ClientOrderId = _types[3]
    Market = _types[4]
    market = _market
    orders = _Orders
    triggers = _Triggers

  return _Namespace


polyester = polyester()
