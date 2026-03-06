__all__ = [
    "BAR_ARRAY_COLUMNS",
    "BarArrays",
    "CANONICAL_BAR_COLUMNS",
    "CanonicalBarIngestionConfig",
    "bar_arrays_from_frame",
    "load_bar_arrays",
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
    from .bar_arrays import (
        BAR_ARRAY_COLUMNS,
        BarArrays,
        bar_arrays_from_frame,
        load_bar_arrays,
    )

    exports = {
        "BAR_ARRAY_COLUMNS": BAR_ARRAY_COLUMNS,
        "BarArrays": BarArrays,
        "CANONICAL_BAR_COLUMNS": CANONICAL_BAR_COLUMNS,
        "CanonicalBarIngestionConfig": CanonicalBarIngestionConfig,
        "bar_arrays_from_frame": bar_arrays_from_frame,
        "load_bar_arrays": load_bar_arrays,
        "materialize_canonical_bars": materialize_canonical_bars,
    }
    return exports[name]
