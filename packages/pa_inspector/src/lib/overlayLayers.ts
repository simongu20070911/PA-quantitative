import type { Overlay, OverlayLayer } from "./types";

export const INITIAL_OVERLAY_LAYERS: Record<OverlayLayer, boolean> = {
  pivot_st: false,
  pivot: true,
  leg: true,
  major_lh: true,
  breakout_start: true,
};

export const OVERLAY_LAYER_ORDER = Object.keys(
  INITIAL_OVERLAY_LAYERS,
) as OverlayLayer[];

export const EMPTY_OVERLAY_LAYER_COUNTS: Record<OverlayLayer, number> = {
  pivot_st: 0,
  pivot: 0,
  leg: 0,
  major_lh: 0,
  breakout_start: 0,
};

export const OVERLAY_LAYER_LABELS: Record<OverlayLayer, string> = {
  pivot_st: "ST Pivots",
  pivot: "Pivots",
  leg: "Legs",
  major_lh: "Major LH",
  breakout_start: "Breakouts",
};

export function overlayToLayer(overlay: Overlay): OverlayLayer | null {
  const sourceKind = overlay.meta.source_kind;
  if (typeof sourceKind === "string") {
    if (sourceKind.startsWith("pivot_st_")) {
      return "pivot_st";
    }
    if (sourceKind.startsWith("pivot_")) {
      return "pivot";
    }
    if (sourceKind.startsWith("leg_")) {
      return "leg";
    }
    if (sourceKind === "major_lh") {
      return "major_lh";
    }
    if (sourceKind === "bearish_breakout_start") {
      return "breakout_start";
    }
  }
  if (overlay.kind === "leg-line") {
    return "leg";
  }
  if (overlay.kind === "major-lh-marker") {
    return "major_lh";
  }
  if (overlay.kind === "breakout-marker") {
    return "breakout_start";
  }
  if (overlay.style_key.startsWith("pivot_st.")) {
    return "pivot_st";
  }
  if (overlay.style_key.startsWith("pivot.")) {
    return "pivot";
  }
  return null;
}

export function filterOverlaysByEnabledLayers(
  overlays: Overlay[],
  overlayLayers: Record<OverlayLayer, boolean>,
): Overlay[] {
  return overlays.filter((overlay) => {
    const layer = overlayToLayer(overlay);
    return layer !== null && overlayLayers[layer];
  });
}

export function countOverlaysByLayer(
  overlays: Overlay[],
): Record<OverlayLayer, number> {
  const counts = { ...EMPTY_OVERLAY_LAYER_COUNTS };
  for (const overlay of overlays) {
    const layer = overlayToLayer(overlay);
    if (layer !== null) {
      counts[layer] += 1;
    }
  }
  return counts;
}
