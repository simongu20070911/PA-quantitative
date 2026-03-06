import type { CanvasRenderingTarget2D } from "fancy-canvas";

import {
  colorWithOpacity,
  defaultAnnotationStyle,
  getAnnotationStyle,
  lineDashForStyle,
} from "./annotationStyle";
import type {
  AnnotationAnchor,
  ChartAnnotation,
  ChartBar,
  ConfirmationGuide,
  Overlay,
  SessionProfile,
} from "./types";

export interface CoordinateProjector {
  timeToCoordinate: (time: number) => number | null;
  priceToCoordinate: (price: number) => number | null;
}

export interface Drawable {
  overlay: Overlay;
  points: Array<{ x: number; y: number }>;
  radius: number;
}

export interface AnnotationDrawable {
  annotation: ChartAnnotation;
  start: { x: number; y: number };
  end: { x: number; y: number };
  bounds: { left: number; top: number; right: number; bottom: number };
}

export interface AnnotationHit {
  drawable: AnnotationDrawable;
  mode: "move" | "start" | "end";
}

export interface AnnotationPointerPosition {
  barId: number;
  barIndex: number;
  price: number;
}

export interface AnnotationDragState {
  annotationId: string;
  mode: "move" | "start" | "end";
  originPointer: AnnotationPointerPosition;
  originalStart: AnnotationAnchor;
  originalEnd: AnnotationAnchor;
}

export interface InspectorPrimitiveState {
  bars: ChartBar[];
  overlays: Overlay[];
  annotations: ChartAnnotation[];
  selectedOverlayId: string | null;
  selectedAnnotationId: string | null;
  confirmationGuide: ConfirmationGuide | null;
  sessionProfile: SessionProfile;
  draftAnnotation: ChartAnnotation | null;
}

export interface InspectorRenderData {
  sessionBoundaries: number[];
  confirmationGuide: ConfirmationGuideRender | null;
  overlayDrawables: Drawable[];
  annotationDrawables: AnnotationDrawable[];
  draftDrawable: AnnotationDrawable | null;
  selectedOverlayId: string | null;
  selectedAnnotationId: string | null;
}

interface ConfirmationGuideRender {
  x: number;
}

interface OverlayPaint {
  stroke: string;
  fill: string;
  accent: string;
  lineWidth: number;
  dash: number[];
}

export function buildInspectorRenderData(
  state: InspectorPrimitiveState,
  projector: CoordinateProjector,
): InspectorRenderData {
  const barTimeById = new Map(state.bars.map((bar) => [bar.bar_id, bar.time]));
  const overlayDrawables = resolveOverlayDrawables(state.bars, state.overlays, projector);
  const annotationDrawables = resolveAnnotationDrawables(
    state.annotations,
    barTimeById,
    projector,
  );
  const sessionBoundaries =
    state.sessionProfile === "rth"
      ? collectSessionBoundaryXCoordinates(state.bars, projector)
      : [];
  const confirmationGuide = resolveConfirmationGuide(
    state.confirmationGuide,
    barTimeById,
    projector,
  );
  const draftDrawable = state.draftAnnotation
    ? resolveAnnotationDrawable(state.draftAnnotation, barTimeById, projector)
    : null;

  return {
    sessionBoundaries,
    confirmationGuide,
    overlayDrawables,
    annotationDrawables,
    draftDrawable,
    selectedOverlayId: state.selectedOverlayId,
    selectedAnnotationId: state.selectedAnnotationId,
  };
}

export function drawInspectorScene(
  target: CanvasRenderingTarget2D,
  data: InspectorRenderData,
) {
  target.useMediaCoordinateSpace(({ context, mediaSize }) => {
    for (const x of data.sessionBoundaries) {
      drawSessionBoundary(context, x, mediaSize.height);
    }

    if (data.confirmationGuide) {
      drawConfirmationGuide(context, data.confirmationGuide, mediaSize.height);
    }

    for (const drawable of data.overlayDrawables) {
      drawOverlay(context, drawable, drawable.overlay.overlay_id === data.selectedOverlayId);
    }

    for (const drawable of data.annotationDrawables) {
      drawAnnotation(
        context,
        drawable,
        drawable.annotation.id === data.selectedAnnotationId,
        false,
      );
    }

    if (data.draftDrawable) {
      drawAnnotation(context, data.draftDrawable, false, true);
    }
  });
}

export function resolveAnnotationPointerPositionFromPoint(
  point: { x: number; y: number },
  bars: ChartBar[],
  coordinateToLogical: (coordinate: number) => number | null,
  coordinateToPrice: (coordinate: number) => number | null,
): AnnotationPointerPosition | null {
  const logical = coordinateToLogical(point.x);
  const price = coordinateToPrice(point.y);
  if (logical === null || price === null || bars.length === 0) {
    return null;
  }
  const barIndex = clampIndex(Math.round(logical), bars.length);
  const bar = bars[barIndex];
  if (!bar) {
    return null;
  }
  return {
    barId: bar.bar_id,
    barIndex,
    price,
  };
}

export function hitTestAnnotation(
  drawables: AnnotationDrawable[],
  x: number,
  y: number,
): AnnotationHit | null {
  for (let index = drawables.length - 1; index >= 0; index -= 1) {
    const drawable = drawables[index];
    const style = getAnnotationStyle(drawable.annotation);
    if (!style.locked && Math.hypot(x - drawable.start.x, y - drawable.start.y) <= 11) {
      return { drawable, mode: "start" };
    }
    if (!style.locked && Math.hypot(x - drawable.end.x, y - drawable.end.y) <= 11) {
      return { drawable, mode: "end" };
    }
    if (drawable.annotation.kind === "line") {
      if (pointToSegmentDistance(x, y, drawable.start, drawable.end) <= 12) {
        return { drawable, mode: "move" };
      }
      continue;
    }
    if (drawable.annotation.kind === "fib50") {
      const left = Math.min(drawable.start.x, drawable.end.x);
      const right = Math.max(drawable.start.x, drawable.end.x);
      const top = Math.min(drawable.start.y, drawable.end.y);
      const bottom = Math.max(drawable.start.y, drawable.end.y);
      const levels = [top, top + (bottom - top) * 0.5, bottom];
      if (x < left - 8 || x > right + 8) {
        continue;
      }
      if (levels.some((levelY) => Math.abs(y - levelY) <= 8)) {
        return { drawable, mode: "move" };
      }
      continue;
    }
    if (pointInsideAnnotationBox(drawable, x, y)) {
      return { drawable, mode: "move" };
    }
  }
  return null;
}

export function projectDraggedAnnotation(
  dragState: AnnotationDragState,
  pointer: AnnotationPointerPosition,
  bars: ChartBar[],
): { start: AnnotationAnchor; end: AnnotationAnchor } | null {
  const barIndexById = new Map(bars.map((bar, index) => [bar.bar_id, index]));
  const originalStartIndex = barIndexById.get(dragState.originalStart.bar_id);
  const originalEndIndex = barIndexById.get(dragState.originalEnd.bar_id);
  if (originalStartIndex === undefined || originalEndIndex === undefined) {
    return null;
  }

  const barDelta = pointer.barIndex - dragState.originPointer.barIndex;
  const priceDelta = pointer.price - dragState.originPointer.price;

  if (dragState.mode === "move") {
    const nextStartIndex = clampIndex(originalStartIndex + barDelta, bars.length);
    const nextEndIndex = clampIndex(originalEndIndex + barDelta, bars.length);
    return {
      start: {
        bar_id: bars[nextStartIndex].bar_id,
        price: dragState.originalStart.price + priceDelta,
      },
      end: {
        bar_id: bars[nextEndIndex].bar_id,
        price: dragState.originalEnd.price + priceDelta,
      },
    };
  }

  if (dragState.mode === "start") {
    return {
      start: {
        bar_id: bars[clampIndex(pointer.barIndex, bars.length)].bar_id,
        price: pointer.price,
      },
      end: dragState.originalEnd,
    };
  }

  return {
    start: dragState.originalStart,
    end: {
      bar_id: bars[clampIndex(pointer.barIndex, bars.length)].bar_id,
      price: pointer.price,
    },
  };
}

export function findOverlayAtPoint(
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

export function resolveOverlayDrawables(
  bars: ChartBar[],
  overlays: Overlay[],
  projector: CoordinateProjector,
): Drawable[] {
  const barTimeById = new Map(bars.map((bar) => [bar.bar_id, bar.time]));
  const overlayDrawables: Drawable[] = [];
  for (const overlay of overlays) {
    const points = overlay.anchor_bars.map((barId, index) => {
      const time = barTimeById.get(barId);
      if (time === undefined) {
        return null;
      }
      const x = projector.timeToCoordinate(time);
      const y = projector.priceToCoordinate(overlay.anchor_prices[index]);
      if (x === null || y === null) {
        return null;
      }
      return { x, y };
    });
    if (points.some((point) => point === null)) {
      continue;
    }
    overlayDrawables.push({
      overlay,
      points: points as Array<{ x: number; y: number }>,
      radius: overlay.kind === "leg-line" ? 8 : 9,
    });
  }
  return overlayDrawables;
}

export function resolveAnnotationDrawables(
  annotations: ChartAnnotation[],
  barTimeById: Map<number, number>,
  projector: CoordinateProjector,
): AnnotationDrawable[] {
  return annotations
    .map((annotation) => resolveAnnotationDrawable(annotation, barTimeById, projector))
    .filter((value): value is AnnotationDrawable => value !== null);
}

export function resolveAnnotationDrawable(
  annotation: ChartAnnotation,
  barTimeById: Map<number, number>,
  projector: CoordinateProjector,
): AnnotationDrawable | null {
  const startTime = barTimeById.get(annotation.start.bar_id);
  const endTime = barTimeById.get(annotation.end.bar_id);
  if (startTime === undefined || endTime === undefined) {
    return null;
  }
  const startX = projector.timeToCoordinate(startTime);
  const endX = projector.timeToCoordinate(endTime);
  const startY = projector.priceToCoordinate(annotation.start.price);
  const endY = projector.priceToCoordinate(annotation.end.price);
  if (startX === null || endX === null || startY === null || endY === null) {
    return null;
  }
  return {
    annotation,
    start: { x: startX, y: startY },
    end: { x: endX, y: endY },
    bounds: {
      left: Math.min(startX, endX),
      top: Math.min(startY, endY),
      right: Math.max(startX, endX),
      bottom: Math.max(startY, endY),
    },
  };
}

function resolveConfirmationGuide(
  guide: ConfirmationGuide | null,
  barTimeById: Map<number, number>,
  projector: CoordinateProjector,
): ConfirmationGuideRender | null {
  if (!guide) {
    return null;
  }
  const confirmTime = barTimeById.get(guide.confirmBarId);
  if (confirmTime === undefined) {
    return null;
  }
  const x = projector.timeToCoordinate(confirmTime);
  if (x === null) {
    return null;
  }
  return { x };
}

function drawAnnotation(
  context: CanvasRenderingContext2D,
  drawable: AnnotationDrawable,
  selected: boolean,
  draft: boolean,
) {
  const { annotation, start, end, bounds } = drawable;
  const style = draft
    ? defaultAnnotationStyle(annotation.kind)
    : getAnnotationStyle(annotation);
  const stroke = colorWithOpacity(style.strokeColor, style.opacity);
  const fill =
    annotation.kind === "box"
      ? colorWithOpacity(style.fillColor, Math.max(0.12, style.opacity * 0.28))
      : "transparent";

  context.save();
  context.lineJoin = "round";
  context.lineCap = "round";
  context.setLineDash(lineDashForStyle(style.lineStyle));
  context.strokeStyle = stroke;
  context.fillStyle = fill;
  context.lineWidth = selected ? style.lineWidth + 0.2 : style.lineWidth;

  if (annotation.kind === "line") {
    context.beginPath();
    context.moveTo(start.x, start.y);
    context.lineTo(end.x, end.y);
    context.stroke();
  } else if (annotation.kind === "box") {
    context.beginPath();
    context.rect(
      bounds.left,
      bounds.top,
      Math.max(bounds.right - bounds.left, 1),
      Math.max(bounds.bottom - bounds.top, 1),
    );
    context.fill();
    context.stroke();
  } else {
    const left = Math.min(start.x, end.x);
    const right = Math.max(start.x, end.x);
    const top = Math.min(start.y, end.y);
    const bottom = Math.max(start.y, end.y);
    const levels = [top, top + (bottom - top) * 0.5, bottom];
    for (const levelY of levels) {
      context.beginPath();
      context.moveTo(left, levelY);
      context.lineTo(right, levelY);
      context.stroke();
    }
  }

  if (selected && !style.locked) {
    drawAnnotationHandle(context, start.x, start.y, style.strokeColor);
    drawAnnotationHandle(context, end.x, end.y, style.strokeColor);
  }
  context.restore();
}

function drawAnnotationHandle(
  context: CanvasRenderingContext2D,
  x: number,
  y: number,
  stroke: string,
) {
  context.beginPath();
  context.setLineDash([]);
  context.fillStyle = "rgba(255, 252, 246, 0.96)";
  context.arc(x, y, 3.8, 0, Math.PI * 2);
  context.fill();
  context.strokeStyle = stroke;
  context.lineWidth = 1.8;
  context.stroke();
}

function collectSessionBoundaryXCoordinates(
  bars: ChartBar[],
  projector: CoordinateProjector,
): number[] {
  const coordinates: number[] = [];
  for (let index = 1; index < bars.length; index += 1) {
    const previous = bars[index - 1];
    const current = bars[index];
    if (previous.session_date === current.session_date) {
      continue;
    }
    const currentX = projector.timeToCoordinate(current.time);
    if (currentX === null) {
      continue;
    }
    const previousX = projector.timeToCoordinate(previous.time);
    coordinates.push(previousX === null ? currentX : (previousX + currentX) / 2);
  }
  return coordinates;
}

function drawSessionBoundary(
  context: CanvasRenderingContext2D,
  x: number,
  height: number,
) {
  context.save();
  context.beginPath();
  context.setLineDash([5, 7]);
  context.strokeStyle = "rgba(98, 108, 124, 0.42)";
  context.lineWidth = 1;
  context.moveTo(Math.round(x) + 0.5, 0);
  context.lineTo(Math.round(x) + 0.5, height);
  context.stroke();
  context.restore();
}

function drawConfirmationGuide(
  context: CanvasRenderingContext2D,
  guide: ConfirmationGuideRender,
  height: number,
) {
  context.save();
  context.beginPath();
  context.setLineDash([]);
  context.strokeStyle = "rgba(37, 99, 235, 0.92)";
  context.lineWidth = 1.5;
  context.moveTo(Math.round(guide.x) + 0.5, 0);
  context.lineTo(Math.round(guide.x) + 0.5, height);
  context.stroke();
  context.restore();
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
  const offset = direction === "up" ? 11 : -11;
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

function pointInsideAnnotationBox(
  drawable: AnnotationDrawable,
  x: number,
  y: number,
) {
  const pad = 10;
  if (
    x < drawable.bounds.left - pad ||
    x > drawable.bounds.right + pad ||
    y < drawable.bounds.top - pad ||
    y > drawable.bounds.bottom + pad
  ) {
    return false;
  }
  return true;
}

function clampIndex(index: number, length: number) {
  return Math.max(0, Math.min(length - 1, index));
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

