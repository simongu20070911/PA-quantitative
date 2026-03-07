__all__ = [
    "EMA_BAR_FINALIZATION",
    "EMA_DTYPE",
    "EMA_FEATURE_KEY",
    "EMA_FEATURE_VERSION",
    "EMA_SOURCE_FIELD",
    "EMA_TIMING_SEMANTICS",
    "EMA_WARMUP_MULTIPLIER",
    "EDGE_FEATURE_KEYS",
    "EDGE_FEATURE_VERSION",
    "EdgeFeatureMaterializationConfig",
    "build_ema_feature_spec",
    "build_initial_edge_feature_specs",
    "compute_ema_values",
    "compute_initial_edge_feature_bundle",
    "ema_warmup_bars",
    "materialize_initial_edge_features",
    "normalize_ema_lengths",
]


def __getattr__(name: str):
    if name not in __all__:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    from .edge_features import (
        EDGE_FEATURE_KEYS,
        EDGE_FEATURE_VERSION,
        EdgeFeatureMaterializationConfig,
        build_initial_edge_feature_specs,
        compute_initial_edge_feature_bundle,
        materialize_initial_edge_features,
    )
    from .ema import (
        EMA_BAR_FINALIZATION,
        EMA_DTYPE,
        EMA_FEATURE_KEY,
        EMA_FEATURE_VERSION,
        EMA_SOURCE_FIELD,
        EMA_TIMING_SEMANTICS,
        EMA_WARMUP_MULTIPLIER,
        build_ema_feature_spec,
        compute_ema_values,
        ema_warmup_bars,
        normalize_ema_lengths,
    )

    exports = {
        "EMA_BAR_FINALIZATION": EMA_BAR_FINALIZATION,
        "EMA_DTYPE": EMA_DTYPE,
        "EMA_FEATURE_KEY": EMA_FEATURE_KEY,
        "EMA_FEATURE_VERSION": EMA_FEATURE_VERSION,
        "EMA_SOURCE_FIELD": EMA_SOURCE_FIELD,
        "EMA_TIMING_SEMANTICS": EMA_TIMING_SEMANTICS,
        "EMA_WARMUP_MULTIPLIER": EMA_WARMUP_MULTIPLIER,
        "EDGE_FEATURE_KEYS": EDGE_FEATURE_KEYS,
        "EDGE_FEATURE_VERSION": EDGE_FEATURE_VERSION,
        "EdgeFeatureMaterializationConfig": EdgeFeatureMaterializationConfig,
        "build_ema_feature_spec": build_ema_feature_spec,
        "build_initial_edge_feature_specs": build_initial_edge_feature_specs,
        "compute_ema_values": compute_ema_values,
        "compute_initial_edge_feature_bundle": compute_initial_edge_feature_bundle,
        "ema_warmup_bars": ema_warmup_bars,
        "materialize_initial_edge_features": materialize_initial_edge_features,
        "normalize_ema_lengths": normalize_ema_lengths,
    }
    return exports[name]
