import { useMemo, useState, type PointerEvent as ReactPointerEvent } from "react";

import type { ChartAdapter } from "../lib/chartAdapter";
import {
  colorWithOpacity,
  getAnnotationStyle,
  lineDashForStyle,
} from "../lib/annotationStyle";
import type { AnnotationAnchor, ChartAnnotation, ChartBar } from "../lib/types";

interface AnnotationLayerProps {
  adapter: ChartAdapter | null;
  annotations: ChartAnnotation[];
  bars: ChartBar[];
  selectedAnnotationId: string | null;
  viewportRevision: number;
  onAnnotationSelect: (annotationId: string | null) => void;
  onAnnotationUpdate: (
    annotationId: string,
    start: AnnotationAnchor,
    end: AnnotationAnchor,
  ) => void;
  onAnnotationDuplicate: (annotationId: string) => string | null;
}

interface RenderedAnnotation {
  annotation: ChartAnnotation;
  start: { x: number; y: number };
  end: { x: number; y: number };
  bounds: { left: number; top: number; width: number; height: number };
}

interface DragState {
  annotationId: string;
  eventOwnerId: string;
  mode: "move" | "start" | "end";
  origin: PointerPosition;
  originalStart: AnnotationAnchor;
  originalEnd: AnnotationAnchor;
}

interface PointerPosition {
  barId: number;
  barIndex: number;
  price: number;
}

const HITBOX_PAD = 14;
const HANDLE_RADIUS = 5;

export function AnnotationLayer({
  adapter,
  annotations,
  bars,
  selectedAnnotationId,
  viewportRevision,
  onAnnotationSelect,
  onAnnotationUpdate,
  onAnnotationDuplicate,
}: AnnotationLayerProps) {
  const [dragState, setDragState] = useState<DragState | null>(null);

  const renderedAnnotations = useMemo(() => {
    if (!adapter) {
      return [];
    }
    const barTimeById = new Map(bars.map((bar) => [bar.bar_id, bar.time]));
    return annotations
      .map((annotation) => resolveRenderedAnnotation(annotation, barTimeById, adapter))
      .filter((annotation): annotation is RenderedAnnotation => annotation !== null);
  }, [adapter, annotations, bars, viewportRevision]);

  return (
    <div className="annotation-layer">
      {renderedAnnotations.map((rendered) => {
        const selected = rendered.annotation.id === selectedAnnotationId;
        return (
          <AnnotationShape
            adapter={adapter}
            bars={bars}
            dragState={dragState}
            key={rendered.annotation.id}
            rendered={rendered}
            selected={selected}
            setDragState={setDragState}
            onAnnotationSelect={onAnnotationSelect}
            onAnnotationUpdate={onAnnotationUpdate}
            onAnnotationDuplicate={onAnnotationDuplicate}
          />
        );
      })}
    </div>
  );
}

interface AnnotationShapeProps {
  adapter: ChartAdapter | null;
  bars: ChartBar[];
  dragState: DragState | null;
  rendered: RenderedAnnotation;
  selected: boolean;
  setDragState: (state: DragState | null) => void;
  onAnnotationSelect: (annotationId: string | null) => void;
  onAnnotationUpdate: (
    annotationId: string,
    start: AnnotationAnchor,
    end: AnnotationAnchor,
  ) => void;
  onAnnotationDuplicate: (annotationId: string) => string | null;
}

function AnnotationShape({
  adapter,
  bars,
  dragState,
  rendered,
  selected,
  setDragState,
  onAnnotationSelect,
  onAnnotationUpdate,
  onAnnotationDuplicate,
}: AnnotationShapeProps) {
  const left = rendered.bounds.left - HITBOX_PAD;
  const top = rendered.bounds.top - HITBOX_PAD;
  const width = rendered.bounds.width + HITBOX_PAD * 2;
  const height = rendered.bounds.height + HITBOX_PAD * 2;

  const localStart = {
    x: rendered.start.x - left,
    y: rendered.start.y - top,
  };
  const localEnd = {
    x: rendered.end.x - left,
    y: rendered.end.y - top,
  };
  const fib50Levels = buildFib50Levels(localStart, localEnd);
  const fib50Left = Math.min(localStart.x, localEnd.x);
  const fib50Right = Math.max(localStart.x, localEnd.x);
  const style = getAnnotationStyle(rendered.annotation);

  const beginDrag = (
    event: ReactPointerEvent<Element>,
    mode: DragState["mode"],
  ) => {
    if (!adapter || event.button !== 0) {
      return;
    }
    if (style.locked) {
      event.preventDefault();
      event.stopPropagation();
      onAnnotationSelect(rendered.annotation.id);
      return;
    }
    const pointer = resolvePointerPositionFromEvent(event, adapter, bars);
    if (!pointer) {
      return;
    }
    event.preventDefault();
    event.stopPropagation();
    let dragAnnotationId = rendered.annotation.id;
    if (event.altKey && selected && mode === "move") {
      const duplicateId = onAnnotationDuplicate(rendered.annotation.id);
      if (!duplicateId) {
        return;
      }
      dragAnnotationId = duplicateId;
    }
    onAnnotationSelect(dragAnnotationId);
    setDragState({
      annotationId: dragAnnotationId,
      eventOwnerId: rendered.annotation.id,
      mode,
      origin: pointer,
      originalStart: rendered.annotation.start,
      originalEnd: rendered.annotation.end,
    });
    event.currentTarget.setPointerCapture(event.pointerId);
  };

  const onPointerDown = (event: ReactPointerEvent<HTMLDivElement>) => {
    const rect = event.currentTarget.getBoundingClientRect();
    const localPoint = {
      x: event.clientX - rect.left,
      y: event.clientY - rect.top,
    };
    const mode = hitTestMode(rendered.annotation.kind, localPoint, localStart, localEnd, {
      width,
      height,
    });
    if (!mode) {
      return;
    }
    beginDrag(event, mode);
  };

  const onPointerMove = (event: ReactPointerEvent<Element>) => {
    if (!adapter || !dragState || dragState.eventOwnerId !== rendered.annotation.id) {
      return;
    }
    const pointer = resolvePointerPositionFromEvent(event, adapter, bars);
    if (!pointer) {
      return;
    }
    event.preventDefault();
    const updated = projectDraggedAnnotation(dragState, pointer, bars);
    if (!updated) {
      return;
    }
    onAnnotationUpdate(dragState.annotationId, updated.start, updated.end);
  };

  const onPointerUp = (event: ReactPointerEvent<Element>) => {
    if (dragState?.eventOwnerId !== rendered.annotation.id) {
      return;
    }
    event.preventDefault();
    event.stopPropagation();
    if (event.currentTarget.hasPointerCapture(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId);
    }
    setDragState(null);
  };

  const stroke = colorWithOpacity(style.strokeColor, style.opacity);
  const fill =
    rendered.annotation.kind === "box"
      ? colorWithOpacity(style.fillColor, Math.max(0.12, style.opacity * 0.28))
      : "none";
  const levelStroke = colorWithOpacity(style.strokeColor, style.opacity);
  const dashArray = lineDashForStyle(style.lineStyle).join(" ");

  return (
    <div
      className={
        rendered.annotation.kind === "fib50"
          ? selected
            ? "annotation-shape annotation-shape-fib50 selected"
            : "annotation-shape annotation-shape-fib50"
          : rendered.annotation.kind === "line"
            ? selected
              ? "annotation-shape annotation-shape-line selected"
              : "annotation-shape annotation-shape-line"
          : selected
            ? "annotation-shape selected"
            : "annotation-shape"
      }
      onPointerDown={onPointerDown}
      onPointerMove={onPointerMove}
      onPointerUp={onPointerUp}
      onPointerCancel={() => setDragState(null)}
      style={{
        left: `${left}px`,
        top: `${top}px`,
        width: `${width}px`,
        height: `${height}px`,
      }}
    >
      <svg className="annotation-svg" viewBox={`0 0 ${width} ${height}`}>
        {rendered.annotation.kind === "line" ? (
          <>
            <line
              className="annotation-geometry"
              stroke={stroke}
              strokeDasharray={dashArray}
              strokeWidth={selected ? style.lineWidth + 0.3 : style.lineWidth}
              x1={localStart.x}
              x2={localEnd.x}
              y1={localStart.y}
              y2={localEnd.y}
            />
            <line
              className="annotation-line-hit-target"
              onPointerDown={(event) => beginDrag(event, "move")}
              onPointerMove={onPointerMove}
              onPointerUp={onPointerUp}
              onPointerCancel={() => setDragState(null)}
              pointerEvents="stroke"
              stroke="transparent"
              strokeWidth={18}
              x1={localStart.x}
              x2={localEnd.x}
              y1={localStart.y}
              y2={localEnd.y}
            />
          </>
        ) : rendered.annotation.kind === "box" ? (
          <rect
            className="annotation-geometry"
            fill={fill}
            height={Math.max(Math.abs(localEnd.y - localStart.y), 1)}
            stroke={stroke}
            strokeDasharray={dashArray}
            strokeWidth={selected ? style.lineWidth + 0.2 : style.lineWidth}
            width={Math.max(Math.abs(localEnd.x - localStart.x), 1)}
            x={Math.min(localStart.x, localEnd.x)}
            y={Math.min(localStart.y, localEnd.y)}
          />
        ) : (
          <>
            {fib50Levels.map((levelY, index) => (
              <line
                className="annotation-geometry"
                key={index}
                stroke={levelStroke}
                strokeDasharray={dashArray}
                strokeWidth={selected ? style.lineWidth + 0.2 : style.lineWidth}
                x1={Math.min(localStart.x, localEnd.x)}
                x2={Math.max(localStart.x, localEnd.x)}
                y1={levelY}
                y2={levelY}
              />
            ))}
          </>
        )}
        {selected && !style.locked ? (
          <>
            <circle
              className="annotation-handle"
              cx={localStart.x}
              cy={localStart.y}
              fill="#ffffff"
              r={HANDLE_RADIUS}
              stroke={style.strokeColor}
              strokeWidth={2}
            />
            <circle
              className="annotation-handle"
              cx={localEnd.x}
              cy={localEnd.y}
              fill="#ffffff"
              r={HANDLE_RADIUS}
              stroke={style.strokeColor}
              strokeWidth={2}
            />
          </>
        ) : null}
      </svg>
      {rendered.annotation.kind === "line" ? (
        <>
          <div
            className="annotation-point-hitbox"
            onPointerDown={(event) => beginDrag(event, "start")}
            onPointerMove={onPointerMove}
            onPointerUp={onPointerUp}
            onPointerCancel={() => setDragState(null)}
            style={{
              left: `${localStart.x - 10}px`,
              top: `${localStart.y - 10}px`,
            }}
          />
          <div
            className="annotation-point-hitbox"
            onPointerDown={(event) => beginDrag(event, "end")}
            onPointerMove={onPointerMove}
            onPointerUp={onPointerUp}
            onPointerCancel={() => setDragState(null)}
            style={{
              left: `${localEnd.x - 10}px`,
              top: `${localEnd.y - 10}px`,
            }}
          />
        </>
      ) : null}
      {rendered.annotation.kind === "fib50" ? (
        <>
          {fib50Levels.map((levelY, index) => (
            <div
              className="annotation-line-hitbox"
              key={`hit-${index}`}
              onPointerDown={(event) => beginDrag(event, "move")}
              onPointerMove={onPointerMove}
              onPointerUp={onPointerUp}
              onPointerCancel={() => setDragState(null)}
              style={{
                left: `${Math.max(fib50Left - 8, 0)}px`,
                top: `${Math.max(levelY - 8, 0)}px`,
                width: `${Math.max(fib50Right - fib50Left + 16, 18)}px`,
                height: "16px",
              }}
            />
          ))}
          <div
            className="annotation-point-hitbox"
            onPointerDown={(event) => beginDrag(event, "start")}
            onPointerMove={onPointerMove}
            onPointerUp={onPointerUp}
            onPointerCancel={() => setDragState(null)}
            style={{
              left: `${localStart.x - 10}px`,
              top: `${localStart.y - 10}px`,
            }}
          />
          <div
            className="annotation-point-hitbox"
            onPointerDown={(event) => beginDrag(event, "end")}
            onPointerMove={onPointerMove}
            onPointerUp={onPointerUp}
            onPointerCancel={() => setDragState(null)}
            style={{
              left: `${localEnd.x - 10}px`,
              top: `${localEnd.y - 10}px`,
            }}
          />
        </>
      ) : null}
    </div>
  );
}

function resolveRenderedAnnotation(
  annotation: ChartAnnotation,
  barTimeById: Map<number, number>,
  adapter: ChartAdapter,
): RenderedAnnotation | null {
  const startTime = barTimeById.get(annotation.start.bar_id);
  const endTime = barTimeById.get(annotation.end.bar_id);
  if (startTime === undefined || endTime === undefined) {
    return null;
  }
  const startX = adapter.timeToCoordinate(startTime);
  const endX = adapter.timeToCoordinate(endTime);
  const startY = adapter.priceToCoordinate(annotation.start.price);
  const endY = adapter.priceToCoordinate(annotation.end.price);
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
      width: Math.max(Math.abs(endX - startX), 1),
      height: Math.max(Math.abs(endY - startY), 1),
    },
  };
}

function resolvePointerPositionFromEvent(
  event: ReactPointerEvent<Element>,
  adapter: ChartAdapter,
  bars: ChartBar[],
): PointerPosition | null {
  const chartSurface = event.currentTarget.closest(".chart-surface");
  if (!(chartSurface instanceof HTMLElement)) {
    return null;
  }
  const rect = chartSurface.getBoundingClientRect();
  return resolvePointerPositionFromPoint(
    adapter,
    bars,
    {
      x: event.clientX - rect.left,
      y: event.clientY - rect.top,
    },
  );
}

function resolvePointerPositionFromPoint(
  adapter: ChartAdapter,
  bars: ChartBar[],
  point: { x: number; y: number },
): PointerPosition | null {
  const logical = adapter.coordinateToLogical(point.x);
  const price = adapter.coordinateToPrice(point.y);
  if (logical === null || price === null || bars.length === 0) {
    return null;
  }
  const barIndex = clampIndex(Math.round(logical), bars.length);
  return {
    barId: bars[barIndex].bar_id,
    barIndex,
    price,
  };
}

function hitTestMode(
  kind: ChartAnnotation["kind"],
  point: { x: number; y: number },
  start: { x: number; y: number },
  end: { x: number; y: number },
  box: { width: number; height: number },
): DragState["mode"] | null {
  if (Math.hypot(point.x - start.x, point.y - start.y) <= 11) {
    return "start";
  }
  if (Math.hypot(point.x - end.x, point.y - end.y) <= 11) {
    return "end";
  }
  if (kind === "line") {
    return pointToSegmentDistance(point.x, point.y, start, end) <= 12 ? "move" : null;
  }
  return point.x >= 0 && point.x <= box.width && point.y >= 0 && point.y <= box.height
    ? "move"
    : null;
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

function projectDraggedAnnotation(
  dragState: DragState,
  pointer: PointerPosition,
  bars: ChartBar[],
): { start: AnnotationAnchor; end: AnnotationAnchor } | null {
  const barIndexById = new Map(bars.map((bar, index) => [bar.bar_id, index]));
  const originalStartIndex = barIndexById.get(dragState.originalStart.bar_id);
  const originalEndIndex = barIndexById.get(dragState.originalEnd.bar_id);
  if (originalStartIndex === undefined || originalEndIndex === undefined) {
    return null;
  }

  const barDelta = pointer.barIndex - dragState.origin.barIndex;
  const priceDelta = pointer.price - dragState.origin.price;

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

function clampIndex(index: number, length: number) {
  return Math.max(0, Math.min(length - 1, index));
}

function buildFib50Levels(
  start: { x: number; y: number },
  end: { x: number; y: number },
) {
  const top = Math.min(start.y, end.y);
  const bottom = Math.max(start.y, end.y);
  return [top, top + (bottom - top) * 0.5, bottom];
}
