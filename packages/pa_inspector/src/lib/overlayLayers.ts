import type { Overlay, OverlayLayer } from "./types";

export const INITIAL_OVERLAY_LAYERS: Record<OverlayLayer, boolean> = {
  pivot: true,
  leg: true,
  major_lh: true,
  breakout_start: true,
};

export const OVERLAY_LAYER_ORDER = Object.keys(
  INITIAL_OVERLAY_LAYERS,
) as OverlayLayer[];

export const EMPTY_OVERLAY_LAYER_COUNTS: Record<OverlayLayer, number> = {
  pivot: 0,
  leg: 0,
  major_lh: 0,
  breakout_start: 0,
};

export const OVERLAY_LAYER_LABELS: Record<OverlayLayer, string> = {
  pivot: "Pivots",
  leg: "Legs",
  major_lh: "Major LH",
  breakout_start: "Breakouts",
};

const OVERLAY_KIND_TO_LAYER: Record<string, OverlayLayer> = {
  "pivot-marker": "pivot",
  "leg-line": "leg",
  "major-lh-marker": "major_lh",
  "breakout-marker": "breakout_start",
};

export function overlayKindToLayer(kind: string): OverlayLayer | null {
  return OVERLAY_KIND_TO_LAYER[kind] ?? null;
}

export function filterOverlaysByEnabledLayers(
  overlays: Overlay[],
  overlayLayers: Record<OverlayLayer, boolean>,
): Overlay[] {
  return overlays.filter((overlay) => {
    const layer = overlayKindToLayer(overlay.kind);
    return layer !== null && overlayLayers[layer];
  });
}

export function countOverlaysByLayer(
  overlays: Overlay[],
): Record<OverlayLayer, number> {
  const counts = { ...EMPTY_OVERLAY_LAYER_COUNTS };
  for (const overlay of overlays) {
    const layer = overlayKindToLayer(overlay.kind);
    if (layer !== null) {
      counts[layer] += 1;
    }
  }
  return counts;
}
