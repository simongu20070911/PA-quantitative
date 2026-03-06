import { useEffect, useMemo, useRef, type RefObject } from "react";

import type { ChartAdapter } from "../lib/chartAdapter";
import type { ChartBar, Overlay, OverlayLayer } from "../lib/types";

interface Drawable {
  overlay: Overlay;
  points: Array<{ x: number; y: number }>;
  radius: number;
}

interface OverlayPaint {
  stroke: string;
  fill: string;
  accent: string;
  lineWidth: number;
  dash: number[];
}

const LAYER_KIND_MAP: Record<OverlayLayer, ReadonlySet<string>> = {
  pivot: new Set(["pivot-marker"]),
  leg: new Set(["leg-line"]),
  major_lh: new Set(["major-lh-marker"]),
  breakout_start: new Set(["breakout-marker"]),
};

export interface OverlayCanvasProps {
  shellRef: RefObject<HTMLElement | null>;
  adapter: ChartAdapter | null;
  width: number;
  height: number;
  bars: ChartBar[];
  overlays: Overlay[];
  enabledLayers: Record<OverlayLayer, boolean>;
  selectedOverlayId: string | null;
  viewportRevision: number;
  onOverlaySelect: (
    overlay: Overlay | null,
    anchorPoint: { x: number; y: number } | null,
  ) => void;
}

export function OverlayCanvas({
  shellRef,
  adapter,
  width,
  height,
  bars,
  overlays,
  enabledLayers,
  selectedOverlayId,
  viewportRevision,
  onOverlaySelect,
}: OverlayCanvasProps) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const drawablesRef = useRef<Drawable[]>([]);
  const visibleOverlays = useMemo(() => {
    const allowedKinds = new Set<string>();
    (Object.entries(enabledLayers) as Array<[OverlayLayer, boolean]>).forEach(
      ([layer, enabled]) => {
        if (!enabled) {
          return;
        }
        LAYER_KIND_MAP[layer].forEach((kind) => allowedKinds.add(kind));
      },
    );
    return overlays.filter((overlay) => allowedKinds.has(overlay.kind));
  }, [enabledLayers, overlays]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || !adapter) {
      return;
    }
    const context = canvas.getContext("2d");
    if (!context) {
      return;
    }

    const dpr = window.devicePixelRatio || 1;
    canvas.width = Math.floor(width * dpr);
    canvas.height = Math.floor(height * dpr);
    canvas.style.width = `${width}px`;
    canvas.style.height = `${height}px`;
    context.setTransform(1, 0, 0, 1, 0, 0);
    context.clearRect(0, 0, canvas.width, canvas.height);
    context.setTransform(dpr, 0, 0, dpr, 0, 0);

    const barTimeById = new Map(bars.map((bar) => [bar.bar_id, bar.time]));
    const drawables: Drawable[] = [];

    for (const overlay of visibleOverlays) {
      const points = overlay.anchor_bars.map((barId, index) => {
        const time = barTimeById.get(barId);
        if (time === undefined) {
          return null;
        }
        const x = adapter.timeToCoordinate(time);
        const y = adapter.priceToCoordinate(overlay.anchor_prices[index]);
        if (x === null || y === null) {
          return null;
        }
        return { x, y };
      });
      if (points.some((point) => point === null)) {
        continue;
      }
      drawables.push({
        overlay,
        points: points as Array<{ x: number; y: number }>,
        radius: overlay.kind === "leg-line" ? 8 : 9,
      });
    }

    for (const drawable of drawables) {
      drawOverlay(context, drawable, drawable.overlay.overlay_id === selectedOverlayId);
    }
    drawablesRef.current = drawables;
  }, [adapter, bars, height, selectedOverlayId, viewportRevision, visibleOverlays, width]);

  useEffect(() => {
    if (!adapter) {
      return;
    }

    const unsubscribeClick = adapter.subscribeClick((param) => {
      const canvas = canvasRef.current;
      const point = param.point;
      if (!point) {
        onOverlaySelect(null, null);
        return;
      }
      const drawable = findOverlayAtPoint(drawablesRef.current, point.x, point.y);
      if (!drawable) {
        onOverlaySelect(null, null);
        return;
      }
      const shell = shellRef.current;
      const surface = canvas?.parentElement ?? null;
      if (!shell || !surface) {
        onOverlaySelect(drawable.overlay, { x: point.x, y: point.y });
        return;
      }
      const shellRect = shell.getBoundingClientRect();
      const surfaceRect = surface.getBoundingClientRect();
      onOverlaySelect(drawable.overlay, {
        x: point.x + (surfaceRect.left - shellRect.left),
        y: point.y + (surfaceRect.top - shellRect.top),
      });
    });

    const unsubscribeMove = adapter.subscribeCrosshairMove((param) => {
      const canvas = canvasRef.current;
      if (!canvas) {
        return;
      }
      const point = param.point;
      const overlay =
        point === undefined
          ? null
          : findOverlayAtPoint(drawablesRef.current, point.x, point.y);
      const target = canvas.parentElement ?? canvas;
      target.style.cursor = overlay ? "pointer" : "crosshair";
    });

    return () => {
      unsubscribeClick();
      unsubscribeMove();
      const canvas = canvasRef.current;
      const target = canvas?.parentElement ?? canvas;
      if (target) {
        target.style.cursor = "default";
      }
    };
  }, [adapter, onOverlaySelect, shellRef]);

  return <canvas className="overlay-canvas" ref={canvasRef} />;
}

function drawOverlay(
  context: CanvasRenderingContext2D,
  drawable: Drawable,
  selected: boolean,
) {
  const style = overlayStyle(drawable.overlay.style_key, selected);
  const isMarker = drawable.overlay.kind !== "leg-line";
  context.save();
  context.lineJoin = "round";
  context.lineCap = "round";
  context.strokeStyle = style.stroke;
  context.fillStyle = style.fill;
  context.lineWidth = style.lineWidth;
  context.shadowColor = isMarker
    ? selected
      ? "rgba(250, 246, 236, 0.32)"
      : "rgba(255, 255, 255, 0)"
    : selected
      ? "rgba(250, 246, 236, 0.88)"
      : "rgba(255, 255, 255, 0.24)";
  context.shadowBlur = isMarker ? (selected ? 2 : 0) : selected ? 10 : 2;

  if (drawable.overlay.kind === "leg-line") {
    const [start, end] = drawable.points;
    drawLegLine(context, start, end, style, selected);
    drawLegEndpoint(context, end, style);
  } else if (drawable.overlay.kind === "pivot-marker") {
    const [point] = drawable.points;
    const isHigh = drawable.overlay.style_key.includes(".high.");
    drawPivotBadge(context, point.x, point.y, 5, isHigh ? "down" : "up", style);
  } else if (drawable.overlay.kind === "major-lh-marker") {
    const [point] = drawable.points;
    drawDiamondBadge(context, point.x, point.y, 6, style);
  } else if (drawable.overlay.kind === "breakout-marker") {
    const [point] = drawable.points;
    drawBreakoutBadge(context, point.x, point.y, 6, style);
  }

  context.restore();
}

function drawLegLine(
  context: CanvasRenderingContext2D,
  start: { x: number; y: number },
  end: { x: number; y: number },
  style: OverlayPaint,
  selected: boolean,
) {
  // Use a soft colored glow instead of a hard bright outline so diagonal
  // legs read smoother against the chart surface.
  context.beginPath();
  context.setLineDash([]);
  context.strokeStyle = withAlpha(style.stroke, selected ? 0.24 : 0.16);
  context.lineWidth = style.lineWidth + (selected ? 3.2 : 2.4);
  context.moveTo(start.x, start.y);
  context.lineTo(end.x, end.y);
  context.stroke();

  context.beginPath();
  context.setLineDash([]);
  context.strokeStyle = withAlpha(style.accent, selected ? 0.28 : 0.18);
  context.lineWidth = style.lineWidth + (selected ? 1.2 : 0.8);
  context.moveTo(start.x, start.y);
  context.lineTo(end.x, end.y);
  context.stroke();

  context.beginPath();
  context.setLineDash(style.dash);
  context.strokeStyle = style.stroke;
  context.lineWidth = style.lineWidth;
  context.moveTo(start.x, start.y);
  context.lineTo(end.x, end.y);
  context.stroke();
}

function drawLegEndpoint(
  context: CanvasRenderingContext2D,
  point: { x: number; y: number },
  style: OverlayPaint,
) {
  context.beginPath();
  context.setLineDash([]);
  context.fillStyle = "rgba(255, 252, 246, 0.94)";
  context.arc(point.x, point.y, 3.1, 0, Math.PI * 2);
  context.fill();
  context.strokeStyle = style.stroke;
  context.lineWidth = 1.6;
  context.stroke();
}

function drawPivotBadge(
  context: CanvasRenderingContext2D,
  x: number,
  y: number,
  size: number,
  direction: "up" | "down",
  style: OverlayPaint,
) {
  const anchor = crispPoint(x, y);
  const offset = direction === "up" ? 8 : -8;
  context.beginPath();
  context.setLineDash([]);
  context.strokeStyle = withAlpha(style.stroke, 0.46);
  context.lineWidth = Math.max(1, Math.round(style.lineWidth));
  context.moveTo(anchor.x, anchor.y);
  context.lineTo(anchor.x, crisp(anchor.y + offset * 0.6));
  context.stroke();

  context.strokeStyle = style.stroke;
  context.fillStyle = "rgba(255, 252, 246, 0.985)";
  drawTriangle(context, anchor.x, crisp(anchor.y + offset), size, direction);
}

function drawDiamondBadge(
  context: CanvasRenderingContext2D,
  x: number,
  y: number,
  size: number,
  style: OverlayPaint,
) {
  const anchor = crispPoint(x, y);
  const badgeY = crisp(anchor.y - 8);
  context.strokeStyle = style.stroke;
  context.fillStyle = "rgba(255, 251, 242, 0.985)";
  drawDiamond(context, anchor.x, badgeY, size);
  context.beginPath();
  context.setLineDash([]);
  context.fillStyle = style.accent;
  context.arc(anchor.x, badgeY, 1.9, 0, Math.PI * 2);
  context.fill();
}

function drawBreakoutBadge(
  context: CanvasRenderingContext2D,
  x: number,
  y: number,
  size: number,
  style: OverlayPaint,
) {
  const anchor = crispPoint(x, y);
  const badgeY = crisp(anchor.y - 9);
  context.beginPath();
  context.setLineDash([]);
  context.fillStyle = "rgba(255, 250, 244, 0.985)";
  context.arc(anchor.x, badgeY, size * 0.82, 0, Math.PI * 2);
  context.fill();
  context.stroke();

  context.beginPath();
  context.strokeStyle = style.accent;
  context.lineWidth = 1.6;
  context.moveTo(crisp(anchor.x - 3), crisp(badgeY - 1));
  context.lineTo(anchor.x, crisp(badgeY + 3));
  context.lineTo(crisp(anchor.x + 3), crisp(badgeY - 1));
  context.stroke();

  context.beginPath();
  context.strokeStyle = style.stroke;
  context.lineWidth = 1.2;
  context.moveTo(anchor.x, crisp(badgeY + size * 0.72));
  context.lineTo(anchor.x, crisp(anchor.y - 2));
  context.stroke();
}

function drawTriangle(
  context: CanvasRenderingContext2D,
  x: number,
  y: number,
  size: number,
  direction: "up" | "down",
) {
  context.beginPath();
  if (direction === "up") {
    context.moveTo(x, y - size);
    context.lineTo(x + size, y + size);
    context.lineTo(x - size, y + size);
  } else {
    context.moveTo(x, y + size);
    context.lineTo(x + size, y - size);
    context.lineTo(x - size, y - size);
  }
  context.closePath();
  context.fill();
  context.stroke();
}

function drawDiamond(
  context: CanvasRenderingContext2D,
  x: number,
  y: number,
  size: number,
) {
  context.beginPath();
  context.moveTo(x, y - size);
  context.lineTo(x + size, y);
  context.lineTo(x, y + size);
  context.lineTo(x - size, y);
  context.closePath();
  context.fill();
  context.stroke();
}

function overlayStyle(styleKey: string, selected: boolean): OverlayPaint {
  const stateOpacity = styleKey.includes(".candidate") ? 0.52 : 0.92;
  if (styleKey.startsWith("leg.up")) {
    return {
      stroke: `rgba(36, 92, 62, ${stateOpacity})`,
      fill: "rgba(36, 92, 62, 0.16)",
      accent: "rgba(79, 151, 111, 0.96)",
      lineWidth: selected ? 2.9 : 1.65,
      dash: styleKey.includes(".candidate") ? [8, 6] : [],
    };
  }
  if (styleKey.startsWith("leg.down")) {
    return {
      stroke: `rgba(179, 84, 54, ${stateOpacity})`,
      fill: "rgba(179, 84, 54, 0.16)",
      accent: "rgba(214, 125, 93, 0.97)",
      lineWidth: selected ? 2.9 : 1.65,
      dash: styleKey.includes(".candidate") ? [8, 6] : [],
    };
  }
  if (styleKey.startsWith("pivot.high")) {
    return {
      stroke: `rgba(179, 84, 54, ${stateOpacity})`,
      fill: "rgba(255, 252, 246, 0.94)",
      accent: "rgba(214, 125, 93, 0.97)",
      lineWidth: selected ? 2.2 : 1.35,
      dash: [],
    };
  }
  if (styleKey.startsWith("pivot.low")) {
    return {
      stroke: `rgba(36, 92, 62, ${stateOpacity})`,
      fill: "rgba(255, 252, 246, 0.94)",
      accent: "rgba(79, 151, 111, 0.96)",
      lineWidth: selected ? 2.2 : 1.35,
      dash: [],
    };
  }
  if (styleKey.startsWith("major_lh")) {
    return {
      stroke: `rgba(87, 60, 27, ${stateOpacity})`,
      fill: "rgba(255, 251, 242, 0.95)",
      accent: "rgba(230, 177, 95, 0.94)",
      lineWidth: selected ? 2.5 : 1.55,
      dash: styleKey.includes(".candidate") ? [5, 4] : [],
    };
  }
  return {
    stroke: `rgba(128, 48, 39, ${stateOpacity})`,
    fill: "rgba(255, 250, 244, 0.96)",
    accent: "rgba(214, 125, 93, 0.98)",
    lineWidth: selected ? 2.5 : 1.55,
    dash: [],
  };
}

function findOverlayAtPoint(
  drawables: Drawable[],
  x: number,
  y: number,
): Drawable | null {
  for (let index = drawables.length - 1; index >= 0; index -= 1) {
    const drawable = drawables[index];
    if (drawable.overlay.kind === "leg-line") {
      const [start, end] = drawable.points;
      if (pointToSegmentDistance(x, y, start, end) <= drawable.radius) {
        return drawable;
      }
      continue;
    }
    const [point] = drawable.points;
    const distance = Math.hypot(x - point.x, y - point.y);
    if (distance <= drawable.radius + 2) {
      return drawable;
    }
  }
  return null;
}

function pointToSegmentDistance(
  px: number,
  py: number,
  start: { x: number; y: number },
  end: { x: number; y: number },
) {
  const dx = end.x - start.x;
  const dy = end.y - start.y;
  if (dx === 0 && dy === 0) {
    return Math.hypot(px - start.x, py - start.y);
  }
  const t = Math.max(
    0,
    Math.min(1, ((px - start.x) * dx + (py - start.y) * dy) / (dx * dx + dy * dy)),
  );
  const projX = start.x + t * dx;
  const projY = start.y + t * dy;
  return Math.hypot(px - projX, py - projY);
}

function withAlpha(rgba: string, alpha: number) {
  const match = rgba.match(
    /^rgba\(\s*([0-9.]+)\s*,\s*([0-9.]+)\s*,\s*([0-9.]+)\s*,\s*([0-9.]+)\s*\)$/,
  );
  if (!match) {
    return rgba;
  }
  const [, r, g, b] = match;
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

function crisp(value: number) {
  return Math.round(value) + 0.5;
}

function crispPoint(x: number, y: number) {
  return { x: crisp(x), y: crisp(y) };
}
