# TypeScript SDK Service Map

This map translates `packages/polyester-client` into the intended Python SDK surface. The goal is to mirror the useful TypeScript service tree while respecting the Python SDK boundary: API-key auth only, no browser wallet/session behavior.

Status values:

- `mirror`: implement the same capability in Python.
- `mirror with API-key caveat`: implement if the backend allows API-key access; document server-side permission/MFA restrictions clearly.
- `defer`: do not block the first useful SDK, but keep a reserved service name or roadmap note.
- `omit`: intentionally out of scope for the Python SDK.

## Client Classes

| TypeScript | Python | Status | Notes |
| --- | --- | --- | --- |
| `PolyesterClient` | `AsyncPolyester` core internals | `mirror` | Shared service tree, transport setup, catalog hydration, API-key auth. |
| `PolyesterBrowserClient` | none | `omit` | Browser JWT, wallet login, cookie/local state, and Svelte-style auth state are out of scope. |
| `PolyesterServerClient` | `AsyncPolyester`, `Polyester` | `mirror` | Python server/bot clients use API keys directly, not cookies or JWT session data. |
| `createPolyesterServerClientFromCookies` | none | `omit` | Cookie parsing is intentionally excluded. |

## Core Service Tree

| TypeScript service | Python service | Status | Notes |
| --- | --- | --- | --- |
| `client.accounts` | `client.accounts` | `mirror with API-key caveat` | Keep `resolve(...)`; confirm backend permission for API keys. |
| `client.apiKeys` | `client.api_keys` | `mirror with API-key caveat` | Include list/get/create/update/delete/generate_keypair. Mutation methods may require MFA/step-up policy support. |
| `client.policies.apiKey` | `client.policies.api_key` | `mirror with API-key caveat` | Mirror list/get/create/update/delete/apply where API-key auth can call them. |
| `client.policies.subaccount` | `client.policies.sub_account` | `mirror with API-key caveat` | Mirror policy management and subscription channel where permitted. |
| `client.subAccounts` | `client.sub_accounts` | `mirror with API-key caveat` | Mirror list/get/create/update/member/invite/event APIs if API-key auth has permission. |
| `client.orders` | `client.orders` | `mirror` | Highest priority trading surface: list open/history, create, cancel, modify, cancel_all, get, subscribe. |
| `client.triggers` | `client.triggers` | `mirror` | Mirror create/get/list/cancel/modify/pause/resume/list_events and realtime subscriptions. |
| `client.trades` | `client.trades` | `mirror` | User trade history and private trade stream. |
| `client.balances` | `client.balances` | `mirror` | Balances, balance history, equity history, private balance stream. |
| `client.transfers` | `client.transfers` | `mirror` | Transfer history and private transfer stream. |
| `client.deposit` | `client.deposit` | `mirror` | Deposit address create/list with subaccount resolution. |
| `client.addressBook` | `client.address_book` | `mirror with API-key caveat` | Mirror address books, entries, tags, counterparties, transfer destinations, whitelist views. |
| `client.guardSigner` | `client.guard_signer` | `mirror with API-key caveat` | Guard signer mutations may require fresh step-up tokens; keep option shape if supported. |
| `client.mfa` | `client.mfa` | `mirror with API-key caveat` | Useful only if API keys can complete step-up flows; otherwise document as unavailable. |
| `client.socialVerification` | `client.social_verification` | `defer` | User/social flows are not trading-bot core and may not fit API-key auth. |
| `client.whiteboard` | `client.whiteboard` | `defer` | Collaboration feature, not trading-bot core. Implement only if the full API mirror requirement remains important after trading services land. |

## Public Market and Chain Data

| TypeScript service | Python service | Status | Notes |
| --- | --- | --- | --- |
| `client.candles` | `client.candles` | `mirror` | List row data, columnar data, integer columnar data, and candle streams. |
| `client.marketData` | `client.market_data` | `mirror` | Market trades, spot config, public trade stream. |
| `client.marketOverview` | `client.market_overview` | `mirror` | List and update stream. |
| `client.orderbook` | `client.orderbook` | `mirror` | Snapshot plus delta subscription/orderbook maintainer. |
| `client.heatmap` | `client.heatmap` | `mirror` | Unary heatmap and live heatmap stream. |
| `client.lifecycle` | `client.lifecycle` | `mirror` | Lifecycle flow list/get/by transaction and public streams. |
| `client.zipper` | `client.zipper` | `mirror` | Deposit/withdraw config and catalog hydration. |

## Bridge Services

TypeScript has `services/bridge/*` modules for auth, balances, chains, deposits, fees, tokens, and transactions. These are not currently wired into `PolyesterClient` in the same way as the core services and several methods are placeholder-like or wallet-token oriented.

Python should mark bridge as `defer`:

- Reserve `client.bridge` only if product direction requires it.
- Do not block core trading SDK work on bridge parity.
- If bridge is added, treat it as a separate service group with explicit auth requirements rather than silently mixing it into exchange trading APIs.

## Omitted TypeScript Areas

Omit these from Python:

- `services/auth/wallet-auth.ts`
- `wallet/*`
- smart-account helpers from `shared/smart-account.ts`
- cookie helpers from `utils/cookies.ts`
- browser token/session helpers from `shared/polyester-token.ts` and `shared/polyester-session.ts`
- `mock/*` local mock runtime
- `browser-client.ts` and cookie-based helpers in `server-client.ts`

The Python SDK should not grow alternate auth modes unless the product explicitly decides to support JWT or wallet login from Python.

## Subaccount Resolution

TypeScript resolves `subAccountId` with this priority:

1. Explicit empty string `""`: force main account by omitting subaccount from the request.
2. Explicit non-empty string: use that subaccount ID.
3. Missing value: ask the active-account resolver for a default subaccount.

Python has no browser auth state, so the resolver should be explicit:

- Client config may accept `default_sub_account_id: str | None`.
- Each service method that supports subaccounts accepts `sub_account_id: str | None = None`.
- Passing `sub_account_id=""` should force main account, matching TypeScript.
- Passing `None` uses `default_sub_account_id` if configured.

Use Python spelling `sub_account_id` publicly, but convert to protobuf `subaccount_id` or `subaccountId` equivalents internally.

## Catalog Hydration

TypeScript initializes build-time catalogs and hydrates them at startup from:

- `marketData.getSpotConfig()`
- `zipper.getDepositWithdrawConfig()`

Python should mirror this as a lightweight catalog manager:

- Bundle generated fallback catalogs if available in the Python repo.
- Hydrate lazily or on client startup with best-effort error handling.
- Never fail client construction just because catalog hydration fails.
- Keep helpers for symbol lookup, asset lookup, display formatting, and symbol ID conversion.

## Formatting and Codecs

The TypeScript SDK converts wire-level protobuf values into user-facing labels and display strings. Python should keep equivalent helpers:

- Enums: side, order type, TIF, fee source, STP mode, trigger type, lifecycle state, market overview status, policy values.
- IDs: base58 display strings backed by uint64 wire values.
- Quantities/prices: string decimal input to scaled integer wire values.
- Timestamps: protobuf timestamps and nanosecond integers to Python `datetime` or integer millisecond/nanosecond fields.
- u128 values: decode to exact integer and expose display helpers where TS does.

Do not expose raw protobuf enum integers as the primary public API.
