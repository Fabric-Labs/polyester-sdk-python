# Changelog

## Unreleased

- A resubscribe on a confirmed private order stream that the server never answers no longer waits forever: after 30 seconds it reports `PrivateOrdersError(kind="subscribe")` and subscribes again with backoff.
- `Polyester.close()` now closes every subscription and the client even when a subscription failed with no `on_error`, then raises the first such failure.
- **Breaking:** A realtime subscription the server ends no longer stays open and silent. Its iterator yields what is queued, then raises the new `PolyesterSubscriptionEndedError` (a `PolyesterRealtimeError`), also reported through `error` and the error callback, with the channel, the server's code and text, and `reason`. Managed order books and market overviews finish their iterator and report it through `last_error` and `on_error`. Migration: handle the error; subscribe again if you still need the stream. Server unsubscribe codes from 2500 ask for a new subscribe and reconnect as before.
- A sub-account's balances, transfers, trades, triggers and lifecycle subscriptions now resume after a server unsubscribe while `ListSubaccounts` lists the sub-account with a role, using a fresh token and reporting the gap through `take_resubscribed()`. They stop with the reason after a `removed` update on this client, when not listed, when the list or token is refused, or after 6 attempts. List reads and attempts are paced across the client.
- Managed order books request an unavailable snapshot again, after 1 s doubling to 8 s, until it is available or the subscription stops. Repeated unavailable answers add no view. A market that stays unavailable keeps being requested once every 8 s. A failed request ends the subscription like a failed sequence-gap refresh.
- **Breaking:** `triggers.create` raises `PolyesterValidationError` for a blank `client_trigger_id` before sending. Migrate by passing a real ID or leaving it out.
- **Breaking:** A ledger refusal carrying `ledger.read.v1.ErrorDetail` now reports `PolyesterApiError` with its specific code, such as `ERROR_CODE_INVALID_SUBACCOUNT_ID` (11), instead of code `invalid_argument`. Migrate by branching on the specific code.
- **Breaking:** A JSON error body with malformed `message` or `details`, with or without a Connect code, now reports by its HTTP status: a `PolyesterAuthError` at 401 or 403, and otherwise a `PolyesterServerError` with outcome unknown and a message such as `400 Bad Request`, instead of a raw `AttributeError` or a server error carrying Python exception text. Migrate by catching SDK errors. Undecodable detail bytes keep the Connect code instead of raising `DecodeError`.
- Trigger reads return a REST 429 refusal and a 503 `ACCOUNT_ROUTING_INVALID` on the first request with their typed reason, instead of retrying them for two seconds. Real unavailability keeps its bounded retry.
- `triggers.create` without a `client_trigger_id` generates one, as the contract requires an ID and Go already does, instead of sending none.
- An empty `default_sub_account_id` now means no scope on every path, instead of raising `PolyesterValidationError` on `orders.batch_replace`, `orders.modify`, `triggers.create` and other writes.
- `sign_request` signs the decoded URL path, as the server verifies it, including percent-escapes that are not UTF-8. A path with percent-escapes no longer gets `401 SIGNATURE_INVALID`. The shared signing vectors now cover escaped paths.
- **Breaking:** Bare REST `UNAVAILABLE` cannot establish an orders-service refusal: report outcome unknown and non-retryable. Only a typed `orders.v1.ErrorDetail` carrying `UNAVAILABLE` establishes a known, retryable refusal. Migration: read back after an unknown outcome; retry reads explicitly.
- **Breaking:** The additional retry-later resource codes `CLIENT_ORDER_IDS_EXHAUSTED`, `CLIENT_ORDER_ID_CAPACITY_REACHED`, `MARKET_LADDER_LIMIT_EXCEEDED`, `MARKET_TRIGGER_LIMIT_EXCEEDED`, `MARKET_TWAP_LIMIT_EXCEEDED`, `NEW_ACCOUNT_CAPACITY_REACHED`, `REQUEST_RECEIPTS_EXHAUSTED`, `RESERVATION_CAPACITY_REACHED`, `TRIGGER_CAPACITY_REACHED`, `TRIGGER_CONTROL_SHARE_EXHAUSTED`, `TWAP_CAPACITY_REACHED` report outcome known and retryable, preserving any server retry delay.
- **Breaking:** Retry-After headers on Connect resource refusals are retained alongside typed retry details.
- **Breaking:** Unknown mutation outcomes are never retryable, including bare Connect unavailable/internal/deadline failures, gateway 502/503 responses, bare or HTML 429 responses and client timeouts. Migration: read back after an unknown outcome; retry reads explicitly. Bounded trigger reads, status waits and snapshot recovery use read context; creates are never automatically resent.
- **Breaking:** Structured order-service admission refusals now report outcome known while remaining retryable. This corrects the previous outcome-unknown result for typed `orders.v1.ErrorDetail` codes `UNAVAILABLE`, `FEE_SCHEDULE_UNAVAILABLE`, `POLICY_UNAVAILABLE`, `RATE_LIMIT_POLICY_UNAVAILABLE` and other documented temporary admission refusals. Specific code-only Connect messages now preserve their refusal code. `QUICKSWAP_ACCOUNT_OWNER_UNKNOWN` is known and retryable; `ACCOUNT_ROUTING_INVALID` is known and non-retryable. Unrecognized dependency failures remain ambiguous.
- **Breaking:** REST validation refusals retain their service codes with outcome known and no retry, while timestamp skew retains its explicit safe-retry guidance. REST and typed `ACCOUNT_REPAIRING` now become retryable with outcome known. REST `RATE_LIMIT_EXCEEDED` and `PRICE_LEVELS_EXHAUSTED` are known admission refusals with retry delays preserved. All REST, typed Connect and message-only resource codes now follow their contract retry guidance; outcome-unknown codes and details take precedence over standalone backoff details.
- **Breaking:** Order create and preview now refuse an account selector combined with a subaccount override instead of replacing the override with the configured default. Migration: pass either `account` or `sub_account_id`, including when supplying a request object.
- **Breaking:** Batch-create items now refuse any subaccount override instead of silently using the batch scope. Migration: remove each item's `sub_account_id` and pass the batch-level `sub_account_id`.
- **Breaking:** Batch-cancel items, batch-replace items and batch guard-signing actions now refuse a subaccount or account key instead of silently using the batch scope. Migration: remove the key and pass the batch-level `sub_account_id`.
- **Breaking:** A whitespace-only ID, including a subaccount override, now fails validation instead of encoding as zero. Migration: pass a real ID, or `""` to omit the subaccount.
- Explicit empty order overrides continue to omit the subaccount field; omitted overrides and `account="main"` retain their existing routing.

- **Breaking:** Transfers and withdrawals now reject integer `AssetAmount` inputs with no source scale or conflicting scale declarations. Migration: set the amount's `scale` or pass `quantity_scale` / `amount_scale`, and keep both declarations equal when supplying both.
- **Breaking:** A live order-book delta with a zero or missing price and positive quantity now closes the managed stream with an invalid-price error at every bucket and depth, including when the row would sort outside the requested depth; `bucket_side` and `side_to_levels` refuse it too. Migration: handle the stream error and resubscribe.
- **Breaking:** `subscribe_sync` with no `on_error` now waits for setup, raises a setup failure from the call and returns no handle. Migration: catch the exception at the call, or pass `on_error` to receive it there.
- **Breaking:** Realtime setup now fails after 30 seconds when the server keeps the connection alive but never confirms: a new private order subscription raises `PolyesterRealtimeError`, and a handshake reply raises `TimeoutError`. Migration: catch the error and subscribe again.
- Managed order books now display a zero bid bucket when a coarse bucket exceeds the market price, preserving bid floor and ask ceiling rounding. Zero-quantity removals at price zero stay harmless.
- Synchronous subscriptions with `on_error` now deliver setup failures to it once, like iteration failures, and closing the handle no longer raises them.

- **Breaking:** A plain REST gateway 504 is now non-retryable with mutation outcome unknown. Reads may retry a 504 explicitly; writes read back first. A client order ID enables reconciliation, not exact replay of a single create. Automatic read retries remain operation-specific; creates are never automatically resent.
- **Breaking:** `OVERLOADED` and `SYSTEM_RATE_LIMITED` now return `PolyesterRateLimitError` instead of API/server errors on Connect and REST. They are retryable admission refusals with no unknown mutation outcome. The new `code` field retains the service code; known order codes use the `ERROR_CODE_` prefix. `ORDER_SEQUENCE_EXHAUSTED` remains a permanent refusal, including REST 429 and Connect responses without typed details. Supplied retry delays are preserved.
- **Breaking:** A Connect message naming an `*_OUTCOME_UNKNOWN` code now classifies as non-retryable with outcome unknown, including codes introduced by a newer server. Known order names are normalized to `ERROR_CODE_…`; future names remain as sent.
- **Breaking:** Connect auth refusals now populate `code` and `status_code`, including transfer/withdrawal service details and refusals without typed details.

## 0.7.1

Git tag: `v0.7.1`. Released 2026-11-06. Built on public contract `748066a`.

- Managed market overview streams finish after terminal failure, report the error, and let callers drain queued rows. Closing with a full consumer queue no longer blocks.
- Order books detect gaps after a sequence-zero snapshot and refetch before applying later deltas.
- A full managed order book queue shuts down cleanly, preserves its error, and releases the connection. Startup failures report the error callback once.
- Unknown market selectors report that catalog hydration is needed instead of a false name/ID conflict.
- Realtime subscriptions preserve publications sent alongside or before the subscribe reply.
- Managed order books finish their update stream after terminal failure and reject conflicting market name and ID selectors before connecting.

## 0.7.0

Git tag: `v0.7.0`. Released 2026-11-06. Built on public contract `748066a`.

- **Breaking:** trigger creation now refuses an invalid `tif`, including an
  empty string, on every path, and an order write with a scaled `Quantity`
  refuses an empty `symbol` sent with a valid symbol ID.
- **Breaking:** Order writes now require the destination pair's catalog quantity scale, including
  requests by symbol ID. An explicitly scaled quantity that disagrees with the
  catalog raises before sending; batches validate each pair separately.
  Quantities tagged for another pair now also raise before sending on create,
  modify, batch replace and trigger create, and a conflicting symbol and symbol
  ID raise on create and batch create.
  Migration: hydrate catalogs and use the destination pair's symbol, ID and scale.

- Create results by symbol ID use the catalog scale for resolved quantities.
- Batch create resolves base and quote-budget scales separately for each item.

- Fixed API-key request signing to sort decoded query bytes before encoding and preserve percent-encoded bytes, including bytes outside valid UTF-8 text. Prefix keys, repeated values and escaped values now match the server.
- **Breaking:** Trigger creation now rejects options that do not apply to the selected strategy or child execution before sending. Migration: remove incompatible options, or select the trigger type and execution that support them (use `trailing_stop` for trailing distances and activation price).

- Transfer history's `since` filter now works, including zero. It is an
  inclusive lower bound in microseconds since the UTC Unix epoch. Invalid
  types (including booleans), negative values and values above uint64 now
  raise a validation error naming `since` before sending.
- **Breaking:** `create_to_funding` and `create_to_external_chain` now raise
  `PolyesterValidationError` if `account` or `sub_account_id` is supplied,
  including `"main"`, `"active"` or a selector matching the API key's scope.
  These arguments previously had no effect. Omit both selectors (or pass
  `None`) and use an API key bound to the intended source. Configured SDK
  defaults do not route API-key withdrawals; wallet withdrawals still support
  account selection and configured defaults.
- **Breaking:** internal transfers now reject a blank or whitespace-only address when it
  is the only destination. A blank address alongside a valid account or
  subaccount is ignored, preserving that recipient.
- **Breaking:** trigger create and modify now reject competing ticks and basis-point
  settings for trailing distance or slippage. A single zero slippage setting
  on modify still clears the cap.
- **Breaking:** transfer history now returns the opaque `next_page_token` string
  instead of an integer `next_cursor`. Pass it as `page_token` on the next
  `transfers.list` call with the same scope, filters and direction. An empty
  string ends pagination. The `since` lower timestamp bound works with this token.
- Preserve continuation tokens in market-overview and candle results. Both
  candle helpers now accept `page_token` for reading the next page.
- Heatmap history now accepts `page_token`. Continuation requests keep the
  original filters and omit a new default time window; repeat an explicit
  original range only when needed.
- **Breaking:** preview by symbol ID now uses the catalog base quantity scale. Without that
  catalog entry, pass a `Quantity` with an explicit scale; an unknown scale
  raises a validation error instead of formatting the result at scale zero.
- Equity history now exposes `btc_prices_q`: the returned BTC-USDT closes as
  integers scaled by 1e9, in timestamp order. An omitted series is an empty list.

## 0.6.2

Git tag: `v0.6.2`. Released 2026-11-06.

- REST errors that say an order or trigger outcome is unknown now use the
  same non-retryable API error as Connect. Read the order or trigger back
  before retrying: the first request may still apply. A gateway timeout
  without a recognised outcome code remains a retryable transport/server
  failure with an unknown outcome; reconcile before retrying a mutation.

## 0.6.1

Git tag: `v0.6.1`. Released 2026-11-06.

- Service-unavailable responses now raise retryable server errors on Connect
  for orders, withdrawals and internal transfers, matching REST. This includes
  policy and fee lookups, backlogs, operations in progress and temporarily
  unavailable dependencies. Policy denials and permanent precondition failures
  remain non-retryable. Rate-limit errors keep their retry delay, and unknown
  mutation outcomes remain non-retryable even on an unavailable response.
- Keep the service code, status and original detail on Connect server errors,
  and retain code, status and problem metadata on REST errors.

## 0.6.0

Git tag: `v0.6.0`. Released 2026-11-05.

- **Breaking:** a trailing stop created with an activation price already
  reached now ends `FAILED` with
  `TRIGGER_FAILURE_REASON_TRIGGER_WOULD_TRIGGER_IMMEDIATELY` (244).
  `ModifyTrigger` and order modifies that would make a trailing stop act at
  once are refused with `ERROR_CODE_TRIGGER_WOULD_TRIGGER_IMMEDIATELY` (302),
  leaving the existing state unchanged. To start trailing from the market,
  clear the activation price with a present zero.
- **Breaking:** remove the public holds-list method, hold models and decoders.
  Read aggregate held trading funds from each asset's `reserved` balance in
  the balances API. Individual hold IDs and expiry times have no replacement.
- **Breaking:** listing events for an unreadable trigger now returns the same
  not-found error as reading that trigger, instead of an empty history.
  Events reads retry a catching-up `UNAVAILABLE` with the trigger-read policy.
- Expose reserve fee rates, the next scheduled change and the full fee
  breakdown. Omitted optional components remain absent and omitted account
  discounts decode as an empty list.
- Preserve REST problem status, code, detail and canonical type on realtime
  authorization and early gateway authentication errors.
- Pin execution-history continuation pages to the returned exchange order ID
  so reuse of a client order ID cannot change generations between pages.

**What a trading bot gains.** A bot can read the product changelog of the
environment it trades on, with no API key, and find the breaking or
action-required changes published since it last looked. It can wait for a
batch replace to settle and see which items were refused after admission, and
a trigger read right after a modify, pause or resume no longer fails on the
server's brief `unavailable`. It can tell from an order alone how much of a
quote-sized buy was spent, see why a stop placed no order, act on why its API
key was refused on either transport, and stop all its automated trading with
one call. Its attached take-profit, stop-loss and trailing stop exits never
trade with the order they protect, it can choose the self-trade prevention
mode they use, and it can read a sub-account's balances in the sub-account
view.

**Breaking changes**
- None in the SDK API.

### Added
- `client.changelog` wraps the public `changelog.v1.ChangelogService`.
  `list_posts`, `get_post` and `list_changes` return typed
  `ChangelogPostSummary`, `ChangelogPost`, `ChangelogSection`,
  `ChangelogChange` and `ChangelogChangeEntry` models. `iter_posts` and
  `iter_changes` yield every page, and `breaking_changes_since` and
  `action_required_since` collect the matching changes published since a
  time. Categories, audiences and surfaces are lowercase labels, and a value
  newer than the SDK reads as its number. Change IDs are base58. An unknown
  slug raises `PolyesterApiError` code `not_found`.
- The sync `Polyester` client turns async iterator methods into plain
  iterators, so `client.changelog.iter_posts()` works there too.
- `orders.wait_batch_replace(batch_request_id=...)` polls
  `get_batch_replace_status` with a short backoff until no item is
  `admitted`, and returns that status. It polls through the `not_found` the
  status read answers for a few seconds after admission, and through server
  and network errors. It stops at the server's 60-second status window, or at
  `timeout=`, even during a read, with the new
  `PolyesterBatchReplaceTimeoutError` (a `PolyesterTimeoutError`) carrying the
  last status read: reconcile the orders themselves after it.
- `BatchReplaceStatusItem.error_code` names an item's refusal as
  `PolyesterApiError.code` names it: the raw `code` (`POST_ONLY_CROSS`) with
  the `ERROR_CODE_` prefix, or `code` unchanged when this SDK does not know it.
- Market-halt reasons: when the exchange halts a market, its orders end
  `canceled` with `cancel_reason` `MARKET_HALTED`, and its triggers end
  `canceled` with `cancel_reason` `market_halted`, on reads and streams. An
  order the halted market refused after admission ends `rejected` with
  `reject_reason` `MARKET_HALTED`. A trigger the halted market refused ends
  `failed` with `failure_reason` `market_halted`, on the trigger and on its
  `failed` and `fire_refused` events; the server no longer reports the
  unnamed reason 212 for it. A reason number this SDK does not name still
  reads as its number.
- `PolyesterSubaccountOwnerRoleLockedError`, a `PolyesterApiError` with code
  `AUTH_SUBACCOUNT_OWNER_ROLE_LOCKED` (exported as a constant): inviting,
  re-roling or removing a sub-account's owner. It maps from Connect
  `failed_precondition` with that `AuthErrorDetail` and from a REST 412
  problem body with that code; not retryable.
- Exact order execution totals. `Order.avg_price` is the exact average
  execution price (`avg_price_e18`) as a `Decimal`, `None` without fills;
  prefer it to `avg_px`. `Order.cum_notional_scaled` is the exact quote amount
  of the fills before fees and `Order.cum_quote(base_quantity_scale)` returns
  it in quote units. `Order.fee_total` (new `OrderFeeTotal`: `amount`,
  `amount_e18`, `is_rebate`, `qty`) is their fee net of rebates; order
  history and single-order reads with execution history carry it.
  `Order.quote_used(...)` and `Order.quote_unspent(...)` tell how much of a
  buy's quote amount the fills used, and return `None` until the fee total
  covers every fill. All exact, never through a float.
- Refused trigger fires: trigger events of type `fire_refused` (filter with
  `list_events(event_type="fire_refused")`) and `TriggerEvent.fire_refusal_reason`,
  set only on them, with the `failure_reason` labels, `account_repairing`
  included. `is_terminal_trigger_event(event_type)` is false for
  `fire_refused` and for event types this SDK does not know.
- `auth_error_code(err)` returns the `auth.v1.AuthErrorCode` name of an error
  from a ConnectRPC `AuthErrorDetail` or a REST problem `code` (`AUTH_`
  prefix added; `UNAUTHENTICATED` reads `AUTH_AUTHENTICATION_REQUIRED`), and
  `auth_error_code_from_rest(code)` maps a REST code. Constants
  `AUTH_SIGNATURE_INVALID`, `AUTH_TIMESTAMP_SKEW`, `AUTH_MISSING_HEADERS`,
  `AUTH_KEY_EXPIRED`, `AUTH_KEY_DISABLED`, `AUTH_IP_NOT_ALLOWED`,
  `AUTH_API_KEY_NOT_ACCEPTED`, `AUTH_AUTHENTICATION_REQUIRED` and
  `AUTH_SESSION_KIND_NOT_ALLOWED`.
- `PolyesterSessionRequiredError` (`is_session_required(err)`): a session-only
  method called with an account API key (`AUTH_SESSION_KIND_NOT_ALLOWED`), from
  Connect `permission_denied` with that `AuthErrorDetail` and from a REST 403
  problem body, on every service. It is both a `PolyesterAuthError` and a
  `PolyesterApiError`; not retryable.
- `PolyesterApiError.violations`: the field violations (`field_path`,
  `rule_id`, `message`) of an `orders.v1.ErrorDetail` or of a REST problem
  body's `violations`, as `OrderFieldViolation`.
- `is_order_already_terminal(err)` and `ORDER_ALREADY_TERMINAL`: a cancel of
  an order that has already ended, a repeat of the cancel that ended it
  included, which the server now refuses instead of answering `accepted`.
- `orders.stop_all_trading(account=, sub_account_id=, symbol=, request_id=)`
  cancels every live trigger (all pages of `created`, `armed`, `running` and
  `paused`), then all open orders, and returns a `StopAllTradingResult` with
  `canceled_trigger_ids`, `trigger_failures` (`StopAllTradingTriggerFailure`:
  `trigger_id`, `error`) and `cancel_all`. A listing error, or a page token
  that repeats, is raised before anything is canceled; a failed trigger cancel
  is recorded and the other cancels and the cancel-all still run; a cancel-all
  error is raised. Cancel-all and the dead-man switch never cancel triggers.
- Changelog: surfaces `market_data`, `quickswap` and `rewards`, and
  `ChangelogSection.surface`, the product area a section covers (`""` for
  none).
- Attached exits and self-trade prevention: an order whose attached exit
  fired while it still rested ends `canceled` with `cancel_reason`
  `ATTACHED_EXIT_FIRED` (its unfilled remainder was canceled first; fills
  before it stand). A `fire_refused` trigger event with
  `fire_refusal_reason` `self_trade_prevented` means self-trade prevention
  expired the exit's order against another of the account's resting orders:
  `child_seq` names that order and the trigger stays live and fires again.
  `is_terminal_trigger_event("fire_refused")` stays false. Error code
  `SELF_TRADE_PREVENTED` (307) reads by name; no request is answered with it.
- `self_trade_prevention_mode` (`expire_taker`, `expire_maker`,
  `expire_both`) on `orders.create`, `orders.preview_order` and
  `orders.batch_create` items, which the order's attached exits use too; an
  unknown value raises `PolyesterValidationError`.
  `Order.self_trade_prevention_mode` reads it back; a mode newer than this
  SDK reads as its number.
- `sub_accounts.get(include_balances=True)` returns the sub-account's
  current balances on `GetSubaccountResult.balances`, a `BalancesList` as
  `balances.list` returns; `None` without `include_balances`. It needs the
  `READ_BALANCES` action on the sub-account; `AUTH_TEMPORARILY_UNAVAILABLE`
  is retryable.

### Changed
- `triggers.get` and `triggers.list` resend the same request while the server
  answers `unavailable` (HTTP 503): after 25 ms, doubling up to 500 ms, for
  about 2 seconds. Trigger reads answer it right after a modify, pause or
  resume until they can show the change.
- A non-Connect HTTP 412 error body now maps as Connect
  `failed_precondition` instead of `unknown`.
- A Connect `unauthenticated` error with an `AuthErrorDetail` of
  `AUTH_TIMESTAMP_SKEW` raises the retryable `PolyesterTimestampSkewError`, as
  the gateway's `TIMESTAMP_SKEW` does; the other API-key reasons raise
  `PolyesterAuthError` with their code (was `PolyesterApiError`).
- `auth_error_code(err)` returns only auth error codes; it used to return any
  `PolyesterApiError.code`, orders codes included.
- A gateway problem body's `detail` is the error message (it was the bare
  code), so a refusal such as "api key policy does not allow
  READ_AUTO_WITHDRAW" reaches the caller as the server wrote it; the code
  stays on `err.code`.
- A REST problem body at HTTP 400 raises `PolyesterApiError` with its
  `ERROR_CODE_` code and violations instead of a retryable
  `PolyesterServerError`.
- Client-side checks of an attached trailing stop's maximum raise
  `PolyesterValidationError` with the server's `code` and `violations`
  (`ERROR_CODE_BAD_PRICE` / `sell_unset` or `buy_at_least_activation`,
  `ERROR_CODE_TRIGGER_BUY_REQUIRES_LIMIT` / `buy_required`, on
  `order.attached_risk.trailing_stop.limit_price_ticks`, or
  `new_attached_risk...` for modify). `PolyesterValidationError` gains `code`
  and `violations`, empty for SDK-only checks.
- A quantity or tick-checked price with a nonzero digit beyond its scale
  raises `PolyesterValidationError` with the code and violation the server
  answers for it: `ERROR_CODE_QTY_STEP_SIZE` / `step_size` at
  `order.base_qty_scaled`, or `ERROR_CODE_PRICE_TICK_SIZE` / `tick_size` at
  the price's field (limit price, attached take-profit and stop-loss trigger
  and limit prices, attached trailing stop activation and limit prices, and
  modify's `new_price_ticks` and `new_attached_risk...`). It had no `code`.
  Zeros beyond the scale are accepted as before.
- Docs: `Order.cum_notional_scaled`, `cum_quote`, `quote_used` and
  `quote_unspent` are exact when the pair's `base_quantity_scale` is at most
  9. Otherwise the first three can exceed the settled quote by less than 1e-18
  per fill, and `quote_unspent` can read lower than what is left by the same
  margin.
  A quote-amount buy (`max_quote_debit`) takes attached risk.
- Docs: a spent quote-sized buy ends `filled`; a ladder whose levels were all
  canceled before any filled ends `cancelled`; attached legs follow the
  order's whole settled position; cancel-all and the dead-man switch leave
  triggers live.

### Fixed
- `get_batch_replace_status` no longer raises `PolyesterResponseContractError`
  for an item refused after admission. Such an item reads `rejected` with a
  code while the admission counts still count it as accepted.
- A `rejected` batch replace status item never carries a
  `replacement_order_id`.

## 0.5.1

Git tag: `v0.5.1`. Released 2026-11-02.

**What a trading bot gains.** A selling order can carry an attached trailing
stop again. That trailing stop buys back, and the server requires the most its
exit pays per unit; 0.5.0 could not send it, so such an order was always
rejected.

**Breaking changes**
- None in the SDK API.

### Fixed
- `TrailingStop.limit_price` (and `limit_price` / `limit_price_ticks` in an
  `attached_risk.trailing_stop` dict) sends the buy-back limit price of a
  trailing stop attached to an order: a 9-decimal string, `Decimal` or
  `Price.from_ticks`. `orders.create` and `orders.batch_create` require it
  when the order sells and reject it when the order buys, and it must be
  positive and at least `activation_price` when both are set; each case raises
  `PolyesterValidationError`. `orders.modify` sends it as given and the server
  applies the side rule. Order reads do not return it yet.

## 0.5.0

Git tag: `v0.5.0`. Released 2026-11-02.

**What a trading bot gains.** An attached take-profit, stop-loss or trailing
stop now says when it starts protecting the position: its trigger events
include `armed`, once, when the parent order's first fill makes the leg live.
A bot can wait for it instead of polling the leg's status. Three new error
codes are final refusals: the request did not apply, so do not resend it
unchanged.

An environment reports `armed` events and the new codes once it runs this
contract: devnet first, then testnet after its next upgrade.

**Breaking changes**
- None in the SDK API.

### Added
- Trigger events decode the new `armed` event type: an attached take-profit,
  stop-loss or trailing-stop leg reports it once, when its parent order's
  first fill makes the leg live (or when a leg paused before that fill
  resumes). It is not terminal. `triggers.list_events` accepts
  `event_type="armed"`. Attached trailing stops still report `activated` when
  they start tracking.
- Error codes `AUTH_SUBACCOUNT_OWNER_ROLE_LOCKED` (the sub-account's owner
  cannot be invited, re-roled or removed),
  `ERROR_CODE_TRIGGER_SYMBOL_MISMATCH` (modify, pause or resume named a listed
  pair other than the trigger's own; name the trigger's pair or omit it) and
  the balance reads' `ERROR_CODE_INVALID_SUBACCOUNT_ID` (a zero or malformed
  sub-account ID).
- Generated messages add `Subaccount.removed` (real-time sub-account updates
  only: the caller lost access, so drop the sub-account),
  `TrailingStopPolicy.limit_price_ticks`, `Checkpoint.opening_value_usd`,
  `ListMyRewardAwardsResponse.awards_may_change` and the Swap reason
  `MAX_ORDER_QUANTITY`, and the trade WebSocket protobufs follow binary schema
  34.

### Server behaviour on this contract
- Batch replace amends an order in place, keeping its order ID and queue
  priority, when an item keeps the price, does not raise the total quantity
  and keeps the client order ID. Otherwise it replaces the order under a new
  order ID.
- An attached trailing stop on a selling order buys back, and the server now
  requires its maximum buy-back price. This SDK's `AttachedRisk.trailing_stop`
  does not send that price yet, so place a selling order with only take-profit
  and stop-loss legs until a later release adds it. A buying order's attached
  trailing stop is unchanged.
- Ladder outcomes: a ladder is completed once no child order remains open and
  at least one reached the book; it is failed only when every child order was
  rejected before reaching the book.

## 0.4.0

Git tag: `v0.4.0`. Released 2026-11-02.

**What a trading bot gains.** An order now says why it ended, in the same
words everywhere. A rejected order's `reject_reason` is the error code the
Orders API returns for the same refusal, and a canceled order's
`cancel_reason` says why it was canceled, on order reads and on the private
order stream alike. Before, the numeric reason used the matching engine's own
numbering, which clashed with the API's error codes. `OrderbookData.available`
tells a bot when a book's levels are unknown rather than empty, so it does not
quote into a book that is being rebuilt. `Trigger.version` picks out the
newest copy of a trigger, and nine new error codes are definite refusals: the
request did not apply, so do not resend it unchanged.

This release works on devnet now, and on testnet after testnet's next upgrade.

**Reason labels in this SDK.** `reject_reason` is the `orders.v1.ErrorCode`
name without its `ERROR_CODE_` prefix, for example `POST_ONLY_CROSS`.
`cancel_reason` is the `orders.v1.CancelReason` name without its
`CANCEL_REASON_` prefix, for example `USER_REQUEST`. The Go and Rust SDKs
format these labels differently.

**Breaking changes**
- The `whiteboard`, `polychart` and `layout` services are removed.
- The generated `orders.v1.Order` loses `terminal_reason_code` and
  `terminal_reason`, and the generated `privatews.v1.OrderEvent` loses
  `reason_code`. Read `Order.reject_reason` and `Order.cancel_reason` instead.
- `PrivateOrderEvent.reason_code` is replaced by `reject_reason` and
  `cancel_reason`.
- `sub_accounts.get()` no longer takes `include_balances`.

### Breaking
- The `whiteboard`, `polychart` and `layout` services are removed from the
  client, because those APIs are no longer part of the public API.
- An order's terminal reason code and name are removed: the generated
  `orders.v1.Order` no longer has `terminal_reason_code` or `terminal_reason`,
  and the generated `privatews.v1.OrderEvent` no longer has `reason_code`.
  Their numbers did not match the Orders API's error codes. Read the typed
  `Order.reject_reason` and `Order.cancel_reason` instead (see Added).
- `PrivateOrderEvent.reason_code` is replaced by `reject_reason` and
  `cancel_reason`. A rejected order's event names its refusal as the order
  write API does (for example `POST_ONLY_CROSS`). A canceled order's event
  names why it ended (for example `USER_REQUEST`), and so does the replaced
  event of the order a replace ended (`REPLACED`). Both are `None` otherwise.
- `sub_accounts.get()` no longer takes `include_balances`: a sub-account read
  no longer returns balances. Read them with `balances.list()` for the
  sub-account.

### Added
- `Order.reject_reason` and `Order.cancel_reason`, on order reads and on the
  orders of the private order stream's snapshots and units. A rejected order
  carries the error code the Orders API returns for the same refusal (for
  example `INSUFFICIENT_FUNDS`); a canceled order carries why it ended (for
  example `USER_REQUEST`, `IOC_REMAINDER`, `STP_EXPIRE_MAKER`, `REPLACED` or
  `GTD_EXPIRED`). Both are `None` for every other status, and on servers that
  do not send them yet. An unknown number reads `UNKNOWN_ERROR_CODE(n)` or
  `UNKNOWN_CANCEL_REASON(n)` instead of raising.
- `OrderbookData.available`. When `False`, the book is being built or was
  invalidated: its levels are unknown, not empty, so request the snapshot
  again later. A subscription's book reports the value of the last snapshot
  it applied; deltas, resets included, do not change it.
- `Trigger.version`: 1 for a trigger's first state, higher for every later
  state change. Keep the copy with the highest version across reads and
  realtime updates. It is `0` from a server that does not send it.
- Order error codes `ATTACHED_LEGS_EXCEEDED`, `FEE_ASSET_INVALID`,
  `FEE_CEILING_INVALID`, `UNSUPPORTED_FIELD_SET`,
  `TRIGGER_FIRE_LIMIT_REACHED`, `CONDITION_FLAGS_INVALID`,
  `CONDITION_PARAMETER_SET`, `TWAP_CAPACITY_REACHED` and
  `CHILD_ORDER_INCONSISTENT`. Each raises a non-retryable `PolyesterApiError`
  and is a definite refusal: the request did not apply.

## 0.3.0

Git tag: `v0.3.0`. Released 2026-10-31.

**What a trading bot gains.** `trades.subscribe()`, `transfers.subscribe()`,
`triggers.subscribe_events()` and `market_data.subscribe_trades()` now yield
every event; before, the rest of each batch was dropped or garbled. Spot
config and the catalog expose each pair's order limits, including the new cap
on one market order's notional, so a bot can size orders before it sends
them. Rejections are easier to act on: a duplicate client order ID names the
order that already holds it, a clock-skew rejection is the retryable
`PolyesterTimestampSkewError`, and a bad key or signature is a non-retryable
`PolyesterAuthError` instead of a retryable server error. Replacement orders
report the quantity they inherited, and slippage caps and trigger inputs are
checked before sending the way the API checks them. The SDK now requires
`connectrpc` 0.10.

This release works on devnet today, and on testnet after testnet's next
upgrade, which brings the new private order stream.

**Breaking changes**
- `triggers.modify()` no longer takes `limit_price`.
- `max_slippage_bps` is at most 9999 for a market order that sells, a sell
  stop-loss or take-profit market child, every trailing stop and
  `triggers.modify()`.
- `trigger_price_source="mark"` raises `PolyesterValidationError`.
- A buy trailing stop's `limit_price` must be at least its `activation_price`.
- API-key rejections from the API gateway raise the retryable
  `PolyesterTimestampSkewError` or the non-retryable `PolyesterAuthError`
  instead of a retryable `PolyesterServerError`.

### Breaking
- `triggers.modify()` no longer takes `limit_price`: the API rejects any
  change to a child's limit price. Cancel the trigger and create a new one.
- Slippage caps match the API: `max_slippage_bps` is 1–9999 for a market
  order that sells, a sell stop-loss or take-profit market child, every
  trailing stop (standalone or attached, either side) and `triggers.modify()`.
  Buy market orders, buy stop-loss or take-profit market children and TWAP
  slices still accept 10000.
- `trigger_price_source="mark"` raises `PolyesterValidationError`: spot
  markets have no mark price. Use `"last"` or `"index"`.
- A buy trailing stop's `limit_price` must be at least its `activation_price`.
- API-key rejections from the API gateway are classified by their code.
  `TIMESTAMP_SKEW` raises the new retryable `PolyesterTimestampSkewError`;
  retrying signs the request again with a fresh timestamp, and the request
  never reached a service, so `mutation_outcome_unknown()` is false. Other
  codes such as `SIGNATURE_INVALID`, `KEY_DISABLED` or `IP_NOT_ALLOWED`
  raise a non-retryable `PolyesterAuthError` carrying the code. Earlier
  versions reported all of them as a retryable `PolyesterServerError`
  without details.

### Added
- Spot config order limits: `SpotConfig.pair_order_limits` and
  `client.catalogs.order_limits_for_symbol(...)` / `order_limits_for_symbol_id(...)`
  return `PairOrderLimits` with `max_limit_qty_base`, `max_market_qty_base`
  and `max_order_notional_quote` (decimal strings, `None` when the pair has
  no maximum) and `max_open_orders_per_pair`. `SpotConfig.max_open_orders_total`
  and `client.catalogs.max_open_orders_total` give the cross-pair limit. The
  open-order counts are venue defaults; an account may have a lower limit.
- `PairOrderLimits.max_market_notional_quote`: the largest notional of one
  market order in quote units, valued at a buy's protection price or a sell's
  reference price. A larger market order is rejected with `MAX_NOTIONAL`.
  `None` means the pair has no cap. Available on `SpotConfig.pair_order_limits`
  and `client.catalogs.order_limits_for_symbol(...)`.
- `Order.inherited_cum_qty`: the filled quantity a replacement order carries
  over from its predecessors.
- `action_taken` on batch replace admission and status items: `"replaced"`
  when a successor was admitted, `"amended"` for a cancel-only outcome.
- `existing_order_id` on a `CONFLICT_DUPLICATE_CLIENT_ORDER_ID` rejection,
  when the server knows the order: `PolyesterApiError.existing_order_id` on a
  single create and `BatchCreateResultItem.existing_order_id` on a batch
  create item.
- `triggers.modify()` and `triggers.resume()` no longer need `symbol` or
  `symbol_id`; without one they target the trigger's own market. An API key
  limited to specific markets must still pass it.
- `LedgerTransfer.transfer_id`, the unsigned 128-bit decimal shared by both
  legs of a transfer.
- `VIPStatus.settled_volume_quality` and `average_aop_quality`
  (`VIPMetricQuality`: `status` of `complete`, `price_unavailable` or
  `incomplete_history`, plus `incomplete_hours`).
- `TriggerTrailingDetails.trigger_price`, the current trailing threshold.
- `AsyncRealtimeClient.subscribe_proto_batch(...)` for channels whose
  publications batch several events.
- A Connect `deadline_exceeded` raises `PolyesterTimeoutError`, a subclass of
  `PolyesterTransportError`, so existing handlers still catch it.
- HTTP 501 and Connect `unimplemented` raise `PolyesterNotImplementedError`,
  a `PolyesterApiError` subclass that `PolyesterRouteNotFoundError` now
  extends.

### Fixed
- `trades.subscribe()`, `transfers.subscribe()`, `triggers.subscribe_events()`
  and `market_data.subscribe_trades()` decode the batched publications these
  channels now send and yield each event on its own, in order. Earlier
  versions decoded a batch as one event, which dropped or garbled the rest of
  it. An event that fails to decode is reported through `set_on_error(...)`
  without dropping the rest of its batch.
- `market_overview.create_subscription(symbols=[...])` keeps only the
  requested markets in live and buffered updates; earlier versions filtered
  the initial snapshot only.
- `trades.list(after_match_id=...)` rejects a value beyond the uint64 range
  before sending.

### Changed
- `connectrpc` minimum raised from 0.9.0 to 0.10.0. 0.9.0 has no
  `connectrpc.codec`, so the SDK failed to import with it.
- The package description now reads "Python SDK for the Polyester API with
  generated protobuf types and ConnectRPC clients."

### Internal
- `sdk-capabilities.json` no longer carries `publicDescriptorSha256` or `generatedAt`, so a proto publication that only changes `src/polyester/gen/` and `manifest.json` no longer makes it stale; `manifest.json` stays the single source of the descriptor hash.

## 0.2.0

Git tag: `v0.2.0`.

**Upgrade before trading.** 0.1.0a55 and earlier encode and decode prices at
6 decimals while the API uses 9, so every price is 1,000 times off. Their
testnet preset points at a host that does not exist, and their devnet preset
at an undocumented host. This release uses 9-decimal prices and the
documented hosts (`api.devnet.polyester.com`, `api.testnet.polyester.com`),
and streams live orders over the private WebSocket.

**New version scheme.** The Go, Python and Rust SDKs now share one version
line and release together. Versions are plain SemVer (`0.2.0`, `0.2.1`,
`0.3.0`) instead of PEP 440 pre-releases (`0.1.0aN`), and Git tags are
`vX.Y.Z`. Before 1.0, a minor release (`0.3.0`) may include breaking changes;
a patch release (`0.2.1`) does not. Pin the exact version
(`polyester-sdk==0.2.0`). This release covers every change since 0.1.0a55.

### Breaking
- Trading prices now use fixed 9-decimal price ticks (one tick is 1e-9 quote
  units), matching the API. This covers order, trigger, trailing-stop,
  ladder, order-book, trade, candle, and market-overview prices and
  `Price.from_ticks`. Earlier SDK versions encode and decode prices at 6
  decimals, which is 1,000 times off against the current API; upgrade
  before trading. Integer `max_slippage_ticks` values are 64-bit Q9 ticks.
- `orders.subscribe()` now streams live orders over the private WebSocket
  (`/v1/ws/private`) instead of the retired `private:spot:orders:<account>:proto`
  realtime channel, which no longer issues subscribe tokens. It yields
  `PrivateOrdersEvent` values instead of bare `Order` objects:
  `PrivateOrdersSnapshot` (the full live view), `PrivateOrdersUnit` (changed
  orders, removed order IDs and order events), `PrivateOrdersReady` (the
  stream reflects every order read made before the subscribe; wait for it
  before relying on the stream), `PrivateOrdersStale`,
  `PrivateOrdersConnected`, `PrivateOrdersDisconnected` and
  `PrivateOrdersError`. Orders are the same `Order` model the reads return.
  The stream resumes from its last position after a gap, an expired token or
  a reconnect. `orders.subscribe_sync(on_event=...)` receives the same events.
- `market_data.get_trades()` drops `from_match_id`, which never reached the
  API (it failed before sending), and `MarketTradesResult.next_match_id` is
  now `next_page_token`. Page a listing with `page_token`.
- A stop-loss or take-profit with a limit child now rejects
  `max_slippage_ticks` / `max_slippage_bps`, and a sell trailing stop rejects
  `limit_price`; earlier versions ignored them.
- `triggers.create()` no longer defaults `trigger_price_source` to `"last"`;
  unset means the last trade price. A TWAP or ladder trigger now rejects
  `trigger_price_source`, which earlier versions ignored.

### Changed
- Documentation links (the PyPI "Documentation" URL, the README capability
  matrix and Market Order Price Protection links) now point at the public
  docs on `https://polyester.com/docs`. The price-protection link was
  broken in earlier versions.
- Candle and market-overview base volume now use the base asset
  `market_data_volume_scale` from `get_spot_config`. Primary candle prices
  use the 9-decimal price scale.
- Composite reference-candle OHLC uses the pair `reference_price_scale`.
  `get_candles(..., include_reference=True)` requests that series.
  `MarketOverviewEntry.volume_24h_base` is the decoded decimal when the
  catalog scale is known; `volume_24h_base_scaled` stays the integer.

### Added
- Index-price triggers: stop-loss, take-profit and trailing-stop triggers,
  standalone (`triggers.create(trigger_price_source=...)`) or attached to an
  order (`trigger_price_source` on each attached leg, in create and modify),
  accept `"last"`, `"index"` or `"mark"`; unset means the last trade price.
  Reads report the same label on `Trigger.trigger_price_source`,
  `RiskLeg.trigger_price_source` and `TrailingStop.trigger_price_source`, so
  a leg read from an order can be passed back unchanged. Earlier versions
  rejected the field on attached legs and dropped it on standalone triggers.
- `CancelAllOrdersResult.listing_status`: `included`, or
  `not_retained_read_open_orders` for a retry with the same `request_id`
  within 120 seconds. Such a retry returns the original counts with an empty
  `cancelled_orders`; the empty list does not mean nothing was cancelled.
- `CancelAllAfterResult.effective_scope` (`DeadManSwitchScope` with
  `account_id`, `symbol_id` and `side`): the orders an armed switch cancels
  on expiry. `None` when the switch is disabled.
- `GetOrderResult.executions_complete`: true when the order's trades across
  every page add up to its filled quantity.
- `LifecycleFlowSummary.is_delayed`: true when an open flow has made no
  progress for well beyond its expected step time.
- New named values: lifecycle reason `deposit_source_not_confirmed`; trigger
  cancel reasons `account_repair`, `pair_drain_trigger`, `pair_drain_twap`,
  `pair_drain_ladder` and `pair_drain_attached_leg`; trigger failure reasons
  `index_price_unavailable` and `trigger_would_trigger_immediately`; order
  error code `ERROR_CODE_TRIGGER_WOULD_TRIGGER_IMMEDIATELY`; pair status
  `PAIR_STATUS_HALTED` (only cancellations are accepted).
- Standalone buy trailing stops: `triggers.create(trigger_type="trailing_stop",
  side="buy", limit_price=...)`, where `limit_price` is the required maximum
  price (decimal or `Price.from_ticks`). Trigger reads show a buy trailing
  stop as an IOC limit child with its maximum price as `limit_price`, and
  `details.trailing.trough_price` as the lowest price tracked.
- `CancelAllOrdersResult.cancelled_orders` (up to 200 `CancelledOrder`
  entries with `order_id` and `client_order_id`, oldest first),
  `total_cancelled` and `truncated`.
- Gap-free public trade backfill: `market_data.get_trades(after_trade_id=...)`
  walks a market's trades by trade ID, oldest first. Results carry
  `complete_through_trade_id`, `next_after_trade_id` and `epoch_ends`
  (`TradeEpochEnd`). `get_trades()` also accepts `start_time`, `end_time`,
  `side` and `page_token`.
- `OrderMutationResult` (from `orders.create`), `ModifyOrderResult` and
  accepted `BatchCreateResultItem` entries carry `take_profit_trigger_id`,
  `stop_loss_trigger_id` and `trailing_stop_trigger_id`: the public IDs of
  the triggers created for the order's attached-risk legs. Each is set only
  for a leg the order configured and is empty otherwise.
- `PolyesterRealtimeError.code` (private WebSocket request error code, for
  example `FORBIDDEN`) and `PolyesterRealtimeError.close_code` (the WebSocket
  close code that ended a stream).
- Trigger events label standalone trailing-stop activation as `activated`,
  and `trigger_event_type_from_label` accepts `activated` as a filter.

### Fixed
- `mutation_outcome_unknown()` now returns true for an order or trigger
  create, cancel, modify or control that was sent but not confirmed in time:
  every orders error code ending in `_OUTCOME_UNKNOWN`
  (`ERROR_CODE_ORDER_CREATE_OUTCOME_UNKNOWN`,
  `ERROR_CODE_ORDER_CANCEL_OUTCOME_UNKNOWN`,
  `ERROR_CODE_ORDER_MODIFY_OUTCOME_UNKNOWN`,
  `ERROR_CODE_TRIGGER_CREATE_OUTCOME_UNKNOWN`,
  `ERROR_CODE_TRIGGER_CONTROL_OUTCOME_UNKNOWN`, and codes added later).
  `is_retryable_error()` returns false for them: the change may have been
  applied, so a retry loop that resends it could, for example, place an
  order twice. Read the order or trigger back before sending it again.
  Earlier versions treated these as definite failures.
- `is_retryable_error()` returns true for `AUTH_TEMPORARILY_UNAVAILABLE`
  (exported as a constant): the request changed nothing, so retry it as is.
- `POLYESTER_TESTNET_ENVIRONMENT` and `environment_from_name("testnet")` now
  use `https://api.testnet.polyester.com` and `wss://api.testnet.polyester.com`.
  Earlier versions pointed at `api-testnet.polyester.com`, which does not
  exist, so every testnet call failed with a DNS error. The devnet preset and
  the client defaults now use the documented `api.devnet.polyester.com` host.
- A stop-loss or take-profit market child now carries its
  `max_slippage_ticks` or `max_slippage_bps` cap. Earlier versions dropped
  the cap silently, so the pair's default market slippage applied instead.
- Trigger reads (`triggers.get`, `triggers.list` and the trigger stream)
  show a stop-loss or take-profit market child's cap as
  `Trigger.max_slippage` (ticks, as a price delta) or
  `Trigger.max_slippage_bps`; earlier versions decoded every market child
  the same way, cap or not.
- Integer tick counts (`max_slippage_ticks`, `trailing_distance_ticks`,
  attached-risk `*_ticks` fields) above the 64-bit range raise
  `PolyesterValidationError` before sending instead of a raw `ValueError`.
- Order reads no longer report an attached-risk leg whose state is
  `not_configured`; the server sends that state for a leg the order does
  not have.
- An error code this SDK version does not know yet no longer crashes error
  handling with `ValueError`. Orders, auth, withdraw and transfer errors
  raise the usual `PolyesterApiError` with `code` set to
  `UNKNOWN_ERROR_CODE(<number>)`; an orders error that carries rate-limit
  details is still a `PolyesterRateLimitError`.
- With `wire_format="json"`, responses that contain fields or enum names
  this SDK version does not know yet decode instead of failing. Unknown enum
  names read as the unspecified value.

## 0.1.0a55

Git tag: `v0.1.0a55`.

### Added
- Market-order create/preview now expose `max_slippage_bps` or
  `max_slippage_ticks` and serialize the chosen override onto
  `OrderIntent.market_ioc`. Omit both to keep pair defaults. The fields
  are mutually exclusive, bounded (`bps` 1–10000, ticks positive),
  rejected on limit orders, and unknown create arguments now error
  instead of being dropped.

## 0.1.0a54

Git tag: `v0.1.0a54`.

### Added
- Limit GTD orders: `tif="gtd"` plus required RFC3339 UTC `expires_at`
  encode `OrderIntent.limit_gtd` (price, optional `post_only`, 1s–30d
  expiry). Order reads expose `expire_at` for GTD and omit it otherwise.

### Changed
- Generated Connect/protobuf bindings now include
  `ClaimsService.GetDailyClaimStatus` and `ClaimDailyReward`. Those RPCs
  stay JWT/session-only and are not wrapped in this API-key SDK.

## 0.1.0a53

Git tag: `v0.1.0a53`.

### Breaking
- `POLYESTER_TESTNET_ENVIRONMENT` is now public testnet (`api-testnet.polyester.com`,
  chain `888169`). The previous preset (devnet URLs, chain `888168`) is
  `POLYESTER_DEVNET_ENVIRONMENT` and remains the client / chain-helper default.

### Added
- Paginated order lineage history: `Order.lineage` / `UserTrade.lineage`
  (`id` + one-based `generation`), `GetOrderResult.transfers` /
  `next_page_token`, and `UserTradesList.transfers`. `orders.get` accepts
  `include_execution_history`, `limit`, and `page_token`. `trades.list`
  accepts mutually exclusive `order_id` / `lineage_id`, optional
  `through_generation` (requires `lineage_id`), and `include_transfers`.
  `wait_for_order_trades_complete` pages execution history; an empty page
  is not a settlement watermark. `cum_qty` / `avg_px` are lineage-cumulative.
- First-class `PolyesterEnvironment` passed to `AsyncPolyester` /
  `Polyester`. Named presets, `create_polyester_environment`,
  `environment.with_urls(...)` for custom / VPC endpoints, and
  `POLYESTER_ENV=devnet|testnet` for `from_env()`.
- CI rejects proto-relative Connect imports (`import fees.v1...`) so a gen
  drop cannot merge until `scripts/rewrite_connect_imports.py` remaps them
  to `polyester.gen.*`.

### Changed
- Restored `polyester.gen.*` imports in the fees, VIP, and rate-limit Connect
  clients after generated output reverted them to proto-relative imports.

## 0.1.0a52

Git tag: `v0.1.0a52`.

### Breaking
- `DepositWithdrawConfig.polyester_chain_id` is removed. The zipper config
  no longer publishes a dedicated Polyester chain id.

### Added
- `market_overview.get_currency_conversion_config` and
  `get_currency_conversion_rates` wrap the public currency-conversion RPCs.
  Fiat `units_per_usd_e8` is currency units per 1 USD at 1e8 scale (USD
  identity is 100_000_000). Stablecoin `usd_per_unit_e8` is observed USD
  per unit at the same scale. A missing fiat snapshot or omitted
  stablecoin is unobserved, not zero. Rates fail with unavailable
  (HTTP 503) before any observation exists. Fraction digits are
  presentation defaults, not rate precision.

### Changed
- Restored `polyester.gen.*` imports in the fees, VIP, and rate-limit Connect
  clients after generated output reverted them to proto-relative imports.

- Document that a reused `client_order_id` on create is a conflict after the
  first admission (`CONFLICT_DUPLICATE_CLIENT_ORDER_ID`). Reconcile with
  `get` / `list_open` before creating again.

## 0.1.0a51

Git tag: `v0.1.0a51`.

### Breaking
- `orders.cancel_all` now sends repeated Connect `symbol_ids` instead of a
  single `symbol_id`. Callers can pass `symbol`, `symbols`, or `symbol_ids`
  (mutually exclusive). An empty collection still matches all symbols; at most
  100 positive IDs are accepted and duplicates are ignored. Reuse `request_id`
  only when retrying identical cancellation criteria, and handle
  `ERROR_CODE_CANCEL_REQUEST_EXPIRED`.

### Added
- `market_overview.get_spot_volume_history` wraps the public
  `GetSpotVolumeHistory` RPC (trailing 24-hour USD volume samples). Omit
  filters for every configured pair, or send up to 2,000 distinct positive
  pair IDs.
- Candle decode now preserves exact traded `quote_volume` decimal strings on
  `CandlePoint`, `Candle`, and columnar candle responses.
- Market overview rows expose optional `volume_24h_base_scaled`,
  `volume_24h_quote_scaled`, and canonical `volume_24h_usd_scaled` (1e6 USD
  scale). Absent values stay `None` when the signed 64-bit amount or USD
  valuation is unavailable.
- Ladder trigger details decode `executed_levels` and `executed_qty`.
- TWAP market-IOC create can set per-slice `max_slippage_ticks` or
  `max_slippage_bps`.
- Connect withdraw and internal-transfer failures unpack the new
  `ErrorDetail` / `ErrorCode` types.
- Social verification `start` accepts Discord without `handle` and with an
  omitted method (server default is channel verification).

### Changed
- Generated Connect/protobuf bindings now include `AuthService.AcceptTerms`.
  That RPC stays JWT/session-only and is not wrapped in this API-key SDK.
  `AUTH_TERMS_NOT_ACCEPTED` is surfaced from Connect error details.
- Restored `polyester.gen.*` imports in the fees, VIP, and rate-limit Connect
  clients after generated output reverted them to proto-relative imports.

## 0.1.0a50

Git tag: `v0.1.0a50`.

### Changed
- Generated Connect/protobuf bindings now include
  `GetPortfolioEquityHistorySeries` and `GetPortfolioEquitySnapshot`. Those
  LedgerRead RPCs stay JWT/session-only (interactive root-account session)
  and are not wrapped in this API-key SDK.
- Equity history decode maps the additive `EquitySeries.portfolio_account`
  grouping (`account_id`, `remaining`) so the shared series type keeps
  portfolio identity instead of dropping it.
- Trigger modify proto validation is stricter: trigger price and trailing
  distance must be positive, and slippage / trailing BPS stay in 1–10000.

## 0.1.0a49

Git tag: `v0.1.0a49`.

### Fixed
- Qty/price **strings** with trailing zeros past scale are accepted when the
  value is exact after trim. `"1.500000000"` at scale 8 matches `"1.5"`;
  `"1.500000001"` still rejects. This is the string/`toFixed()` path, not
  `Decimal`.

## 0.1.0a48

Git tag: `v0.1.0a48`.

### Breaking
- `MeResult.api_key_id` is the public `ak_` + 32-hex string from
  `MeResponse.api_key_id`, not a formatted numeric ID. It is empty when the
  call was not API-key authenticated.
- Subaccount `status` is decoded from `SubaccountStatus` (`active` /
  `disabled`; unspecified is empty). Invite list/get filters encode
  `incoming` / `outgoing` onto `SubaccountInviteDirection` and reject unknown
  labels.
- Cancel, cancel-all, cancel-all-after, and batch-cancel outcomes decode from
  closed proto enums onto the existing public labels (`accepted`,
  `submitted`, `dry_run`, `armed`, `disabled`, `rejected`). Unspecified or
  unknown values fail closed.

### Changed
- Generated Connect/protobuf bindings now include `GenerateUsernameOptions`
  and `ClaimGeneratedUsername`. Those Profile RPCs stay JWT/session-only and
  are not wrapped in this API-key SDK.
- Restored `polyester.gen.*` imports in the fees, VIP, and rate-limit Connect
  clients so generated proto-relative imports resolve inside the package.

## 0.1.0a47

Git tag: `v0.1.0a47`.

### Added
- `Order.attached_risk` legs expose typed `AttachedRiskLegState` runtime
  status, armed/terminal nanosecond timestamps, trigger ID, and child-order ID,
  including state-only wrappers returned when policy inclusion is disabled.

### Fixed
- Attached and standalone trailing-stop basis-point fields validate within
  1–10,000 before protobuf assignment; explicit zero clears remain available
  only on trigger modify.
- Batch create rejects duplicate non-empty client order IDs while continuing
  to allow omitted/generated IDs.
- Attached-risk decode preserves stop-loss and trailing-stop legs together in
  malformed or legacy responses instead of hiding observable state.
- Buffered stale orderbook resets no longer clear or rewind newer snapshots.
- Ladder trigger ranges require resolved minimum price ticks to be strictly
  less than maximum price ticks.

## 0.1.0a46

Git tag: `v0.1.0a46`.

### Breaking
- Connect market, order, trigger, fee, policy, and orderbook payloads are
  `symbol_id`-only. `GetSpotConfig` is the remaining message that still
  returns both `symbol` and `symbol_id`. Public methods still accept display
  `symbol` and resolve it through the hydrated catalog.
- Market overview, trigger list, cancel-all, and cancel-all-after no longer
  forward raw symbol strings. Unknown symbols fail closed.
- Trigger `modify` / `resume` require `symbol` or `symbol_id` so the Connect
  request can carry the required market identifier.
- Policy models dropped perpetual rules and unenforced money-movement fields.
  `READ_TRANSFER_DESTINATIONS` is now `READ_ADDRESS_BOOK`.
- Removed `PerpMarketRule`.
- `TradingRateLimitRule.tier` is now `vip_tier`.
- `TriggerEvent.reason` is removed. Canceled/failed triggers and events
  expose typed `cancel_reason` / `failure_reason` labels.
- `trades.list(after_match_id=...)` requires `symbol` or `symbol_id`.

### Added
- `LedgerTransfer.source` / `destination` (`TransferSide`) including optional
  `chain_id` for external-address sides. This is the Zipper
  `ChainConfig.chain_id`, not an EIP-155 or Polyester chain id.
- `trades.list(after_match_id=...)` durable fill replay cursor.
- Address-book `get_view(minimum_view_revision=...)` plus `view_revision`
  on the view and invalidation events.

### Changed
- `Order.orig_qty` is documented as the current accepted total (updates after
  a successful modify). Batch-create `request_id` is the batch idempotency
  key; item `client_order_id` remains optional.
- Trigger modify omits `activation_price` / `max_slippage_*` to preserve
  current values and sends explicit zero to clear them. Create/modify reject
  `max_slippage_bps` outside 1–10000; modify still accepts `0` to clear.

### Removed
- Unused handwritten Connect header and body helpers. Generated Connect
  clients own unary requests, including `application/proto` for binary.

### Testing
- Compatibility coverage for unary content type, codec body bytes, and
  API-key signatures on binary and JSON wire formats.

### Docs
- README links the sibling
  [`polyester-examples-python`](https://github.com/Fabric-Labs/polyester-examples-python)
  cookbook near the top.
- README examples use placeholder `YOUR_ACCOUNT_ID` and `BTC-USDT`
  instead of a live Account ID and `BNB-USDT`.

## 0.1.0a45

Git tag: `v0.1.0a45`.

### Added
- Address-book writes: `create_entry` / `update_entry` / `delete_entry` and
  `create_tag` / `update_tag` / `delete_tag`. Entry create and update accept
  `new_tags` so a tag can be created and attached in the same request.
  Update is a durable PATCH (`expected_revision` + FieldMask). When `tag_ids`
  is also selected the resulting set is those ids plus `new_tags`; otherwise
  `new_tags` are appended.
- `AUTH_INTERNAL_ERROR` from `auth.v1.AuthErrorDetail`.

### Changed
- `orders.create` / `modify` encode attached TP/SL from friendly keys
  (`trigger_price`, `order_type`, `limit_price`) and `AttachedRisk` models onto
  the write `RiskPolicy` wire. Unknown fields and the extra `child.execution`
  wrapper are rejected instead of being dropped.
- `AsyncPolyester.from_env()` / `Polyester.from_env()` read `POLYESTER_API_URL`
  and `POLYESTER_WS_URL`.
- Re-export `is_batch_replace_settled` from `polyester`.
- Social verification Twitter handles accept an optional leading `@`. The SDK
  forwards the handle as supplied; the API strips the prefix.

## 0.1.0a44

Git tag: `v0.1.0a44`.

### Added
- VIP catalog and caller-root status: `client.vip.list_vip_tiers()` /
  `client.vip.get_vip_status()` (`vip.v1.VIPService`). Optional qualification
  metrics, timestamps, and next-tier thresholds stay omitted when unset.
- Effective spot fee rates: `client.fees.get_spot_fee_rates()`
  (`fees.v1.FeeService`), optionally filtered by subaccount and `symbol_id`.
- Public trading rate-limit catalog and authenticated account/API-key limits:
  `client.rate_limits.get_rate_limit_config()` /
  `client.rate_limits.get_trading_rate_limits()` (`ratelimit.v1.RateLimitService`).
  `policy_class` uses full protobuf enum names.

### Changed
- SDK boundary cleanup: raw `symbol` / `symbols` filters on market overview,
  triggers.list, and orders cancel-all paths forward to the API without
  catalog fail-closed admission.
- Removed client-side pair-constraint preflight (tick/step/min qty/notional)
  and the `PairConstraints` public accessor; catalog hydration still resolves
  symbol IDs / scales and treats zero-valued optional minima as unset.
- `ts_ns` decode no longer rejects millisecond-shaped integers; unit correctness
  remains an API concern.
- Pagination `validate_limit` is wire-safety only (reject bool/non-int); the
  SDK no longer hardcodes a global 1–1000 max across endpoints.

## 0.1.0a43

Git tag: `v0.1.0a43`.

### Added
- Market overview `index_price` from proto `index_price_ticks` (multi-venue index
  in quote units scaled by 1e6; omitted/`None` when no fresh index is available).

## 0.1.0a42

### Added
- Fail-closed catalog-backed symbol filters for market overview and raw symbol paths.
- Shared positive/ranged limit validation before protobuf encoding.
- Catalog pair-constraint accessors and deterministic order/trigger preflight
  (tick size, step size, min quantity, computable min notional).
- Shared `ts_ns` response-contract invariant that rejects millisecond-shaped values.
- Regression coverage for F001/F002/F004/F006/F007/F018/F019/F020/F027/F008/F031
  audit behaviors, including malformed-secret non-disclosure.

### Fixed
- Unknown non-empty symbol filters no longer degrade into unfiltered requests.
- Trigger label decode failures surface as `PolyesterValidationError` instead of
  raw `ValueError`.
- Zero-valued optional catalog minimums (`min_qty_base`, `min_notional_quote`)
  are treated as unset so live catalogs hydrate.

## 0.1.0a41

### Added
- Public `RateLimitDetail` model for `polyester.ratelimit.v1` quota rejection
  payloads (`reason`, presence-aware `limit` / `remaining` / `retry_after_ms` /
  `policy_version`, plus `operation_id`, `policy_class`, `scope`, `refill_model`).
- `PolyesterRateLimitError.detail` carries that structured payload when Connect
  attaches top-level `RateLimitDetail` or nested `orders.v1.ErrorDetail.rate_limit`.
  `retry_after` prefers `detail.retry_after_ms`, then `Retry-After` /
  `Retry-After-Ms` / `Grpc-Retry-Pushback-Ms` headers on HTTP 429 paths.
- Preview / batch create / batch replace / batch cancel rejections surface
  `rate_limit` on `OrderErrorDetail` and batch result items when present.

## 0.1.0a40

### Breaking
- Generated `TriggerEvent.fire_price_ticks` is now optional (absent for
  time-scheduled TWAP slice fires). Decoded `TriggerEvent.fire_price` is `None`
  when the wire field is unset.

### Added
- `orders.list_open(..., trigger_id=...)` and
  `orders.list_history(..., trigger_id=...)` filter child orders created by a
  standalone trigger (TWAP/ladder slice children and their execution prices).

## 0.1.0a39

### Breaking
- `lifecycle.get_flow_by_tx(...)` now returns `LifecycleFlowsList` instead of
  silently returning only the first match. Its default page size is now 50;
  use `list_flows_by_tx(...)` with `next_page_token` for complete pagination.

### Added
- Generated `polyester.ratelimit.v1` contracts expose structured quota
  rejection details used by order and trade WebSocket responses.

## 0.1.0a38

### Added
- `withdraw.validate_destination` wraps `ValidateWithdrawDestination` and maps
  validation codes to snake labels (`valid`, `invalid_address`,
  `denylisted_address`, …) for preflight checks before Trading → external
  withdraws.

## 0.1.0a37

### Added
- Lifecycle reason catalog maps trading-withdraw failure codes to snake labels:
  `trading_withdraw_policy_denied`, `trading_withdraw_contract_reverted`, and
  `trading_withdraw_execution_failed` .

## 0.1.0a36

### Fixed
- `ExportGuardSignerWalletResult.__repr__` redacts `private_key`.

### Docs
- README documents `UserTrade` fee e18 fields and `fee_is_rebate` polarity.
- README notes that the PyPI package excludes `tests/`; full pytest needs a git checkout.

## 0.1.0a35

### Breaking
- `UserTrade` fee fields move from asset-scaled integers to fixed 18-decimal
  magnitudes: `fee_scaled` → `fee_amount_e18`, `referral_share_scaled` →
  `referral_share_amount_e18` (decimal strings of wire `U128`). Convert to the
  fee asset's catalog scale before subtracting from BUY fill quantity.
- `UserTrade` adds sparse `fee_is_rebate`. When true, `fee_amount_e18` is a
  rebate credit rather than a fee debit (proto3 omits false).

## 0.1.0a34

### Docs
- PyPI Documentation URL points to the Python SDK docs on polyester.ai
  (`/docs/sdk/python/get-started/overview`).

## 0.1.0a33

### Fixed
- Attached `trailing_stop` encode rejects non-positive distance/max slippage and rejects
  `order_type` under `trailing_stop` (child is always market).
- Decode omits attached trailing legs that lack a positive distance (no fabricated
  zero-distance stop).

## 0.1.0a32

### Breaking
- Trigger snapshots no longer expose `child_order_ids`. Child-order history is
  authoritative on trigger events: use `triggers.list_events(..., event_type="fired")`
  and read `child_order_id` / `child_seq`.
- `TriggerEvent.fire_px` renamed to `fire_price`.

### Added
- `triggers.list_events(..., event_type=...)` optional filter
  (`fired` / `canceled` / `updated`).
- `TriggerEvent` thickens with `subaccount_id`, `child_seq`, and
  `child_order_id` (plus existing `symbol_id`, `trigger_type`, `fire_price`,
  `reason`, `ts_ns`).

## 0.1.0a31

### Breaking
- `PreviewOrderResult` no longer exposes fee/debit estimates
  (`estimated_quote_debit`, `estimated_fee`, `estimated_net_base_qty`,
  `fee_asset`, `fresh_at_ts_ns`) or `price_bound`. Wire/public result is now
  admissibility-focused: `admissible`, optional `rejection`
  (`OrderErrorDetail` with `code` + `violations`), `resolved_base_qty_scaled` /
  `resolved_base_qty`, `protected_price_bound` (renamed from `price_bound`;
  protective boundary, not expected fill), and `evaluated_at_ms`.
  Known Preview rejection codes use TypeScript-compatible labels such as
  `BAD_QTY`; unknown open-enum values use `UNKNOWN_ERROR_CODE(<n>)`.
- Lifecycle flow summaries expose `lifecycle_reason` (snake catalog label;
  unknown wire codes become `unknown_reason_{code}`) and optional
  `zipper_reason` (`ZipperReasonDetails`: numeric `code`, `reason_id`,
  `message`). Wire `FlowReason` / `reason_code` renamed to `LifecycleReason` /
  `lifecycle_reason`.

### Added
- `OrderErrorDetail`, `OrderFieldViolation`, and `ZipperReasonDetails` public
  models for Preview rejection and lifecycle Zipper failure detail.

## 0.1.0a30

### Breaking
- `PreviewOrderResult` now exposes typed `estimated_quote_debit` and
  `estimated_fee` (`Quantity`) instead of bare `estimated_quote_debit_scaled` /
  `estimated_fee_scaled` strings. Quote estimates carry `QuantityDomain.ORDER_QUOTE`
  and the pair's catalog quote scale; fee estimates use `ORDER_BASE` or
  `ORDER_QUOTE` according to `fee_asset`.
- Quote-budget encoding (`max_quote_debit`) always resolves the catalog
  `quote_quantity_scale` and rejects typed `Quantity` values that omit scale or
  mismatch the catalog. Prefer `Quantity.from_quote_scaled` /
  `from_quote_decimal` / `from_quote_decimal_str` with
  `QuantityDomain.ORDER_QUOTE`.
- Wire break: `PreviewOrderRequest` now wraps an `OrderIntent`
  (`subaccount_id` + `order`), matching create. The public
  `orders.preview_order(...)` kwargs stay the same create shape.
- Wire break: `TrailingStopTrigger` carries `side`. Standalone trailing create
  still validates sell-only, but encode always populates the wire field.
  Trigger decode surfaces type/side/`parent_order_id` for attached trailing
  stops (side is no longer hardcoded to sell).

### Added
- `QuantityDomain.ORDER_QUOTE` and `Quantity.from_quote_*` constructors.
- Local validation rejects create, cancel, and replace batches above 20 items.

### Fixed
- Transfer/withdraw `AssetAmount` encoding fails closed when neither the value
  nor request parameters provide a source scale (no silent e18 assumption).

### Clarified
- Preview is not deployed on every API host; handle unimplemented/not-found and
  do not make Preview a prerequisite for order submission.
- Market orders enforce slippage-derived price protection; see
  [Market Order Price Protection](https://polyester.ai/developer-docs/shared-concepts/market-order-price-protection).

## 0.1.0a29

### Changed
- README install pin catches up to the current alpha tag. No API changes from `0.1.0a28`.

## 0.1.0a28

### Breaking
- Replaced `fee_source` with `fee_asset` (`quote` or `base`) on trigger and trade models. The backend no longer emits the prior received-asset enum.

### Features
- Orders support explicit base-quantity or quote-budget (`max_quote_debit`) sizing. Create and preview results expose resolved base quantity, quote debit, fee asset, and estimates where returned by the API.
- Added `orders.preview_order(...)` and `is_batch_replace_settled(...)`.

### Fixed
- Batch-replace status decoding now rejects aggregate counts that do not reconcile with item phases.

### Clarified
- Batch-replace admission is not finality: predecessor IDs may be stale after admission, while status returns successor IDs and phases. Poll status for reconciliation, reuse the same `request_id` on retry, and do not treat `is_batch_replace_settled` as finality.

## 0.1.0a27

### Breaking
- Replaced `orders.batch_modify` with `orders.batch_replace`. The new write returns an admission receipt (`batch_request_id`, admission outcomes, and accepted/rejected counts), without behavior or partial-execution options. Poll `orders.get_batch_replace_status(batch_request_id=...)` for execution phases.

## 0.1.0a26

### Breaking
- Order lookup/mutation APIs take a typed `OrderKey` (`OrderId` | `ClientOrderId`) instead of dual optional `order_id` / `client_order_id` kwargs. Affects `orders.get`, `orders.cancel`, `orders.modify`, `wait_for_order_trades_complete`, and batch cancel/modify item dicts (`key=` instead of `order_id`/`client_order_id` fields).

### Fixed
- Reject market creates that also supply a limit `price`.
- Decimal price parsing stays exact (no float intermediate).
- TWAP trigger projection coverage for proto decode paths.

## 0.1.0a25

### Breaking
- `get_current_candle` returns `None` when no candle rows exist, matching Rust `Option<Candle>` instead of a synthetic empty `Candle`.

### Fixed
- Outbound HTTP/Connect/JSON-RPC requests send an explicit `User-Agent: polyester-sdk-python/<version>` instead of the default `python-httpx/*` / library identity, so edge WAF rules that ban browser signatures (Cloudflare error 1010) do not block the SDK before authentication.
- Cloudflare error 1010 responses are mapped to `PolyesterTransportError` with an explicit WAF message instead of being misclassified as `PolyesterAuthError`.
- Orderbook snapshots reject missing or invalid levels, and managed books reject malformed levels and invalid sequence ranges atomically without advancing.
- Regression coverage preserves the protocol's exact depth `1` and `1000` mappings.
- Singular cancel and lookup by client-order-id validate the documented identifier constraints before contacting the transport.
- API-key trading withdraws can be prepared, signed over exact deterministic protobuf bytes, persisted, restored, and submitted unchanged.
- Withdraw and internal-transfer amounts rescale exactly from their declared input scale to `amount_e18`.
- Mutation response-contract violations fail closed with `PolyesterResponseContractError`.
- Snapshot recovery drains post-snapshot publications atomically and coalesces orderbook gap refreshes into a bounded single-flight worker.

## 0.1.0a24

### Fixed
- Local orderbook bucketing rounds asks up and rejects negative prices/quantities instead of emitting corrupted levels.
- `cancel_all` / `cancel_all_after` response decoding rejects empty or unknown statuses (`submitted`/`dry_run`, `armed`/`disabled`) instead of returning success for ambiguous payloads. Cancel-all now also surfaces `failed_cancels`.
- Client order/trigger IDs and caller-supplied request IDs are trimmed and validated locally for documented length and ASCII-character constraints before a request is sent.

### Testing
- Decoder coverage asserts empty/unknown cancel-all and cancel-all-after statuses fail closed.
- Orderbook unit coverage asserts negative levels are rejected and ask buckets round up.

## 0.1.0a23

### Fixed
- Concurrent identical requests receive unique authentication timestamps with a five-second future-skew ceiling. Async Connect/realtime signing uses bounded cooperative backpressure; the synchronous low-level signer returns an immediate retryable capacity error instead of sleeping the caller's thread.

### Clarified
- Document that `client_order_id` on order create is API-optional; set a stable value when retrying after ambiguous mutation failures.

### Testing
- A 10,000-identical-request hardening probe verifies unique bounded authentication tuples while an independent event-loop timer continues to run.

## 0.1.0a22

### Fixed
- Batch-modify and batch-cancel decoding reconcile aggregate counts against per-item outcomes and reject unknown/ambiguous result states.
- Columnar candles reject misaligned OHLCV arrays instead of emitting empty fields.
- Deposit-address creation and singular lifecycle lookups reject missing required entities instead of returning placeholder models.
- User trades expose fee source and referral share, so received-asset fees can be distinguished from quote fees and BUY net quantity can be calculated correctly.
- Concurrent identical requests receive unique authentication timestamps with a five-second future-skew ceiling and bounded backpressure.

### Testing
- Public-service Connect fault injection covers inconsistent batch counts and misaligned candle columns in addition to decoder-level boundary tests.
- The funded BUY-to-SELL acceptance test waits for complete fill projection and sells net received base quantity after received-asset fees.

## 0.1.0a21

### Breaking
- Trading withdrawals require explicit non-empty `idempotency_key` and non-zero `nonce` values.
- Scale-dependent market data, orderbook, and Zipper supply paths require hydrated catalog scales instead of guessing.
- Low-level trigger, candle, realtime-candle, and local-orderbook codecs require an explicit quantity scale.

### Features
- `AsyncSubscription.set_on_error` exposes background transport and terminal feed errors.
- Retry classifiers and cryptographically random withdrawal key/nonce helpers are exported.

### Fixed
- Batch-create decoding rejects missing outcomes and inconsistent aggregate counts; unknown rejection enum values retain their numeric code.
- Realtime reconnects use capped exponential backoff with per-subscription jitter.
- Signing timestamps stay on wall clock during large concurrent bursts and malformed absolute URLs fail before send.
- Catalog hydration rejects conflicting symbol/asset identities atomically, preserves the previous valid snapshot after a rejected refresh, and accepts valid scale `0`; REST and realtime public trades carry catalog quantity-scale metadata.

## 0.1.0a20

### Breaking
- Removed the unused `max_retries` constructor/transport option. The SDK never performed automatic unary retries; applications must retry eligible transport/rate-limit failures with stable idempotency keys and reconcile mutation outcomes.

### Fixed
- ConnectRPC responses are capped at 4 MiB explicitly, including catalog hydration.
- The funded market roundtrip can use external order-book liquidity when dedicated maker credentials are unavailable, carries partial BUY fills into cleanup, and cancels only its own client order IDs.
- Live market reference-price helpers format typed `Price` values before decimal sizing.
- Removed an unused legacy JSON unary bridge that referenced a nonexistent authenticated transport method; all service calls remain generated binary ConnectRPC.
- Corrected kw-only `ApiData` construction in heatmap and zipped-supply realtime decoders.

### Testing
- Hardening coverage now injects corrupt and oversized protobuf catalog responses.
- Whole-source `mypy` is now a required CI gate for the advertised typed package.
- Tests that use non-dry-run `cancel_all` require an explicit dedicated-account cleanup gate.

## 0.1.0a19

### Fixed
- Realtime HTTP 401/403 errors now expose `code`, `context`, and `endpoint` in addition to the existing status/label/body fields.
- Snapshot reconnect retries retain buffered publications across failed attempts and close the replacement WebSocket when cancellation interrupts refresh.
- Oversized WebSocket messages fail closed instead of entering a reconnect loop.
- Every live-test and smoke path now uses `POLYESTER_TEST_TRADE_SYMBOL`; legacy smoke-symbol variables are no longer consulted.

### Testing
- Added oversized-message and combined reconnect/retry/cancellation fault-injection regressions.

## 0.1.0a18

### Breaking
- `wait_for_catalogs()` now raises when catalog hydration fails (HTTP errors, empty/malformed spot or zipper, out-of-range scales/ids). Previously returned successfully after a best-effort failure. Use `catalogs_last_error` to inspect the failure.
- `format_qty_scaled` / `format_ledger_u128` / `Quantity.format` / `AssetAmount.format` raise `PolyesterValidationError` when `scale > MAX_PROTOCOL_SCALE` (36) instead of allocating pathological padding.
- Realtime token HTTP 403 maps to `PolyesterAuthError` with `status_code`, `label`, and truncated `body` (not opaque `PolyesterRealtimeError("… HTTP 403")`).

### Features
- `MAX_PROTOCOL_SCALE = 36` exported; catalog hydrate rejects `u64→u32` truncation and scales above the protocol max.
- `CatalogManager.hydrate_zipper_config_typed` accepts typed `DepositWithdrawConfig` without a consumer JSON round-trip.
- `wait_for_order_trades_complete` / `orders.wait_for_order_trades_complete` poll until sum(trade qtys) equals order `cum_qty` or timeout.
- JSON-RPC client enforces a 1 MiB response body cap and validates `jsonrpc=="2.0"`, matching `id`, and exactly one of `result`|`error`.
- `AsyncSnapshotThenStreamSubscription.last_error` / `err()` surfaces snapshot refresh failures; one bounded reconnect retry then fail-closed.
- `AsyncRealtimeClient.aclose` cancels tracked subscriptions; WebSocket inbound frames bounded by `WS_MAX_MESSAGE_BYTES`.

### Fixed
- Realtime token fetch and JSON-RPC request/arequest now enforce one absolute wall-clock deadline across headers + bounded body collect (slow-drip safe). Sync JSON-RPC uses a deadline closer that aborts the client without leaking worker threads.
- Realtime token exchange streams and size-caps the body under the HTTP client timeout.
- `TransportFactory` / `TransportConfig` `__repr__` redacts credentials (parity with credential repr).

### Testing
- Local public-API hardening L2 suite (`tests/hardening/`) for token stall/403, JSON-RPC, catalogs, snapshot, and scale.
- Live harness: STRICT_LIVE fail-on-skip + executed/skipped/failed counts; `POLYESTER_TEST_TRADE_SYMBOL`; market BUY→SELL roundtrip carries filled qty; BatchModify 5×40 regression (gated).

## 0.1.0a17

### Breaking
- `AssetBalance` drops `trading_updated_at_ns` / `funding_updated_at_ns` / `reserved_updated_at_ns`. Use `trading_revision` (orders trading/reserved/available) and `funding_revision` (orders funding independently) instead.
- `CatalogManager.base_quantity_scale_for_symbol` / `_id` return `None` when unknown/unhydrated instead of inventing scale `8`. Decode-only paths (orderbook/market data) keep an explicit `or 8` fallback.

### Fixed
- Order/trigger write paths auto-await `wait_for_catalogs` before resolving pair quantity scale, preventing first-order false `INSUFFICIENT_FUNDS` when ETH-USDT (scale 6) was encoded at invented scale 8.

## 0.1.0a16

### Fixed
- Realtime now negotiates the `centrifuge-protobuf` WebSocket subprotocol and uses binary, length-delimited Centrifugo commands, replies, pings, and publications. Previous releases selected `:proto` channels while speaking the JSON client protocol, so subscriptions could handshake but receive no binary publications.
- Concurrent authenticated calls now receive distinct monotonic signing timestamps, preventing identical same-millisecond requests from colliding with replay protection.
- BUY trailing-stop requests are rejected locally because the wire strategy is SELL-only; they are no longer silently encoded as SELL.
- Authentication failures without server detail now carry a non-empty fallback message.
- `ApiKeyCredentials` / `Ed25519Keypair` repr output redacts private key material.
- Realtime subscription-token HTTP exchange rejects response bodies larger than 64 KiB.
- Public ID parsing prefers canonical base58 when an all-digit string round-trips via `format_id`.
- Quantity scale resolution no longer silently defaults to 8 when catalogs/symbol are missing for decimal qty.
- WebSocket read timeout is treated as connection death (reconnect / error), not a silent continue.
- Subscriptions expose `resubscribed` / `take_resubscribed()` after reconnect gaps.
- Candle subscriptions normalize aliases (`MIN_1` / `min1`) to the live channel label (`1m`).

## 0.1.0a15

### Breaking
- `TriggerEventsList.next_before_ts_ns` renamed to `next_page_token` (opaque API cursor; no longer timestamp-shaped)
- `triggers.list_events(..., before_ts_ns=...)` renamed to `page_token=...` and now sets the proto `page_token` field

### Fixed
- `TriggersList` and `TriggerEventsList` expose `next_page_token` from the API so trigger list/event pagination can continue
- JSON wire decode for trigger events maps `fire_price_ticks` onto `fire_px` (was a broken `fire_px_ticks` kwarg)

## 0.1.0a14

### Breaking
- Stable MFA auth error codes: `AUTH_API_KEY_MFA_REQUIRED` is removed; use `AUTH_MFA_NOT_ENROLLED`, `AUTH_STEP_UP_REQUIRED`, `AUTH_MFA_ELEVATION_REQUIRED`, and `AUTH_MFA_LAST_FACTOR_REQUIRED` from `AuthErrorDetail`
- Removed JWT/session-only account-admin RPCs from the API-key SDK surface. Use the TypeScript browser client for interactive account administration.
  - Policies: unary create/update/delete/list/get/set removed; keep `subscribe_subaccount_policies` / `subscribe_api_policies`
  - API keys: `create` / `update` / `delete` removed; keep `list` / `get` / `subscribe` / `generate_keypair`
  - Subaccounts: create/update/delete and member/invite mutations removed; keep reads + `subscribe` / `subscribe_api_keys`
  - Address book: entry/tag mutations removed; keep list/get/view/subscribe
  - Profile: `get` / `update` / `get_username_history` removed; keep `subscribe_identity`
  - Account resolve (`client.resolve` / `client.accounts`) removed entirely

### Features
- `is_mfa_enrollment_required` / `is_step_up_required` / `is_mfa_elevation_required` / `is_mfa_last_factor_required` classify MFA control flow from structured auth codes only (no message heuristics)
- Public method options expose `polyester.api.MFARequirement` documentation metadata
- `policies.subscribe_api_policies` typed subscribe for `private:auth:api-policies:{account_id}:proto` (sync: `subscribe_api_policies_sync`)

### Testing
- Unit coverage for MFA auth-code mapping and predicates
- Unit coverage for API/subaccount policy realtime protobuf decode
- Live trigger create asserts `status == "accepted"`

### Changed
- CI no longer auto-commits `sdk-capabilities.json` / README on pull requests. Capability refresh + optional bot commit runs only on merge to `main`.
- README capability matrix labels clarify API-key-safe account surfaces (reads/subscribe vs session-only admin)
- Realtime subscribe waits for the Centrifugo handshake (including private token fetch) before returning; initial auth failures are returned immediately

## 0.1.0a13

### Breaking
- wire break: order and trigger creation now target explicit execution variants. The flat `order_type`/`tif`/`post_only`/`price` inputs are still accepted on `CreateOrderRequest` but are mapped onto the new `OrderIntent` execution oneof (`market_ioc`/`limit_gtc`/`limit_ioc`/`limit_fok`); `post_only` is only valid for limit-GTC and is rejected otherwise
- `CreateOrderRequest` now wraps an `OrderIntent` (`subaccount_id` + `order`); batch create items are `OrderIntent`s and the removed `allow_partial` argument is accepted but ignored
- `triggers.create` maps flat params onto the new `TriggerIntent` strategy oneof (`stop_loss`/`take_profit` conditional, `trailing_stop`, `twap`, `ladder`); trailing stops are always SELL market-IOC, ladder distribution only accepts `linear`, and `trigger_price_source` is dropped from the wire
- `CreateOrderResponse` / `CreateTriggerResponse` no longer carry a `status` field; admitted mutations synthesize `status="accepted"`
- Batch-create result items now use an `accepted`/`rejected` oneof, projected back onto the flat `status`/`order_id`/`code` result model
- `Trigger` read model now exposes full proto fields (order params, timestamps, detail blocks, `post_only`, `parent_order_id`, child order ids)
- `Order` read model adds `post_only` and `attached_risk`
- `triggers.list` accepts validated `status` filter labels (`created`/`armed`/`running`/`completed`/`cancelled`/`failed`/`paused`)

### Fixed
- Order/trigger decode reads the shapes: attached-risk legs derive `order_type`/`limit_price` from their `RiskExecution` child, and the thick `Trigger` projection is rebuilt from the configuration oneof + runtime detail blocks
- `orders.get` / list with `include_attached_risk=True` now returns policy data on `Order.attached_risk`

## 0.1.0a12

### Fixed
- `CreateSubaccountResult.revision` is returned from create so clients can pass `expected_revision` on the next mutation without a follow-up read

## 0.1.0a11

### Breaking
- Durable auth PATCH contract: subaccount, API key, subaccount/API policy, and address-book entry updates require nested mutable specs, a non-empty FieldMask, and a positive `expected_revision` from a prior read
- Policy creates nest fields under `policy` (optional `sub_account_id` / `assign_to_key_id` remain on the outer request)
- Soft-delete subaccount requires `expected_revision`; update APIs are presence-aware via omitted kwargs / `UNSET` so `""`, `[]`, `false`, `0`, and null timestamp clears survive
- Address-book entry updates no longer accept `new_tags` (mutable paths: `label`, `note`, `tag_ids`); tag updates remain optional `name` / `color` without revision/mask
- Durable resource models expose `revision`; Connect `AuthErrorDetail` maps `AUTH_REVISION_CONFLICT` onto `PolyesterApiError.code`

### Testing
- Live funded UserOp tests: Funding → Trading (`TradingGateway.deposit`) and Funding → external (`withdrawToChain`), gated by `POLYESTER_TEST_CHAIN_USEROP=1`
- Unit coverage for nested FieldMask request construction, presence/clear semantics, revision decode, and revision-conflict error mapping

### Changed
- Realtime (`websockets`) and on-chain Funding helpers (`eth-abi` / friends) are required dependencies, not optional extras. Empty `[realtime]` / `[chain]` extras remain for install compatibility.

## 0.1.0a10

### Features
- Optional `[chain]` smart-account path: CREATE2 Safe prediction, ERC-4337 UserOp submit (bundler + paymaster), Funding → external / Funding → Trading calldata, Zipper fee quote, and full FundingAccount / GuardRegistry whitelist encoders
- Realtime delivery is fail-closed on queue overflow (`PolyesterRealtimeOverflowError`); managed snapshot-then-stream subscriptions refresh Connect snapshots on reconnect and expose recovery hooks

### Changed
- Connect RPC coverage gate no longer commits dashboard reports under `docs/`; CI fails on unexpected gaps only (`sdk-coverage.toml` + `scripts/check_sdk_coverage.py`)

### Docs
- README `Supported surface` table is generated from `sdk-capabilities.json` (`--write-capabilities`); links to the public [SDK capability matrix](https://polyester.ai/docs/developer-docs/getting-started/sdk-capability-matrix)
- CI auto-commits refreshed `sdk-capabilities.json` + README capability table when they drift (same-repo)
- README documents on-chain Funding UserOps (caller-supplied owner EOA → derive Polyester Safe) vs Trading withdraw RPCs; realtime overflow / reconnect recovery contract

### Testing
- Live smokes on Polyester testnet: Funding → Trading UserOp (`TradingGateway.deposit`) and Funding → BSC USDT withdraw (`withdrawToChain`) via owner-key smart account

## 0.1.0a9

### Features
- Realtime, orderbook, and market-overview subscriptions support `async with` for automatic cleanup
- Connect RPC wrapper coverage gate: `scripts/check_sdk_coverage.py` + `sdk-coverage.toml`

### Docs
- README realtime examples use `async with` instead of manual `try` / `finally` / `aclose()`

## 0.1.0a8

### Breaking
- Authoritative freshness: `Order.state_revision` → `Order.version`; balance `trading_version` / `funding_version` / `reserved_version` → `trading_updated_at_ns` / `funding_updated_at_ns` / `reserved_updated_at_ns`; subaccount and API-key `updated_at` are configuration timestamps; API-key `last_used_at` stays independent activity time

### Features
- Generated reconciliation and policy types exposed in the public SDK surface
- Internal transfer amounts use U128 wire types end-to-end

## 0.1.0a7

### Breaking
- Dual-path qty/price scalars: reads expose typed `price` / `qty` domain values (`.ticks` / `.scaled`) instead of primary digit-string `price_ticks` / `qty_scaled` fields
- Order, trigger, transfer, and withdraw writes accept human decimals (`str` / `Decimal`) or bot scaled inputs (`Price` / `Quantity` / `AssetAmount`); excess precision is rejected (no silent `ROUND_DOWN`)

### Money types
- New `Price`, `Quantity`, and `AssetAmount` helpers for human decimal and scaled/tick paths, with compatibility checks when reusing read values on writes

### Docs / examples
- README documents human vs bot dual-path usage

### Testing
- Unit coverage for money conversion, bounds, and mismatch rejection
- Funded/integration asserts updated for typed price/qty reads
- Skip transfer-to-user smoke on Connect `"Request timed out"` as a devnet unavailable signal

## 0.1.0a6

### Breaking
- Removed private `ledger.write.v1` / `client.ledger_write` from the public SDK (not in `public.files.txt`)

## 0.1.0a5

### Triggers
- `triggers.create()` exposes the full `CreateTriggerRequest` surface, unblocking `TRAILING_STOP`, `TWAP`, and `LADDER` creation via the SDK: `fee_asset`, `self_trade_prevention_mode`, `trailing_distance_ticks`/`trailing_distance_bps`, `activation_price`, `max_slippage_ticks`/`max_slippage_bps`, `twap_duration_ms`/`twap_slice_interval_ms`, `ladder_price_min`/`ladder_price_max`, `ladder_levels`, and `ladder_distribution`
- `trigger_price` is now optional on `create()` (not required for trailing/TWAP/ladder types)

### Testing
- Unit tests for advanced trigger param mapping (`tests/unit/test_triggers_codecs.py`)
- Devnet mutation e2e proving trailing stop, TWAP, and ladder creation through the SDK (`tests/e2e/test_advanced_trigger_creation.py`)

## 0.1.0a4

### Breaking
- `orders.cancel_all()` no longer accepts `max_orders`; the field was removed from the public proto and server no longer honors it

### Orders
- Market orders: pass `market_client_ref_price` on `create()` when the orderbook may be empty (required for IOC market buys on devnet)
- Proto gen bump (2026-07-03 bundle) aligned with server contract

### Realtime
- Auto-reconnect on Centrifugo disconnect with 30s read timeout (matches Go SDK behavior)

### Testing
- Market order mutation e2e (single-account IOC buy/sell on devnet)
- Market order fill e2e and spot fill e2e with optional maker credentials (`POLYESTER_TEST_MAKER_*`)
- Realtime reconnect unit test; integration batch excludes duplicate realtime runs
- `test_balances_get_health` marked optional when route is not mounted

## 0.1.0a3

### Codecs
- Decode candle OHLC from wire price ticks (1e6) to decimal strings, matching the TypeScript SDK surface
- Decode candle volume using the pair's `base_quantity_scale` from spot config when catalogs are loaded

## 0.1.0a2

### Documentation
- README: remove stale hardcoded alpha version from PyPI project description
- Align `polyester.__version__` with package metadata

## 0.1.0a1

### SDK surface
- Orders: `batch_create`, `batch_cancel`, `cancel_all_after`; `cancel(symbol=…)` resolves `symbol_id`
- API keys: `create`, `update`, `delete`
- Withdraw: `create_wallet_trading_withdraw`
- Address book: full CRUD, views, whitelist, counterparties
- New services: `policies`, `sub_accounts`, `guard_signer`
- `market_overview.create_subscription()`: snapshot-then-stream merge (TS parity)

### Codecs
- Proto decode migration for balances history/equity/holds, triggers, transfers, deposit, withdraw, internal transfers, api keys, resolve, and public market services
- `order_mutation_from_proto` handles `CancelOrderResponse` (no `client_order_id` field)

### Realtime
- Centrifugo heartbeat: reply to `{}` ping frames with `{}` pong (fixes websocket `3012 no pong` disconnects)
- Graceful stream teardown without unhandled background task exceptions

### Dependencies
- Pin `connectrpc<0.11` (protobuf stub compatibility)

### Testing
- Restructured `tests/unit`, `tests/integration`, `tests/e2e`, `tests/e2e/funded`
- Pytest markers: `integration`, `smoke`, `mutation`, `funded`, `treasury`, `optional`, `realtime`
- `POLYESTER_TEST_TRADE_SYMBOL` for order/trigger mutation (separate from `POLYESTER_TEST_SMOKE_SYMBOL`)
- Dynamic mutation pricing from `market_overview` (~2% of last trade)
- `test_orders_get_round_trips_list_open`: proof-style when open orders exist
- `scripts/test_all.sh` and `scripts/smoke_test.py` (pytest wrapper)
- `scripts/smoke_realtime.sh`: unit realtime tests + live Centrifugo heartbeat (~35s)
- Unit tests for Centrifugo ping/pong and batched frames
- Integration test holds a public trades subscription past Centrifugo heartbeat interval
- CI: `pytest tests/unit` with coverage on non-`gen/` code
- Full devnet suite documents honest skips for OMS read lag, JWT routes, optional mounts, and account-specific prerequisites

## 0.1.0a0

- Initial alpha release with core trading and market data services.
