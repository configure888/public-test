# Microstructure Enrichment Pipeline

## Purpose

Pine is the deterministic candidate generator. It does **not** have venue-native L2, true aggressor flow, spread/depth, funding, or open-interest state. The external service enriches the exact Pine `event_id` with those fields before Jev or shadow evaluation.

## Event path

```
TradingView Pine
   -> /webhook/tradingview/{token}
   -> idempotent events table
   -> nearest streamed microstructure snapshot
      OR REST live fallback
   -> enrichment attached to event_id
   -> optional /jev/request/{event_id}
   -> external Jev typed decision
   -> /webhook/jev/{token}
   -> deterministic fail-closed policy
   -> shadow trade only
```

No live order router exists in this repository.

## Binance USD-M

REST enrichment uses public endpoints under `https://fapi.binance.com`:

- `/fapi/v1/depth`: book snapshot.
- `/fapi/v1/aggTrades`: recent aggregate trades; `m=true` means the buyer was the maker, therefore the taker/aggressor was a seller.
- `/fapi/v1/premiumIndex`: mark, index, latest funding and next funding time.
- `/fapi/v1/openInterest`: current OI.

The live streamer uses the current USD-M public WebSocket route:

`wss://fstream.binance.com/public/ws`

and dynamically subscribes to `<symbol>@depth20@100ms` and `<symbol>@aggTrade`.

Binance migrated USD-M WebSocket traffic in 2026 to separated `/public`, `/market` and `/private` paths. Keep the endpoint configurable; do not bury it in strategy logic.

Official references:

- https://developers.binance.com/en/docs/products/derivatives-trading-usds-futures/websocket-market-streams/Live-Subscribing-Unsubscribing-to-streams
- https://developers.binance.com/en/docs/products/derivatives-trading-coin-futures/change-log

## Hyperliquid

REST enrichment uses:

`POST https://api.hyperliquid.xyz/info`

with:

- `{"type":"l2Book","coin":"BTC"}`
- `{"type":"metaAndAssetCtxs"}`

The live streamer connects to:

`wss://api.hyperliquid.xyz/ws`

and subscribes to:

- `l2Book`
- `trades`
- `activeAssetCtx`

The active asset context supplies mark, oracle, funding and open interest. Hyperliquid documents a maximum of 20 book levels per side for the L2 info snapshot and recommends reconnect logic for WebSocket clients.

Official references:

- https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/info-endpoint
- https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/info-endpoint/perpetuals
- https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/websocket/subscriptions
- https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/rate-limits-and-user-limits

## Feature definitions

### Book

- `spread_bps = (ask - bid) / mid * 10,000`
- `microprice = (ask * bid_qty + bid * ask_qty) / (bid_qty + ask_qty)`
- `microprice_edge_bps = (microprice - mid) / mid * 10,000`
- top-5 / top-10 / top-20 bid and ask depth
- `book_imbalance_N = (bid_depth_N - ask_depth_N) / (bid_depth_N + ask_depth_N)`

These are descriptive state variables, not assumed alpha.

### Aggressor flow

For a rolling live trade window:

- taker-buy quantity / notional
- taker-sell quantity / notional
- quantity CVD
- notional CVD
- trade imbalance
- buy-notional ratio
- actual elapsed trade-window milliseconds

The elapsed window is stored because a fixed count of trades does not imply a fixed amount of clock time.

### Perpetual context

- funding rate
- open interest
- mark price
- index/oracle price
- basis in bps
- daily notional volume when supplied by venue

## Staleness

Every event stores:

- Pine event timestamp
- market snapshot timestamp
- absolute capture distance in milliseconds
- source (`stream_cache` or `rest_live`)
- `stale` flag

The default nearest-snapshot tolerance is 5 seconds. Tighten this after measuring actual TradingView webhook latency.

## Storage

SQLite/WAL is intentionally the first deployment target:

- single-node, auditable, easy to back up;
- unique `event_id` prevents duplicate webhook rows;
- enriched features are copied into the event row, so rolling raw snapshots can be pruned without destroying the training record.

Move snapshots to Parquet/object storage once volume justifies it. Do not introduce Kafka/ClickHouse simply because they are fashionable; introduce them when throughput or retention requires them.

## Research rule

Never let post-event microstructure enter a pre-trade feature set. Any after-entry trajectory data must have a separate namespace and is valid only for labels/execution analysis.
