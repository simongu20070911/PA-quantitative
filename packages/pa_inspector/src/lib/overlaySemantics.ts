import type { Overlay, OverlayLayer } from "./types";

export interface OverlaySemantics {
  geometryKind: OverlayGeometryKind;
  layer: OverlayLayer | null;
  pivotDirection: "high" | "low" | null;
  pivotTier: "pivot_st" | "pivot" | null;
}

type OverlayGeometryKind =
  | "leg-line"
  | "pivot-marker"
  | "major-lh-marker"
  | "breakout-marker"
  | null;

export function resolveOverlaySemantics(overlay: Overlay): OverlaySemantics {
  const geometryKind = resolveOverlayGeometryKind(overlay);
  const sourceKind = resolveSourceKind(overlay);
  const styleKey = overlay.style_key;

  if (sourceKind?.startsWith("pivot_st_")) {
    return {
      geometryKind,
      layer: "pivot_st",
      pivotDirection: sourceKind.endsWith("_high") ? "high" : "low",
      pivotTier: "pivot_st",
    };
  }
  if (sourceKind?.startsWith("pivot_")) {
    return {
      geometryKind,
      layer: "pivot",
      pivotDirection: sourceKind.endsWith("_high") ? "high" : "low",
      pivotTier: "pivot",
    };
  }
  if (sourceKind?.startsWith("leg_")) {
    return {
      geometryKind,
      layer: "leg",
      pivotDirection: null,
      pivotTier: null,
    };
  }
  if (sourceKind === "major_lh") {
    return {
      geometryKind,
      layer: "major_lh",
      pivotDirection: null,
      pivotTier: null,
    };
  }
  if (sourceKind === "bearish_breakout_start") {
    return {
      geometryKind,
      layer: "breakout_start",
      pivotDirection: null,
      pivotTier: null,
    };
  }
  if (styleKey.startsWith("pivot_st.high")) {
    return {
      geometryKind,
      layer: "pivot_st",
      pivotDirection: "high",
      pivotTier: "pivot_st",
    };
  }
  if (styleKey.startsWith("pivot_st.low")) {
    return {
      geometryKind,
      layer: "pivot_st",
      pivotDirection: "low",
      pivotTier: "pivot_st",
    };
  }
  if (styleKey.startsWith("pivot.high")) {
    return {
      geometryKind,
      layer: "pivot",
      pivotDirection: "high",
      pivotTier: "pivot",
    };
  }
  if (styleKey.startsWith("pivot.low")) {
    return {
      geometryKind,
      layer: "pivot",
      pivotDirection: "low",
      pivotTier: "pivot",
    };
  }
  if (geometryKind === "leg-line") {
    return {
      geometryKind,
      layer: "leg",
      pivotDirection: null,
      pivotTier: null,
    };
  }
  if (geometryKind === "major-lh-marker") {
    return {
      geometryKind,
      layer: "major_lh",
      pivotDirection: null,
      pivotTier: null,
    };
  }
  if (geometryKind === "breakout-marker") {
    return {
      geometryKind,
      layer: "breakout_start",
      pivotDirection: null,
      pivotTier: null,
    };
  }
  return {
    geometryKind,
    layer: null,
    pivotDirection: null,
    pivotTier: null,
  };
}

export function resolveOverlayLayer(overlay: Overlay): OverlayLayer | null {
  return resolveOverlaySemantics(overlay).layer;
}

function resolveOverlayGeometryKind(overlay: Overlay): OverlayGeometryKind {
  if (
    overlay.kind === "leg-line" ||
    overlay.kind === "pivot-marker" ||
    overlay.kind === "major-lh-marker" ||
    overlay.kind === "breakout-marker"
  ) {
    return overlay.kind;
  }
  return null;
}

function resolveSourceKind(overlay: Overlay): string | null {
  const sourceKind = overlay.meta.source_kind;
  return typeof sourceKind === "string" ? sourceKind : null;
}
