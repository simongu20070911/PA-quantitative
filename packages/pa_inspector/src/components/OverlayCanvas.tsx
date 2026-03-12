import { useEffect, useMemo, useRef, type RefObject } from "react";

import type { ChartAdapter } from "../lib/chartAdapter";
import { defaultAnnotationStyle } from "../lib/annotationStyle";
import { filterOverlaysByEnabledLayers } from "../lib/overlayLayers";
import {
  findOverlayAtPoint,
  hitTestAnnotation,
  projectDraggedAnnotation,
  resolveAnnotationPointerPositionFromPoint,
  type AnnotationDragState,
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
  selectedAnnotationIds: string[];
  confirmationGuide: ConfirmationGuide | null;
  replayEnabled: boolean;
  replayCursorBarId: number | null;
  onAnnotationCreate: (annotation: {
    kind: AnnotationKind;
    start: AnnotationAnchor;
    end: AnnotationAnchor;
  }) => void;
  onAnnotationSelect: (annotationIds: string[]) => void;
  onAnnotationUpdate: (
    annotationId: string,
    start: AnnotationAnchor,
    end: AnnotationAnchor,
  ) => void;
  onAnnotationDuplicate: (annotationIds: string[]) => string[];
  onOverlaySelect: (
    overlay: Overlay | null,
    anchorPoint: { x: number; y: number } | null,
  ) => void;
  onOverlayCommandSelect: (overlay: Overlay) => void;
  onReplayCursorSelect: (barId: number) => void;
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
  selectedAnnotationIds,
  confirmationGuide,
  replayEnabled,
  replayCursorBarId,
  onAnnotationCreate,
  onAnnotationSelect,
  onAnnotationUpdate,
  onAnnotationDuplicate,
  onOverlaySelect,
  onOverlayCommandSelect,
  onReplayCursorSelect,
}: OverlayCanvasProps) {
  const activeDrawRef = useRef(false);
  const activeDragRef = useRef<AnnotationDragState | null>(null);
  const activeBlankTapRef = useRef<{
    pointerId: number;
    startX: number;
    startY: number;
  } | null>(null);
  const suppressNextChartClickRef = useRef(false);
  const draftStateRef = useRef<{
    start: AnnotationAnchor;
    current: AnnotationAnchor;
  } | null>(null);
  const lineSnapActiveRef = useRef(false);
  const modifierPressedRef = useRef(false);
  const barsRef = useRef(bars);
  const annotationsRef = useRef(annotations);
  const visibleOverlaysRef = useRef<Overlay[]>([]);
  const sessionProfileRef = useRef(sessionProfile);
  const selectedOverlayIdRef = useRef(selectedOverlayId);
  const selectedAnnotationIdsRef = useRef(selectedAnnotationIds);
  const confirmationGuideRef = useRef(confirmationGuide);
  const annotationToolRef = useRef(annotationTool);
  const replayEnabledRef = useRef(replayEnabled);
  const replayCursorBarIdRef = useRef(replayCursorBarId);
  const replayHoverBarIdRef = useRef<number | null>(null);
  const onAnnotationCreateRef = useRef(onAnnotationCreate);
  const onAnnotationSelectRef = useRef(onAnnotationSelect);
  const onAnnotationUpdateRef = useRef(onAnnotationUpdate);
  const onAnnotationDuplicateRef = useRef(onAnnotationDuplicate);
  const onOverlaySelectRef = useRef(onOverlaySelect);
  const onOverlayCommandSelectRef = useRef(onOverlayCommandSelect);
  const onReplayCursorSelectRef = useRef(onReplayCursorSelect);

  const visibleOverlays = useMemo(() => {
    return filterOverlaysByEnabledLayers(overlays, enabledLayers);
  }, [enabledLayers, overlays]);

  const syncInspectorPrimitiveState = (nextAdapter: ChartAdapter | null = adapter) => {
    if (!nextAdapter) {
      return;
    }
    nextAdapter.setInspectorPrimitiveState(
      buildInspectorPrimitiveState({
        bars: barsRef.current,
        overlays: visibleOverlaysRef.current,
        annotations: annotationsRef.current,
        selectedOverlayId: selectedOverlayIdRef.current,
        selectedAnnotationIds: selectedAnnotationIdsRef.current,
        confirmationGuide: confirmationGuideRef.current,
        sessionProfile: sessionProfileRef.current,
        annotationTool: annotationToolRef.current,
        draftState: draftStateRef.current,
        replayEnabled: replayEnabledRef.current,
        replayCursorBarId: replayCursorBarIdRef.current,
        replayHoverBarId: replayHoverBarIdRef.current,
      }),
    );
  };

  useEffect(() => {
    annotationToolRef.current = annotationTool;
    if (annotationTool === "none") {
      activeDrawRef.current = false;
      activeDragRef.current = null;
      lineSnapActiveRef.current = false;
      draftStateRef.current = null;
      syncInspectorPrimitiveState();
    }
  }, [adapter, annotationTool]);

  useEffect(() => {
    barsRef.current = bars;
    annotationsRef.current = annotations;
    visibleOverlaysRef.current = visibleOverlays;
    sessionProfileRef.current = sessionProfile;
    selectedOverlayIdRef.current = selectedOverlayId;
    selectedAnnotationIdsRef.current = selectedAnnotationIds;
    confirmationGuideRef.current = confirmationGuide;
    onAnnotationCreateRef.current = onAnnotationCreate;
    onAnnotationSelectRef.current = onAnnotationSelect;
    onAnnotationUpdateRef.current = onAnnotationUpdate;
    onAnnotationDuplicateRef.current = onAnnotationDuplicate;
    onOverlaySelectRef.current = onOverlaySelect;
    onOverlayCommandSelectRef.current = onOverlayCommandSelect;
    replayEnabledRef.current = replayEnabled;
    replayCursorBarIdRef.current = replayCursorBarId;
    if (!replayEnabled || replayCursorBarId !== null) {
      replayHoverBarIdRef.current = null;
    }
    onReplayCursorSelectRef.current = onReplayCursorSelect;
    if (!adapter) {
      return;
    }
    syncInspectorPrimitiveState(adapter);
  }, [
    adapter,
    annotations,
    bars,
    confirmationGuide,
    selectedAnnotationIds,
    selectedOverlayId,
    sessionProfile,
    visibleOverlays,
    replayEnabled,
    replayCursorBarId,
    onReplayCursorSelect,
  ]);

  useEffect(() => {
    const onKeyChange = (event: KeyboardEvent) => {
      lineSnapActiveRef.current = event.metaKey || event.ctrlKey;
      modifierPressedRef.current = event.metaKey || event.ctrlKey;
    };
    const onBlur = () => {
      lineSnapActiveRef.current = false;
      modifierPressedRef.current = false;
    };
    window.addEventListener("keydown", onKeyChange);
    window.addEventListener("keyup", onKeyChange);
    window.addEventListener("blur", onBlur);
    return () => {
      window.removeEventListener("keydown", onKeyChange);
      window.removeEventListener("keyup", onKeyChange);
      window.removeEventListener("blur", onBlur);
    };
  }, []);

  useEffect(() => {
    if (!adapter) {
      return;
    }

    const unsubscribeClick = adapter.subscribeClick((param) => {
      if (suppressNextChartClickRef.current) {
        suppressNextChartClickRef.current = false;
        return;
      }
      if (annotationToolRef.current !== "none") {
        return;
      }

      const point =
        param.point ??
        (param.sourceEvent
          ? {
              x: Number(param.sourceEvent.localX),
              y: Number(param.sourceEvent.localY),
            }
          : undefined);
      if (!point) {
        onAnnotationSelectRef.current([]);
        onOverlaySelectRef.current(null, null);
        return;
      }

      const renderData = adapter.getInspectorRenderData();
      const overlayDrawable = findOverlayAtPoint(
        renderData.overlayDrawables,
        point.x,
        point.y,
      );
      if (!overlayDrawable) {
        if (replayEnabledRef.current) {
          const replayBarId = resolveBarIdFromPoint(adapter, barsRef.current, point);
          if (replayBarId !== null) {
            onReplayCursorSelectRef.current(replayBarId);
          }
        }
        onAnnotationSelectRef.current([]);
        onOverlaySelectRef.current(null, null);
        return;
      }

      onAnnotationSelectRef.current([]);
      const shell = shellRef.current;
      const surface = surfaceRef.current;
      if (!shell || !surface) {
        onOverlaySelectRef.current(overlayDrawable.overlay, point);
        return;
      }
      const shellRect = shell.getBoundingClientRect();
      const surfaceRect = surface.getBoundingClientRect();
      onOverlaySelectRef.current(overlayDrawable.overlay, {
        x: point.x + (surfaceRect.left - shellRect.left),
        y: point.y + (surfaceRect.top - shellRect.top),
      });
    });

    const unsubscribeMove = adapter.subscribeCrosshairMove((param) => {
      const surface = surfaceRef.current;
      if (!surface) {
        return;
      }

      if (annotationToolRef.current !== "none") {
        surface.style.cursor = "default";
        return;
      }

      const point = param.point;
      const renderData = adapter.getInspectorRenderData();
      const annotationHit =
        point === undefined
          ? null
          : hitTestAnnotation(renderData.annotationDrawables, point.x, point.y);
      if (annotationHit) {
        surface.style.cursor =
          annotationHit.mode === "move"
            ? "grab"
            : annotationHit.mode === "scale"
              ? "ns-resize"
              : "nwse-resize";
        return;
      }

      const overlayDrawable =
        point === undefined
          ? null
          : findOverlayAtPoint(renderData.overlayDrawables, point.x, point.y);
      if (replayEnabledRef.current && replayCursorBarIdRef.current === null) {
        const hoverBarId =
          point === undefined ? null : resolveBarIdFromPoint(adapter, barsRef.current, point);
        if (replayHoverBarIdRef.current !== hoverBarId) {
          replayHoverBarIdRef.current = hoverBarId;
          syncInspectorPrimitiveState(adapter);
        }
      }
      surface.style.cursor = overlayDrawable ? "pointer" : "default";
    });

    return () => {
      unsubscribeClick();
      unsubscribeMove();
      const surface = surfaceRef.current;
      if (surface) {
        surface.style.cursor = "default";
      }
    };
  }, [
    adapter,
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
        activeBlankTapRef.current = null;
        if (!pointer) {
          return;
        }
        event.preventDefault();
        event.stopPropagation();
        suppressNextChartClickRef.current = true;
        onAnnotationSelectRef.current([]);
        onOverlaySelectRef.current(null, null);
        activeDrawRef.current = true;
        draftStateRef.current = {
          start: { bar_id: pointer.barId, price: pointer.price },
          current: { bar_id: pointer.barId, price: pointer.price },
        };
        syncInspectorPrimitiveState(adapter);
        surface.setPointerCapture(event.pointerId);
        return;
      }

      const renderData = adapter.getInspectorRenderData();
      const overlayDrawable = findOverlayAtPoint(
        renderData.overlayDrawables,
        point.x,
        point.y,
      );
      if (overlayDrawable && (event.metaKey || event.ctrlKey)) {
        activeBlankTapRef.current = null;
        event.preventDefault();
        event.stopPropagation();
        suppressNextChartClickRef.current = true;
        onAnnotationSelectRef.current([]);
        onOverlayCommandSelectRef.current(overlayDrawable.overlay);
        return;
      }
      const annotationHit = hitTestAnnotation(
        renderData.annotationDrawables,
        point.x,
        point.y,
      );
      if (annotationHit) {
        activeBlankTapRef.current = null;
        event.preventDefault();
        event.stopPropagation();
        suppressNextChartClickRef.current = true;
        onOverlaySelectRef.current(null, null);
        const style = annotationHit.drawable.annotation.style;
        const annotationId = annotationHit.drawable.annotation.id;
        const currentSelection = selectedAnnotationIdsRef.current;
        const modifierPressed = event.metaKey || event.ctrlKey;
        let dragAnnotationId = annotationId;
        if (event.altKey) {
          const duplicateIds = onAnnotationDuplicateRef.current([annotationId]);
          const duplicateId = duplicateIds[duplicateIds.length - 1] ?? null;
          if (duplicateId) {
            dragAnnotationId = duplicateId;
            onAnnotationSelectRef.current([duplicateId]);
          } else {
            onAnnotationSelectRef.current([annotationId]);
          }
        } else if (modifierPressed) {
          const nextSelection = currentSelection.includes(annotationId)
            ? currentSelection.filter((id) => id !== annotationId)
            : [...currentSelection, annotationId];
          onAnnotationSelectRef.current(nextSelection);
          return;
        } else {
          onAnnotationSelectRef.current([annotationId]);
        }
        if (!pointer || style.locked) {
          return;
        }
        activeDragRef.current = {
          annotationId: dragAnnotationId,
          annotationKind: annotationHit.drawable.annotation.kind,
          mode: annotationHit.mode,
          originPointer: pointer,
          originalStart: annotationHit.drawable.annotation.start,
          originalEnd: annotationHit.drawable.annotation.end,
        };
        surface.setPointerCapture(event.pointerId);
        return;
      }

      activeBlankTapRef.current =
        selectedAnnotationIdsRef.current.length > 0 ||
        selectedOverlayIdRef.current !== null ||
        replayEnabledRef.current
          ? {
              pointerId: event.pointerId,
              startX: point.x,
              startY: point.y,
            }
          : null;
    };

    const onPointerMove = (event: PointerEvent) => {
      if (isToolbarEvent(event.target)) {
        return;
      }
      if (activeDrawRef.current) {
        activeBlankTapRef.current = null;
        const rawAnchor = resolvePoint(event);
        const surfaceRect = surface.getBoundingClientRect();
        const anchor =
          rawAnchor && draftStateRef.current?.start
            ? resolveDraftAnchor(
                adapter,
                barsRef.current,
                annotationToolRef.current,
                draftStateRef.current.start,
                {
                  x: event.clientX - surfaceRect.left,
                  y: event.clientY - surfaceRect.top,
                },
                event.metaKey || event.ctrlKey,
              )
            : null;
        if (!anchor) {
          return;
        }
        event.preventDefault();
        event.stopPropagation();
        if (!draftStateRef.current) {
          return;
        }
        draftStateRef.current = {
          start: draftStateRef.current.start,
          current: { bar_id: anchor.bar_id, price: anchor.price },
        };
        syncInspectorPrimitiveState(adapter);
        return;
      }
      if (!activeDragRef.current) {
        const blankTap = activeBlankTapRef.current;
        if (blankTap && blankTap.pointerId === event.pointerId) {
          const point = {
            x: event.clientX - surface.getBoundingClientRect().left,
            y: event.clientY - surface.getBoundingClientRect().top,
          };
          const dx = point.x - blankTap.startX;
          const dy = point.y - blankTap.startY;
          if (Math.hypot(dx, dy) > 6) {
            activeBlankTapRef.current = null;
          }
        }
        return;
      }
      activeBlankTapRef.current = null;
      const pointer = resolvePoint(event);
      if (!pointer) {
        return;
      }
      const projectedPointer =
        (event.metaKey || event.ctrlKey) &&
        activeDragRef.current.annotationKind === "line" &&
        (activeDragRef.current.mode === "start" || activeDragRef.current.mode === "end")
          ? resolveSnappedDragPointer(
              adapter,
              barsRef.current,
              activeDragRef.current,
              {
                x: event.clientX - surface.getBoundingClientRect().left,
                y: event.clientY - surface.getBoundingClientRect().top,
              },
            ) ?? pointer
          : pointer;
      event.preventDefault();
      event.stopPropagation();
      const updated = projectDraggedAnnotation(
        activeDragRef.current,
        projectedPointer,
        barsRef.current,
      );
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
        activeBlankTapRef.current = null;
        const drawKind = annotationToolRef.current;
        if (drawKind === "none") {
          activeDrawRef.current = false;
          return;
        }
        const pointer = resolvePoint(event);
        const start = draftStateRef.current?.start ?? null;
        const current = draftStateRef.current?.current ?? null;
        const surfaceRect = surface.getBoundingClientRect();
        const anchor = pointer && start
          ? resolveDraftAnchor(
              adapter,
              barsRef.current,
              annotationToolRef.current,
              start,
              {
                x: event.clientX - surfaceRect.left,
                y: event.clientY - surfaceRect.top,
              },
              event.metaKey || event.ctrlKey,
            )
          : current ?? start;
        event.preventDefault();
        event.stopPropagation();
        if (surface.hasPointerCapture(event.pointerId)) {
          surface.releasePointerCapture(event.pointerId);
        }
        activeDrawRef.current = false;
        if (!start || !anchor) {
          draftStateRef.current = null;
          syncInspectorPrimitiveState(adapter);
          return;
        }
        onAnnotationCreateRef.current({
          kind: drawKind,
          start,
          end: anchor,
        });
        draftStateRef.current = null;
        syncInspectorPrimitiveState(adapter);
        return;
      }
      if (activeDragRef.current) {
        activeBlankTapRef.current = null;
        event.preventDefault();
        event.stopPropagation();
        if (surface.hasPointerCapture(event.pointerId)) {
          surface.releasePointerCapture(event.pointerId);
        }
        activeDragRef.current = null;
        return;
      }

      const blankTap = activeBlankTapRef.current;
      activeBlankTapRef.current = null;
      if (!blankTap || blankTap.pointerId !== event.pointerId) {
        return;
      }
      const point = {
        x: event.clientX - surface.getBoundingClientRect().left,
        y: event.clientY - surface.getBoundingClientRect().top,
      };
      const replayBarId =
        replayEnabledRef.current ? resolveBarIdFromPoint(adapter, barsRef.current, point) : null;
      suppressNextChartClickRef.current = true;
      onAnnotationSelectRef.current([]);
      onOverlaySelectRef.current(null, null);
      if (replayBarId !== null) {
        onReplayCursorSelectRef.current(replayBarId);
      }
    };

    const onPointerCancel = (event: PointerEvent) => {
      if (isToolbarEvent(event.target)) {
        return;
      }
      if (surface.hasPointerCapture(event.pointerId)) {
        surface.releasePointerCapture(event.pointerId);
      }
      activeBlankTapRef.current = null;
      activeDrawRef.current = false;
      activeDragRef.current = null;
      lineSnapActiveRef.current = false;
      draftStateRef.current = null;
      syncInspectorPrimitiveState(adapter);
    };

    const onContextMenu = (event: MouseEvent) => {
      const point = {
        x: event.clientX - surface.getBoundingClientRect().left,
        y: event.clientY - surface.getBoundingClientRect().top,
      };
      const renderData = adapter.getInspectorRenderData();
      const overlayDrawable = findOverlayAtPoint(
        renderData.overlayDrawables,
        point.x,
        point.y,
      );
      if (overlayDrawable && (event.metaKey || event.ctrlKey || modifierPressedRef.current)) {
        event.preventDefault();
        event.stopPropagation();
      }
    };

    surface.addEventListener("pointerdown", onPointerDown, true);
    surface.addEventListener("pointermove", onPointerMove, true);
    surface.addEventListener("pointerup", onPointerUp, true);
    surface.addEventListener("pointercancel", onPointerCancel, true);
    surface.addEventListener("contextmenu", onContextMenu, true);

    return () => {
      surface.removeEventListener("pointerdown", onPointerDown, true);
      surface.removeEventListener("pointermove", onPointerMove, true);
      surface.removeEventListener("pointerup", onPointerUp, true);
      surface.removeEventListener("pointercancel", onPointerCancel, true);
      surface.removeEventListener("contextmenu", onContextMenu, true);
    };
  }, [
    adapter,
    shellRef,
    surfaceRef,
  ]);

  return null;
}

function resolveBarIdFromPoint(
  adapter: ChartAdapter,
  bars: ChartBar[],
  point: { x: number; y: number },
): number | null {
  const logical = adapter.coordinateToLogical(point.x);
  if (logical === null || bars.length === 0) {
    return null;
  }
  const barIndex = Math.max(0, Math.min(bars.length - 1, Math.round(logical)));
  return bars[barIndex]?.bar_id ?? null;
}

function buildInspectorPrimitiveState(args: {
  bars: ChartBar[];
  overlays: Overlay[];
  annotations: ChartAnnotation[];
  selectedOverlayId: string | null;
  selectedAnnotationIds: string[];
  confirmationGuide: ConfirmationGuide | null;
  sessionProfile: SessionProfile;
  annotationTool: AnnotationTool;
  draftState: { start: AnnotationAnchor; current: AnnotationAnchor } | null;
  replayEnabled: boolean;
  replayCursorBarId: number | null;
  replayHoverBarId: number | null;
}) {
  return {
    bars: args.bars,
    overlays: args.overlays,
    annotations: args.annotations,
    selectedOverlayId: args.selectedOverlayId,
    selectedAnnotationIds: args.selectedAnnotationIds,
    confirmationGuide: args.confirmationGuide,
    sessionProfile: args.sessionProfile,
    draftAnnotation: buildDraftAnnotation(args.annotationTool, args.draftState),
    replayMode: args.replayEnabled,
    replayCursorBarId: args.replayCursorBarId,
    replayHoverBarId: args.replayHoverBarId,
  };
}

function buildDraftAnnotation(
  tool: AnnotationTool,
  draftState: { start: AnnotationAnchor; current: AnnotationAnchor } | null,
) {
  if (tool === "none" || !draftState) {
    return null;
  }
  return {
    id: "draft",
    familyKey: "draft",
    kind: tool,
    start: draftState.start,
    end: draftState.current,
    style: defaultAnnotationStyle(tool),
  };
}

function resolveDraftAnchor(
  adapter: ChartAdapter,
  bars: ChartBar[],
  tool: AnnotationTool,
  start: AnnotationAnchor,
  point: { x: number; y: number },
  snapLine: boolean,
): AnnotationAnchor | null {
  if (tool === "line" && snapLine) {
    return resolveSnappedLineAnchor(adapter, bars, start, point);
  }
  return resolveAnchorFromPoint(adapter, bars, point);
}

function resolveSnappedDragPointer(
  adapter: ChartAdapter,
  bars: ChartBar[],
  dragState: AnnotationDragState,
  point: { x: number; y: number },
) {
  const fixedAnchor =
    dragState.mode === "start" ? dragState.originalEnd : dragState.originalStart;
  const anchor = resolveSnappedLineAnchor(adapter, bars, fixedAnchor, point);
  if (!anchor) {
    return null;
  }
  const barIndex = bars.findIndex((bar) => bar.bar_id === anchor.bar_id);
  if (barIndex < 0) {
    return null;
  }
  return {
    barId: anchor.bar_id,
    barIndex,
    price: anchor.price,
  };
}

function resolveSnappedLineAnchor(
  adapter: ChartAdapter,
  bars: ChartBar[],
  fixedAnchor: AnnotationAnchor,
  point: { x: number; y: number },
): AnnotationAnchor | null {
  const barTimeById = new Map(bars.map((bar) => [bar.bar_id, bar.time]));
  const fixedTime = barTimeById.get(fixedAnchor.bar_id);
  if (fixedTime === undefined) {
    return null;
  }
  const originX = adapter.timeToCoordinate(fixedTime);
  const originY = adapter.priceToCoordinate(fixedAnchor.price);
  if (originX === null || originY === null) {
    return null;
  }
  const dx = point.x - originX;
  const dy = point.y - originY;
  const snappedPoint = snapVectorToPreferredAngles(originX, originY, dx, dy);
  return resolveAnchorFromPoint(adapter, bars, snappedPoint);
}

function snapVectorToPreferredAngles(
  originX: number,
  originY: number,
  dx: number,
  dy: number,
) {
  const diagonal = Math.SQRT1_2;
  const candidates = [
    { x: 1, y: 0 },
    { x: 0, y: 1 },
    { x: diagonal, y: diagonal },
    { x: diagonal, y: -diagonal },
  ];
  let best = { x: originX + dx, y: originY + dy };
  let bestDistance = Number.POSITIVE_INFINITY;
  for (const candidate of candidates) {
    const projection = dx * candidate.x + dy * candidate.y;
    const snappedX = originX + projection * candidate.x;
    const snappedY = originY + projection * candidate.y;
    const distance = Math.hypot(originX + dx - snappedX, originY + dy - snappedY);
    if (distance < bestDistance) {
      bestDistance = distance;
      best = { x: snappedX, y: snappedY };
    }
  }
  return best;
}

function resolveAnchorFromPoint(
  adapter: ChartAdapter,
  bars: ChartBar[],
  point: { x: number; y: number },
): AnnotationAnchor | null {
  const logical = adapter.coordinateToLogical(point.x);
  const price = adapter.coordinateToPrice(point.y);
  if (logical === null || price === null || bars.length === 0) {
    return null;
  }
  const barIndex = Math.max(0, Math.min(bars.length - 1, Math.round(logical)));
  return {
    bar_id: bars[barIndex].bar_id,
    price,
  };
}
