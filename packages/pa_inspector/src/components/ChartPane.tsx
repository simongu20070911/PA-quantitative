import { useEffect, useMemo, useRef } from "react";
import type { LogicalRange } from "lightweight-charts";

import { createChartAdapter, type ChartAdapter } from "../lib/chartAdapter";
import type { PersistedViewportState } from "../lib/inspectorPersistence";
import { EmaToolbar } from "./EmaToolbar";
import type {
  AnnotationToolbarPopover,
  AnnotationKind,
  AnnotationStyle,
  AnnotationTool,
  ChartAnnotation,
  ChartBar,
  ConfirmationGuide,
  EmaStyle,
  FloatingPosition,
  Overlay,
  OverlayLayer,
  RenderedEmaLine,
  SessionProfile,
} from "../lib/types";
import { AnnotationRail } from "./AnnotationRail";
import { AnnotationToolbar } from "./AnnotationToolbar";
import { OverlayCanvas } from "./OverlayCanvas";

export interface ChartPaneProps {
  bars: ChartBar[];
  displayBars: ChartBar[];
  emptyMessage?: string;
  emaLines: RenderedEmaLine[];
  overlays: Overlay[];
  annotations: ChartAnnotation[];
  annotationTool: AnnotationTool;
  sessionProfile: SessionProfile;
  enabledLayers: Record<OverlayLayer, boolean>;
  selectedOverlayId: string | null;
  selectedAnnotations: ChartAnnotation[];
  selectedAnnotationIds: string[];
  confirmationGuide: ConfirmationGuide | null;
  replayEnabled: boolean;
  replayCursorVisible: boolean;
  replayInteractionLocked: boolean;
  replayCursorSelectionEnabled: boolean;
  replayCursorBarId: number | null;
  annotationCount: number;
  annotationRailPosition: FloatingPosition;
  onAnnotationRailPositionChange: (position: FloatingPosition) => void;
  annotationToolbarPosition: FloatingPosition | null;
  onAnnotationToolbarPositionChange: (position: FloatingPosition | null) => void;
  annotationToolbarOpenPopover: AnnotationToolbarPopover;
  onAnnotationToolbarOpenPopoverChange: (
    popover: AnnotationToolbarPopover,
  ) => void;
  selectedEmaLine: RenderedEmaLine | null;
  emaToolbarPosition: FloatingPosition | null;
  onEmaToolbarPositionChange: (position: FloatingPosition | null) => void;
  emaToolbarOpenPopover: AnnotationToolbarPopover;
  onEmaToolbarOpenPopoverChange: (popover: AnnotationToolbarPopover) => void;
  onEmaStyleChange: (length: number, patch: Partial<EmaStyle>) => void;
  viewportFamilyKey: string;
  initialViewport: PersistedViewportState | null;
  onViewportStateChange: (viewport: PersistedViewportState | null) => void;
  onAnnotationCreate: (annotation: {
    kind: AnnotationKind;
    start: { bar_id: number; price: number };
    end: { bar_id: number; price: number };
    control?: { bar_id: number; price: number } | null;
  }) => void;
  onAnnotationSelect: (annotationIds: string[]) => void;
  onAnnotationUpdate: (
    annotationId: string,
    start: { bar_id: number; price: number },
    end: { bar_id: number; price: number },
    control: { bar_id: number; price: number } | null,
  ) => void;
  onAnnotationDuplicate: (annotationIds: string[]) => string[];
  onAnnotationStyleChange: (
    annotationIds: string[],
    patch: Partial<AnnotationStyle>,
  ) => void;
  onAnnotationToolChange: (tool: AnnotationTool) => void;
  onDeleteSelectedAnnotation: () => void;
  onClearAnnotations: () => void;
  onOverlaySelect: (
    overlay: Overlay | null,
    anchorPoint: { x: number; y: number } | null,
  ) => void;
  onOverlayCommandSelect: (overlay: Overlay) => void;
  onReplayCursorSelect: (barId: number) => void;
  onViewportBoundaryApproach: (centerBarId: number) => void;
}

export function ChartPane({
  bars,
  displayBars,
  emptyMessage,
  emaLines,
  overlays,
  annotations,
  annotationTool,
  sessionProfile,
  enabledLayers,
  selectedOverlayId,
  selectedAnnotations,
  selectedAnnotationIds,
  confirmationGuide,
  replayEnabled,
  replayCursorVisible,
  replayInteractionLocked,
  replayCursorSelectionEnabled,
  replayCursorBarId,
  annotationCount,
  annotationRailPosition,
  onAnnotationRailPositionChange,
  annotationToolbarPosition,
  onAnnotationToolbarPositionChange,
  annotationToolbarOpenPopover,
  onAnnotationToolbarOpenPopoverChange,
  selectedEmaLine,
  emaToolbarPosition,
  onEmaToolbarPositionChange,
  emaToolbarOpenPopover,
  onEmaToolbarOpenPopoverChange,
  onEmaStyleChange,
  viewportFamilyKey,
  initialViewport,
  onViewportStateChange,
  onAnnotationCreate,
  onAnnotationSelect,
  onAnnotationUpdate,
  onAnnotationDuplicate,
  onAnnotationStyleChange,
  onAnnotationToolChange,
  onDeleteSelectedAnnotation,
  onClearAnnotations,
  onOverlaySelect,
  onOverlayCommandSelect,
  onReplayCursorSelect,
  onViewportBoundaryApproach,
}: ChartPaneProps) {
  const shellRef = useRef<HTMLElement | null>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);
  const adapterRef = useRef<ChartAdapter | null>(null);
  const lastViewportCenterRef = useRef<number | null>(null);
  const barsRef = useRef<ChartBar[]>(bars);
  const onViewportBoundaryApproachRef = useRef(onViewportBoundaryApproach);
  const onViewportStateChangeRef = useRef(onViewportStateChange);
  const restoreViewportRef = useRef(initialViewport);
  const viewportFamilyKeyRef = useRef(viewportFamilyKey);
  const replayCursorSelectionEnabledRef = useRef(replayCursorSelectionEnabled);
  const replayCursorSelectionPriceScaleRef = useRef<{
    baseline: PersistedViewportState["priceScale"];
    locked: PersistedViewportState["priceScale"];
  } | null>(null);
  const replayCursorSelectionRestorePendingRef = useRef(false);

  useEffect(() => {
    onViewportBoundaryApproachRef.current = onViewportBoundaryApproach;
  }, [onViewportBoundaryApproach]);

  useEffect(() => {
    onViewportStateChangeRef.current = onViewportStateChange;
  }, [onViewportStateChange]);

  useEffect(() => {
    viewportFamilyKeyRef.current = viewportFamilyKey;
  }, [viewportFamilyKey]);

  useEffect(() => {
    restoreViewportRef.current = initialViewport;
  }, [viewportFamilyKey, initialViewport]);

  useEffect(() => {
    const adapter = adapterRef.current;
    const previouslyEnabled = replayCursorSelectionEnabledRef.current;
    replayCursorSelectionEnabledRef.current = replayCursorSelectionEnabled;
    if (!adapter || previouslyEnabled === replayCursorSelectionEnabled) {
      return;
    }
    if (replayCursorSelectionEnabled) {
      const baseline = adapter.getPriceScaleState();
      const locked =
        baseline !== null && baseline.from !== null && baseline.to !== null
          ? {
              autoScale: false,
              from: baseline.from,
              to: baseline.to,
            }
          : baseline;
      replayCursorSelectionPriceScaleRef.current = { baseline, locked };
      replayCursorSelectionRestorePendingRef.current = false;
      return;
    }
    replayCursorSelectionRestorePendingRef.current = true;
  }, [replayCursorSelectionEnabled]);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) {
      return;
    }
    const adapter = createChartAdapter(container);
    adapterRef.current = adapter;
    let pointerDrivenInteraction = false;
    let wheelPersistTimer: number | null = null;

    const publishViewportState = (rangeOverride?: { from: number; to: number } | null) => {
      const nextBars = barsRef.current;
      const range = rangeOverride ?? adapter.getVisibleLogicalRange();
      if (!range || nextBars.length === 0) {
        return;
      }
      const visibleCenterBarId = resolveVisibleCenterBarId(nextBars, range);
      if (visibleCenterBarId === null) {
        return;
      }
      onViewportStateChangeRef.current({
        familyKey: viewportFamilyKeyRef.current,
        centerBarId: visibleCenterBarId,
        span: Math.max(range.to - range.from, 1),
        priceScale: adapter.getPriceScaleState(),
      });
    };

    const onViewportChange = (range: { from: number; to: number } | null) => {
      const nextBars = barsRef.current;
      if (!range || nextBars.length === 0) {
        return;
      }
      publishViewportState(range);
      const from = Math.max(0, Math.floor(range.from));
      const to = Math.min(nextBars.length - 1, Math.ceil(range.to));
      const visibleSpan = Math.max(to - from, 0);
      if (visibleSpan >= Math.max(nextBars.length - 8, 0)) {
        return;
      }
      const threshold = Math.max(18, Math.floor(visibleSpan * 0.3));
      const nearLeft = from <= threshold;
      const nearRight = to >= nextBars.length - 1 - threshold;
      if (!nearLeft && !nearRight) {
        return;
      }
      const centerIndex = Math.min(
        nextBars.length - 1,
        Math.max(0, Math.round((from + to) / 2)),
      );
      const centerBarId = nextBars[centerIndex]?.bar_id ?? null;
      if (centerBarId === null || lastViewportCenterRef.current === centerBarId) {
        return;
      }
      lastViewportCenterRef.current = centerBarId;
      onViewportBoundaryApproachRef.current(centerBarId);
    };

    const scheduleViewportPersist = () => {
      window.requestAnimationFrame(() => {
        publishViewportState();
      });
    };

    const handlePointerDown = () => {
      pointerDrivenInteraction = true;
    };

    const handlePointerEnd = () => {
      if (!pointerDrivenInteraction) {
        return;
      }
      pointerDrivenInteraction = false;
      scheduleViewportPersist();
    };

    const handleWheel = () => {
      if (wheelPersistTimer !== null) {
        window.clearTimeout(wheelPersistTimer);
      }
      wheelPersistTimer = window.setTimeout(() => {
        wheelPersistTimer = null;
        scheduleViewportPersist();
      }, 160);
    };

    const handleDoubleClick = () => {
      scheduleViewportPersist();
    };

    const unsubscribeViewport = adapter.subscribeViewportChange(onViewportChange);
    const resizeObserver = new ResizeObserver((entries) => {
      const entry = entries[0];
      const width = Math.floor(entry.contentRect.width);
      const height = Math.floor(entry.contentRect.height);
      adapter.resize(width, height);
    });
    resizeObserver.observe(container);
    container.addEventListener("pointerdown", handlePointerDown);
    container.addEventListener("wheel", handleWheel, { passive: true });
    container.addEventListener("dblclick", handleDoubleClick);
    window.addEventListener("pointerup", handlePointerEnd);
    window.addEventListener("pointercancel", handlePointerEnd);

    return () => {
      if (wheelPersistTimer !== null) {
        window.clearTimeout(wheelPersistTimer);
      }
      unsubscribeViewport();
      resizeObserver.disconnect();
      container.removeEventListener("pointerdown", handlePointerDown);
      container.removeEventListener("wheel", handleWheel);
      container.removeEventListener("dblclick", handleDoubleClick);
      window.removeEventListener("pointerup", handlePointerEnd);
      window.removeEventListener("pointercancel", handlePointerEnd);
      adapter.destroy();
      adapterRef.current = null;
    };
  }, [viewportFamilyKey]);

  useEffect(() => {
    const adapter = adapterRef.current;
    const previousBars = barsRef.current;
    const previousRange = adapter?.getVisibleLogicalRange() ?? null;
    const previousCenterLogical =
      previousRange !== null ? (previousRange.from + previousRange.to) / 2 : null;
    const previousCenterTime = resolveVisibleCenterTime(previousBars, previousRange);
    const previousCenterBarId = resolveVisibleCenterBarId(previousBars, previousRange);
    const previousCenterIndex =
      previousCenterLogical !== null ? Math.round(previousCenterLogical) : null;
    const previousCenterOffset =
      previousCenterLogical !== null && previousCenterIndex !== null
        ? previousCenterLogical - previousCenterIndex
        : 0;
    const previousPriceScale = adapter?.getPriceScaleState() ?? null;
    const firstBarLoad = previousBars.length === 0;
    const restoreViewport = restoreViewportRef.current;
    const restoredRange =
      firstBarLoad &&
      restoreViewport?.familyKey === viewportFamilyKey &&
      restoreViewport.span > 0
        ? {
            from: -restoreViewport.span / 2,
            to: restoreViewport.span / 2,
          } as LogicalRange
        : previousRange;
    const restoredCenterTime =
      firstBarLoad && restoreViewport?.familyKey === viewportFamilyKey
        ? null
        : previousCenterTime;
    const restoredCenterBarId =
      firstBarLoad && restoreViewport?.familyKey === viewportFamilyKey
        ? restoreViewport.centerBarId
        : previousCenterBarId;
    let restoredPriceScale =
      firstBarLoad && restoreViewport?.familyKey === viewportFamilyKey
        ? restoreViewport.priceScale
        : previousPriceScale;
    if (replayCursorSelectionEnabled) {
      restoredPriceScale =
        replayCursorSelectionPriceScaleRef.current?.locked ?? restoredPriceScale;
      replayCursorSelectionRestorePendingRef.current = false;
    } else if (replayCursorSelectionRestorePendingRef.current) {
      restoredPriceScale =
        replayCursorSelectionPriceScaleRef.current?.baseline ?? restoredPriceScale;
      replayCursorSelectionRestorePendingRef.current = false;
      replayCursorSelectionPriceScaleRef.current = null;
    }
    adapter?.setBars(bars, emaLines, {
      displayBars,
      preserveLogicalRange: restoredRange,
      preserveAnchorTime: restoredCenterTime,
      preserveAnchorBarId: restoredCenterBarId,
      preserveAnchorOffset: firstBarLoad ? 0 : previousCenterOffset,
      preservePriceScale: restoredPriceScale,
    });
    const settledRange = adapter?.getVisibleLogicalRange() ?? null;
    const settledCenterBarId = resolveVisibleCenterBarId(bars, settledRange);
    if (settledRange && settledCenterBarId !== null) {
      onViewportStateChangeRef.current({
        familyKey: viewportFamilyKey,
        centerBarId: settledCenterBarId,
        span: Math.max(settledRange.to - settledRange.from, 1),
        priceScale: adapter?.getPriceScaleState() ?? null,
      });
    }
    barsRef.current = bars;
    lastViewportCenterRef.current = null;
  }, [bars, displayBars, emaLines, viewportFamilyKey, replayCursorSelectionEnabled]);

  const empty = useMemo(() => bars.length === 0, [bars.length]);

  return (
    <section className="chart-shell" ref={shellRef}>
      <div className="chart-surface" ref={containerRef}>
        <AnnotationRail
          annotationTool={annotationTool}
          annotationCount={annotationCount}
          hasSelection={selectedAnnotationIds.length > 0}
          initialPosition={annotationRailPosition}
          onPositionChange={onAnnotationRailPositionChange}
          onToolChange={onAnnotationToolChange}
          onDeleteSelected={onDeleteSelectedAnnotation}
          onClearAll={onClearAnnotations}
        />
        {empty ? (
          <div className="chart-empty">
            <p>{emptyMessage ?? "Load a chart window to start inspecting bars and overlays."}</p>
          </div>
        ) : null}
      </div>
      <AnnotationToolbar
        surfaceRef={containerRef}
        annotations={selectedAnnotations}
        initialPosition={annotationToolbarPosition}
        onPositionChange={onAnnotationToolbarPositionChange}
        initialOpenPopover={annotationToolbarOpenPopover}
        onOpenPopoverChange={onAnnotationToolbarOpenPopoverChange}
        onAnnotationStyleChange={onAnnotationStyleChange}
        onAnnotationDuplicate={onAnnotationDuplicate}
        onDeleteSelectedAnnotations={onDeleteSelectedAnnotation}
      />
      <EmaToolbar
        surfaceRef={containerRef}
        emaLine={selectedEmaLine}
        initialPosition={emaToolbarPosition}
        onPositionChange={onEmaToolbarPositionChange}
        initialOpenPopover={emaToolbarOpenPopover}
        onOpenPopoverChange={onEmaToolbarOpenPopoverChange}
        onEmaStyleChange={onEmaStyleChange}
      />
      <OverlayCanvas
        shellRef={shellRef}
        surfaceRef={containerRef}
        adapter={adapterRef.current}
        bars={bars}
        overlays={overlays}
        annotations={annotations}
        annotationTool={annotationTool}
        sessionProfile={sessionProfile}
        enabledLayers={enabledLayers}
        selectedOverlayId={selectedOverlayId}
        selectedAnnotationIds={selectedAnnotationIds}
        confirmationGuide={confirmationGuide}
        replayEnabled={replayEnabled}
        replayCursorVisible={replayCursorVisible}
        replayInteractionLocked={replayInteractionLocked}
        replayCursorSelectionEnabled={replayCursorSelectionEnabled}
        replayCursorBarId={replayCursorBarId}
        onAnnotationCreate={onAnnotationCreate}
        onAnnotationSelect={onAnnotationSelect}
        onAnnotationUpdate={onAnnotationUpdate}
        onAnnotationDuplicate={onAnnotationDuplicate}
        onOverlaySelect={onOverlaySelect}
        onOverlayCommandSelect={onOverlayCommandSelect}
        onReplayCursorSelect={onReplayCursorSelect}
      />
    </section>
  );
}

function resolveVisibleCenterTime(
  bars: ChartBar[],
  range: { from: number; to: number } | null,
): number | null {
  if (bars.length === 0 || !range) {
    return null;
  }
  const centerIndex = Math.max(
    0,
    Math.min(bars.length - 1, Math.round((range.from + range.to) / 2)),
  );
  return bars[centerIndex]?.time ?? null;
}

function resolveVisibleCenterBarId(
  bars: ChartBar[],
  range: { from: number; to: number } | null,
): number | null {
  if (bars.length === 0 || !range) {
    return null;
  }
  const centerIndex = Math.max(
    0,
    Math.min(bars.length - 1, Math.round((range.from + range.to) / 2)),
  );
  return bars[centerIndex]?.bar_id ?? null;
}
