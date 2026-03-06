__all__ = [
    "FEATURE_BUNDLE_BASE_COLUMNS",
    "PIVOT_KIND_GROUP",
    "PIVOT_LEFT_WINDOW",
    "PIVOT_RIGHT_WINDOW",
    "PIVOT_RULEBOOK_VERSION",
    "PIVOT_STRUCTURE_VERSION",
    "PivotMaterializationConfig",
    "PivotScanResult",
    "StructureInputs",
    "build_feature_ref",
    "build_pivot_structure_frame",
    "build_structure_id",
    "build_structure_input_ref",
    "compute_pivot_scan",
    "compute_pivot_scan_reference",
    "iter_structure_input_part_frames",
    "load_structure_inputs",
    "materialize_pivots",
    "structure_inputs_from_frames",
]


def __getattr__(name: str):
    if name not in __all__:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    from .ids import build_structure_id
    from .input import (
        FEATURE_BUNDLE_BASE_COLUMNS,
        StructureInputs,
        build_feature_ref,
        build_structure_input_ref,
        iter_structure_input_part_frames,
        load_structure_inputs,
        structure_inputs_from_frames,
    )
    from .pivots import (
        PIVOT_KIND_GROUP,
        PIVOT_LEFT_WINDOW,
        PIVOT_RIGHT_WINDOW,
        PIVOT_RULEBOOK_VERSION,
        PIVOT_STRUCTURE_VERSION,
        PivotMaterializationConfig,
        PivotScanResult,
        build_pivot_structure_frame,
        compute_pivot_scan,
        compute_pivot_scan_reference,
        materialize_pivots,
    )

    exports = {
        "FEATURE_BUNDLE_BASE_COLUMNS": FEATURE_BUNDLE_BASE_COLUMNS,
        "PIVOT_KIND_GROUP": PIVOT_KIND_GROUP,
        "PIVOT_LEFT_WINDOW": PIVOT_LEFT_WINDOW,
        "PIVOT_RIGHT_WINDOW": PIVOT_RIGHT_WINDOW,
        "PIVOT_RULEBOOK_VERSION": PIVOT_RULEBOOK_VERSION,
        "PIVOT_STRUCTURE_VERSION": PIVOT_STRUCTURE_VERSION,
        "PivotMaterializationConfig": PivotMaterializationConfig,
        "PivotScanResult": PivotScanResult,
        "StructureInputs": StructureInputs,
        "build_feature_ref": build_feature_ref,
        "build_pivot_structure_frame": build_pivot_structure_frame,
        "build_structure_id": build_structure_id,
        "build_structure_input_ref": build_structure_input_ref,
        "compute_pivot_scan": compute_pivot_scan,
        "compute_pivot_scan_reference": compute_pivot_scan_reference,
        "iter_structure_input_part_frames": iter_structure_input_part_frames,
        "load_structure_inputs": load_structure_inputs,
        "materialize_pivots": materialize_pivots,
        "structure_inputs_from_frames": structure_inputs_from_frames,
    }
    return exports[name]
