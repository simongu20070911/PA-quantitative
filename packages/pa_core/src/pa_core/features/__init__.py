__all__ = [
    "EDGE_FEATURE_KEYS",
    "EDGE_FEATURE_VERSION",
    "EdgeFeatureMaterializationConfig",
    "build_initial_edge_feature_specs",
    "compute_initial_edge_feature_bundle",
    "materialize_initial_edge_features",
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

    exports = {
        "EDGE_FEATURE_KEYS": EDGE_FEATURE_KEYS,
        "EDGE_FEATURE_VERSION": EDGE_FEATURE_VERSION,
        "EdgeFeatureMaterializationConfig": EdgeFeatureMaterializationConfig,
        "build_initial_edge_feature_specs": build_initial_edge_feature_specs,
        "compute_initial_edge_feature_bundle": compute_initial_edge_feature_bundle,
        "materialize_initial_edge_features": materialize_initial_edge_features,
    }
    return exports[name]
