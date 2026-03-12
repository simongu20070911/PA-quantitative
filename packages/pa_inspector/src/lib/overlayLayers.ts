import type { Overlay, OverlayLayer } from "./types";
import { resolveOverlayLayer } from "./overlaySemantics";

export const INITIAL_OVERLAY_LAYERS: Record<OverlayLayer, boolean> = {
  pivot_st: false,
  pivot: true,
  leg: true,
  major_lh: true,
};

export const OVERLAY_LAYER_ORDER = Object.keys(
  INITIAL_OVERLAY_LAYERS,
) as OverlayLayer[];

export const EMPTY_OVERLAY_LAYER_COUNTS: Record<OverlayLayer, number> = {
  pivot_st: 0,
  pivot: 0,
  leg: 0,
  major_lh: 0,
};

export const OVERLAY_LAYER_LABELS: Record<OverlayLayer, string> = {
  pivot_st: "ST Pivots",
  pivot: "Pivots",
  leg: "Legs",
  major_lh: "Major LH",
};

export function overlayToLayer(overlay: Overlay): OverlayLayer | null {
  return resolveOverlayLayer(overlay);
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
