# China Futures Tick Profile

Status: active source-profile contract
Last updated: 2026-03-15
Project root: `/Users/simongu/Projects/PA quantitative`

## Purpose

This document captures the source-specific contract for the encrypted China-futures data hosted on `homebox`.

It exists to keep source quirks contained in one place while the canonical architecture stays:

`market_events -> bars -> features -> structures -> overlays -> review`

This profile is subordinate to:

- `/Users/simongu/Projects/PA quantitative/docs/canonical_spec.md`
- `/Users/simongu/Projects/PA quantitative/docs/artifact_contract.md`
- `/Users/simongu/Projects/PA quantitative/docs/tick_data_spec.md`

## Storage Policy

Bulk China-futures data should stay on the large data disk, not in the repo checkout and not on the Mac SSD.

Preferred `homebox` layout:

- raw vendor zips: `/mnt/data980/期货/Tick` and `/mnt/data980/期货/1m`
- normalized artifacts: `/mnt/data980/期货/PA_quantitative/artifacts/market_events/...`
- parity audits: `/mnt/data980/期货/PA_quantitative/artifacts/market_events/.../checks/bar_parity/...`
- tick-built bars later: `/mnt/data980/期货/PA_quantitative/artifacts/bars/...`

The repo checkout keeps:

- code
- specs
- tests
- small manifests and sample fixtures only

## Raw Source Families

Current discovered source families:

- `Tick`: encrypted daily zip archives with one CSV member per contract
- `1m`: encrypted daily zip archives with one CSV member per contract, plus continuous contracts such as `8888`, `9998`, and `9999`

Current known storage split:

- before `2025-05-01`, `Tick` archives are organized by trading day
- from `2025-05-01` onward, `Tick` archives are organized by natural day and require explicit night/day merge logic

Current implementation scope:

- only pre-`2025-05-01` trading-day `Tick` archives are normalized
- only the `trades` dataset class is materialized
- a durable per-minute parity audit now exists against the vendor `1m` archive for overlapping contract-days

## Vendor Password Rule

Encrypted archives use a deterministic filename-derived password:

- `password = sha256(f"{zip_filename}vvtr123!@#qwe")`

The `.zip` suffix is part of `zip_filename`.

Example:

- `20250303.zip -> 78cb5b101f83e75e304c9f80300099508eec6a1c036ecc07e82ae1bed4854be0`

## Raw Tick Fields

Observed tick CSV header:

```csv
TradingDay,InstrumentID,UpdateTime,UpdateMillisec,LastPrice,Volume,BidPrice1,BidVolume1,AskPrice1,AskVolume1,AveragePrice,Turnover,OpenInterest
```

Interpretation:

- `TradingDay`: vendor trading-day integer such as `20250303`
- `InstrumentID`: contract code such as `ag2505`
- `UpdateTime` + `UpdateMillisec`: local source wall-clock time
- `LastPrice`: latest trade price, not bid/ask
- `Volume`: cumulative traded volume
- `Turnover`: cumulative turnover
- `OpenInterest`: latest open-interest snapshot
- `BidPrice1/BidVolume1/AskPrice1/AskVolume1`: top-of-book snapshot

Important nuance:

- not every raw row is a new trade
- some rows are quote/state refreshes with unchanged cumulative trade fields

## `1m` Reference Fields

Observed `1m` CSV header:

```csv
exchange,symbol,open,close,high,low,amount,volume,position,bob,eob,type,sequence
```

This source is the first reference surface for parity checks once tick-built bars are introduced.

## Databento Alignment

This source aligns best to Databento semantics as follows:

- `trades`: good fit
- top-of-book quotes: good fit as `quotes_l1`
- `tbbo`: approximate fit only
- `mbp-1`: not a faithful fit
- `mbo`: not supported

Why `tbbo` is only approximate:

- the source provides `LastPrice` plus top-of-book snapshot fields on the same row
- the source does not prove that the bid/ask snapshot is the strict pre-trade BBO in the Databento `tbbo` sense
- there are no visible bid/ask order-count fields

Current policy:

- normalize strict `trades` first
- retain trade-adjacent L1 snapshot fields on the normalized trade rows
- add a dedicated `quotes` or `tbbo_like` dataset later instead of overclaiming strict Databento `tbbo`

## Initial Normalized `trades` Contract

Initial normalized artifact path:

```text
artifacts/market_events/data_version=<cnfut_trades_v1_hash>/dataset=trades/symbol=<instrument_id>/year=<year>/part-00000.parquet
```

Current row contract:

- `event_id`
- `event_order`
- `symbol`
- `instrument_id`
- `exchange`
- `ts_utc_ns`
- `ts_local_ns`
- `session_id`
- `session_date`
- `event_action`
- `source_event_ref`
- `price`
- `size`
- `turnover_delta`
- `open_interest`
- `bid_price_1`
- `bid_size_1`
- `ask_price_1`
- `ask_size_1`

Current semantics:

- `event_order` is the raw source row number within the member CSV
- `event_action` is currently always `published`
- `session_id` and `session_date` are currently both the source `TradingDay`
- `ts_local_ns` and `ts_utc_ns` now map evening-session rows in pre-`2025-05-01` trading-day archives onto the previous natural day, while midnight and day-session rows stay on the stated `TradingDay`
- `price` comes from `LastPrice`
- `size` is the positive delta of cumulative `Volume`
- `turnover_delta` is the positive delta of cumulative `Turnover`
- top-of-book fields are carried as source-adjacent trade snapshots for later L1 work

Trade emission rule:

- emit a normalized trade row only when `LastPrice` is present and cumulative `Volume` increases positively

Reset rule:

- if cumulative `Volume` or `Turnover` moves backward, treat the row as a new baseline instead of producing a negative trade delta

## Initial Cleaning Rules

Current required cleaning:

- combine `TradingDay`, `UpdateTime`, and `UpdateMillisec` into a source-local timestamp, treating evening-session rows as the previous natural day for these trading-day archives
- convert the source-local timestamp into UTC
- treat blank numeric cells as null, not zero
- derive per-trade `size` from cumulative `Volume`
- derive `turnover_delta` from cumulative `Turnover`
- preserve source row ordering exactly
- reject member files whose `InstrumentID` does not match the requested member stem

Current explicit non-goals:

- no correction/cancel reconstruction
- no post-`2025-05-01` natural-day merge yet
- no continuous-contract synthesis from tick yet
- no strict `tbbo` semantics claim yet

## Integration Stack

The intended stack for this source is:

1. `Tick` encrypted zip on `/mnt/data980/期货/Tick`
2. stream one member through `7z` using the deterministic password rule
3. normalize vendor rows into canonical `artifacts/market_events/dataset=trades`
4. validate tick-built `1m` bars against vendor `1m`
5. materialize canonical China-futures bars from normalized trades
6. wire tick-backed replay transport only after bar parity is proven

## Deferred Datasets

The next planned datasets for this source are:

- `quotes_l1`
- `tbbo_like`
- correction-resolved `effective_trades`
- tick-built `1m`

## Current Implementation Hooks

Current code entrypoints:

- `packages/pa_core/src/pa_core/data/cn_futures_ticks.py`
- `packages/pa_core/src/pa_core/artifacts/market_events.py`
- `packages/pa_core/src/pa_core/data/cn_futures_bar_parity.py`
- `packages/pa_core/src/pa_core/artifacts/bar_parity.py`

Current CLI:

```bash
cd packages/pa_core && PYTHONPATH=src python3 -m pa_core.data.cn_futures_ticks \
  --source-zip /mnt/data980/期货/Tick/202503/20250303.zip \
  --member ag2505.csv \
  --exchange SHFE \
  --artifacts-root /mnt/data980/期货/PA_quantitative/artifacts

cd packages/pa_core && PYTHONPATH=src python3 -m pa_core.data.cn_futures_bar_parity \
  --tick-zip /mnt/data980/期货/Tick/202503/20250303.zip \
  --tick-member ag2508.csv \
  --reference-zip /mnt/data980/期货/1m/2025/202503/20250303.zip \
  --reference-member ag2508.csv \
  --exchange SHFE \
  --artifacts-root /mnt/data980/期货/PA_quantitative/artifacts
```

## Next Step

Characterize the remaining mismatched vendor `1m` buckets precisely, then design the first canonical tick-built `1m` bar dataset and manifest path without overloading the current ES-specific bar schema.
