# Changelog

## Unreleased

- **Breaking:** An API key of the main account reads `subaccount_id == ""`, as the Go and Rust SDKs read it, whether the server leaves `subaccount_id` unset or sends an explicit 0. It read `"0"`, which is not a sub-account ID. A key scoped to a sub-account still reads that sub-account's public ID. The JSON-dict decoder `decode_api_key` now reads a key exactly as the binary decoder does: it read `subaccount_id` as the decimal of the protobuf JSON (`"42"`) instead of the public ID, and dropped `policy_id`, `ip_whitelist`, `expires_at`, `public_key_ed25519`, `created_at`, `last_used_at` and `updated_at`; a dict that is not a valid `auth.v1.ApiKey` raises `PolyesterResponseContractError`. Migration: test a main-account key with `not key.subaccount_id` (or `== ""`) instead of `== "0"`; equality and serialization of `ApiKeySummary` leave out `subaccount_id` for a main-account key. Affected: `api_keys.list`, `api_keys.get` and `api_keys.subscribe`, the API keys of `sub_accounts.get` and `sub_accounts.subscribe_api_keys`, on `AsyncPolyester` and `Polyester`; `polyester.codecs.decode.api_keys.api_key_from_proto`, `api_keys_list_from_proto` and `get_api_key_from_proto` (alias `api_key_from_get_proto`), `polyester.codecs.decode.sub_accounts.get_subaccount_from_proto`, `polyester.codecs.realtime_decode.decode_api_key_bytes`, and `polyester.codecs.wire_decode.decode_api_key` and `decode_api_keys_list`.
- **Breaking:** API keys read back how they are shown and who created them: `ApiKeySummary` gains `icon`, the user-chosen icon or emoji, `color`, the user-chosen color token, both as sent (at most 32 characters each), and `created_by_actor`, the read-only label of who created the key, such as a username or account label. Each is `""` when the server sends none. They were dropped although the server sends them. Migration: equality and serialization of `ApiKeySummary` now include `icon`, `color` and `created_by_actor` when set; compare or store the fields you need instead of whole keys. Affected: `api_keys.list`, `api_keys.get` and `api_keys.subscribe`, the API keys of `sub_accounts.get` and `sub_accounts.subscribe_api_keys`, on `AsyncPolyester` and `Polyester`; `polyester.codecs.decode.api_keys.api_key_from_proto`, `api_keys_list_from_proto` and `get_api_key_from_proto` (alias `api_key_from_get_proto`), `polyester.codecs.decode.sub_accounts.get_subaccount_from_proto`, `polyester.codecs.realtime_decode.decode_api_key_bytes`, and `polyester.codecs.wire_decode.decode_api_key` and `decode_api_keys_list`.

## 0.24.0

Git tag: `v0.24.0`. Released 2026-11-12. Built on public contract `e339360`.

- **Breaking:** Each entry of an address-book view keeps its own `revision`, the value to pass as `expected_revision` to `update_entry`, as `list_entries` already did. `ExternalAddressBookEntryView` and `InternalAddressBookEntryView` gain `revision`; it was dropped although the server sends it, so updating an entry from the view needed another read. It is 0 when the server sends none, and it is the entry's revision, never the view's `view_revision`. Migration: equality and serialization of `ExternalAddressBookEntryView` and `InternalAddressBookEntryView` now include `revision`; compare or store the fields you need instead of whole entries. Affected: `address_book.get_view` on `AsyncPolyester` and `Polyester`; `polyester.codecs.decode.address_book.external_entry_view_from_proto`, `internal_entry_view_from_proto`, `entries_view_from_proto` and `address_book_view_from_proto`.
- **Breaking:** API keys read back with their restrictions: `ApiKeySummary` gains `policy_id`, the public ID of the attached API policy in the form of `ApiPolicy.id` (`""` when none is attached, and then the key has no permissions); `ip_whitelist`, the CIDR allowlist as sent (`[]` for no IP restriction); `expires_at`, the UTC `datetime`, to the microsecond, after which the key cannot authenticate whatever its status (`None` when it does not expire); and `public_key_ed25519`, the hex of the key's Ed25519 public key (`""` when none is sent). They were dropped although the server sends them. Migration: equality and serialization of `ApiKeySummary` now include `policy_id`, `ip_whitelist`, `expires_at` and `public_key_ed25519` when set; compare or store the fields you need instead of whole keys. Affected: `api_keys.list`, `api_keys.get` and `api_keys.subscribe`, the API keys of `sub_accounts.get` and `sub_accounts.subscribe_api_keys`, on `AsyncPolyester` and `Polyester`; `polyester.codecs.decode.api_keys.api_key_from_proto`, `api_keys_list_from_proto` and `get_api_key_from_proto` (alias `api_key_from_get_proto`), `polyester.codecs.decode.sub_accounts.get_subaccount_from_proto`, and `polyester.codecs.realtime_decode.decode_api_key_bytes`.
- **Breaking:** An order admitted by a batch replace keeps that batch's ID: `Order` gains `batch_request_id`, the public ID that `orders.batch_replace` returned as `BatchReplaceResult.batch_request_id`, exact for every 64-bit ID, and `""` for an order of any other origin (the contract's 0), never a made-up `"0"`. It was dropped although the server sends it. Migration: equality and serialization of `Order` now include `batch_request_id` when set; compare or store the fields you need instead of whole orders. Affected: `orders.get`, `orders.list_open`, `orders.list_history`, `orders.wait_for_order_trades_complete` and `orders.subscribe` on `AsyncPolyester` and `Polyester`; `polyester.codecs.decode.orders.order_from_proto`, `scaled_order_from_proto`, `get_order_from_proto` and `orders_list_from_proto`, and `polyester.codecs.decode.private_orders.private_orders_from_proto` and `private_orders_unit_from_proto`.

## 0.23.0

Git tag: `v0.23.0`. Released 2026-11-12. Built on public contract `e339360`.

- **Breaking:** API keys now need an account permission on their API-key policy for deposit addresses, sub-accounts and Guard Signer status, and for the main account's address book. Any active key could make these calls before, with or without a policy. The new permissions are `CREATE_DEPOSIT_ADDRESS` (`deposit.create_address`), `READ_DEPOSIT_ADDRESSES` (`deposit.list_addresses`), `READ_SUBACCOUNTS` (`sub_accounts.list`, `sub_accounts.get`), `READ_SUBACCOUNT_ACTIVITY` (`sub_accounts.list_activity`), `READ_SUBACCOUNT_MEMBERS` (`sub_accounts.list_members` and the members of `sub_accounts.get`), `READ_SUBACCOUNT_INVITES` (`sub_accounts.list_invites` and the invites of `sub_accounts.get`) and `READ_GUARD_SIGNER_STATUS` (`guard_signer.get_status`); a key scoped to the main account also needs `READ_ADDRESS_BOOK` (or `MANAGE_ADDRESS_BOOK`) for the main account's book. A key without the permission raises `PolyesterApiError` with `auth_error_code(err) == "AUTH_API_KEY_ACCESS_DENIED"` naming the permission (the address book: `AUTH_SUBACCOUNT_ACCESS_DENIED`); `sub_accounts.get` leaves out members and invites the key may not read. `guard_signer.get_status` no longer answers an API key for a sub-account another main account shares with yours. Policy subscriptions report the new permissions by name (`read_subaccounts`). This is a server change: no SDK code changed, and the docstrings and README name the permission each call needs. Affected: `deposit.create_address`, `deposit.list_addresses`, `sub_accounts.list`, `get`, `list_activity`, `list_members`, `list_invites`, `guard_signer.get_status`, and the main account's `address_book.list_entries`, `list_transfer_counterparties`, `list_transfer_destinations`, `list_internal_transfer_whitelist_entries`, `get_withdraw_whitelist_view` and `get_view`, on `AsyncPolyester` and `Polyester`. Migration: attach an API-key policy that grants these permissions to every key that makes these calls (existing policies were granted them when the change was deployed); keep them when you rewrite a policy's whole action list; read a shared sub-account's Guard Signer status with a key of the main account that owns it.
- `get_version()` on `AsyncPolyester` and `Polyester` returns the build the API serves (`system.v1.SystemService/GetVersion`) as the new `ServerVersion`: `version`, the full source `commit` and the `environment` that answered, all plain strings, so an environment this SDK does not know still reads. A build after a release reads like `0.10.0-12-g4e21a2f09670`; `release` is the part before the first `-`. It needs no API key and sends none. Affected: `AsyncPolyester.get_version` and `Polyester.get_version` (new), `polyester.models.ServerVersion` (new).
- `withdraw.get_wallet_balances()` (also `trading_withdraws`) reads the zTokens of the account's smart account wallet live from Polyester Chain (`chain.withdraw.v1.WithdrawService/GetWalletBalances`): a withdrawal Zipper rejects is refunded there, net of its kept fee. It returns `WalletBalances` (`smart_account_address`, `balances`), each `WalletBalance` with `zipped_asset_id`, `unified_asset_id`, `chain_id`, `ztoken_address`, the exact `amount_e18` and `amount` in whole units. `sub_account_id=` (or the client default) selects a sub-account. An API key needs `READ_BALANCES`. Affected: `withdraw.get_wallet_balances` on `AsyncPolyester` and `Polyester` (new), `polyester.models.WalletBalance` and `WalletBalances` (new), `codecs.decode.withdraw.wallet_balances_from_proto` (new).
- Price alerts, available on devnet and not yet routed on testnet: `client.alerts` wraps `alerts.v1.PriceAlertService` with `create`, `list`, `iter_alerts`, `update` and `cancel`. An alert watches one market's last or index price and fires once when it crosses the alert price (`"above"`: >=, `"below"`: <=), delivered in-app and/or to the linked Telegram account. Markets resolve by name or `symbol_id`; prices are exact `Price` values, and a `Price` bound to another market, or bound to any market when the catalogs don't know the `symbol_id`, is refused before sending. `update` changes only the fields it is given; with none it sets a triggered alert again. `create` and `update` take an optional `idempotency_key` that makes sending them again safe. Alerts belong to the main account: an API key scoped to a sub-account raises `PolyesterAuthError` with `code` `SUBACCOUNT_KEY_REFUSED`. Other refusals keep their contract code: `PRICE_UNAVAILABLE` raises a retryable `PolyesterServerError` (nothing changed); `SERVICE_UNAVAILABLE` raises a `PolyesterServerError` whose outcome is unknown for a create, update or cancel, as for other services (send a create or update again with the same `idempotency_key`, cancel again, or read back); the rest raise `PolyesterApiError`. Affected: `AsyncPolyester.alerts` and `Polyester.alerts` (new), `polyester.models.alerts.PriceAlert`, `PriceAlertsPage` and `PriceAlertUpdate` (new).
- Withdrawal refusals carrying a `chain.withdraw.v1.ErrorDetail` raise the new `PolyesterWithdrawError`, a `PolyesterApiError` with the same `code`, plus `field_path` (the request field to fix), `min_floor_e18` and `min_floor` (`ERROR_CODE_MIN_AMOUNT_BELOW_FLOOR`) and `payable_from` (`ERROR_CODE_EXTERNAL_DESTINATION_COOLING_DOWN`: a broker vault's destination whitelisted less than 24 hours ago, payable from that time; not a whitelist error and not retryable at once). The contract adds `ERROR_CODE_DESTINATION_INVALID`, `ERROR_CODE_ROUTE_UNSUPPORTED`, `ERROR_CODE_VERSION_CONFLICT`, `ERROR_CODE_MIN_AMOUNT_BELOW_FLOOR` and `ERROR_CODE_EXTERNAL_DESTINATION_COOLING_DOWN`. Affected: every withdraw method that the server refuses with that detail, such as `withdraw.create_to_external_chain`, `withdraw.create_wallet_trading_withdraw` and `withdraw.validate_destination`; `polyester.PolyesterWithdrawError` (new). Only an auto-withdraw rule change, which needs an interactive session and this SDK does not wrap, is refused with `ERROR_CODE_MIN_AMOUNT_BELOW_FLOOR` today.
- `SpotConfig.assets` lists each spot-config asset as the new `SpotAssetConfig` (`asset`, `ledger_id`, `name`, `quantity_scale`, `quantity_display_decimals`, `market_data_volume_scale`, `included_in_equity`). `included_in_equity` says whether the asset counts in total equity; it is `None` when the server does not say, never `False`. Affected: `market_data.get_spot_config` and `codecs.spot_config.spot_config_from_dict`; `polyester.models.SpotAssetConfig` (new).
- API keys report their `purpose`: `"standard"` for the user's keys, `"assistant"` for keys of the Polyester assistant, `""` when unset. Affected: `ApiKeySummary.purpose` from `api_keys.list`, `api_keys.get` and the API-key subscriptions.
- Lifecycle flows read the reason `zipper_compliance_transferred`; it read `unknown_reason_<n>`. A withdrawal Zipper rejects now ends `refunded` with the same `zipper_validation_rejected` or `zipper_execution_rejected` reason instead of `failed`: accept both. Affected: `LifecycleFlowSummary.lifecycle_reason` from `lifecycle.list_flows`, `lifecycle.get_flow` and their streams.
- `social_verification.get(provider="telegram")` reads a Telegram link: `STATUS_AWAITING_CONFIRMATION` while it waits for the user, with the `handle` of the Telegram account that sent the code. An API key reads the link status only, so `displayName` and `providerUserId` stay empty. Starting, marking ready, confirming and unlinking a Telegram link need an interactive session. Affected: `social_verification.get`; `start` and `mark_ready` accept `provider="telegram"`.
- **Breaking:** `AUTH_REPLAY_DETECTED` (REST `REPLAY_DETECTED`, HTTP 401) raises a final `PolyesterAuthError` with that `auth_error_code` and `status_code` 401; over ConnectRPC it raised a plain `PolyesterApiError`. The server refuses with it a signed trading WebSocket login whose nonce was already used; this SDK sends none, and a replayed signed HTTP request is still refused as `AUTH_SIGNATURE_INVALID`: `is_retryable_error` reports `False`. The new constant `polyester.AUTH_REPLAY_DETECTED` is in `API_KEY_AUTH_ERROR_CODES`. Affected: `auth_error_code`, `is_retryable_error`; `polyester.errors.API_KEY_AUTH_ERROR_CODES`; `polyester.AUTH_REPLAY_DETECTED` (new). Migration: catch it as `PolyesterAuthError`; an `except PolyesterApiError` that relied on it no longer catches it.
- The contract's new names read as such with no SDK change: transfer code 1075 `withdraw_failed` (a failed withdrawal's debit) in transfer history and streams, the auth codes `AUTH_ASSISTANT_KEY_*` from `auth_error_code`, and the rate-limit classes `ASSISTANT_MESSAGE`, `ASSISTANT_CONTROL` and `ASSISTANT_READ` in `RateLimitDetail.policy_class`; tests pin them. Request signing needs no change: the SDK never sent `X-API-NONCE`, and the private order stream authenticates with a signed token request over an unsigned WebSocket upgrade, which the single-use upgrade nonces do not affect. Affected: `transfers.list`, `transfers.subscribe`, `auth_error_code`, `PolyesterRateLimitError.detail`.
- `orders.cancel_all` and `orders.cancel_all_after` say what they leave running: standalone triggers keep running and can place orders, and an attached leg whose exit order they cancel ends, with its OCO siblings. `orders.stop_all_trading` cancels triggers first. Affected: docstrings and README only.
- `sdk-coverage.toml` drops the removed `DisableAutoWithdrawRule` and says why the new calls this SDK does not wrap stay out: the assistant, assistant keys, Telegram confirm and unlink, and auto-withdraw pause and resume accept only an interactive session; the auto-withdraw run preview accepts API keys but is not wrapped, like the other auto-withdraw reads; Quick Swap referrals are outside the API-key SDK. The capability table gains server version and price alerts.
- **Breaking:** The generated `chain.withdraw.v1` `AutoWithdrawService` client loses `DisableAutoWithdrawRule` and its request and response messages, which the public contract removed, and gains `SetAutoWithdrawRuleEnabled` and `PreviewAutoWithdrawRun`. Affected: the generated auto-withdraw client and messages. Migration: pause or resume a rule with `SetAutoWithdrawRuleEnabled` from an interactive session; API keys could never call either.

## 0.22.0

Git tag: `v0.22.0`. Released 2026-11-12. Built on public contract `a3e3784`.

- **Breaking:** A trigger read back from `triggers.get`, `triggers.list` or `triggers.subscribe` reports the slippage cap of a market TWAP and of a trailing stop on its top-level `max_slippage` (ticks, as a `Price` delta) and `max_slippage_bps`, as it already did for a stop-loss or take-profit market child. A market TWAP's per-slice cap (`TwapMarketIoc.max_slippage`) was dropped, so a TWAP saved with `max_slippage_bps=50` or `max_slippage_ticks=25_000_000_000` read back as if it had no cap; a trailing stop's cap read back only under `details.trailing`, with the top-level fields empty. The variant sent is kept: a cap in ticks fills `max_slippage` and leaves `max_slippage_bps` at `0`, a cap in basis points the reverse, and a trigger saved without a cap leaves both unset, which means the pair's default market slippage, not an unprotected order. `details.trailing` is unchanged. Affected, on `AsyncPolyester` and `Polyester`: `triggers.get`, `triggers.list` and `triggers.subscribe`; the `Trigger` model; `polyester.codecs.decode.triggers.trigger_from_proto`, `triggers_list_from_proto` and `get_trigger_from_proto`, and `polyester.codecs.realtime_decode.decode_trigger_bytes`. Migration: code that read a non-zero top-level cap as a stop-loss or take-profit child's should check `trigger_type`; read `max_slippage` and `max_slippage_bps` for every trigger type instead of `details.trailing`.
- **Breaking:** A sub-account update says when the caller lost access, as the contract's `Subaccount.removed` does. `SubAccount` gains `removed`, true when the caller can no longer access the sub-account, for example after its owner removed the caller as a member: drop it from the caller's list. A removal's role is the contract's `SUBACCOUNT_ROLE_UNSPECIFIED` and now reads as an empty `role`; it read as `viewer`, so a removal from `sub_accounts.subscribe` looked the same as an active viewer update with the same `revision` and `updated_at`. A role the server does not set now reads as an empty `role` on sub-account members and invites too. Reads never set `removed`. Affected, on `AsyncPolyester` and `Polyester`: `sub_accounts.subscribe`, `sub_accounts.list`, `sub_accounts.get`, `sub_accounts.list_members` and `sub_accounts.list_invites`; the `SubAccount` model; `polyester.codecs.decode.sub_accounts.subaccount_from_proto`, `subaccount_member_from_proto` and `subaccount_invite_from_proto`, and `polyester.codecs.realtime_decode.decode_subaccount_bytes`. Migration: on an update with `removed` true, remove the sub-account instead of applying its fields; compare `role` with `""` where you compared it with `"viewer"` to spot a missing role.
- **Breaking:** `triggers.create` refuses an order type other than `limit` on a ladder with `PolyesterValidationError` (`order_type='market' does not apply to a ladder: a ladder places limit GTC orders only; pass order_type='limit' or leave it out`), before anything is sent. The contract's ladder places LINEAR limit GTC orders only and has no market execution, so `trigger_type="ladder", order_type="market"` created a ladder of resting limit orders without an error. `order_type` now defaults to `None`: a ladder created without one works as before, and a stop-loss, take-profit, trailing stop or TWAP without one is a market child, as with the old default `"market"`. Affected, on `AsyncPolyester` and `Polyester`: `triggers.create`; `polyester.codecs.triggers.create_trigger_to_proto`. Migration: drop `order_type` from ladder creates, or pass `order_type="limit"`.
- With the catalogs loaded, a trigger's `symbol` names its pair, such as `BTC-USDT`, on `triggers.get`, `triggers.list` and `triggers.subscribe`. It was always empty, and only `symbol_id` was set. Before the catalogs load, or for a pair they do not list, `symbol` stays empty, as before. Affected, on `AsyncPolyester` and `Polyester`: `triggers.get`, `triggers.list` and `triggers.subscribe`; `polyester.codecs.decode.triggers.trigger_from_proto`, which takes an optional `symbol`, and `triggers_list_from_proto`, `get_trigger_from_proto` and `polyester.codecs.realtime_decode.decode_trigger_bytes`, which take an optional `symbols` lookup.
- **Breaking:** `triggers.modify` takes `max_slippage_bps` from 0 to 10000, as the contract's `ModifyTriggerRequest` does and as `triggers.create` takes it for a buy stop-loss or take-profit with a market child. It refused 10000 before sending (`max_slippage_bps must be between 1 and 9999`), so such a trigger created with a 10000 cap could not be modified back to it. The server decides by side and type: a sell stop-loss or take-profit and a trailing stop on either side still refuse 10000, now with the server's `MAX_SLIPPAGE_INVALID`. 10001 and negative values are still refused before sending (`max_slippage_bps must be between 1 and 10000`), and `0` still clears the cap. Affected, on `AsyncPolyester` and `Polyester`: `triggers.modify`; `polyester.codecs.triggers.modify_trigger_to_proto`. Migration: expect the server's `MAX_SLIPPAGE_INVALID` instead of `PolyesterValidationError` when sending 10000 for a sell or a trailing stop.
- `triggers.list` filters by strategy and by parent order, as the contract's `ListTriggersRequest` does: `trigger_type` takes `stop_loss`, `take_profit`, `trailing_stop`, `twap` or `ladder`, the labels `triggers.create` takes, and `parent_order_id` takes an order ID (base58 or decimal) and keeps that order's attached take-profit, stop-loss and trailing-stop triggers. An unknown trigger type, or a parent order ID that is zero or not a uint64 ID, raises `PolyesterValidationError` before sending. Calls without them list as before. Affected, on `AsyncPolyester` and `Polyester`: `triggers.list`; `polyester.codecs.triggers.trigger_type_to_proto` (new).

## 0.21.1

Git tag: `v0.21.1`. Released 2026-11-12. Built on public contract `a3e3784`.

- Requests signed with an API key could be refused by servers running the new clock rule, which refuses a timestamp more than one second ahead of the server clock as `TIMESTAMP_SKEW` (devnet runs it now; testnet gets it with its next release). The SDK gives each request of a key its own millisecond timestamp, and during a burst it let those timestamps run up to five seconds ahead of the local clock, so a burst of more than about a thousand signed requests, or a few hundred on a host whose clock is a little fast, raised `PolyesterTimestampSkewError`. Automatic timestamps now lead the local clock by at most 500 ms (`polyester.auth.MAX_SIGNING_FUTURE_SKEW_MS` is `500`, was `5000`). A larger burst waits for the clock on the async and sync clients, which sign through `sign_request_async`, as it did at the old ceiling; the low-level synchronous `polyester.auth.sign_request` raises its retryable `PolyesterRateLimitError` (with `retry_after`) once a burst runs 500 ms ahead of the clock, roughly 500 more signatures than milliseconds elapsed, instead of 5000 ms ahead. Keep the host clock synchronized: the other half second is all the room the server leaves for skew. The docs also give the server's new default receive window, 5000 ms (was 10000), used when `recv_window_ms` is `None`. Affected: every method that signs with an API key, such as `auth.me`, `orders.create` and `balances.list`, on `AsyncPolyester` and `Polyester`; the realtime connection and subscription token requests behind every private subscription and the private order stream; `polyester.auth.sign_request` and `sign_request_async` without an explicit timestamp; `polyester.auth.MAX_SIGNING_FUTURE_SKEW_MS`.

## 0.21.0

Git tag: `v0.21.0`. Released 2026-11-11. Built on public contract `a3e3784`.

- **Breaking:** A market order asking for a time in force other than IOC is refused before anything is sent, with `PolyesterValidationError` (`tif='fok' is only valid for limit orders`), as `tif='gtd'` already was. The public contract has one market execution, `market_ioc`: "Market orders always execute as immediate-or-cancel". `tif="fok"` and `tif="gtc"` on a market order were accepted and sent as IOC, so a caller who asked for fill-or-kill could get a partial fill. `tif="ioc"` and no `tif` still send a market IOC order. The same rule now holds for a standalone trigger's market child and for a trailing stop, whose child is always IOC: a market `stop_loss`, `take_profit` or `twap` child, or a `trailing_stop`, takes `tif="ioc"` or no `tif`, and `gtc` or `fok` raises `PolyesterValidationError` (`tif=gtc applies only to limit children: a market child or a trailing_stop executes IOC`). `triggers.create`'s `tif` now defaults to `None`, which a limit child reads as `gtc`, as before. Attached take-profit, stop-loss and trailing-stop legs take no `tif` and are unchanged. Affected, on `AsyncPolyester` and `Polyester`: `orders.create`, `orders.preview`, `orders.batch_create` and `triggers.create`; and `polyester.codecs.orders.order_intent_from_request`, `create_order_to_proto`, `preview_order_to_proto`, `batch_create_orders_to_proto` and `polyester.codecs.triggers.create_trigger_to_proto`. Migration: drop `tif` from market orders, market trigger children and trailing stops, or pass `tif="ioc"`; for fill-or-kill, send a limit order with `tif="fok"`.
- **Breaking:** Orders and triggers read back with the catalogs loaded carry their pair's quantity scales, as `orders.create` and `orders.preview` results do. `orders.get`, `orders.list_open` and `orders.list_history` returned orders whose quantities had no scale, so `cum_qty.as_decimal()`, `cum_quote()`, `quote_used()` and `quote_unspent()` raised `PolyesterValidationError` (`base_quantity_scale is required: pass the pair's base quantity scale`) unless the caller passed the scale. Each order's `orig_qty`, `cum_qty`, `inherited_cum_qty`, `leaves_qty` and `fee_total.qty` now have the pair's base quantity scale, and the new `Order.quote_quantity_scale` holds its quote quantity scale, which `quote_unspent()` uses when `quote_quantity_scale` is not passed; it is now optional and raises `PolyesterValidationError` (`quote_quantity_scale is required: ...`) when neither is known. The trades of `orders.get` and `trades.list`, the trades of `trades.subscribe`, the orders and fills of `orders.subscribe` (including the cached view a consumer joining a running stream gets, decoded at the scales known when it joins), and a trigger's `qty` and TWAP and ladder `executed_qty` from `triggers.get`, `triggers.list` and `triggers.subscribe` are scaled the same way. These reads wait for the spot config load in progress, never for the funding config; a failed spot load, a pair the catalogs don't list, or `hydrate_catalogs=False` leaves the quantities without a scale, as before, and explicit scale arguments still win. Affected, on `AsyncPolyester` and `Polyester`: `orders.get`, `orders.list_open`, `orders.list_history`, `orders.wait_for_order_trades_complete`, `orders.subscribe`, `trades.list`, `trades.subscribe`, `triggers.get`, `triggers.list` and `triggers.subscribe`; the `Order` model; `polyester.codecs.decode.orders.order_from_proto`, `orders_list_from_proto`, `get_order_from_proto` and `user_trades_list_from_proto`, `polyester.codecs.decode.private_orders.private_orders_from_proto` and `private_orders_unit_from_proto`, `polyester.codecs.decode.triggers.triggers_list_from_proto` and `get_trigger_from_proto`, and `polyester.codecs.realtime_decode.decode_trigger_bytes` and `decode_user_trade_batch_bytes`, which take an optional `scales`; and `AsyncRealtimeClient.subscribe_private_orders`, which takes `order_scales`. Migration: drop the scale arguments you passed to these helpers if you like; equality and serialization of `Order` now include `quote_quantity_scale`, so compare the fields you need instead of whole orders.
- **Breaking:** A canceled trigger's `status` reads `canceled`, the contract's spelling (`STATUS_CANCELED`), as its `canceled` event and the TypeScript and Rust SDKs do. It read `cancelled`. The status filter of `triggers.list` and the event-type filter of `triggers.list_events` no longer accept `cancelled`: it raises `PolyesterValidationError` (`invalid trigger status 'cancelled'; ...`) before sending, so there is one spelling for outputs and inputs. Affected, on `AsyncPolyester` and `Polyester`: `triggers.get`, `triggers.list`, `triggers.list_events` and `triggers.subscribe`, and the `status` of trigger mutation results such as `triggers.cancel`; `polyester.codecs.decode.triggers.trigger_from_proto`, `trigger_status_from_label`, `trigger_event_type_from_label` and `trigger_mutation_from_proto`. Migration: compare a trigger's `status` with `"canceled"`, and filter with `status="canceled"` and `event_type="canceled"`.
- **Breaking:** Order preview is `orders.preview`, as in the TypeScript, Rust and Go SDKs; `orders.preview_order` is removed, with no alias. Arguments, overloads and result are unchanged. Affected: `orders.preview_order` on `AsyncPolyester` and `Polyester` (`AsyncOrdersService` and `SyncOrdersService`). Migration: rename `client.orders.preview_order(...)` to `client.orders.preview(...)`.

## 0.20.0

Git tag: `v0.20.0`. Released 2026-11-11. Built on public contract `a3e3784`.

- **Breaking:** Spot trading no longer depends on the funding (deposit/withdraw) config. The client loaded the spot config and then the funding config as one step, so when the funding read failed, for example because a proxy closed the connection after the spot config arrived (`peer closed connection without sending TLS close_notify`) or the read stalled until `timeout`, `wait_for_catalogs()` raised and every call that names a market raised `PolyesterCatalogHydrationError`, although the spot config had loaded: a trading bot could not start. The two now load on their own. `wait_for_catalogs()` returns once the spot config has loaded and validated, and spot calls go on while the funding config is still loading or failed to load. The new `wait_for_funding_catalog()` waits for the funding config and raises `PolyesterCatalogHydrationError` naming it when it could not be loaded; `zipper.subscribe_zipped_asset_supply`, which decodes with its scales, waits for it, sends nothing until it loads and raises the same, without sending, when it failed. Only what reads the funding config waits: withdrawals and deposit addresses (`withdraw.create_*`, `deposit.list_addresses`, `deposit.create_address`) and `zipper.get_deposit_withdraw_config` read nothing from it and work while it is loading or failed. `catalogs.ledger_id_for_asset` and `catalogs.quantity_scale_for_asset` keep their signatures and don't wait: `None` means either that the funding config has not loaded (yet, or its load failed) or that it does not know the asset. With `hydrate_catalogs=False` nothing changes. A spot config that is missing, empty or invalid still fails every spot call closed. `Polyester()` returns once the spot config is ready. `wait_for_catalogs()` now raises `PolyesterCatalogHydrationError` where it raised the load's failure itself, such as a `PolyesterTimeoutError`, `PolyesterServerError` or `PolyesterValidationError`; that failure is its `__cause__`, and `catalogs_last_error` still holds it. `CatalogManager` gains `mark_spot_unusable` and `mark_funding_unusable`; `is_unusable` is true when either catalog is. Affected: `AsyncPolyester.wait_for_catalogs` and the `Polyester` constructor, `AsyncPolyester.wait_for_funding_catalog` and `Polyester.wait_for_funding_catalog` (new), `catalogs_last_error`, `zipper.subscribe_zipped_asset_supply`, and `client.catalogs`: `zipper`, `deposit_withdraw_config`, `zipper_config`, `ledger_id_for_asset`, `quantity_scale_for_asset`, `is_unusable` and `unusable_reason`. Migration: catch `PolyesterCatalogHydrationError` around `wait_for_catalogs()` and read `__cause__` for the failure; call `await client.wait_for_funding_catalog()` (`client.wait_for_funding_catalog()` on `Polyester`) before reading the funding catalog or the asset lookups.
- A catalog read at startup that times out, cannot connect, loses its connection or is answered `unavailable` (such as an HTTP 502, 503 or 504, but not a rate limit) is read again instead of failing the load: at most 3 reads per catalog, 0.25 s and then 0.5 s apart, each retry on a new connection, so it never waits behind a dropped or stalled one, all within `catalog_timeout` seconds of creating the client. `catalog_timeout` is a new keyword of `AsyncPolyester` and `Polyester`, a positive number of seconds that defaults to twice `timeout`; any other value raises `PolyesterValidationError`. Each read gets at most `timeout`. A read that keeps stalling now fails within that deadline. Any other error answer, and a catalog that does not validate, fails at once; only these two reads are retried, and mutations never are. Affected: the catalogs `AsyncPolyester` and `Polyester` load when they are created (`marketdata.v1.MarketDataService/GetSpotConfig` and `chain.zipper.v1.ZipperService/GetDepositWithdrawConfig`).
- `PolyesterCatalogHydrationError` says what failed: its message names the catalog and the operation, the kind of failure, the number of reads and the time they took, and the edge's response reference when a response arrived, such as `catalog hydration failed: funding config (chain.zipper.v1.ZipperService/GetDepositWithdrawConfig) connection closed after 3 attempts in 0.8s: ...`. It gains `catalog` (`"spot"` or `"funding"`), `operation`, `failure` (`"timeout"`, `"connection_closed"`, `"connect_failed"`, `"unavailable"`, `"invalid"` or `"error"`), `attempts` and `response_ref` (the `cf-ray` header, or `x-request-id` when there is none), each `None` on an error that does not come from a catalog load, and takes them as keywords. The message drops URL credentials and the proxy URLs the environment configures (`HTTPS_PROXY` and the like). Affected: `PolyesterCatalogHydrationError`, as `wait_for_catalogs`, `wait_for_funding_catalog` and every call that waits for the catalogs raise it.
- No member of an SDK error's chain prints a credential any more. An answer or a transport error quoting a URL with userinfo, such as a proxy's, was redacted in the SDK error's own message only (for catalog loads), while the `ConnectError` and the causes kept for debugging still held it, so `traceback.format_exception` printed it. Where Connect errors are mapped, the whole chain is now redacted in place: every quoted URL loses its userinfo, query and fragment, whatever characters they hold, and fails closed when it does not parse, and a proxy URL from the environment reads `[proxy]`. That covers each exception's message and `args`, fields such as `OSError.strerror` and `filename`, and structured diagnostics such as `problem` and a rate limit's `detail`. Each exception keeps its class and its `__cause__`. A URL the URL parser refuses is dropped whole, and a userinfo holding `?` or `#` is dropped too. The client's own secrets never reach an error's text however an answer quotes them: the exact userinfo and password of its API and WebSocket URLs, of a proxy the environment sets, and its API private key read `[REDACTED]`, raw and percent-decoded. Limitations: a password shorter than 4 characters is not replaced where it stands alone, since replacing so short a string would mangle ordinary text; and a request signature is not redacted when the server echoes it back, since it is single-use and expires with its receive window. Affected: every service method that raises a mapped SDK error, such as `orders.create`, `market_data.get_spot_config` and `balances.list`, and the catalog loads behind `wait_for_catalogs` and `wait_for_funding_catalog`.
- **Breaking:** `orders.list_history` refuses a `symbol` that does not name the market of `symbol_id` with `PolyesterValidationError` (`orders.list_history symbol mismatch: 'LTC-USDT' does not match symbol_id 1 (BTC-USDT)`), before anything is sent, as `trades.list` already does. It sent `symbol_id` alone, so `symbol="LTC-USDT", symbol_id=1` returned BTC-USDT history under the LTC-USDT label, and so did a symbol the catalog does not know paired with `symbol_id=1`. A matching pair, `symbol` alone and `symbol_id` alone select their market as before. `symbol_id=0` now raises `PolyesterValidationError` (`must be non-zero when explicitly supplied`), as for `trades.list`; it was sent as 0. `orderbook.create_subscription` and `orderbook.subscribe` refuse a mismatched pair with the same error through the same resolver; they refused another market's name with their own message, and an unknown name paired with a `symbol_id` with the missing-quantity-scale error. Affected: `orders.list_history`, `orderbook.create_subscription` and `orderbook.subscribe` on `AsyncPolyester` and `Polyester`, and `orderbook.subscribe_sync` on `Polyester`. Migration: pass `symbol` or `symbol_id`, or a pair that names one market; catch `PolyesterValidationError` for a mismatch.
- **Breaking:** A signed request answered with a redirect whose `Location` does not parse, such as one with a non-numeric port or an unclosed IPv6 host, raises `PolyesterRedirectError` with the new `malformed` attribute true and an empty `origin`, whose message never repeats the `Location`. It raised `PolyesterServerError` with urllib's parse error ("Port could not be cast to integer value ..."), which `is_retryable_error` reports as retryable, so a retry loop sent the signed request again and got the same redirect; a private WebSocket handshake answered that way raised a bare `ValueError`. As for every refused redirect, `mutation_outcome_unknown` is true and `is_retryable_error` false. No URL credential reached an error before. URLs the SDK names in an error now keep only their scheme, host, port and path: an invalid realtime WebSocket URL raises `InvalidURI` without its query or fragment (an unclosed IPv6 host raised a bare `ValueError`), and `PolyesterAuthError.endpoint` of a refused subscription token request is `.../v1/rt/subscribe` without `?channel=...`, which the message still names. Affected: every method that signs a ConnectRPC request with an API key, such as `auth.me`, `orders.create` and `orders.cancel`; the private order stream and private channel subscriptions, whose WebSocket handshake refuses redirects; the realtime connection and subscription token requests; and `PolyesterRedirectError`. Migration: handle `PolyesterRedirectError` with `malformed` true as any refused redirect, a configuration error: set `api_url` to the API's own origin and read a mutation back before sending it again; read a refused subscription token's channel from the message, not from `endpoint`.

## 0.19.0

Git tag: `v0.19.0`. Released 2026-11-10. Built on public contract `a3e3784`.

- **Breaking:** A request signed with an API key no longer follows an HTTP redirect; it raises the new `PolyesterRedirectError` instead. A ConnectRPC call answered with a 307 or 308 whose `Location` named another host or port was sent there again, with its key ID, timestamp and a valid signature, so the redirect target could replay it within its receive window. A realtime token request did the same through an `httpx.AsyncClient` passed to `AsyncRealtimeClient(http=...)` with `follow_redirects=True`, for any redirect status. And the WebSocket of a private channel or of the private order stream followed a handshake redirect to any origin, then sent its realtime token there. The private key was never exposed. Now no redirect of a signed request is followed, whatever its status, and whether it names another origin or the same one: the signature covers the path, so a same-origin redirect to another path could not verify either. `PolyesterRedirectError` is a `PolyesterError` with the redirect status (`status_code`), the origin it pointed at (`origin`, without path, query or userinfo) and whether that is the origin the request went to (`same_origin`). Nothing was sent to the redirect target, but the redirect does not prove that the configured origin did not apply the request first, so `mutation_outcome_unknown` is true for it, and `is_retryable_error` is false, since sending again gets the same answer. The handshake of a private channel's WebSocket, and of the private order stream's, no longer follows a redirect either, and raises `PolyesterRedirectError`; public channels still follow handshake redirects. A refused realtime token request, sub-account list read or private handshake ends the subscription or private order stream instead of reconnecting. Signed ConnectRPC requests now go through a pyqwest transport with pyqwest's default settings and `follow_redirects=False`; unsigned public calls still use pyqwest's default transport and follow redirects as before. The `pyqwest` requirement rises to `>=0.9.0`, the first release with `follow_redirects`. Affected: every method that signs with an API key, on `AsyncPolyester` and `Polyester`, such as `auth.me`, `orders.create`, `orders.cancel`, `balances.list` and `internal_transfers.create`; the realtime connection and subscription token requests behind every private subscription, such as `orders.subscribe` and `balances.subscribe`; `subscribe_proto`, `subscribe_proto_batch` and `subscribe_private_orders` on a private channel; and `AsyncRealtimeClient` with any `http` client. Migration: set `api_url` to the API's own origin, such as `https://` rather than `http://` where the server redirects one to the other, and handle `PolyesterRedirectError` as a configuration error, not a retry; after one on a mutation, read the order or trigger back before sending it again.

## 0.18.0

Git tag: `v0.18.0`. Released 2026-11-10. Built on public contract `a3e3784`.

- A method that names a market by `symbol`, or needs a pair's catalog scales, now waits for the catalogs the client loads when it is created. It read them at once, so a call made right after creating an `AsyncPolyester`, such as `orderbook.create_subscription(symbol="DOGE-USDT", depth=10)`, refused a valid symbol with `PolyesterValidationError` (`symbol_id is required for orderbook subscriptions` or `Unknown symbol`) while the load was still running. Calling another method first, such as `market_overview.list()`, did not wait for the load and only helped when it happened to finish later. When the load failed, the call now raises the new `PolyesterCatalogHydrationError` (`catalog hydration failed: ...`, with the failure as `__cause__`) instead of refusing the symbol. A symbol the loaded catalogs don't know is refused with `PolyesterValidationError` (`Unknown symbol ...`), now also by `orders.modify` and `triggers.create`, which reported the missing quantity scale instead. With `hydrate_catalogs=False` nothing waits and every refusal is unchanged, `orders.modify` and `triggers.create` still reporting the missing quantity scale (`quantity scale for ... is unavailable`). `Polyester` waits for the load when it is created, so its calls behave as before. Affected, on `AsyncPolyester`: `orderbook.get`, `orderbook.create_subscription` and `orderbook.subscribe`; `market_data.get_trades`, `get_candles`, `get_candles_columns`, `get_current_candle`, `subscribe_trades` and `subscribe_candles` (also as `candles`); `heatmap.get` and `heatmap.subscribe_live`, `trades.list`, `orders.list_history` and `orders.cancel`, each with `symbol`; and `zipper.subscribe_zipped_asset_supply`, whose updates are decoded with the catalog scales; and the unknown-symbol refusal of `orders.modify` and `triggers.create`.
- `market_overview.list`, `market_overview.get_spot_volume_history`, `market_overview.create_subscription` and `market_overview.subscribe` without a symbol filter, and `fees.get_spot_fee_rates`, now wait for a catalog load in progress before they label and scale their rows. Called right after the client was created, they returned rows with an empty `symbol` and without the sizes and volumes the catalog scales decode. A failed load still leaves those fields empty and raises nothing. Affected: these methods on `AsyncPolyester`.
- `AsyncMarketDataService`, `AsyncOrderbookService`, `AsyncHeatmapService`, `AsyncTradesService`, `AsyncFeeService` and `AsyncZipperService` take the keyword `wait_for_catalogs` that `AsyncOrdersService`, `AsyncTriggersService` and `AsyncMarketOverviewService` already take: a coroutine function with no arguments, such as `client.wait_for_catalogs`, that the service awaits before it reads the catalogs. A read that only labels its rows from the catalogs goes on when it raises.
- **Breaking:** The methods that already waited for the catalogs now raise `PolyesterCatalogHydrationError` when the load failed, where they raised the load's failure itself, such as a `PolyesterTransportError`. Affected, on `AsyncPolyester`: `orders.create`, `orders.preview_order`, `orders.batch_create`, `orders.batch_replace` and `orders.modify`; `orders.cancel_all`, `orders.cancel_all_after` and `orders.stop_all_trading` with `symbol` or `symbols`; `triggers.create`, and `triggers.list`, `triggers.modify` and `triggers.resume` with `symbol`; and `market_overview.list`, `market_overview.get_spot_volume_history` and `market_overview.create_subscription` with `symbols`. Migration: catch `PolyesterCatalogHydrationError`, and read its `__cause__` for the failure, the error `wait_for_catalogs()` raises and `catalogs_last_error` holds.
- Cancelling a call while it waits for the catalogs, `wait_for_catalogs()` included, no longer cancels the load. Awaiting it cancelled the load the whole client shares, so a call cut short by a timeout left the client without catalogs for good. Affected: `AsyncPolyester.wait_for_catalogs` and the methods above.
- `InternalTransferResult` gains `flow_id`, the transfer's lifecycle flow ID, to read with `client.lifecycle.get_flow(flow_id=...)`; empty when the response names none. The flow may become readable after the receipt. Affected: `internal_transfers.create` and `codecs.decode.internal_transfer_from_proto`, and the JSON decoder `codecs.wire_decode.decode_internal_transfer_result`.
- `ZipperChainConfig` and `ZipperEnrichedAssetChain` gain the network's memo rule for withdrawal destinations: `memo_requirement` (`required`, `optional` or `not_supported`; empty when the server names none, which does not mean a memo can be omitted; an unknown number reads as its decimal string), and `memo_label` ("Memo", "Destination tag") and `memo_format_hint`, display text kept as sent. Affected: `zipper.get_deposit_withdraw_config`, the zipper catalog (`client.catalogs.zipper`, kept when `zipper.subscribe_zipped_asset_supply` patches its supply) and `codecs.decode.deposit_withdraw_config_from_proto`.
- The JSON transfer decoder reads the transfer reason from `transferCode` as the REST and JSON transfer streams send it, by lowercase label (`system_adjustment`), enum name (`SYSTEM_ADJUSTMENT`) or number, and maps every `ledger.v1.TransferCode` of the contract, including `trading_withdraw_fee_leg` (1066), `quickswap_polyester_fee` (1067), `quickswap_broker_fee` (1068), `quickswap_affiliate_fee` (1069), `fee_sweep` (1072), `fee_refill` (1073) and `system_adjustment` (1074). It read only a numeric `type` and raised `ValueError` on a label; a name it does not know reads 0. `LedgerTransfer.transfer_type` names the reason, not the direction: a system adjustment credits (account seeding) or debits (a correction) the account, so read `is_debit`. Binary transfer rows already kept the number. Affected: `codecs.wire_decode.decode_ledger_transfer` and `codecs.wire_decode.decode_transfers_list`.
- API-key policies decode the new account permissions by name, as every action: `read_api_keys`, `read_api_policies`, `read_subaccount_policies`, `read_subaccount_permissions`, `read_vip_status`, `read_social_verification`, `read_profile`, `read_account_directory`, `read_withdraw_validation`, `read_daily_claims`, `claim_daily_reward`, `read_checkpoints` and `read_rewards`. Affected: `policies.subscribe_api_policies`, `policies.subscribe_subaccount_policies`, `codecs.decode.policies.api_policy_from_proto` and `codecs.decode.policies.subaccount_policy_from_proto`.
- The server now lets an API key call reads that needed an interactive session, each with its own permission on the key's API-key policy. The docstrings and README name it: `api_keys.list` and `api_keys.get` need `READ_API_KEYS`, `vip.get_vip_status` needs `READ_VIP_STATUS` on a main-account key, and `social_verification.get` needs `READ_SOCIAL_VERIFICATION` on a main-account key and returns the link status only. A missing permission raises `PolyesterApiError` whose `auth_error_code(err)` is `AUTH_API_KEY_ACCESS_DENIED`, naming the permission. Affected: `api_keys.list`, `api_keys.get`, `vip.get_vip_status` and `social_verification.get`.
- **Breaking:** The server now requires `READ_WITHDRAW_VALIDATION` instead of `EXTERNAL_WITHDRAW` on an API key's policy for `trading_withdraws.validate_destination`; a key without it raises `PolyesterAuthError` with `ERROR_CODE_PERMISSION_DENIED`, naming the permission. The server granted it to existing policies that grant `EXTERNAL_WITHDRAW`. Affected: `trading_withdraws.validate_destination`. Migration: include `READ_WITHDRAW_VALIDATION` when you create an API-key policy, and keep it, with the other account permissions you read back, when you rewrite a policy's whole action list.
- The orders and auth path and body ID mismatch codes (`ERROR_CODE_PATH_BODY_ID_MISMATCH`, `AUTH_PATH_BODY_ID_MISMATCH`) keep their code: a REST problem with `PATH_BODY_ID_MISMATCH` raises `PolyesterApiError` with `ERROR_CODE_PATH_BODY_ID_MISMATCH`, not a generic validation error. ConnectRPC requests carry no path ID, so this SDK's own calls don't receive it. Affected: every service method.
- `sdk-coverage.toml` says which calls an API key can now make that this SDK does not wrap yet: policy, profile and username-history reads, account resolve, effective sub-account permissions, daily claims, checkpoints and reward awards. Internal transfer lookup (`GetInternalTransfer`) and reward acknowledgement stay unwrapped: they accept only an interactive session.

## 0.17.0

Git tag: `v0.17.0`. Released 2026-11-10. Built on public contract `c8d9827`.

- **Breaking:** Depths and limits accept any exact integer, such as a NumPy integer: a value whose type implements `__index__`. They refused everything but `int`, so `depth=np.int64(10)` raised `PolyesterValidationError` before connecting. `bool` and `float` are still refused, and the SDK sends and reports a plain `int` (a view's `depth` from a NumPy depth is an `int`). Affected depths, on `AsyncPolyester` and `Polyester`: `orderbook.get`, `orderbook.create_subscription`, `orderbook.subscribe`, `orderbook.subscribe_deltas` and `heatmap.get`, and on `Polyester` `orderbook.subscribe_sync`; and the helpers `polyester.codecs.orderbook.orderbook_snapshot_depth`, `covering_snapshot_depth`, `orderbook_stream_tier`, `require_published_stream_depth` and `depth_to_connect_enum`, and `polyester.codecs.heatmap.heatmap_depth` and `depth_to_proto_name`. Affected limits, on `AsyncPolyester` and `Polyester`: `address_book.list_entries`, `list_transfer_counterparties`, `list_transfer_destinations`, `list_internal_transfer_whitelist_entries` and `get_view`; `changelog.list_posts`, `list_changes`, `iter_posts` and `iter_changes`; `heatmap.get`; `lifecycle.list_flows` and `list_flows_by_tx`; `market_data.get_trades`, `get_candles` and `get_candles_columns`; `market_overview.list` and `market_overview.create_subscription`, and on `Polyester` `market_overview.subscribe_sync`; `orders.list_open`, `list_history` and `get`; `sub_accounts.list_activity`; `trades.list`; `transfers.list`; and `triggers.list` and `list_events`. Added `polyester.codecs.orderbook.exact_int`. Migration: none needed; drop any `int(...)` you added around a NumPy depth or limit if you like.
- **Breaking:** A managed order book adds one view when it applies a snapshot together with the deltas buffered behind it. It added a view of the snapshot and then one per buffered delta, including a delta the snapshot already covered, which repeated a view: the extra views were copies of superseded states, and a stale copy could be the next view read after `set_bucket`. Affected: `orderbook.create_subscription` and `orderbook.subscribe` (their iterator and `on_event`) on `AsyncPolyester` and `Polyester`, and `orderbook.subscribe_sync` (its `on_event`) on `Polyester`. Migration: expect one view per snapshot, at the sequence of the last buffered delta; read `book_seq` instead of counting views.
- Added `OrderbookSubscription.since_last_publication()`, the seconds since the managed book's stream last delivered a publication, or since it started, and `SyncSubscription.since_last_publication()`, the same for an order book from `orderbook.subscribe_sync` (`None` for other streams). The age is never negative, also when read from another thread while publications arrive. The server republishes each book's whole view about every 30 s even when nothing changes, so an age far above that means the stream stalled while the socket stayed open, not that the market is quiet. The SDK sets no threshold; poll it and refresh or resubscribe on a stall.
- The trailing distance in ticks is documented as what it is: a price delta in 1e-9 quote-unit ticks, the scale of every price tick, sent as given. On BTC-USDT, 50 USDT is `50_000_000_000` ticks and 0.5 USDT is `500_000_000` (`int(Decimal("0.5").scaleb(9))`). It is not a count of the pair's tick size. Affected docs: `triggers.create` and `triggers.modify` (`trailing_distance_ticks`), the `TrailingStop` model (`distance_ticks`) and the README's trigger section.
- The live tests that write (an address-book create, update and delete, and two social-verification starts) run only with `POLYESTER_TEST_MUTATION=1`. The `mutation` marker now skips a test without that opt-in by itself, and a test keeps every live test that writes behind a write marker.

## 0.16.0

Git tag: `v0.16.0`. Released 2026-11-10. Built on public contract `c8d9827`.

- **Breaking:** `AsyncOrdersService.create`, `AsyncOrdersService.preview_order` and `AsyncOrdersService.batch_create` (on `AsyncPolyester.orders` and `Polyester.orders`) refuse a limit order with `market_client_ref_price` set with `PolyesterValidationError` (`market_client_ref_price is only valid for market orders`), before anything is sent, as they already refuse `max_slippage_ticks` and `max_slippage_bps` on a limit order. The public contract carries the reference price on market orders only. On a limit order the SDK accepted it, then dropped it, so the order was created without it and read back with `market_client_ref_price` `None`. `polyester.codecs.orders.order_intent_from_request`, `create_order_to_proto`, `preview_order_to_proto` and `batch_create_orders_to_proto` apply the same rule. Migration: remove `market_client_ref_price` from limit orders; it never had an effect on them.
- A sync subscription closed from a client callback, its own `on_event` included, now stops delivery and returns at once. `close()` and `unsubscribe()` waited on the client loop that runs the callback, so they blocked every subscription and call on the client for 10 seconds and then raised `TimeoutError`: delivery ended through `on_error` or as the subscription's failure, or, if the callback caught the `TimeoutError`, events kept arriving. The close finishes on the loop after the callback returns, and no `on_event` starts after `close()` returns; every `close()` from another thread until one has seen it finish, `Polyester.close()` included, waits for it and raises its failure, so the client never stops with a close still running. A `close()` from another thread still waits up to 10 seconds for the stream to close, and closing again does nothing. Affected: `SyncSubscription.close` and `SyncSubscription.unsubscribe`, on the handle every `subscribe*_sync` method of `Polyester` returns.
- **Breaking:** A sync call that would have to wait on the client loop now raises `PolyesterError` at once when it is made from a client callback, naming the method and saying to call it from another thread, as `subscribe_sync` already refused with `PolyesterRealtimeError`. Such a call blocked the loop that runs callbacks: a sync method, or iterating a sync iterator such as `changelog.iter_posts`, never returned, and `Polyester.close()` blocked for 10 seconds per open subscription plus 10 seconds for shutdown, and then raised `RuntimeError` ("cannot join current thread"). A refused `Polyester.close()` leaves the client open. Affected, on `Polyester`: every service method that runs on the client loop and returns a result or an iterator, such as `orders.get`, `orders.create` and `changelog.iter_posts`, and `Polyester.close`. Migration: close the subscription from the callback, and hand other calls, including closing the client, to another thread.
- **Breaking:** `MarketOverviewEntry` gains the 24-hour range, the top of the book and two times the server sends for each market: `high_24h` and `low_24h` (`Price`), `best_bid` and `best_ask` (`Price`), `best_bid_qty` and `best_ask_qty` (`Quantity`, base quantity, at the pair's base quantity scale when the catalogs know it), and `last_trade_ts_ns` and `listed_ts_ns` (epoch nanoseconds as a decimal string). They were dropped, so the overview showed neither the 24-hour range nor the best bid and ask. Values are exact, as sent; a price and its size are `None` when that side of the book is empty, the range is `None` when the server sends none, and a time is `""` when there is none. Affected: `market_overview.list`, `market_overview.create_subscription`, `market_overview.subscribe` and, on `Polyester`, `market_overview.subscribe_sync`; `polyester.codecs.decode.market_overview.market_overview_entry_from_proto` and `market_overview_list_from_proto`; `polyester.codecs.realtime_decode.decode_market_overview_batch_bytes`; and `polyester.codecs.wire_decode.decode_market_overview_entry` and `decode_market_overview_list`, which take no catalogs and so leave the sizes without a scale. These JSON decoders now raise `PolyesterResponseContractError` for a `lastTradeTsNs` or `listedTsNs` that is negative or not an integer. Migration: equality and serialization of `MarketOverviewEntry` now include these fields; compare or store the fields you need instead of whole rows.
- **Breaking:** `AddressBookViewInvalidation.scope` is now an `AccountScope` (`scope_type`, `root_account_id`, `sub_account_id`) instead of a `str`, so an event names the address book that changed. A sub-account's change reported only the root account, so it read the same as a change to the root account's book. `scope_type` is `"root"` or `"subaccount"`; `sub_account_id` is the sub-account's public ID, and empty for a root scope; `scope` is `None` when the event names none, where it was `""`. Affected: `address_book.subscribe_view_invalidations` on `AsyncPolyester` and `Polyester`, `address_book.subscribe_sync` on `Polyester`, and `polyester.codecs.realtime_decode.decode_address_book_invalidation_bytes`. Migration: check `event.scope is not None`, read `event.scope.root_account_id` where you read `event.scope`, and refresh the sub-account's book when `event.scope.scope_type == "subaccount"`.
- **Breaking:** `polyester.codecs.wire_decode.decode_batch_replace_result` keeps each item's `violations`, `rate_limit` and `action_taken`, decoded from the item's `error` and `actionTaken` as `batch_replace_from_proto` decodes them, from proto JSON and snake_case keys alike. It dropped them, so a rejected item decoded from JSON named no field to fix. An item `error` that is not a valid `ErrorDetail` raises `PolyesterResponseContractError`. Migration: equality and serialization of the items now include these fields; catch `PolyesterResponseContractError` where you decode untrusted JSON.

## 0.15.1

Git tag: `v0.15.1`. Released 2026-11-09. Built on public contract `c8d9827`.

- Order reads now return an attached trailing stop's buy-back limit as `TrailingStop.limit_price`: the maximum price of a trailing stop on an order that sells, the most its exit pays per unit, exactly as the server returns it. It was always `None` on a read, though the server returned it, so a trailing stop read back without its cap and only `triggers.get` showed it. It stays `None` when the server sends none, as for the trailing stop of an order that buys. A `TrailingStop` read from an order and passed back to `orders.modify` now keeps its limit. Affected: `orders.get`, `orders.list_open` and `orders.list_history` with attached risk, and `orders.subscribe`, on `AsyncPolyester` and `Polyester`, and `polyester.codecs.decode.orders.order_from_proto`, `get_order_from_proto` and `orders_list_from_proto`, and `polyester.codecs.decode.private_orders.private_orders_from_proto`.
- The `TrailingStop` docstring and the README's attached trailing stop section now say what the trailing stop sends when it fires: with a buy-back `limit_price`, a limit IOC child at that price, which fills what it can at or below the limit and cancels the rest instead of resting; without one, a market child. The `PolyesterValidationError` for an `order_type` under `attached_risk.trailing_stop` said the child is always market; it now reads "attached trailing_stop takes no order_type: its child is a limit IOC at limit_price when the order sells, and a market order when it buys". `order_type` there is still refused.

## 0.15.0

Git tag: `v0.15.0`. Released 2026-11-09. Built on public contract `c8d9827`.

- **Breaking:** `BatchCreateResultItem`, `BatchCancelResultItem` and `BatchReplaceAdmissionItem` gain `violations`, the field violations (`OrderFieldViolation`: `field_path`, `rule_id`, `message`) a rejected item carries, in the order the server sent them, as `orders.preview` already reports them. A batch create item refused for `error_code_price_tick_size` now names `order.attached_risk.take_profit.trigger_price_ticks` and rule `tick_size`, for example. They were dropped, so a caller could not tell which field to fix. `violations` is empty for an accepted item and for a rejection that names no field. Affected: `AsyncOrdersService.batch_create`, `batch_cancel` and `batch_replace` (`AsyncPolyester.orders` and `Polyester.orders`), and `polyester.codecs.decode.orders.batch_create_from_proto`, `batch_cancel_from_proto` and `batch_replace_from_proto`. Migration: equality and serialization of these items now include `violations` when the server names a field; compare or store the fields you need instead of the whole item.
- **Breaking:** `AsyncTriggersService.create` (`AsyncPolyester.triggers.create` and `Polyester.triggers.create`) refuses a sell TWAP with `order_type="market"` and `max_slippage_bps=10000` with `PolyesterValidationError` (`max_slippage_bps must be between 1 and 9999`), before anything is sent. The server refuses it with `MAX_SLIPPAGE_INVALID`, since a 100% cap leaves a sell no positive price; a sell stop-loss or take-profit market child was already refused the same way. A buy TWAP keeps 1 to 10000. `polyester.codecs.triggers.create_trigger_to_proto` applies the same rule. Migration: cap a sell TWAP at 9999 bps or less, or set `max_slippage_ticks` instead.
- **Breaking:** The sync `Polyester` client is typed. Its constructor and every method of its services take the parameters of the `AsyncPolyester` method of the same name and return its result type, so a type checker such as mypy checks sync calls as it checks async ones. The services forwarded every call untyped, so a misspelt keyword such as `qyt=`, a wrong argument type, a wrong use of the result, an unknown method name and an unknown `Polyester(...)` keyword all type-checked and failed only at runtime. A method that is an async generator on `AsyncPolyester`, such as `changelog.iter_posts`, returns an `Iterator` of the same items, and each `subscribe*_sync` method takes `on_event` (called with the subscription's event type), `on_error` and the keywords of the async subscription it starts; `on_event` and `on_error` may return a value, which is ignored. `Polyester()` takes the keyword parameters of `AsyncPolyester()` instead of `**config`. Runtime behaviour is unchanged, except that an unknown keyword to a `subscribe*_sync` method now raises `TypeError` naming it from the call, before subscribing; with `on_error` given, it reached `on_error` instead. Affected, on `Polyester`: the constructor; and every method of `realtime` (`aclose`, `subscribe_market_trades`, `subscribe_private_orders`, `subscribe_proto`, `subscribe_proto_batch`); `auth` (`me`); `auth.profile` (`subscribe_identity`, `subscribe_sync`); `chain_analytics` (`get_unified_asset_balances`, `get_zipped_asset_supply`, `get_zipped_asset_supply_group`); `market_data` (`get_candles`, `get_candles_columns`, `get_current_candle`, `get_spot_config`, `get_trades`, `subscribe_candles`, `subscribe_candles_sync`, `subscribe_trades`, `subscribe_trades_sync`); `market_overview` (`create_subscription`, `get_currency_conversion_config`, `get_currency_conversion_rates`, `get_spot_volume_history`, `list`, `subscribe`, `subscribe_sync`); `zipper` (`get_deposit_withdraw_config`, `subscribe_sync`, `subscribe_zipped_asset_supply`); `heatmap` (`get`, `subscribe_live`, `subscribe_sync`); `lifecycle` (`get_flow`, `get_flow_by_tx`, `list_flows`, `list_flows_by_tx`, `subscribe_flow_detail`, `subscribe_flow_detail_sync`, `subscribe_open_flows`, `subscribe_open_flows_sync`); `balances` (`get_balance_history`, `get_equity_history`, `list`, `subscribe`, `subscribe_sync`); `orderbook` (`create_subscription`, `get`, `subscribe`, `subscribe_deltas`, `subscribe_sync`); `orders` (`batch_cancel`, `batch_create`, `batch_replace`, `cancel`, `cancel_all`, `cancel_all_after`, `create`, `get`, `get_batch_replace_status`, `list_history`, `list_open`, `modify`, `preview_order`, `stop_all_trading`, `subscribe`, `subscribe_sync`, `wait_batch_replace`, `wait_for_order_trades_complete`); `trades` (`list`, `subscribe`, `subscribe_sync`); `triggers` (`cancel`, `create`, `get`, `list`, `list_events`, `modify`, `pause`, `resume`, `subscribe`, `subscribe_events`, `subscribe_events_sync`, `subscribe_sync`); `transfers` (`list`, `subscribe`, `subscribe_sync`); `internal_transfers` (`create`); `deposit` (`create_address`, `list_addresses`); `fees` (`get_spot_fee_rates`); `api_keys` (`generate_keypair`, `get`, `list`, `subscribe`, `subscribe_sync`); `policies` (`subscribe_api_policies`, `subscribe_api_policies_sync`, `subscribe_subaccount_policies`, `subscribe_sync`); `sub_accounts` (`get`, `list`, `list_activity`, `list_invites`, `list_members`, `subscribe`, `subscribe_api_keys`, `subscribe_api_keys_sync`, `subscribe_sync`); `address_book` (`create_entry`, `create_tag`, `delete_entry`, `delete_tag`, `get_view`, `get_withdraw_whitelist_view`, `list_books`, `list_entries`, `list_internal_transfer_whitelist_entries`, `list_transfer_counterparties`, `list_transfer_destinations`, `subscribe_sync`, `subscribe_view_invalidations`, `update_entry`, `update_tag`); `social_verification` (`get`, `mark_ready`, `start`); `guard_signer` (`batch_sign_protected_actions`, `create_wallet`, `export_wallet`, `get_status`, `rotate_wallet`, `sign_protected_action`); `rate_limits` (`get_rate_limit_config`, `get_trading_rate_limits`); `vip` (`get_vip_status`, `list_vip_tiers`); `changelog` (`action_required_since`, `breaking_changes_since`, `get_post`, `iter_changes`, `iter_posts`, `list_changes`, `list_posts`); `withdraw` (`create_api_key_to_external`, `create_api_key_to_external_chain`, `create_api_key_to_funding`, `create_to_external_chain`, `create_to_funding`, `create_wallet_trading_withdraw`, `prepare_api_key_to_external`, `prepare_api_key_to_external_chain`, `prepare_api_key_to_funding`, `submit_prepared`, `validate_destination`); and the aliases `candles` (of `market_data`) and `trading_withdraws` (of `withdraw`). Migration: correct the call the type checker names; to reach an undeclared or private attribute of a sync service, use the `AsyncPolyester` client instead.
- **Breaking:** `AsyncPolyester(default_sub_account_id=...)` and `Polyester(default_sub_account_id=...)`, and their `from_env`, now refuse a default sub-account ID of `0` with `PolyesterValidationError` ("default_sub_account_id must be a non-zero ID, not 0") when the client is built, before anything is sent. An `int` 0 was falsy, so the client treated it as no default and every call addressed the main account, while a `"1"` or `"0"` default, a `sub_account_id=0` and an `account={"subaccountId": 0}` selector were already refused. `False`, `True` and any value that is neither a `str` nor an `int`, such as `0.0`, are refused the same way, and an `int` above 2**64 - 1 or below 0 is refused when the client is built instead of on the first call. The setting is typed `str | int | None`, as the client accepts it: an `int` is the numeric ID, and `client.default_sub_account_id` holds its public ID string. A string default, an empty string and `None` are unchanged. Migration: leave `default_sub_account_id` unset, or pass `""`, to address the main account, and pass a sub-account's ID otherwise. When you pass an `int`, `client.default_sub_account_id` now holds its public ID string instead of the `int`, so code that reads it back gets a `str`.
- WebSocket handshakes no longer log the credentials of a WebSocket URL. With the `websockets.client` logger at DEBUG, websockets logged every handshake header, including the `Authorization: Basic` header it builds from the URL's user name and password, which decodes back to the password. The SDK now gives websockets a logger that writes the same lines to `websockets.client`, with the value of an `Authorization` or `Proxy-Authorization` header replaced by `[REDACTED]`; the header is still sent, and the other handshake lines are unchanged. Affected: every realtime subscription on `AsyncPolyester` and `Polyester`, through `AsyncRealtimeClient.subscribe_proto`, `subscribe_proto_batch`, `subscribe_market_trades` and `subscribe_private_orders`, including `orders.subscribe`.

## 0.14.0

Git tag: `v0.14.0`. Released 2026-11-08. Built on public contract `c8d9827`.

The `c8d9827` contract changes (received transfers in flow lists, receive windows, and the replay-capacity, receive-window and request-deadline refusals) are available on devnet with its next deployment, and on testnet with its next release.
- **Breaking:** `InternalTransferResult`, returned by `AsyncInternalTransfersService.create` (`AsyncPolyester.internal_transfers.create`, and `Polyester.internal_transfers.create`), gains `status`: `"accepted"`, `"rejected"` or `"failed"`, as the service answered the request; empty when the response names none, and `"UNKNOWN(n)"` for a status this version does not know. Receipts that differed only in their status read the same before. `"accepted"` means the transfer has a durable transfer ID, not that it has settled. Migration: equality and serialization of `InternalTransferResult` now include `status`.
- **Breaking:** `heatmap.subscribe_live` now subscribes to the channel the server publishes live buckets on, `public:spot:market:heatmap:<1s|1m|5m|1h>:<symbol_id>:proto`. It used the interval's enum name (`...:heatmap:INTERVAL_1S:...`), which the server acknowledged but never published on, so every interval received nothing. An interval other than `1s`, `1m`, `5m`, `1h` or an enum name such as `INTERVAL_1S` (any case) is now refused with `PolyesterValidationError` before connecting, instead of subscribing to a channel that never delivers. Migration: pass one of those intervals; code that subscribed to the lowercase channel directly as a workaround can use `subscribe_live` again.
- **Breaking:** `heatmap.get` checks `interval` and `quantity_mode` against their own values only. A quantity mode passed as the interval (`interval="PEAK"`) was sent as one minute, and an interval passed as the quantity mode (`quantity_mode="INTERVAL_1M"`) was sent as peak; both, and `INTERVAL_UNSPECIFIED` and `QTY_MODE_UNSPECIFIED`, now raise `PolyesterValidationError` before sending. `interval` takes `1s`, `1m`, `5m`, `1h` or their enum names, and `quantity_mode` takes `close` or `peak`, in any case. Added `polyester.codecs.heatmap.resolve_heatmap_interval` and `resolve_heatmap_quantity_mode`. Migration: pass the interval as `interval` and the quantity mode as `quantity_mode`.
- **Breaking:** `heatmap.get` with `from_ts_sec` and an explicit `end_time` now ends the first page at `end_time`. It ended it at the current time and sent `end_time` only on the continuation, so the server refused the continuation with "page_token does not match request" and the first page ran past the end you asked for. Migration: none, unless you relied on `from_ts_sec` ignoring `end_time`; leave `end_time` unset to read up to now.
- **Breaking:** `heatmap.get` requests the depth you pass when it is a supported depth (1, 5, 10, 20, 50, 100, 200, 500 or 1000), and any other depth up to 1000 as the smallest supported depth covering it, the rule `orderbook.get` follows. It requested the nearest supported depth, so 11 returned 10 levels and 300 returned 200. 0 now requests 50 instead of 1. A depth below 0 or above 1000, or one that is not an `int` (such as `True` or `1.5`), now raises `PolyesterValidationError` before sending, instead of requesting 1 or 1000. The response's `depth` names the depth requested. `polyester.codecs.heatmap.depth_to_proto_name` follows the same rule and refusals, and `polyester.codecs.heatmap.heatmap_depth` gives the depth requested. Migration: pass an `int` from 0 to 1000, and read `depth` from the response for the depth you got.
- **Breaking:** `market_overview.get_spot_volume_history` sends each pair once when `symbols` names it more than once, as it already did for repeated `symbol_ids`. Two `"BTC-USDT"` were sent as two IDs, which the server refused ("repeated value must contain unique items"), and 2,001 copies of one name were refused locally although they select one pair. The 2,000 limit now counts distinct pairs for both forms. Migration: none, unless you relied on the refusal.
- **Breaking:** `CatalogManager.orderbook_price_buckets_for_symbol` returns every digit of a catalog's price buckets. It formatted a numeric bucket to six decimal places, so BONK-USDT's 0.000000001, 0.00000001 and 0.0000001 read as `"0"`. They now read `"0.000000001"`, `"0.00000001"` and `"0.0000001"`; larger buckets read as before, and a `bool` bucket is skipped. Migration: none, unless you replaced the `"0"` buckets yourself.
- **Breaking:** `polyester.codecs.wire_decode.decode_market_overview_list` and `decode_market_overview_entry` read the 24-hour change from `change24hBps` / `change_24h_bps`, the field the API sends, and count the rows returned as `total`, as the protobuf decoder does. They looked for `change24hBp` / `change_24h_bp` and a `total` field the response does not have, so every change read `""` and `total` read 0. A change the JSON omits, which protobuf JSON does for 0, now reads `"0"`. Migration: read `change_24h_bp` and `total` as for the protobuf decoder.
- **Breaking:** `MarketOverviewEntry` gains `sparklines`, a list of `MarketOverviewSparkline` (`interval`, such as `"SPARKLINE_24H"`, and `close_prices`, newest first as the server sends them, as `Price` values), from `market_overview.list`, `market_overview.create_subscription` and `decode_market_overview_list` when `include_sparklines=True` was requested. They were sent but dropped. A managed subscription keeps the snapshot's sparklines when a live update, which carries none, replaces a row. Added `polyester.codecs.decode.market_overview.market_overview_sparkline_from_proto`. Migration: none, unless you compare or serialize whole `MarketOverviewEntry` values, which now include `sparklines`.
- **Breaking:** `ExportGuardSignerWalletResult.private_key` and `Ed25519Keypair.secret_key_hex` and `secret_key` now hold a `polyester.Secret` (also `polyester.models.Secret`) instead of a `str` or `bytes`, so no rendering or serialization path reveals the private key. Their `repr` already redacted it, but Rich (`pretty_repr`, `Console.print`), `msgspec.structs.asdict` and `astuple`, `msgspec.to_builtins`, msgspec JSON and MessagePack encoding and pickling showed or carried it. A `Secret` prints `[REDACTED]` through `repr`, `str`, `format`, logging and Rich; pickling it raises `TypeError` and msgspec refuses to encode it; copies share the value, and `bool()` and `==` compare the value. The models wrap a plain `str` or `bytes` passed to them. Affected: `guard_signer.export_wallet` and `polyester.codecs.decode.guard_signer.export_wallet_from_proto`; `api_keys.generate_keypair`; on the async and the sync client. Migration: read the keys with `result.private_key.reveal()`, `keypair.secret_key_hex.reveal()` and `keypair.secret_key.reveal()`, and store a key you export on purpose from `reveal()`, not by encoding or pickling the whole result.
- **Breaking:** Errors and diagnostics no longer carry the user name or password of a URL. When the API refused a realtime connection or subscription token with HTTP 401 or 403, `PolyesterAuthError.endpoint` and the error text held the token URL with the API URL's userinfo, password included; they now hold it without userinfo, and keep the status, code and the rest of the endpoint. Every realtime token request also handed httpx the API URL with its userinfo, so httpx logged it, password included, at INFO for each request, successful or not, and kept it on the request of its connection and timeout errors. The SDK now gives httpx the URL without userinfo and sends the same Basic auth explicitly, decoded as httpx decoded it; a client with its own `auth` still sends that instead. The signed path and query are unchanged. Signing refused an API URL with an unsupported scheme or no authority, such as `ftp://user:password@host` or `https:user:password@host`, with a `PolyesterAuthError` that quoted the whole URL; its message is now the fixed "Cannot sign malformed absolute HTTP URL", and the realtime token request drops the userinfo before signing. A WebSocket URL that websockets refuses raised its `InvalidURI` with the whole URL; it now names the URL the same way. A REST call that could not reach the API raised an error whose text, and the HTTP client error it chains, quoted the request URL with its userinfo; the SDK now drops the userinfo before sending, which the HTTP client never sent anyway. `TransportConfig` and `TransportFactory` `repr` print the API URL without userinfo. Affected: every private `subscribe` (`api_keys.subscribe`, `address_book.subscribe_view_invalidations`, `balances.subscribe`, `lifecycle.subscribe_open_flows`, `orders.subscribe`, `policies.subscribe_subaccount_policies`, `policies.subscribe_api_policies`, `sub_accounts.subscribe`, `sub_accounts.subscribe_api_keys`, `trades.subscribe`, `transfers.subscribe`, `triggers.subscribe` and `triggers.subscribe_events`), `AsyncRealtimeClient.subscribe_proto`, `subscribe_proto_batch` and `subscribe_private_orders`, `polyester.realtime.auth.fetch_connection_token` and `fetch_subscription_token`, `polyester.auth.sign_request` and `sign_request_async`, every REST call, on the async and the sync client. Migration: none, unless you matched `PolyesterAuthError.endpoint` against a URL that included userinfo; compare it with the URL without userinfo.
- **Breaking:** `lifecycle.list_flows` with `owner_account_id` or `smart_account_address` now also returns the transfers that account received, such as a transfer from another user or from another sub-account of the same main account, or a reward payout. It used to return only the flows the account owns. A `page_token` is now bound to the request it was returned for: sent with a different account, participation, scope or order it raises `PolyesterValidationError`, and tokens issued before this change are refused. `LifecycleFlowSummary` gains `participation` (`"owner"` or `"recipient"` on a list that selects an account, `"unspecified"` on an unscoped list, a flow detail and a realtime update, empty on a transaction lookup), `source_address` and `destination_address`, from `lifecycle.list_flows`, `lifecycle.get_flow`, `lifecycle.subscribe_open_flows` and `lifecycle.subscribe_flow_detail` on `AsyncPolyester` and `Polyester`, and `polyester.codecs.decode.lifecycle.flow_summary_from_proto`, `flows_list_from_proto` and `flow_detail_from_proto`; `lifecycle.get_flow_by_tx`, `lifecycle.list_flows_by_tx` and `polyester.codecs.decode.lifecycle.flows_by_tx_list_from_proto` fill the two addresses too. `lifecycle.list_flows` takes `participation=` (`"owner"` or `"recipient"`) to narrow a list that selects an account; any other value raises `PolyesterValidationError` before anything is sent. Migration: for the previous owner-only list, pass `participation="owner"`; for a transfer, read the counterparty from `destination_address` when `participation` is `"owner"` and from `source_address` when it is `"recipient"`; and restart pagination from the first page instead of reusing a stored `page_token`.
- **Breaking:** An order or trigger write whose receive window (10 seconds without `recv_window_ms`) ends before it is sent on for admission is now refused with `ERROR_CODE_REQUEST_DEADLINE_EXCEEDED` (308; REST 400 `REQUEST_DEADLINE_EXCEEDED`, ConnectRPC `failed_precondition`) and changes nothing. Such a request used to be processed late. It raises `PolyesterApiError` with `code` `ERROR_CODE_REQUEST_DEADLINE_EXCEEDED` (the constant `REQUEST_DEADLINE_EXCEEDED`), which `is_request_deadline_exceeded` reports. It is never an unknown outcome, and `is_retryable_error` now returns `True` for it. Affected, on `AsyncPolyester` and `Polyester`: `orders.create`, `cancel`, `modify`, `cancel_all`, `cancel_all_after`, `batch_create`, `batch_cancel`, `batch_replace` and `stop_all_trading`; and `triggers.create`, `cancel`, `modify`, `pause` and `resume`. Migration: handle it like `PolyesterTimestampSkewError`: send the request again, which signs it with a fresh timestamp.
- `AsyncPolyester` and `Polyester` take `recv_window_ms`, the receive window of every signed API request, sent as the signed `X-API-RECV-WINDOW` header: the server processes a request only until its signing timestamp plus that many milliseconds. It must be an `int` from 1 to 60000; any other value raises `PolyesterValidationError` when the client is built. `None`, the default, sends no header, and the server applies 10000 as before. Realtime token requests always use the default. `polyester.auth.sign_request`, `sign_request_async` and `canonical_signing_string` take the same `recv_window_ms` for requests you sign yourself, signing the window's decimal string on its own line right after the timestamp; `polyester.auth.validate_recv_window_ms`, `MIN_RECV_WINDOW_MS` and `MAX_RECV_WINDOW_MS` check it, and `TransportConfig.recv_window_ms` carries it.
- `AUTH_RECV_WINDOW_INVALID` and `is_recv_window_invalid` name the refusal of an `X-API-RECV-WINDOW` header that is not one whole number from 1 to 60000, empty, or repeated (REST 401 `RECV_WINDOW_INVALID`, ConnectRPC `unauthenticated` with `AuthErrorDetail`). It raises `PolyesterAuthError`, like the other API-key refusals, and is not retryable without fixing the window.
- **Breaking:** `AUTH_REPLAY_CAPACITY_EXHAUSTED` and `is_replay_capacity_exhausted` name the refusal (REST 429 `REPLAY_CAPACITY_EXHAUSTED`, ConnectRPC `resource_exhausted` with `AuthErrorDetail`) that every service that checks signed requests can answer when the API key, or its account, holds its full share of the record that keeps signed requests from being replayed until their receive windows end. It raises `PolyesterRateLimitError` with that `code`, which `auth_error_code` reads, and `is_retryable_error` returns `True`: the credentials are valid, the request was not processed, and the share frees as earlier windows end. It carries no `Retry-After`, so `retry_after` is `None` unless the response named one: back off briefly and send again, which signs again; a shorter `recv_window_ms` makes room sooner. It used to raise a `PolyesterApiError` that was not retryable. Migration: handle it as a retryable `PolyesterRateLimitError` (back off and send again, which signs with a fresh timestamp) instead of a terminal `PolyesterApiError`.
- **Breaking:** A consumer that subscribes to an account's private order stream while that stream is reconnecting now gets `PrivateOrdersConnected` first, then the cached `PrivateOrdersSnapshot`, `PrivateOrdersReady` and `PrivateOrdersStale`, as a consumer joining a connected stream does. It got the cached snapshot (and ready and stale) at once, and `PrivateOrdersConnected` only after the reconnect, so a consumer that set up its state on `Connected` received orders before it. Affected: `orders.subscribe` and `realtime.subscribe_private_orders`, on `AsyncPolyester` and `Polyester`. Migration: none, unless you read the snapshot before `Connected`; set up state on `Connected` and apply the snapshot that follows it.
- **Breaking:** A REST problem whose code belongs to the transfer, withdraw or ledger service now reads with the `ERROR_CODE_` prefix in `PolyesterApiError.code`, and in `PolyesterServerError.code` for a temporary refusal such as `SERVICE_UNAVAILABLE`, as its typed ConnectRPC detail already did and as order codes already did over REST. `internal_transfers.create` refused with `SAME_SOURCE_DESTINATION` over REST and `ERROR_CODE_SAME_SOURCE_DESTINATION` over ConnectRPC; both now read `ERROR_CODE_SAME_SOURCE_DESTINATION`. Likewise `ERROR_CODE_AMOUNT_BELOW_MINIMUM` from `withdraw.create_to_funding`, `withdraw.create_to_external_chain`, `withdraw.create_api_key_to_funding`, `withdraw.create_api_key_to_external_chain` (and its alias `withdraw.create_api_key_to_external`), `withdraw.submit_prepared`, `withdraw.create_wallet_trading_withdraw` and `withdraw.validate_destination`, and `ERROR_CODE_INVALID_SUBACCOUNT_ID` from `balances.list`, `balances.get_balance_history`, `balances.get_equity_history` and `transfers.list`. A code no service's `ErrorCode` names stays as sent, and auth codes keep their `AUTH_` form. A transfer or withdraw code the auth service also names, `INVALID_REQUEST`, stays as sent over REST, which can't say which service refused, so `auth_error_code` still reads `AUTH_INVALID_REQUEST`. Migration: compare against the `ERROR_CODE_` form, or strip the prefix before comparing.
- **Breaking:** A replacement price or quantity finer than the pair's tick or step now raises `PolyesterValidationError` with the code and violation the server answers, as `orders.create` and an `orders.modify` price already did: `ERROR_CODE_PRICE_TICK_SIZE` / `tick_size` at `new_price_ticks`, and `ERROR_CODE_QTY_STEP_SIZE` / `step_size` at `new_qty_scaled`. It raised `FractionalDigitsError` with no code and no violation, so the caller had to parse the message. Affected: the `new_qty` of `orders.modify` and `polyester.codecs.orders.modify_order_to_proto`, and an item's `new_price` and `new_qty` in `orders.batch_replace`, `polyester.codecs.orders.batch_replace_orders_to_proto` and `batch_replace_item_to_proto`. The message is unchanged, and the `FractionalDigitsError` is its `__cause__`. Migration: catch `PolyesterValidationError` and read its `code` and `violations` instead of catching `FractionalDigitsError`.
- **Breaking:** A standalone buy trailing stop with a maximum price (`limit_price`) of zero now raises `PolyesterValidationError` ("trailing_stop with side=buy: limit_price must be positive (the maximum price)") before anything is sent, whether given as a string, a `Decimal` or a `Price`. It was encoded as `limit_price_ticks=0`, which the wire reads as no maximum price. Affected: `triggers.create` and `polyester.codecs.triggers.create_trigger_to_proto`. An attached trailing stop already refused it, as do the Go and Rust SDKs. Migration: pass the most the buy may pay per unit, at least one tick.
- **Breaking:** A market name and a numeric market ID given together must name the same market, or the call raises `PolyesterValidationError` ("… symbol mismatch: 'LTC-USDT' does not match symbol_id 1 (BTC-USDT)") before anything is sent. The ID was sent and the name ignored, so `triggers.modify(symbol="LTC-USDT", symbol_id=1, …)` changed a BTC-USDT trigger. A name the catalog maps to another ID, or that is not the catalog's name for the ID, is refused; without catalogs, or for an ID and a name the catalog doesn't know, the ID is sent as before. A name alone, an ID alone, or both naming one market are unchanged. Affected: `triggers.modify`, `triggers.resume`, `trades.list`, `market_data.get_trades`, `market_data.get_candles`, `market_data.get_candles_columns`, `market_data.get_current_candle`, `market_data.subscribe_trades`, `market_data.subscribe_candles`, `heatmap.get` and `heatmap.subscribe_live`, on `AsyncPolyester` and `Polyester`. The orders methods already refused it. Migration: pass the name or the ID alone, or both for the same market.
- **Breaking:** An attached-risk policy with `oco=True` and only one leg (take-profit, stop-loss or trailing stop alone) now raises `PolyesterValidationError` ("oco requires take_profit and exactly one stop leg (stop_loss or trailing_stop)") before anything is sent, with the contract's `risk_policy.oco_requires_tp_and_one_stop` violation at the policy's field: `order.attached_risk` for `orders.create`, `orders.preview_order` and `orders.batch_create`, and `new_attached_risk` for `orders.modify` and `orders.batch_replace`. It was sent, and the server refused it with `invalid_argument`. This applies to a dictionary and to an `AttachedRisk` model alike, and to the public codecs `polyester.codecs.orders.risk_policy_from_dict`, `order_intent_from_request`, `create_order_to_proto`, `preview_order_to_proto`, `batch_create_orders_to_proto`, `modify_order_to_proto` and `batch_replace_orders_to_proto`. A one-leg policy without `oco`, and an OCO policy with a take-profit and a stop-loss or trailing stop, are sent as before. The Go and Rust SDKs already refuse it. Migration: add the missing leg, or drop `oco` for a single leg.
- **Breaking:** A call on the sync `Polyester` client now ends when its async call ends, for every service method, including `orders.create`, `orders.modify`, `orders.cancel`, `orders.batch_create`, `orders.batch_cancel`, `orders.batch_replace`, `triggers.create`, `triggers.modify`, `internal_transfers.create` and the `withdraw` writes. The sync client waited at most 60 seconds and then raised the built-in `TimeoutError`, for which `mutation_outcome_unknown` was false, while the call went on and could still be sent, retried and applied. A longer configured `timeout`, such as 90 seconds, was cut at 60. The configured `timeout` and a method's own `timeout` now bound the call, as on `AsyncPolyester`: a mutation they cut short raises `PolyesterTimeoutError`, for which `mutation_outcome_unknown` is true. A caller interrupted while it waits, for example by `KeyboardInterrupt`, gets the interruption only once the call has been cancelled, so nothing is sent for it afterwards. A call on a closed client raises `PolyesterError` at once; it waited 60 seconds for `TimeoutError`. `Polyester()` starts its event loop before its first call, and raises `PolyesterError` if that loop can't start. Iterating a subscription on the sync client no longer raises `TimeoutError` after 60 seconds without an event; it waits until an event arrives or the subscription closes, and `Polyester()` construction no longer gives up on its bootstrap after 60 seconds. Migration: catch `PolyesterTimeoutError` (or `PolyesterError`) instead of `TimeoutError`, put your own deadline around sync subscription iteration if you relied on the old 60-second limit, reconcile a mutation whose outcome is unknown before you send it again, and set the client `timeout` to the longest wait you accept.

## 0.13.0

Git tag: `v0.13.0`. Released 2026-11-08. Built on public contract `1bf038e`.

- **Breaking:** `orders.create` and `orders.preview_order` type their keyword arguments, so a type checker such as mypy refuses a misspelt or unknown keyword such as `qyt=`, a call without `side` or `order_type`, and a `CreateOrderRequest` passed together with keywords. Both took `**kwargs: Any`, so such calls type-checked, and only the client refused them at runtime. It still does, naming the keyword, before anything is sent. The keywords are the fields of `CreateOrderRequest`, given by the new `polyester.models.CreateOrderParams` `TypedDict`. Their `account=` now takes the selectors every other method takes, where it was typed as only a string or a `dict[str, str]`. Migration: correct the keyword the type checker names. To build the keywords before the call, annotate the dict as `CreateOrderParams`, or pass a `CreateOrderRequest`; unpacking a `dict[str, Any]` still type-checks.
- **Breaking:** `orders.batch_create` types `items` as `Sequence[CreateOrderRequest | CreateOrderItem]`, where it was `list[CreateOrderRequest | dict[str, Any]]`. A type checker now refuses a dict item with an unknown key or with its own `sub_account_id`, which the client refuses at runtime, as before. The new `polyester.models.CreateOrderItem` `TypedDict` has the fields of `CreateOrderRequest` except `sub_account_id`: the batch's own `sub_account_id` or `account` scopes every item. A `list[dict[str, Any]]` no longer type-checks, and a `list[CreateOrderRequest]` now does. Migration: annotate the items as `list[CreateOrderItem]`, or build `CreateOrderRequest` objects.
- **Breaking:** `withdraw.create_api_key_to_funding` and `withdraw.create_api_key_to_external_chain` (and its alias `withdraw.create_api_key_to_external`) take the keyword-only parameters of `withdraw.prepare_api_key_to_funding` and `withdraw.prepare_api_key_to_external_chain`, where they took `**kwargs`, so a type checker refuses a misspelt keyword. The `TypeError` that names it at runtime, before anything is signed or sent, is unchanged. Migration: correct the keyword the type checker names.
- `orders.create` and `orders.preview_order` accept an `int` `sub_account_id` keyword as the numeric ID, as a `CreateOrderRequest` passed to them already did. `sub_account_id=42` raised `PolyesterValidationError` ("Invalid orders.create request") before sending. 0, `True`, a negative integer and one above 2**64 - 1 are still refused before sending; 0 now with "sub_account_id must be a non-zero ID, not 0". A `batch_create` dict item with an `int` `sub_account_id` is refused as an item scope, like one with a string.
- Every `sub_account_id` parameter is typed `str | int | None`, as `balances.list` already was, so a type checker accepts the numeric ID that the client accepts at runtime. An `int` is the numeric ID, and 0 is refused before sending, as before. `CreateOrderRequest.sub_account_id` and the `sub_account_id` key of `CreateOrderParams` are typed the same way, and an `account=` dict selector may be a `dict[str, str | int]`. Affected: `address_book.list_entries`, `list_transfer_counterparties`, `list_transfer_destinations`, `list_internal_transfer_whitelist_entries`, `get_withdraw_whitelist_view`, `get_view`, `create_entry` and `create_tag`; `api_keys.list`; `balances.get_balance_history` and `get_equity_history`; `deposit.list_addresses` and `create_address`; `fees.get_spot_fee_rates`; `guard_signer.create_wallet`, `get_status`, `sign_protected_action`, `batch_sign_protected_actions`, `rotate_wallet` and `export_wallet`; `internal_transfers.create`; `orders.create`, `preview_order`, `list_open`, `list_history`, `get`, `cancel`, `modify`, `cancel_all`, `cancel_all_after`, `stop_all_trading`, `batch_create`, `batch_cancel`, `batch_replace`, `get_batch_replace_status`, `wait_batch_replace` and `wait_for_order_trades_complete`, and the module-level `polyester.services.orders.wait_for_order_trades_complete`; `rate_limits.get_trading_rate_limits`; `sub_accounts.get`, `list_members` and `list_activity`; `trades.list`; `transfers.list`; `triggers.list`, `get`, `create`, `cancel`, `modify`, `pause`, `resume` and `list_events`; and `withdraw.create_wallet_trading_withdraw`, `create_to_funding` and `create_to_external_chain`, the last two of which still refuse any sub-account selector. Every `account_id` parameter was already typed `str | int | None`.
- **Breaking:** `polyester.codecs.scalars.format_scaled` raises `PolyesterValidationError` ("scale must be non-negative") for a negative scale. It returned the value unchanged, so `format_scaled(12345, -2)` read `"12345"`. The Go SDK refuses a negative scale the same way, and the Rust SDK's scales are unsigned, so a negative one can't be passed. Migration: pass a scale of 0 or more.

## 0.12.0

Git tag: `v0.12.0`. Released 2026-11-07. Built on public contract `1bf038e`.

- `ChangelogPostSummary` (and so `ChangelogPost.summary`) gains `revision` and `updated_at`, from `changelog.list_posts`, `changelog.iter_posts` and `changelog.get_post` (and `changelog_post_summary_from_proto`, `changelog_posts_page_from_proto` and `changelog_post_from_proto`). A published post can now be republished, for example to correct its copy or withdraw a change: `revision` starts at 1 and increases with each republication, and `updated_at` is when the current revision was published. Its `slug`, `published_at` and change ids stay the same. A server that predates revisions sends neither: `revision` reads 0 and `updated_at` `None`. To follow edits, read a post again when its `revision` differs from the one you hold.
- **Breaking:** `changelog.iter_changes` yields each change id once per walk, and `changelog.breaking_changes_since` and `changelog.action_required_since` return each change once, on the async and the sync client. When a post is republished while a walk pages through it, the next page restarts at that post's first change, so changes already received came again and were returned twice. `iter_changes` skips the repeat; the two helpers keep the change at its first position with the wording last received. The helpers still filter on first publication, which a republication does not move, so they don't report an edit to an older post. Migration: none, unless you counted repeats; compare `revision` from `changelog.iter_posts` to find edited posts.
- **Breaking:** A REST `RATE_LIMIT_EXCEEDED` problem now fills `PolyesterRateLimitError.detail` with a `RateLimitDetail` read from its `rate_limit` object, for every call, whichever side refused. Every field is optional: the gateway's own refusal sends only `reason` and `scope` (`CLIENT_IP`, with no `operation_id`), and a service's also names the operation, the policy class and the remaining quota. An integer field that is not ASCII digits within the unsigned 64-bit range, such as `"²"` or a 5000-digit string, reads as absent. `retry_after` now prefers the problem's `retry_after_ms` over the `Retry-After` header, as for a ConnectRPC `RateLimitDetail`, and stays `None` when the server gave no hint, as for a refusal of too many concurrent requests. It used to drop the object and read only `Retry-After`. The gateway's ConnectRPC refusal (`resource_exhausted`, "rate limit exceeded, retry later") still has no detail and falls back to `Retry-After` when present. A 429 problem with another code, such as `AUTH_RESOURCE_EXHAUSTED`, still raises `PolyesterApiError`, which waiting does not resolve. Migration: wait for `retry_after` when it is set, which can now be shorter than `Retry-After`, and back off on your own schedule when it is `None`.
- `REQUEST_TOO_LARGE` and `is_request_too_large` name the uniform HTTP 413 refusal that every service now answers for a request body over its size limit, before authenticating it, on known-length and chunked bodies alike. Ledger reads (balances, balance and equity history, transfers) answered `PAYLOAD_TOO_LARGE` instead until server release 9.2.6, so match `REQUEST_TOO_LARGE` from then on. It already raised `PolyesterApiError` with that `code` and its `problem`, which is not retryable and leaves no unknown outcome: reduce the body to fit the limit. A ConnectRPC message over the limit once decoded keeps its Connect `resource_exhausted` answer.
- `AUTH_WALLET_ALREADY_LINKED` and `is_wallet_already_linked` name the `auth.v1.AuthErrorCode` that `auth_error_code` reads from the ConnectRPC `AuthErrorDetail` (`already_exists`) and the REST 409 problem alike: a valid wallet login whose wallet is already linked to another account. It raises `PolyesterApiError`, terminal and never retryable; log in with the account address the wallet already uses.
- `orders.get_batch_replace_status`, `orders.wait_batch_replace` and `orders.batch_replace` document the 60-second status window: the status is readable as soon as `batch_replace` returns, `unavailable` raises the retryable `PolyesterServerError` (retry the same read within the window), and `not_found` never means a rejected replacement. After the window, reconcile the individual orders and never send an accepted batch again. An item's `updated_ts_ns` is an observation time that can be a later recovery time. `wait_batch_replace` still polls through `not_found` within the window, for APIs that answered it shortly after admission.
- **Breaking:** An account or sub-account ID that decodes to 0 now raises `PolyesterValidationError` before anything is sent, whatever form it arrives in. `"1"` is the public ID of 0, and `"0"` and `"00"` read as 0. Such a sub-account ID was sent as 0, which the server reads as unset, so the call addressed the main account instead of the sub-account named; such an account ID subscribed to the channel of account 0. An int 0 passed straight to a public codec was encoded too, or dropped as no sub-account by `create_order_to_proto` and `preview_order_to_proto`. This covers `sub_account_id=`, an `account=` string or `{"subaccountId": ...}` / `{"sub_account_id": ...}` dict, a request object's `sub_account_id`, the client's `default_sub_account_id` and `default_account_id`, a subscribe `account_id=`, `internal_transfers.create`'s `destination_account_id` and `destination_subaccount_id`, and `lifecycle.list_flows`'s `owner_account_id`. A subscribe `account_id` that isn't a valid ID at all, such as `"acct_test"`, is now refused the same way instead of naming a channel no account has. Omitting the sub-account, or passing `""`, still addresses the main account. Affected, on `AsyncPolyester` and `Polyester`: `api_keys.list`; `address_book.list_entries`, `list_transfer_counterparties`, `list_transfer_destinations`, `list_internal_transfer_whitelist_entries`, `get_withdraw_whitelist_view`, `get_view`, `create_entry` and `create_tag`; `balances.list`, `get_balance_history` and `get_equity_history`; `deposit.list_addresses` and `create_address`; `fees.get_spot_fee_rates`; `guard_signer.create_wallet`, `get_status`, `sign_protected_action`, `batch_sign_protected_actions`, `rotate_wallet` and `export_wallet`; `internal_transfers.create`; `lifecycle.list_flows`; `orders.create`, `preview_order`, `list_open`, `list_history`, `get`, `cancel`, `modify`, `cancel_all`, `cancel_all_after`, `batch_create`, `batch_cancel`, `batch_replace`, `get_batch_replace_status`, `wait_batch_replace`, `wait_for_order_trades_complete` and `stop_all_trading`; `rate_limits.get_trading_rate_limits`; `sub_accounts.get`, `list_members` and `list_activity`; `trades.list`; `transfers.list`; `triggers.list`, `get`, `create`, `cancel`, `pause`, `resume`, `modify` and `list_events`; `withdraw.create_wallet_trading_withdraw`; every private subscribe (`api_keys.subscribe`, `address_book.subscribe_view_invalidations`, `balances.subscribe`, `lifecycle.subscribe_open_flows`, `orders.subscribe`, `policies.subscribe_subaccount_policies`, `policies.subscribe_api_policies`, `sub_accounts.subscribe`, `sub_accounts.subscribe_api_keys`, `trades.subscribe`, `transfers.subscribe`, `triggers.subscribe` and `triggers.subscribe_events`); and the public codecs `polyester.codecs.orders.parse_optional_subaccount_id`, `create_order_to_proto`, `preview_order_to_proto`, `modify_order_to_proto`, `cancel_all_orders_to_proto`, `cancel_all_after_to_proto`, `batch_create_orders_to_proto`, `batch_cancel_orders_to_proto` and `batch_replace_orders_to_proto`, `polyester.codecs.triggers.create_trigger_to_proto` and `modify_trigger_to_proto`, and `polyester.codecs.address_book.create_entry_to_proto`. Added `polyester.codecs.scalars.parse_account_id`, which decodes an account or sub-account ID and refuses 0. Migration: to address the main account, omit the sub-account ID (`None` or `""`), or pass `account="main"`, instead of passing `"1"`, `"0"` or `0`, and pass the public ID of a real account wherever an account ID is required.

## 0.11.0

Git tag: `v0.11.0`. Released 2026-11-07. Built on public contract `748066a`.

- **Breaking:** `orders.wait_for_order_trades_complete` (and the module-level `wait_for_order_trades_complete`) now reports completion only once the order has ended (`filled`, `canceled` or `rejected`) and its trades add up to `cum_qty`, the rule the Go and Rust SDKs follow. It returned as soon as the trades recorded so far added up to `cum_qty`, so a partially filled order that was still working, or a working order with no fills yet, could be reported complete while more fills were still to come. Such an order now keeps the wait polling until it ends or the timeout passes, which raises `PolyesterTransportError`. Migration: call the wait once the order is expected to end (an IOC or FOK order, or after a cancel), and to check the trades recorded so far on an order that is still working, read it with `orders.get` and compare its trades to `cum_qty`.
- Added `polyester.codecs.scalars.format_scaled(value, scale)`, which formats `value / 10**scale` as a decimal string for any non-negative scale.
- **Breaking:** A decimal order quantity that doesn't fit the signed 64-bit wire field now raises `PolyesterValidationError` ("qty exceeds int64 range") before anything is sent. On a market with base quantity scale 18, a quantity of 10 scales to 10000000000000000000, which raised protobuf's `ValueError` ("Value out of range") instead; nothing was sent. Affected: `orders.create`, `orders.preview_order`, `orders.batch_create`, `orders.modify`, `orders.batch_replace` and `triggers.create`, for `qty`, `new_qty` and `max_quote_debit`, `polyester.types.resolve_qty_scaled` and `resolve_quote_qty_scaled`, and `polyester.codecs.orders.create_order_to_wire`, which returned the out-of-range value instead of raising. `parse_qty_scaled` still allows wider values at scale 18. Migration: catch `PolyesterValidationError` instead of `ValueError`, and keep the scaled quantity at or below 9223372036854775807, which is 9.223372036854775807 at scale 18.
- **Breaking:** A `Decimal` quantity, price or amount is checked against its scale and size before it is written out in full. `Decimal("1e-1000000")` used to build a million-digit string and a 1,000,041-character error, and `Decimal("1e+1000000")` a million-digit integer, before being refused; both are now refused at once with a short `PolyesterValidationError`. This applies to every write that takes a `Decimal`, including `orders.create`, `orders.preview_order` and `orders.batch_create`. The value an error repeats is cut to 64 characters. A `Decimal` whose scaled value has more than 75 digits, more than fits a 128-bit wire field even after rescaling from scale 36, is now refused with "… is too large": `polyester.codecs.parse_qty_scaled`, `polyester.codecs.scalars.decimal_to_scaled` and `polyester.types.resolve_asset_amount_scaled` returned it, for example 10**78 for `Decimal("1e60")` at scale 18. `parse_price_ticks`, `resolve_qty_scaled` and `resolve_quote_qty_scaled` refused such values before too, as out of int64 range; for a `Decimal` they now say "is too large". Decimal strings are not affected. Migration: pass a value whose scaled form fits the field you send it to, and catch `PolyesterValidationError`.
- **Breaking:** `Order.cum_quote`, `Order.quote_used` and `Order.quote_unspent` now work at every base quantity scale the catalog accepts, 0 to 36. At base scales 28 to 36 the amount is at 37 to 45 decimals, which `format_qty_scaled` refused, so they raised `PolyesterValidationError`. They now raise `PolyesterValidationError` for a `base_quantity_scale` or `quote_quantity_scale` below 0 or above 36. Below 0 used to give an amount at the wrong scale; above 36 already raised. Migration: pass the pair's scales from the catalog, `CatalogManager.base_quantity_scale_for_symbol_id` and `CatalogManager.quote_quantity_scale_for_symbol`.
- **Breaking:** Independently created credentials for one API key no longer sign identical requests identically. Each `ApiKeyCredentials` had its own timestamp allocator, so two clients for the same key, such as two `AsyncPolyester` or `Polyester` instances, signed the same request in the same millisecond with the same timestamp and signature, which the server rejects as a replay. Every `ApiKeyCredentials` with the same `key_id` now shares one allocator in the process, for `sign_request`, `sign_request_async` and every client call. They therefore also share the five-second timestamp lead: a burst across those clients waits, and the synchronous `sign_request` raises `PolyesterRateLimitError`, once their combined burst fills it, instead of once each client's own burst does. Async clients on separate event loops (each `Polyester` runs its own) wait without blocking each other. The protocol has no cross-process nonce, so use one API key per process. Migration: honor `retry_after` from `sign_request`, or give clients that burst together their own API keys.
- `ApiKeyCredentials` refuses pickling, deep-copying and `dataclasses.asdict`/`astuple` with a `TypeError` that says it holds a private key, for every pickle protocol. These already failed; protocols 0 and 1 raised `pickle.PicklingError`. `repr`, `str` and logging still redact the key, and `copy.copy` and `dataclasses.replace` still work.
- **Breaking:** `orders.batch_replace` and `orders.batch_cancel` raise `PolyesterValidationError` before sending for a dictionary item with a field they don't support, and name it. They used to drop it and send the rest, so a misspelt stop-loss, or a `symbol` on a cancel item, was lost silently. A replace item takes `key`, `new_price`, `new_qty`, `new_client_order_id` and `new_attached_risk`; a cancel item takes `key` and `symbol_id`. Migration: correct a misspelt field, and give a cancel item's market as an integer `symbol_id`.
- `orders.batch_replace` now sends an item's `new_attached_risk`, as the Go and Rust SDKs do: a dictionary in the `orders.modify` form, or the new `BatchReplaceItem.new_attached_risk`. It used to be dropped. An item may change only its attached risk.
- **Breaking:** `orders.batch_cancel` and `orders.batch_replace` accept up to 50 items, the limit the public contract sets, instead of 20; 51 or more still raise `PolyesterValidationError`. `orders.batch_create` keeps its limit of 20. The limits are read from the contract's validation rules; `MAX_BATCH_ITEMS` in `polyester.codecs.orders` is replaced by `BATCH_MAX_ITEMS`, keyed by operation. Migration: read `BATCH_MAX_ITEMS[...]` for the operation instead of `MAX_BATCH_ITEMS`.
- **Breaking:** An `int` sub-account ID is now that numeric ID. `sub_account_id=42` and `account={"subaccountId": 42}` (or `"sub_account_id"`) addressed sub-account 175 instead, because the integer was turned into the string `"42"` and read as a public ID; a larger valid ID such as 9876543219876543219 raised a uint64 range error, and `True` was accepted. A `bool`, a negative integer or one above 2**64 - 1 now raises `PolyesterValidationError` before sending. This applies to `balances.list`, `balances.get_balance_history`, `balances.get_equity_history`, `orders.create`, `orders.preview_order`, `orders.get`, `orders.list_open`, `orders.list_history`, `orders.modify`, `orders.cancel`, `orders.cancel_all`, `orders.cancel_all_after`, `orders.stop_all_trading`, `orders.batch_create`, `orders.batch_cancel`, `orders.batch_replace`, `orders.get_batch_replace_status`, `orders.wait_batch_replace`, `orders.wait_for_order_trades_complete`, `triggers.create`, `triggers.get`, `triggers.list`, `triggers.list_events`, `triggers.modify`, `triggers.pause`, `triggers.resume`, `triggers.cancel`, `trades.list`, `transfers.list`, `internal_transfers.create`, `deposit.create_address`, `deposit.list_addresses`, `fees.get_spot_fee_rates`, `api_keys.list`, `sub_accounts.get`, `sub_accounts.list_activity`, `sub_accounts.list_members`, `address_book.create_entry`, `address_book.create_tag`, `address_book.get_view`, `address_book.get_withdraw_whitelist_view`, `address_book.list_entries`, `address_book.list_internal_transfer_whitelist_entries`, `address_book.list_transfer_counterparties`, `address_book.list_transfer_destinations`, `guard_signer.get_status`, `guard_signer.create_wallet`, `guard_signer.export_wallet`, `guard_signer.rotate_wallet`, `guard_signer.sign_protected_action`, `guard_signer.batch_sign_protected_actions`, `rate_limits.get_trading_rate_limits`, `withdraw.create_wallet_trading_withdraw` and `address_book.subscribe_view_invalidations`. An `int` `account_id` passed to `balances.subscribe`, `orders.subscribe`, `trades.subscribe`, `transfers.subscribe`, `triggers.subscribe`, `triggers.subscribe_events`, `api_keys.subscribe`, `policies.subscribe_api_policies`, `policies.subscribe_subaccount_policies`, `sub_accounts.subscribe`, `sub_accounts.subscribe_api_keys` and `lifecycle.subscribe_open_flows` likewise subscribes to that account's channel. Public ID strings are unchanged. Migration: an `int` you passed must be the numeric ID; pass the public ID string you got from the API as a `str`.
- **Breaking:** An explicit `int` sub-account ID of 0, such as `sub_account_id=0`, `account={"subaccountId": 0}` or `CreateOrderRequest(sub_account_id=0)`, is refused with `PolyesterValidationError` before sending, as is an `int` `account_id` of 0; 0 means no sub-account (the main account) on the wire. This applies to every method in the entry above. `sub_account_id=0` used to be sent as ID 0. Migration: omit the sub-account to act on the main account.
- **Breaking:** `triggers.modify` refuses a `Price` bound to another market for `trigger_price` or `activation_price` when `symbol` or `symbol_id` is given, as trigger creation, order previews and order writes already did. It used to send the price's ticks, so a SOL-USDT price could move a BTC-USDT stop. Both parameters are now typed `str | Decimal | Price`. A bound price for a `symbol_id` the catalogs don't know, or with no catalogs, is refused too, since it can't be checked. Without `symbol` or `symbol_id` the trigger's market isn't known and the price is sent as before. Migration: pass a price for the trigger's market, or an unbound one.
- `Order` from `orders.get`, `orders.list_open`, `orders.list_history`, `orders.wait_for_order_trades_complete` and `orders.subscribe` now has the order's terminal time, origin and MARKET slippage protection, which the server already sent. `terminal_ts_ns` is when the order became terminal, in Unix nanoseconds, and is empty while it is open. `origin` (the new `OrderOrigin`) names its `scope` (`direct`, `attached_risk`, `standalone_trigger` or `system`) and, for a child of a trigger or attached-risk leg, its `trigger_type`, `trigger_id`, `parent_order_id` and `child_seq`; it is `None` when the server sends none. A MARKET order's `market_max_slippage` (a `Price` distance) or `market_max_slippage_bps`, and the `market_client_ref_price` it was measured from, are `None` or 0 when the order has none.
- **Breaking:** `orders.wait_for_order_trades_complete` (and the module-level `wait_for_order_trades_complete`) now bounds every page read by its `timeout`: a slow multi-page read raises `PolyesterTransportError` at the timeout instead of succeeding after it, a read that finishes after the timeout (for example while it decodes) is no longer returned as a success, and a stalled page raises at the timeout instead of when the HTTP timeout ends it. The sleep between polls no longer runs past the timeout, and a timeout of 0 or less times out before any read instead of reading once. A `next_page_token` that repeats a page token of the same read raises `PolyesterResponseContractError` instead of paging forever. The result already carried the final read's `executions_complete`. Migration: pass a timeout long enough to read every execution page, and handle `PolyesterResponseContractError` like any other failed read.
- **Breaking:** `changelog.list_changes`, `changelog.iter_changes`, `changelog.breaking_changes_since` and `changelog.action_required_since` send `start_time` and `end_time` exactly, as protobuf's own conversion does. A time with a fraction of a second before 1970 was sent one second late (1969-12-31T23:59:59.5Z as 00:00:00.5), and the last microseconds of year 9999, such as `datetime.max`, were sent as year 10000, which the server refuses. `codecs.datetime_to_timestamp_dict` returns the same exact values. Migration: none needed, unless you shifted pre-1970 bounds yourself to compensate.
- **Breaking:** Cancelling a task that awaits an SDK call now raises `asyncio.CancelledError`, and `asyncio.timeout` around the call raises `TimeoutError`. Both used to raise `PolyesterServerError` ("Request was cancelled"), so a caller couldn't tell its own deadline from a server failure, and an `asyncio.TaskGroup` reported the cancelled call as a second error. On Python 3.11 a retried read such as `triggers.get` could also miss the cancellation and run on until its retry budget ran out. This applies to every API call, including retried reads and the snapshot read that `orderbook.create_subscription` and `market_overview.create_subscription` make before they return. A `canceled` answer from the server is still `PolyesterServerError`, and a call that runs past the client's own `timeout` raises what it did before. Migration: catch `asyncio.CancelledError` or `TimeoutError` where you caught `PolyesterServerError` for your own cancellations and deadlines, and let `CancelledError` propagate.

## 0.10.0

Git tag: `v0.10.0`. Released 2026-11-07. Built on public contract `748066a`.

- **Breaking:** A zipped-asset supply at a quantity scale of 0 now reads as whole units. `get_deposit_withdraw_config` and `subscribe_zipped_asset_supply` reported a BONK supply of 3582802 as `0.000000000003582802`, because `format_ledger_u128` treated `scale=0` as 18. It now formats at the scale you pass, including 0; leaving `scale` out still means 18. A zipped asset that isn't in the hydrated catalog is still refused. Migration: leave `scale` out, or pass `LEDGER_SCALE`, for 18-decimal balances.
- **Breaking:** `get_deposit_withdraw_config` now reports a token's `decimals` as 0 when the API says 0, instead of 18, matching the Go and Rust SDKs. Migration: treat 0 as a real decimals value.
- **Breaking:** `orderbook.get` requests the smallest snapshot depth covering a depth between snapshot depths, instead of the nearest one, and reports the depth it requested as `depth`: 11 now requests and reports 20 where it requested 10 and reported 11. 0 requests and reports 50 instead of requesting 1 and reporting 0. A depth below 0 or above 1000, or a value that isn't an `int`, now raises `PolyesterValidationError` before any request, instead of requesting 1 or 1000 and reporting the value passed. `depth_to_connect_enum` follows the same rule. Migration: read `depth` for the depth you got, pass an `int` from 0 to 1000, and trim the levels yourself if you need fewer. `orderbook_snapshot_depth` in `polyester.codecs.orderbook` gives the depth requested for a depth.
- **Breaking:** `apply_delta` refuses a delta with a positive quantity at price zero like any other malformed delta: it changes neither side, keeps the sequence and asks for a snapshot refresh, instead of applying it, advancing the sequence and leaving a book that can't be rendered. A managed subscription therefore rebuilds its book from a fresh snapshot (`on_sequence_gap`, then `on_snapshot_refresh`) on such a delta and stays open, instead of closing with an invalid-price error. Migration: none needed; code that resubscribed on that error no longer sees it.
- **Breaking:** Order-book levels from `orderbook.get` and from managed subscriptions carry the book's symbol on each `Price` and `Quantity`, as the Go and Rust SDKs do, so the existing cross-market check now raises `PolyesterValidationError` when one is passed to an order, preview or trigger for another market, which used to be accepted. `side_to_levels` and `orderbook_level_from_proto` take an optional `symbol`. Migration: pass book levels only to the market they were read for; to reuse a value on another market on purpose, build a new one for that market, for example `Price.from_ticks(level.price.ticks, symbol=other)` or `Quantity.from_scaled(level.qty.scaled, scale=level.qty.scale, symbol=other)`.
- **Breaking:** `build_orderbook_data` raises `PolyesterValidationError` for a negative depth, which used to return a view with levels silently dropped from the end of each side. Depth 0 still renders no levels. Migration: pass a depth of 0 or more; to drop the last levels of a side, slice the returned `bids` or `asks` yourself.
- `LedgerTransfer` from `transfers.list` and `transfers.subscribe` now has `balance_after` and `link_id`, which the server already sent. `balance_after` is the account bucket's balance after the transfer, an exact integer at the 18-decimal ledger scale like `amount`; it is `None` when the server sends none, and a zero balance is `"0"`. `link_id` is the decimal correlation ID shared by related legs, empty when there is none.
- Private realtime subscriptions (balances, transfers, trades, triggers, trigger events, lifecycle flows, sub-accounts, API keys, API and sub-account policies and address books) now renew their subscription and connection tokens on the same connection before they expire. The server used to end each one about once a token lifetime with code 2501, or close the connection, and it reconnected, reporting the error and counting a resubscribe every time. A renewal that the token API or the server refuses is reported through `set_on_error(...)`; the server then ends the subscription and it resubscribes as before. `subscribe_private_orders` already renewed its tokens and is unchanged.
- **Breaking:** A market selector must be an integer market ID, or a list of them where a list is accepted. Every `symbol_id=` and `symbol_ids=` argument now follows this rule, including `fees.get_spot_fee_rates`, `orders.cancel_all` (both forms), `heatmap.get`, `heatmap.subscribe_live`, `market_data.get_trades`, `get_candles`, `subscribe_trades` and `subscribe_candles`, `trades.list`, `triggers.modify`, `triggers.resume` and `market_overview.get_spot_volume_history`, as well as a `symbol_id` on a `CreateOrderRequest` passed to `orders.create`, `orders.preview_order` or `orders.batch_create` and a `batch_cancel` item's `symbol_id`. They raise `PolyesterValidationError` before sending for a str, bytes, float, `Decimal`, bool, mapping or a value outside 0 to 4294967295. These used to be converted: `"12"` selected markets 1 and 2, `8.9` market 8 and `True` market 1, so a fee read, a preview or a cancel-all could act on markets you didn't name. Keyword `symbol_id` arguments to `orders.create` and `orders.preview_order` were already refused. Python integers and integer types such as NumPy's are still accepted. Migration: pass `int` market IDs, for example `[12]` instead of `"12"`, and resolve a display symbol with `symbol=`/`symbols=` instead of passing it as an ID.

## 0.9.0

Git tag: `v0.9.0`. Released 2026-11-07. Built on public contract `748066a`.

- `orderbook.create_subscription` at a depth the server doesn't publish no longer goes silent after its first view. Depths 5, 10, 25 and 100, for example, were accepted by the server and got no updates, with no error. Any depth from 1 to 500 now subscribes to the smallest published depth that covers it (1, 20, 50, 200 or 500), takes its snapshot there, and trims each view to the depth you asked for. Sequence-gap, availability and bucket behaviour are unchanged, and a view can update when only levels outside it changed.
- **Breaking:** `orderbook.create_subscription` raises `PolyesterValidationError` before connecting for a depth above 500, which used to be clamped to 500 and report that depth, and for a depth below 1 or that isn't an `int`, which used to be clamped or converted with `int()`. That now refuses `20.0`, `"10"`, `True` and NumPy integers such as `np.int64(10)`. Migration: pass a depth from 1 to 500 as an `int`, using `int(depth)` for a NumPy value, or read a snapshot of up to 1000 levels with `orderbook.get`, which is unchanged.
- **Breaking:** `orderbook.subscribe_deltas` raises `PolyesterValidationError` before connecting for any depth other than 1, 20, 50, 200 or 500, or for a value that isn't an `int`, instead of subscribing to a stream that sends nothing or clamping to 1 or 500. Raw deltas can't be trimmed. Migration: pass a published depth as an `int`, or use `orderbook.create_subscription` for a book at any depth up to 500.
- Added `ORDERBOOK_STREAM_DEPTHS`, `orderbook_stream_tier` and `require_published_stream_depth` in `polyester.codecs.orderbook`, the published stream depths and the checks the client uses.

## 0.8.0

Git tag: `v0.8.0`. Released 2026-11-07. Built on public contract `748066a`.

**Known issue:** a managed order book subscribed at a depth other than 1, 20, 50,
200 or 500 can stop updating with no error. Use one of those depths until the
next release.

- A resubscribe on a confirmed private order stream that the server never answers no longer waits forever: after 30 seconds it reports `PrivateOrdersError(kind="subscribe")` and subscribes again with backoff.
- `Polyester.close()` now closes every subscription and the client even when a subscription failed with no `on_error`, then raises the first such failure.
- **Breaking:** A realtime subscription the server ends no longer stays open and silent. Its iterator yields what is queued, then raises the new `PolyesterSubscriptionEndedError` (a `PolyesterRealtimeError`), also reported through `error` and the error callback, with the channel, the server's code and text, and `reason`. Managed order books and market overviews finish their iterator and report it through `last_error` and `on_error`. Migration: handle the error; subscribe again if you still need the stream. Server unsubscribe codes from 2500 ask for a new subscribe and reconnect as before.
- A sub-account's balances, transfers, trades, triggers and lifecycle subscriptions now resume after a server unsubscribe while `ListSubaccounts` lists the sub-account with a role, using a fresh token and reporting the gap through `take_resubscribed()`. They stop with the reason after a `removed` update on this client, when not listed, when the list or token is refused, or after 6 attempts. List reads and attempts are paced across the client.
- Managed order books request an unavailable snapshot again, after 1 s doubling to 8 s, until it is available or the subscription stops. Repeated unavailable answers add no view. A market that stays unavailable keeps being requested once every 8 s. A failed request ends the subscription like a failed sequence-gap refresh.
- **Breaking:** An HTTP error with no recognised code no longer reports a known failure, because a gateway or an edge can send it too. No code, an empty code, the placeholder `ERROR_CODE_UNSPECIFIED` or `AUTH_UNSPECIFIED`, a service detail with no code or with a code this SDK can't name, unless a recognised refusal Connect code stands behind it, an unrecognised code, Connect `unknown`, `data_loss` or `canceled`, HTML, text or an empty body now raise `PolyesterServerError` with outcome unknown and not retryable at every status except 401 and 403, which stay `PolyesterAuthError`. That includes 400, 404 with a JSON body, 405, 409, 412, 422, 500, 501 and 520, which raised `PolyesterApiError` or `PolyesterNotImplementedError`. Trigger reads still retry 429, 502, 503 and 504; retry other reads yourself if you want to. Creates are sent once. A bare 404 stays `PolyesterRouteNotFoundError`, now with outcome unknown. A well-formed unrecognised code at 429 stays a known `PolyesterApiError`. REST `INTERNAL_ERROR`, `SERVER_ERROR` and `GATEWAY_MISCONFIGURED` at 500 now raise `PolyesterServerError`, and REST codes at 409, 413 and 501 keep their code instead of `unknown`. Migration: read back after these errors instead of treating them as refusals, and branch on `error.code` only for codes the contract defines; a validation code newer than this SDK reads outcome unknown until you upgrade, which errs toward reading back.
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
- **Breaking:** Structured order-service admission refusals now report outcome known while remaining retryable. This corrects the previous outcome-unknown result for typed `orders.v1.ErrorDetail` codes `UNAVAILABLE`, `FEE_SCHEDULE_UNAVAILABLE`, `POLICY_UNAVAILABLE`, `RATE_LIMIT_POLICY_UNAVAILABLE` and other documented temporary admission refusals. Specific code-only Connect messages now preserve their refusal code. `ACCOUNT_ROUTING_INVALID` is known and non-retryable. Unrecognized dependency failures remain ambiguous.
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
