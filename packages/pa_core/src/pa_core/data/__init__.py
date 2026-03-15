__all__ = [
    "BAR_ARRAY_COLUMNS",
    "BarArrays",
    "BarParitySummary",
    "CANONICAL_BAR_COLUMNS",
    "CONTINUOUS_VERSION",
    "ChinaFuturesTickTradeIngestionConfig",
    "ChinaFuturesContractBarConfig",
    "ChinaFuturesContinuousV0Config",
    "CanonicalBarIngestionConfig",
    "VendorMinuteBar",
    "bar_arrays_from_frame",
    "build_cn_futures_continuous_v0_table",
    "build_cn_futures_contract_bar_table",
    "compare_tick_trades_to_vendor_1m",
    "compare_contract_bars_to_vendor_1m",
    "derive_vvtr_zip_password",
    "load_vendor_1m_bars",
    "load_trading_day_aligned_vendor_1m_bars",
    "load_bar_arrays",
    "materialize_cn_futures_contract_bars",
    "materialize_cn_futures_contract_bars_from_trade_data_version",
    "materialize_cn_futures_continuous_v0",
    "run_cn_futures_1m_parity",
    "materialize_cn_futures_trade_events",
    "materialize_canonical_bars",
]


def __getattr__(name: str):
    if name not in __all__:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    from .canonical_bars import (
        CANONICAL_BAR_COLUMNS,
        CanonicalBarIngestionConfig,
        materialize_canonical_bars,
    )
    from .cn_futures_ticks import (
        ChinaFuturesTickTradeIngestionConfig,
        derive_vvtr_zip_password,
        materialize_cn_futures_trade_events,
    )
    from .cn_futures_contract_bars import (
        ChinaFuturesContractBarConfig,
        build_cn_futures_contract_bar_table,
        materialize_cn_futures_contract_bars,
        materialize_cn_futures_contract_bars_from_trade_data_version,
    )
    from .cn_futures_continuous_bars import (
        CONTINUOUS_VERSION,
        ChinaFuturesContinuousV0Config,
        build_cn_futures_continuous_v0_table,
        materialize_cn_futures_continuous_v0,
    )
    from .cn_futures_bar_parity import (
        BarParitySummary,
        VendorMinuteBar,
        compare_contract_bars_to_vendor_1m,
        compare_tick_trades_to_vendor_1m,
        load_trading_day_aligned_vendor_1m_bars,
        load_vendor_1m_bars,
        run_cn_futures_1m_parity,
    )
    from .bar_arrays import (
        BAR_ARRAY_COLUMNS,
        BarArrays,
        bar_arrays_from_frame,
        load_bar_arrays,
    )

    exports = {
        "BAR_ARRAY_COLUMNS": BAR_ARRAY_COLUMNS,
        "BarArrays": BarArrays,
        "BarParitySummary": BarParitySummary,
        "CANONICAL_BAR_COLUMNS": CANONICAL_BAR_COLUMNS,
        "CONTINUOUS_VERSION": CONTINUOUS_VERSION,
        "ChinaFuturesTickTradeIngestionConfig": ChinaFuturesTickTradeIngestionConfig,
        "ChinaFuturesContractBarConfig": ChinaFuturesContractBarConfig,
        "ChinaFuturesContinuousV0Config": ChinaFuturesContinuousV0Config,
        "CanonicalBarIngestionConfig": CanonicalBarIngestionConfig,
        "VendorMinuteBar": VendorMinuteBar,
        "bar_arrays_from_frame": bar_arrays_from_frame,
        "build_cn_futures_continuous_v0_table": build_cn_futures_continuous_v0_table,
        "build_cn_futures_contract_bar_table": build_cn_futures_contract_bar_table,
        "compare_contract_bars_to_vendor_1m": compare_contract_bars_to_vendor_1m,
        "compare_tick_trades_to_vendor_1m": compare_tick_trades_to_vendor_1m,
        "derive_vvtr_zip_password": derive_vvtr_zip_password,
        "load_trading_day_aligned_vendor_1m_bars": load_trading_day_aligned_vendor_1m_bars,
        "load_vendor_1m_bars": load_vendor_1m_bars,
        "load_bar_arrays": load_bar_arrays,
        "materialize_cn_futures_contract_bars": materialize_cn_futures_contract_bars,
        "materialize_cn_futures_contract_bars_from_trade_data_version": materialize_cn_futures_contract_bars_from_trade_data_version,
        "materialize_cn_futures_continuous_v0": materialize_cn_futures_continuous_v0,
        "run_cn_futures_1m_parity": run_cn_futures_1m_parity,
        "materialize_cn_futures_trade_events": materialize_cn_futures_trade_events,
        "materialize_canonical_bars": materialize_canonical_bars,
    }
    return exports[name]
