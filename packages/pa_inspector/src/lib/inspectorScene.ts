import type { CanvasRenderingTarget2D } from "fancy-canvas";

import {
  colorWithOpacity,
  defaultAnnotationStyle,
  getAnnotationStyle,
  lineDashForStyle,
} from "./annotationStyle";
import { resolveOverlaySemantics } from "./overlaySemantics";
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
  control: { x: number; y: number } | null;
  bounds: { left: number; top: number; right: number; bottom: number };
}

interface AnnotationLineSegment {
  start: { x: number; y: number };
  end: { x: number; y: number };
}

export interface AnnotationHit {
  drawable: AnnotationDrawable;
  mode: "move" | "start" | "end" | "scale";
}

export interface AnnotationPointerPosition {
  barId: number;
  barIndex: number;
  price: number;
}

export interface AnnotationDragState {
  annotationId: string;
  annotationKind: ChartAnnotation["kind"];
  mode: "move" | "start" | "end" | "scale";
  originPointer: AnnotationPointerPosition;
  originalStart: AnnotationAnchor;
  originalEnd: AnnotationAnchor;
  originalControl: AnnotationAnchor | null;
}

export interface AnnotationProjection {
  start: AnnotationAnchor;
  end: AnnotationAnchor;
  control: AnnotationAnchor | null;
}

export interface InspectorPrimitiveState {
  bars: ChartBar[];
  overlays: Overlay[];
  annotations: ChartAnnotation[];
  selectedOverlayId: string | null;
  selectedAnnotationIds: string[];
  confirmationGuide: ConfirmationGuide | null;
  sessionProfile: SessionProfile;
  draftAnnotation: ChartAnnotation | null;
  replayMode: boolean;
  replayCursorVisible: boolean;
  replayCursorBarId: number | null;
  replayHoverBarId: number | null;
}

export interface InspectorRenderData {
  sessionBoundaries: number[];
  confirmationGuide: ConfirmationGuideRender | null;
  replayBoundary: ReplayCursorRender | null;
  replaySelectionGuide: ReplayCursorRender | null;
  replayWatermark: ReplayWatermarkRender | null;
  overlayDrawables: Drawable[];
  annotationDrawables: AnnotationDrawable[];
  draftDrawable: AnnotationDrawable | null;
  selectedOverlayId: string | null;
  selectedAnnotationIds: string[];
}

export interface InspectorGeometryCache {
  barTimeById: Map<number, number>;
  sessionBoundaries: number[];
  overlayDrawables: Drawable[];
  annotationDrawables: AnnotationDrawable[];
}

export interface InspectorPresentationState {
  confirmationGuide: ConfirmationGuideRender | null;
  replayBoundary: ReplayCursorRender | null;
  replaySelectionGuide: ReplayCursorRender | null;
  replayWatermark: ReplayWatermarkRender | null;
  draftDrawable: AnnotationDrawable | null;
  selectedOverlayId: string | null;
  selectedAnnotationIds: string[];
}

export interface ConfirmationGuideRender {
  x: number;
}

export interface ReplayCursorRender {
  x: number;
}

export interface ReplayWatermarkRender {
  label: string;
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
  const geometry = buildInspectorGeometryCache(state, projector);
  const presentation = buildInspectorPresentationState(
    state,
    geometry.barTimeById,
    projector,
  );
  return composeInspectorRenderData(geometry, presentation);
}

export function buildBarTimeIndex(bars: ChartBar[]): Map<number, number> {
  return new Map(bars.map((bar) => [bar.bar_id, bar.time]));
}

export function buildInspectorGeometryCache(
  state: Pick<
    InspectorPrimitiveState,
    "bars" | "overlays" | "annotations" | "sessionProfile"
  >,
  projector: CoordinateProjector,
  barTimeById: Map<number, number> = buildBarTimeIndex(state.bars),
): InspectorGeometryCache {
  return {
    barTimeById,
    sessionBoundaries:
      state.sessionProfile === "rth"
        ? collectSessionBoundaryXCoordinates(state.bars, projector)
        : [],
    overlayDrawables: resolveOverlayDrawables(state.bars, state.overlays, projector),
    annotationDrawables: resolveAnnotationDrawables(
      state.annotations,
      barTimeById,
      projector,
    ),
  };
}

export function buildInspectorPresentationState(
  state: Pick<
    InspectorPrimitiveState,
    | "confirmationGuide"
    | "bars"
    | "draftAnnotation"
    | "selectedOverlayId"
    | "selectedAnnotationIds"
    | "replayMode"
    | "replayCursorVisible"
    | "replayCursorBarId"
    | "replayHoverBarId"
  >,
  barTimeById: Map<number, number>,
  projector: CoordinateProjector,
): InspectorPresentationState {
  return {
    confirmationGuide: resolveConfirmationGuide(
      state.confirmationGuide,
      state.bars,
      barTimeById,
      projector,
    ),
    replayBoundary: resolveReplayBoundary(
      state.replayMode,
      state.replayCursorVisible,
      state.replayCursorBarId,
      state.bars,
      barTimeById,
      projector,
    ),
    replaySelectionGuide: resolveReplaySelectionGuide(
      state.replayMode,
      state.replayCursorVisible,
      state.replayCursorBarId,
      state.replayHoverBarId,
      state.bars,
      barTimeById,
      projector,
    ),
    replayWatermark: state.replayMode ? { label: "Replay" } : null,
    draftDrawable: state.draftAnnotation
      ? resolveAnnotationDrawable(state.draftAnnotation, barTimeById, projector)
      : null,
    selectedOverlayId: state.selectedOverlayId,
    selectedAnnotationIds: state.selectedAnnotationIds,
  };
}

export function composeInspectorRenderData(
  geometry: InspectorGeometryCache,
  presentation: InspectorPresentationState,
): InspectorRenderData {
  return {
    sessionBoundaries: geometry.sessionBoundaries,
    confirmationGuide: presentation.confirmationGuide,
    replayBoundary: presentation.replayBoundary,
    replaySelectionGuide: presentation.replaySelectionGuide,
    replayWatermark: presentation.replayWatermark,
    overlayDrawables: geometry.overlayDrawables,
    annotationDrawables: geometry.annotationDrawables,
    draftDrawable: presentation.draftDrawable,
    selectedOverlayId: presentation.selectedOverlayId,
    selectedAnnotationIds: presentation.selectedAnnotationIds,
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

    if (data.replayWatermark) {
      drawReplayWatermark(context, data.replayWatermark, mediaSize.width, mediaSize.height);
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
        data.selectedAnnotationIds.includes(drawable.annotation.id),
        false,
      );
    }

    if (data.draftDrawable) {
      drawAnnotation(context, data.draftDrawable, false, true);
    }

    if (data.replaySelectionGuide) {
      drawReplayFutureMask(
        context,
        data.replaySelectionGuide,
        mediaSize.width,
        mediaSize.height,
      );
    }

    if (data.replaySelectionGuide) {
      drawReplayCursor(context, data.replaySelectionGuide, mediaSize.height);
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
    if (drawable.annotation.kind === "parallel_lines") {
      const control = parallelLineControlPoint(drawable);
      if (!style.locked && Math.hypot(x - control.x, y - control.y) <= 11) {
        return { drawable, mode: "scale" };
      }
    }
    if (drawable.annotation.kind === "fib50") {
      const center = fib50CenterPoint(drawable);
      if (!style.locked && Math.hypot(x - center.x, y - center.y) <= 11) {
        return { drawable, mode: "scale" };
      }
    }
    if (!style.locked && Math.hypot(x - drawable.start.x, y - drawable.start.y) <= 11) {
      return { drawable, mode: "start" };
    }
    if (!style.locked && Math.hypot(x - drawable.end.x, y - drawable.end.y) <= 11) {
      return { drawable, mode: "end" };
    }
    if (isLineAnnotationKind(drawable.annotation.kind)) {
      const segments = annotationLineSegments(drawable);
      if (
        segments.some(
          (segment) => pointToSegmentDistance(x, y, segment.start, segment.end) <= 12,
        )
      ) {
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
): AnnotationProjection | null {
  const barIndexById = new Map(bars.map((bar, index) => [bar.bar_id, index]));
  const originalStartIndex = barIndexById.get(dragState.originalStart.bar_id);
  const originalEndIndex = barIndexById.get(dragState.originalEnd.bar_id);
  if (originalStartIndex === undefined || originalEndIndex === undefined) {
    return null;
  }

  const barDelta = pointer.barIndex - dragState.originPointer.barIndex;
  const priceDelta = pointer.price - dragState.originPointer.price;

  if (dragState.annotationKind === "parallel_lines") {
    const originalControlIndex =
      dragState.originalControl === null
        ? null
        : barIndexById.get(dragState.originalControl.bar_id) ?? null;

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
        control:
          originalControlIndex === null
            ? null
            : {
                bar_id: bars[clampIndex(originalControlIndex + barDelta, bars.length)].bar_id,
                price: dragState.originalControl!.price + priceDelta,
              },
      };
    }

    if (dragState.mode === "start") {
      const nextBarIndex = clampIndex(pointer.barIndex, bars.length);
      const startBarShift = nextBarIndex - originalStartIndex;
      return {
        start: {
          bar_id: bars[nextBarIndex].bar_id,
          price: pointer.price,
        },
        end: dragState.originalEnd,
        control:
          originalControlIndex === null
            ? null
            : {
                bar_id: bars[clampIndex(originalControlIndex + startBarShift, bars.length)].bar_id,
                price:
                  dragState.originalControl!.price +
                  (pointer.price - dragState.originalStart.price),
              },
      };
    }

    if (dragState.mode === "scale") {
      return {
        start: dragState.originalStart,
        end: dragState.originalEnd,
        control: {
          bar_id: bars[clampIndex(pointer.barIndex, bars.length)].bar_id,
          price: pointer.price,
        },
      };
    }

    return {
      start: dragState.originalStart,
      end: {
        bar_id: bars[clampIndex(pointer.barIndex, bars.length)].bar_id,
        price: pointer.price,
      },
      control: dragState.originalControl,
    };
  }

  if (dragState.annotationKind === "horizontal_line") {
    const nextStartIndex =
      dragState.mode === "end"
        ? originalStartIndex
        : clampIndex(
            dragState.mode === "move" ? originalStartIndex + barDelta : pointer.barIndex,
            bars.length,
          );
    const nextEndIndex =
      dragState.mode === "move" || dragState.mode === "start"
        ? clampIndex(originalEndIndex + barDelta, bars.length)
        : clampIndex(pointer.barIndex, bars.length);
    const nextPrice =
      dragState.mode === "move"
        ? dragState.originalStart.price + priceDelta
        : pointer.price;
    return {
      start: { bar_id: bars[nextStartIndex].bar_id, price: nextPrice },
      end: { bar_id: bars[nextEndIndex].bar_id, price: nextPrice },
      control: null,
    };
  }

  if (dragState.annotationKind === "vertical_line") {
    const nextBarIndex =
      dragState.mode === "move"
        ? clampIndex(originalStartIndex + barDelta, bars.length)
        : pointer.barIndex;
    return {
      start: { bar_id: bars[nextBarIndex].bar_id, price: dragState.originalStart.price },
      end: { bar_id: bars[nextBarIndex].bar_id, price: pointer.price },
      control: null,
    };
  }

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
      control: null,
    };
  }

  if (dragState.mode === "scale") {
    const midpoint = (dragState.originalStart.price + dragState.originalEnd.price) / 2;
    const originalHalfRange =
      Math.abs(dragState.originalEnd.price - dragState.originalStart.price) / 2;
    const halfRange = Math.max(originalHalfRange + priceDelta, 0.0001);
    const ascending = dragState.originalEnd.price >= dragState.originalStart.price;
    return {
      start: {
        bar_id: dragState.originalStart.bar_id,
        price: ascending ? midpoint - halfRange : midpoint + halfRange,
      },
      end: {
        bar_id: dragState.originalEnd.bar_id,
        price: ascending ? midpoint + halfRange : midpoint - halfRange,
      },
      control: null,
    };
  }

  if (dragState.mode === "start") {
    return {
      start: {
        bar_id: bars[clampIndex(pointer.barIndex, bars.length)].bar_id,
        price: pointer.price,
      },
      end: dragState.originalEnd,
      control: null,
    };
  }

  return {
    start: dragState.originalStart,
    end: {
      bar_id: bars[clampIndex(pointer.barIndex, bars.length)].bar_id,
      price: pointer.price,
    },
    control: null,
  };
}

export function findOverlayAtPoint(
  drawables: Drawable[],
  x: number,
  y: number,
): Drawable | null {
  for (let index = drawables.length - 1; index >= 0; index -= 1) {
    const drawable = drawables[index];
    if (drawable.overlay.meta.replay_event_type) {
      continue;
    }
    if (resolveOverlaySemantics(drawable.overlay).geometryKind === "leg-line") {
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
    const semantics = resolveOverlaySemantics(overlay);
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
      radius: semantics.geometryKind === "leg-line" ? 8 : semantics.pivotTier === "pivot_st" ? 7 : 9,
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
  const controlTime =
    annotation.control === null || annotation.control === undefined
      ? null
      : barTimeById.get(annotation.control.bar_id) ?? null;
  const controlX = controlTime === null ? null : projector.timeToCoordinate(controlTime);
  const controlY =
    annotation.control === null || annotation.control === undefined
      ? null
      : projector.priceToCoordinate(annotation.control.price);
  if (
    startX === null ||
    endX === null ||
    startY === null ||
    endY === null ||
    (annotation.control !== null &&
      annotation.control !== undefined &&
      (controlX === null || controlY === null))
  ) {
    return null;
  }
  return {
    annotation,
    start: { x: startX, y: startY },
    end: { x: endX, y: endY },
    control:
      controlX === null || controlY === null ? null : { x: controlX, y: controlY },
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
  bars: ChartBar[],
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
  const barIndex = bars.findIndex((bar) => bar.bar_id === guide.confirmBarId);
  if (barIndex < 0) {
    return { x };
  }
  const nextBar = bars[barIndex + 1] ?? null;
  const previousBar = bars[barIndex - 1] ?? null;
  const nextX =
    nextBar === null ? null : projector.timeToCoordinate(nextBar.time);
  const previousX =
    previousBar === null ? null : projector.timeToCoordinate(previousBar.time);
  const rightSpacing =
    nextX !== null && nextX > x
      ? nextX - x
      : previousX !== null && x > previousX
        ? x - previousX
        : null;
  if (rightSpacing === null) {
    return { x };
  }
  return { x: x + Math.max(5, rightSpacing * 0.42) };
}

function resolveReplayBoundary(
  replayMode: boolean,
  replayCursorVisible: boolean,
  replayCursorBarId: number | null,
  bars: ChartBar[],
  barTimeById: Map<number, number>,
  projector: CoordinateProjector,
): ReplayCursorRender | null {
  if (!replayMode || !replayCursorVisible) {
    return null;
  }
  if (replayCursorBarId === null) {
    return null;
  }
  return resolveReplayCursorX(replayCursorBarId, bars, barTimeById, projector);
}

function resolveReplaySelectionGuide(
  replayMode: boolean,
  replayCursorVisible: boolean,
  replayCursorBarId: number | null,
  replayHoverBarId: number | null,
  bars: ChartBar[],
  barTimeById: Map<number, number>,
  projector: CoordinateProjector,
): ReplayCursorRender | null {
  if (!replayMode || !replayCursorVisible) {
    return null;
  }
  const guideBarId = replayHoverBarId ?? replayCursorBarId;
  if (guideBarId === null) {
    return null;
  }
  return resolveReplayCursorX(guideBarId, bars, barTimeById, projector);
}

function resolveReplayCursorX(
  activeBarId: number,
  bars: ChartBar[],
  barTimeById: Map<number, number>,
  projector: CoordinateProjector,
): ReplayCursorRender | null {
  const cursorTime = barTimeById.get(activeBarId);
  if (cursorTime === undefined) {
    return null;
  }
  const x = projector.timeToCoordinate(cursorTime);
  if (x === null) {
    return null;
  }
  const barIndex = bars.findIndex((bar) => bar.bar_id === activeBarId);
  if (barIndex < 0) {
    return { x };
  }
  const nextBar = bars[barIndex + 1] ?? null;
  const previousBar = bars[barIndex - 1] ?? null;
  const nextX =
    nextBar === null ? null : projector.timeToCoordinate(nextBar.time);
  const previousX =
    previousBar === null ? null : projector.timeToCoordinate(previousBar.time);
  const rightSpacing =
    nextX !== null && nextX > x
      ? nextX - x
      : previousX !== null && x > previousX
        ? x - previousX
        : null;
  if (rightSpacing === null) {
    return { x };
  }
  return { x: x + Math.max(5, rightSpacing * 0.42) };
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

  if (isLineAnnotationKind(annotation.kind)) {
    for (const segment of annotationLineSegments(drawable)) {
      context.beginPath();
      context.moveTo(segment.start.x, segment.start.y);
      context.lineTo(segment.end.x, segment.end.y);
      context.stroke();
    }
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
    if (annotation.kind === "parallel_lines") {
      const control = parallelLineControlPoint(drawable);
      drawAnnotationHandle(context, control.x, control.y, style.strokeColor);
    }
    if (annotation.kind === "fib50") {
      const center = fib50CenterPoint(drawable);
      drawAnnotationHandle(context, center.x, center.y, style.strokeColor);
    }
  }
  context.restore();
}

function isLineAnnotationKind(kind: ChartAnnotation["kind"]) {
  return (
    kind === "line" ||
    kind === "parallel_lines" ||
    kind === "horizontal_line" ||
    kind === "vertical_line"
  );
}

function annotationLineSegments(drawable: AnnotationDrawable): AnnotationLineSegment[] {
  if (drawable.annotation.kind === "horizontal_line") {
    return [
      {
        start: { x: -100000, y: drawable.start.y },
        end: { x: 100000, y: drawable.start.y },
      },
    ];
  }
  if (drawable.annotation.kind === "vertical_line") {
    return [
      {
        start: { x: drawable.start.x, y: -100000 },
        end: { x: drawable.start.x, y: 100000 },
      },
    ];
  }
  if (drawable.annotation.kind === "parallel_lines") {
    return parallelLineSegments(drawable.start, drawable.end, drawable.control);
  }
  return [{ start: drawable.start, end: drawable.end }];
}

function parallelLineSegments(
  start: { x: number; y: number },
  end: { x: number; y: number },
  control: { x: number; y: number } | null,
): AnnotationLineSegment[] {
  const translated =
    control === null
      ? defaultParallelTranslation(start, end)
      : { x: control.x - start.x, y: control.y - start.y };
  return [
    { start, end },
    {
      start: { x: start.x + translated.x, y: start.y + translated.y },
      end: { x: end.x + translated.x, y: end.y + translated.y },
    },
  ];
}

function parallelLineControlPoint(drawable: AnnotationDrawable) {
  return annotationLineSegments(drawable)[1].start;
}

function defaultParallelTranslation(
  start: { x: number; y: number },
  end: { x: number; y: number },
) {
  const dx = end.x - start.x;
  const dy = end.y - start.y;
  const length = Math.hypot(dx, dy);
  if (length < 0.001) {
    return { x: 0, y: 24 };
  }
  const normalX = -dy / length;
  const normalY = dx / length;
  const offset = 24;
  return { x: normalX * offset, y: normalY * offset };
}

function drawReplayWatermark(
  context: CanvasRenderingContext2D,
  watermark: ReplayWatermarkRender,
  width: number,
  height: number,
) {
  context.save();
  context.textAlign = "center";
  context.textBaseline = "middle";
  context.font = "600 52px ui-sans-serif, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif";
  context.fillStyle = "rgba(100, 116, 139, 0.055)";
  context.fillText(watermark.label, width / 2, height / 2);
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

function fib50CenterPoint(drawable: AnnotationDrawable) {
  return {
    x: (drawable.start.x + drawable.end.x) / 2,
    y: (drawable.start.y + drawable.end.y) / 2,
  };
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

function drawReplayFutureMask(
  context: CanvasRenderingContext2D,
  cursor: ReplayCursorRender,
  width: number,
  height: number,
) {
  context.save();
  context.fillStyle = "rgba(247, 248, 250, 0.6)";
  context.fillRect(cursor.x, 0, Math.max(width - cursor.x, 0), height);
  context.restore();
}

function drawReplayCursor(
  context: CanvasRenderingContext2D,
  cursor: ReplayCursorRender,
  height: number,
) {
  context.save();
  context.beginPath();
  context.setLineDash([]);
  context.strokeStyle = "rgba(37, 99, 235, 0.95)";
  context.lineWidth = 1.5;
  context.moveTo(Math.round(cursor.x) + 0.5, 0);
  context.lineTo(Math.round(cursor.x) + 0.5, height);
  context.stroke();
  context.restore();
}

function drawOverlay(
  context: CanvasRenderingContext2D,
  drawable: Drawable,
  selected: boolean,
) {
  const semantics = resolveOverlaySemantics(drawable.overlay);
  const style = overlayStyle(drawable.overlay.style_key, selected);
  const isMarker = semantics.geometryKind !== "leg-line";
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

  if (semantics.geometryKind === "leg-line") {
    const [start, end] = drawable.points;
    drawLegLine(context, start, end, style, selected);
    drawLegEndpoint(context, end, style);
  } else if (semantics.geometryKind === "pivot-marker") {
    const [point] = drawable.points;
    const isHigh = semantics.pivotDirection === "high";
    if (semantics.pivotTier === "pivot_st") {
      drawDiamondBadge(context, point.x, point.y, 4.5, isHigh ? "above" : "below", style);
    } else {
      drawPivotBadge(context, point.x, point.y, 5, isHigh ? "down" : "up", style);
    }
  } else if (semantics.geometryKind === "major-lh-marker") {
    const [point] = drawable.points;
    drawDiamondBadge(context, point.x, point.y, 6, "above", style);
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
  context.fillStyle = style.fill;
  drawTriangle(context, anchor.x, crisp(anchor.y + offset), size, direction);
}

function drawDiamondBadge(
  context: CanvasRenderingContext2D,
  x: number,
  y: number,
  size: number,
  placement: "above" | "below",
  style: OverlayPaint,
) {
  const anchor = crispPoint(x, y);
  const badgeY = crisp(anchor.y + (placement === "above" ? -8 : 8));
  context.strokeStyle = style.stroke;
  context.fillStyle = style.fill;
  drawDiamond(context, anchor.x, badgeY, size);
  context.beginPath();
  context.setLineDash([]);
  context.fillStyle = style.accent;
  context.arc(anchor.x, badgeY, 1.9, 0, Math.PI * 2);
  context.fill();
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
  const candidate = styleKey.includes(".candidate");
  const retired = styleKey.includes(".invalidated") || styleKey.includes(".replaced");
  const stateOpacity = retired ? 0.16 : candidate ? 0.52 : 0.92;
  const pivotStOpacity = retired ? 0.12 : candidate ? 0.36 : 0.62;
  const fillOpacity = retired ? 0.035 : 0.16;
  const retiredDash = retired ? [3, 4] : [];
  if (styleKey.startsWith("leg.up")) {
    return {
      stroke: `rgba(36, 92, 62, ${stateOpacity})`,
      fill: `rgba(36, 92, 62, ${fillOpacity})`,
      accent: "rgba(79, 151, 111, 0.96)",
      lineWidth: selected ? 2.9 : 1.65,
      dash: candidate ? [8, 6] : retiredDash,
    };
  }
  if (styleKey.startsWith("leg.down")) {
    return {
      stroke: `rgba(179, 84, 54, ${stateOpacity})`,
      fill: `rgba(179, 84, 54, ${fillOpacity})`,
      accent: "rgba(214, 125, 93, 0.97)",
      lineWidth: selected ? 2.9 : 1.65,
      dash: candidate ? [8, 6] : retiredDash,
    };
  }
  if (styleKey.startsWith("pivot_st.high")) {
    return {
      stroke: `rgba(164, 99, 73, ${pivotStOpacity})`,
      fill: retired ? "rgba(255, 247, 238, 0.16)" : "rgba(255, 247, 238, 0.82)",
      accent: retired ? "rgba(196, 129, 103, 0.34)" : "rgba(196, 129, 103, 0.88)",
      lineWidth: selected ? 1.9 : 1.1,
      dash: retiredDash,
    };
  }
  if (styleKey.startsWith("pivot_st.low")) {
    return {
      stroke: `rgba(52, 104, 80, ${pivotStOpacity})`,
      fill: retired ? "rgba(246, 252, 248, 0.16)" : "rgba(246, 252, 248, 0.82)",
      accent: retired ? "rgba(98, 148, 122, 0.34)" : "rgba(98, 148, 122, 0.88)",
      lineWidth: selected ? 1.9 : 1.1,
      dash: retiredDash,
    };
  }
  if (styleKey.startsWith("pivot.high")) {
    return {
      stroke: `rgba(179, 84, 54, ${stateOpacity})`,
      fill: retired ? "rgba(255, 252, 246, 0.18)" : "rgba(255, 252, 246, 0.94)",
      accent: retired ? "rgba(214, 125, 93, 0.4)" : "rgba(214, 125, 93, 0.97)",
      lineWidth: selected ? 2.2 : 1.35,
      dash: retiredDash,
    };
  }
  if (styleKey.startsWith("pivot.low")) {
    return {
      stroke: `rgba(36, 92, 62, ${stateOpacity})`,
      fill: retired ? "rgba(255, 252, 246, 0.18)" : "rgba(255, 252, 246, 0.94)",
      accent: retired ? "rgba(79, 151, 111, 0.4)" : "rgba(79, 151, 111, 0.96)",
      lineWidth: selected ? 2.2 : 1.35,
      dash: retiredDash,
    };
  }
  if (styleKey.startsWith("major_lh")) {
    return {
      stroke: `rgba(87, 60, 27, ${stateOpacity})`,
      fill: "rgba(255, 251, 242, 0.95)",
      accent: "rgba(230, 177, 95, 0.94)",
      lineWidth: selected ? 2.5 : 1.55,
      dash: candidate ? [5, 4] : retiredDash,
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
