import { useEffect, useMemo, useRef, useState, type RefObject } from "react";

import type { ChartAdapter } from "../lib/chartAdapter";
import { defaultAnnotationStyle } from "../lib/annotationStyle";
import {
  findOverlayAtPoint,
  hitTestAnnotation,
  projectDraggedAnnotation,
  resolveAnnotationDrawables,
  resolveAnnotationPointerPositionFromPoint,
  resolveOverlayDrawables,
  type AnnotationDragState,
  type AnnotationDrawable,
  type Drawable,
} from "../lib/inspectorScene";
import type {
  AnnotationAnchor,
  AnnotationKind,
  AnnotationTool,
  ChartAnnotation,
  ChartBar,
  ConfirmationGuide,
  Overlay,
  OverlayLayer,
  SessionProfile,
} from "../lib/types";

const LAYER_KIND_MAP: Record<OverlayLayer, ReadonlySet<string>> = {
  pivot: new Set(["pivot-marker"]),
  leg: new Set(["leg-line"]),
  major_lh: new Set(["major-lh-marker"]),
  breakout_start: new Set(["breakout-marker"]),
};

export interface OverlayCanvasProps {
  shellRef: RefObject<HTMLElement | null>;
  surfaceRef: RefObject<HTMLDivElement | null>;
  adapter: ChartAdapter | null;
  bars: ChartBar[];
  overlays: Overlay[];
  annotations: ChartAnnotation[];
  annotationTool: AnnotationTool;
  sessionProfile: SessionProfile;
  enabledLayers: Record<OverlayLayer, boolean>;
  selectedOverlayId: string | null;
  selectedAnnotationId: string | null;
  confirmationGuide: ConfirmationGuide | null;
  viewportRevision: number;
  onAnnotationCreate: (annotation: {
    kind: AnnotationKind;
    start: AnnotationAnchor;
    end: AnnotationAnchor;
  }) => void;
  onAnnotationSelect: (annotationId: string | null) => void;
  onAnnotationUpdate: (
    annotationId: string,
    start: AnnotationAnchor,
    end: AnnotationAnchor,
  ) => void;
  onOverlaySelect: (
    overlay: Overlay | null,
    anchorPoint: { x: number; y: number } | null,
  ) => void;
  onOverlayCommandSelect: (overlay: Overlay) => void;
}

export function OverlayCanvas({
  shellRef,
  surfaceRef,
  adapter,
  bars,
  overlays,
  annotations,
  annotationTool,
  sessionProfile,
  enabledLayers,
  selectedOverlayId,
  selectedAnnotationId,
  confirmationGuide,
  viewportRevision,
  onAnnotationCreate,
  onAnnotationSelect,
  onAnnotationUpdate,
  onOverlaySelect,
  onOverlayCommandSelect,
}: OverlayCanvasProps) {
  const overlayDrawablesRef = useRef<Drawable[]>([]);
  const annotationDrawablesRef = useRef<AnnotationDrawable[]>([]);
  const activeDrawRef = useRef(false);
  const activeDragRef = useRef<AnnotationDragState | null>(null);
  const draftStartRef = useRef<AnnotationAnchor | null>(null);
  const draftCurrentRef = useRef<AnnotationAnchor | null>(null);
  const barsRef = useRef(bars);
  const annotationToolRef = useRef(annotationTool);
  const onAnnotationCreateRef = useRef(onAnnotationCreate);
  const onAnnotationSelectRef = useRef(onAnnotationSelect);
  const onAnnotationUpdateRef = useRef(onAnnotationUpdate);
  const onOverlaySelectRef = useRef(onOverlaySelect);
  const onOverlayCommandSelectRef = useRef(onOverlayCommandSelect);
  const [draftStart, setDraftStart] = useState<AnnotationAnchor | null>(null);
  const [draftCurrent, setDraftCurrent] = useState<AnnotationAnchor | null>(null);
  const [isDrawing, setIsDrawing] = useState(false);

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

  const draftAnnotation =
    annotationTool !== "none" && draftStart && draftCurrent
      ? {
          id: "draft",
          familyKey: "draft",
          kind: annotationTool,
          start: draftStart,
          end: draftCurrent,
          style: defaultAnnotationStyle(annotationTool),
        }
      : null;

  useEffect(() => {
    if (annotationTool === "none") {
      activeDrawRef.current = false;
      setDraftStart(null);
      setDraftCurrent(null);
      setIsDrawing(false);
    }
  }, [annotationTool]);

  useEffect(() => {
    barsRef.current = bars;
    annotationToolRef.current = annotationTool;
    onAnnotationCreateRef.current = onAnnotationCreate;
    onAnnotationSelectRef.current = onAnnotationSelect;
    onAnnotationUpdateRef.current = onAnnotationUpdate;
    onOverlaySelectRef.current = onOverlaySelect;
    onOverlayCommandSelectRef.current = onOverlayCommandSelect;
  }, [
    bars,
    annotationTool,
    onAnnotationCreate,
    onAnnotationSelect,
    onAnnotationUpdate,
    onOverlaySelect,
    onOverlayCommandSelect,
  ]);

  useEffect(() => {
    if (!adapter) {
      return;
    }
    const barTimeById = new Map(bars.map((bar) => [bar.bar_id, bar.time]));
    overlayDrawablesRef.current = resolveOverlayDrawables(bars, visibleOverlays, adapter);
    annotationDrawablesRef.current = resolveAnnotationDrawables(
      annotations,
      barTimeById,
      adapter,
    );
  }, [adapter, annotations, bars, visibleOverlays, viewportRevision]);

  useEffect(() => {
    if (!adapter) {
      return;
    }
    adapter.setInspectorPrimitiveState({
      bars,
      overlays: visibleOverlays,
      annotations,
      selectedOverlayId,
      selectedAnnotationId,
      confirmationGuide,
      sessionProfile,
      draftAnnotation,
    });
  }, [
    adapter,
    annotations,
    bars,
    confirmationGuide,
    draftAnnotation,
    selectedAnnotationId,
    selectedOverlayId,
    sessionProfile,
    visibleOverlays,
  ]);

  useEffect(() => {
    if (!adapter) {
      return;
    }

    const unsubscribeMove = adapter.subscribeCrosshairMove((param) => {
      const surface = surfaceRef.current;
      if (!surface) {
        return;
      }

      if (annotationTool !== "none") {
        surface.style.cursor = "default";
        if (draftStart && param.point) {
          const pointer = resolveAnnotationPointerPositionFromPoint(
            param.point,
            bars,
            adapter.coordinateToLogical,
            adapter.coordinateToPrice,
          );
          setDraftCurrent(pointer ? { bar_id: pointer.barId, price: pointer.price } : null);
        }
        return;
      }

      const point = param.point;
      const annotationHit =
        point === undefined
          ? null
          : hitTestAnnotation(annotationDrawablesRef.current, point.x, point.y);
      if (annotationHit) {
        surface.style.cursor =
          annotationHit.mode === "move" ? "grab" : "nwse-resize";
        return;
      }

      const overlayDrawable =
        point === undefined
          ? null
          : findOverlayAtPoint(overlayDrawablesRef.current, point.x, point.y);
      surface.style.cursor = overlayDrawable ? "pointer" : "default";
    });

    return () => {
      unsubscribeMove();
      const surface = surfaceRef.current;
      if (surface) {
        surface.style.cursor = "default";
      }
    };
  }, [
    adapter,
    annotationTool,
    bars,
    draftStart,
    isDrawing,
    onAnnotationSelect,
    onOverlayCommandSelect,
    onOverlaySelect,
    shellRef,
    surfaceRef,
  ]);

  useEffect(() => {
    const surface = surfaceRef.current;
    if (!surface || !adapter) {
      return;
    }

    const isToolbarEvent = (target: EventTarget | null) =>
      target instanceof Element && target.closest(".annotation-toolbar") !== null;

    const resolvePoint = (event: PointerEvent) => {
      const rect = surface.getBoundingClientRect();
      return resolveAnnotationPointerPositionFromPoint(
        {
          x: event.clientX - rect.left,
          y: event.clientY - rect.top,
        },
        barsRef.current,
        adapter.coordinateToLogical,
        adapter.coordinateToPrice,
      );
    };

    const onPointerDown = (event: PointerEvent) => {
      if (event.button !== 0) {
        return;
      }
      if (isToolbarEvent(event.target)) {
        return;
      }
      const point = {
        x: event.clientX - surface.getBoundingClientRect().left,
        y: event.clientY - surface.getBoundingClientRect().top,
      };
      const pointer = resolvePoint(event);
      if (annotationToolRef.current !== "none") {
        if (!pointer) {
          return;
        }
        event.preventDefault();
        event.stopPropagation();
        onAnnotationSelectRef.current(null);
        onOverlaySelectRef.current(null, null);
        activeDrawRef.current = true;
        setIsDrawing(true);
        draftStartRef.current = { bar_id: pointer.barId, price: pointer.price };
        draftCurrentRef.current = { bar_id: pointer.barId, price: pointer.price };
        setDraftStart(draftStartRef.current);
        setDraftCurrent(draftCurrentRef.current);
        surface.setPointerCapture(event.pointerId);
        return;
      }

      const annotationHit = hitTestAnnotation(
        annotationDrawablesRef.current,
        point.x,
        point.y,
      );
      if (annotationHit) {
        event.preventDefault();
        event.stopPropagation();
        onOverlaySelectRef.current(null, null);
        onAnnotationSelectRef.current(annotationHit.drawable.annotation.id);
        const style = annotationHit.drawable.annotation.style;
        if (!pointer || style.locked) {
          return;
        }
        activeDragRef.current = {
          annotationId: annotationHit.drawable.annotation.id,
          mode: annotationHit.mode,
          originPointer: pointer,
          originalStart: annotationHit.drawable.annotation.start,
          originalEnd: annotationHit.drawable.annotation.end,
        };
        surface.setPointerCapture(event.pointerId);
        return;
      }

      const overlayDrawable = findOverlayAtPoint(overlayDrawablesRef.current, point.x, point.y);
      if (overlayDrawable) {
        event.preventDefault();
        event.stopPropagation();
        onAnnotationSelectRef.current(null);
        if (event.metaKey || event.ctrlKey) {
          onOverlayCommandSelectRef.current(overlayDrawable.overlay);
          return;
        }
        const shell = shellRef.current;
        if (!shell) {
          onOverlaySelectRef.current(overlayDrawable.overlay, point);
          return;
        }
        const shellRect = shell.getBoundingClientRect();
        const surfaceRect = surface.getBoundingClientRect();
        onOverlaySelectRef.current(overlayDrawable.overlay, {
          x: point.x + (surfaceRect.left - shellRect.left),
          y: point.y + (surfaceRect.top - shellRect.top),
        });
        return;
      }

      onAnnotationSelectRef.current(null);
      onOverlaySelectRef.current(null, null);
    };

    const onPointerMove = (event: PointerEvent) => {
      if (isToolbarEvent(event.target)) {
        return;
      }
      if (activeDrawRef.current) {
        const anchor = resolvePoint(event);
        if (!anchor) {
          return;
        }
        event.preventDefault();
        event.stopPropagation();
        draftCurrentRef.current = { bar_id: anchor.barId, price: anchor.price };
        setDraftCurrent(draftCurrentRef.current);
        return;
      }
      if (!activeDragRef.current) {
        return;
      }
      const pointer = resolvePoint(event);
      if (!pointer) {
        return;
      }
      event.preventDefault();
      event.stopPropagation();
      const updated = projectDraggedAnnotation(activeDragRef.current, pointer, barsRef.current);
      if (!updated) {
        return;
      }
      onAnnotationUpdateRef.current(activeDragRef.current.annotationId, updated.start, updated.end);
    };

    const onPointerUp = (event: PointerEvent) => {
      if (isToolbarEvent(event.target)) {
        return;
      }
      if (activeDrawRef.current) {
        const drawKind = annotationToolRef.current;
        if (drawKind === "none") {
          activeDrawRef.current = false;
          return;
        }
        const pointer = resolvePoint(event);
        const start = draftStartRef.current;
        const current = draftCurrentRef.current;
        const anchor = pointer
          ? { bar_id: pointer.barId, price: pointer.price }
          : current ?? start;
        event.preventDefault();
        event.stopPropagation();
        if (surface.hasPointerCapture(event.pointerId)) {
          surface.releasePointerCapture(event.pointerId);
        }
        activeDrawRef.current = false;
        setIsDrawing(false);
        if (!start || !anchor) {
          draftStartRef.current = null;
          draftCurrentRef.current = null;
          setDraftStart(null);
          setDraftCurrent(null);
          return;
        }
        onAnnotationCreateRef.current({
          kind: drawKind,
          start,
          end: anchor,
        });
        draftStartRef.current = null;
        draftCurrentRef.current = null;
        setDraftStart(null);
        setDraftCurrent(null);
        return;
      }
      if (activeDragRef.current) {
        event.preventDefault();
        event.stopPropagation();
        if (surface.hasPointerCapture(event.pointerId)) {
          surface.releasePointerCapture(event.pointerId);
        }
        activeDragRef.current = null;
      }
    };

    const onPointerCancel = (event: PointerEvent) => {
      if (isToolbarEvent(event.target)) {
        return;
      }
      if (surface.hasPointerCapture(event.pointerId)) {
        surface.releasePointerCapture(event.pointerId);
      }
      activeDrawRef.current = false;
      activeDragRef.current = null;
      draftStartRef.current = null;
      draftCurrentRef.current = null;
      setIsDrawing(false);
      setDraftStart(null);
      setDraftCurrent(null);
    };

    surface.addEventListener("pointerdown", onPointerDown, true);
    surface.addEventListener("pointermove", onPointerMove, true);
    surface.addEventListener("pointerup", onPointerUp, true);
    surface.addEventListener("pointercancel", onPointerCancel, true);

    return () => {
      surface.removeEventListener("pointerdown", onPointerDown, true);
      surface.removeEventListener("pointermove", onPointerMove, true);
      surface.removeEventListener("pointerup", onPointerUp, true);
      surface.removeEventListener("pointercancel", onPointerCancel, true);
    };
  }, [
    adapter,
    shellRef,
    surfaceRef,
  ]);

  return null;
}

function isCommandClick(
  param: { sourceEvent?: { metaKey?: boolean; ctrlKey?: boolean } },
) {
  return Boolean(param.sourceEvent?.metaKey || param.sourceEvent?.ctrlKey);
}
