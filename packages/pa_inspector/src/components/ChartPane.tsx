import { useEffect, useMemo, useRef, useState } from "react";
import type { LogicalRange } from "lightweight-charts";

import { createChartAdapter, type ChartAdapter } from "../lib/chartAdapter";
import type {
  AnnotationToolbarPopover,
  AnnotationKind,
  AnnotationStyle,
  AnnotationTool,
  ChartAnnotation,
  ChartBar,
  ConfirmationGuide,
  FloatingPosition,
  Overlay,
  OverlayLayer,
  SessionProfile,
} from "../lib/types";
import { AnnotationRail } from "./AnnotationRail";
import { AnnotationToolbar } from "./AnnotationToolbar";
import { OverlayCanvas } from "./OverlayCanvas";

export interface ChartPaneProps {
  bars: ChartBar[];
  overlays: Overlay[];
  annotations: ChartAnnotation[];
  annotationTool: AnnotationTool;
  sessionProfile: SessionProfile;
  enabledLayers: Record<OverlayLayer, boolean>;
  selectedOverlayId: string | null;
  selectedAnnotation: ChartAnnotation | null;
  selectedAnnotationId: string | null;
  confirmationGuide: ConfirmationGuide | null;
  annotationCount: number;
  annotationRailPosition: FloatingPosition;
  onAnnotationRailPositionChange: (position: FloatingPosition) => void;
  annotationToolbarPosition: FloatingPosition | null;
  onAnnotationToolbarPositionChange: (position: FloatingPosition | null) => void;
  annotationToolbarOpenPopover: AnnotationToolbarPopover;
  onAnnotationToolbarOpenPopoverChange: (
    popover: AnnotationToolbarPopover,
  ) => void;
  viewportFamilyKey: string;
  initialViewport: { familyKey: string; centerBarId: number; span: number } | null;
  onViewportStateChange: (
    viewport: { familyKey: string; centerBarId: number; span: number } | null,
  ) => void;
  onAnnotationCreate: (annotation: {
    kind: AnnotationKind;
    start: { bar_id: number; price: number };
    end: { bar_id: number; price: number };
  }) => void;
  onAnnotationSelect: (annotationId: string | null) => void;
  onAnnotationUpdate: (
    annotationId: string,
    start: { bar_id: number; price: number },
    end: { bar_id: number; price: number },
  ) => void;
  onAnnotationDuplicate: (annotationId: string) => string | null;
  onAnnotationStyleChange: (
    annotationId: string,
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
  onViewportBoundaryApproach: (centerBarId: number) => void;
}

export function ChartPane({
  bars,
  overlays,
  annotations,
  annotationTool,
  sessionProfile,
  enabledLayers,
  selectedOverlayId,
  selectedAnnotation,
  selectedAnnotationId,
  confirmationGuide,
  annotationCount,
  annotationRailPosition,
  onAnnotationRailPositionChange,
  annotationToolbarPosition,
  onAnnotationToolbarPositionChange,
  annotationToolbarOpenPopover,
  onAnnotationToolbarOpenPopoverChange,
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
  const [size, setSize] = useState({ width: 0, height: 0 });
  const [viewportRevision, setViewportRevision] = useState(0);

  useEffect(() => {
    onViewportBoundaryApproachRef.current = onViewportBoundaryApproach;
  }, [onViewportBoundaryApproach]);

  useEffect(() => {
    onViewportStateChangeRef.current = onViewportStateChange;
  }, [onViewportStateChange]);

  useEffect(() => {
    restoreViewportRef.current = initialViewport;
  }, [viewportFamilyKey, initialViewport]);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) {
      return;
    }
    const adapter = createChartAdapter(container);
    adapterRef.current = adapter;
    setSize({ width: container.clientWidth, height: container.clientHeight });

    const onViewportChange = (range: { from: number; to: number } | null) => {
      const nextBars = barsRef.current;
      setViewportRevision((value) => value + 1);
      if (!range || nextBars.length === 0) {
        return;
      }
      const visibleCenterBarId = resolveVisibleCenterBarId(nextBars, range);
      const span = Math.max(range.to - range.from, 1);
      if (visibleCenterBarId !== null) {
        onViewportStateChangeRef.current({
          familyKey: viewportFamilyKey,
          centerBarId: visibleCenterBarId,
          span,
        });
      }
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
    const unsubscribeViewport = adapter.subscribeViewportChange(onViewportChange);
    const unsubscribePresentation = adapter.subscribePresentationChange(() => {
      setViewportRevision((value) => value + 1);
    });
    const resizeObserver = new ResizeObserver((entries) => {
      const entry = entries[0];
      const width = Math.floor(entry.contentRect.width);
      const height = Math.floor(entry.contentRect.height);
      adapter.resize(width, height);
      setSize({ width, height });
      setViewportRevision((value) => value + 1);
    });
    resizeObserver.observe(container);

    return () => {
      unsubscribeViewport();
      unsubscribePresentation();
      resizeObserver.disconnect();
      adapter.destroy();
      adapterRef.current = null;
    };
  }, [viewportFamilyKey]);

  useEffect(() => {
    const adapter = adapterRef.current;
    const previousBars = barsRef.current;
    const previousRange = adapter?.getVisibleLogicalRange() ?? null;
    const previousCenterTime = resolveVisibleCenterTime(previousBars, previousRange);
    const previousCenterBarId = resolveVisibleCenterBarId(previousBars, previousRange);
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
    adapter?.setBars(bars, {
      preserveLogicalRange: restoredRange,
      preserveAnchorTime: restoredCenterTime,
      preserveAnchorBarId: restoredCenterBarId,
    });
    const settledRange = adapter?.getVisibleLogicalRange() ?? null;
    const settledCenterBarId = resolveVisibleCenterBarId(bars, settledRange);
    if (settledRange && settledCenterBarId !== null) {
      onViewportStateChangeRef.current({
        familyKey: viewportFamilyKey,
        centerBarId: settledCenterBarId,
        span: Math.max(settledRange.to - settledRange.from, 1),
      });
    }
    barsRef.current = bars;
    lastViewportCenterRef.current = null;
    setViewportRevision((value) => value + 1);
  }, [bars, viewportFamilyKey]);

  const empty = useMemo(() => bars.length === 0, [bars.length]);

  return (
    <section className="chart-shell" ref={shellRef}>
      <div className="chart-surface" ref={containerRef}>
        <AnnotationRail
          annotationTool={annotationTool}
          annotationCount={annotationCount}
          hasSelection={selectedAnnotationId !== null}
          initialPosition={annotationRailPosition}
          onPositionChange={onAnnotationRailPositionChange}
          onToolChange={onAnnotationToolChange}
          onDeleteSelected={onDeleteSelectedAnnotation}
          onClearAll={onClearAnnotations}
        />
        {empty ? (
          <div className="chart-empty">
            <p>Load a chart window to start inspecting bars and overlays.</p>
          </div>
        ) : null}
      </div>
      <AnnotationToolbar
        hostRef={shellRef}
        surfaceRef={containerRef}
        annotation={selectedAnnotation}
        initialPosition={annotationToolbarPosition}
        onPositionChange={onAnnotationToolbarPositionChange}
        initialOpenPopover={annotationToolbarOpenPopover}
        onOpenPopoverChange={onAnnotationToolbarOpenPopoverChange}
        onAnnotationStyleChange={onAnnotationStyleChange}
        onAnnotationDuplicate={onAnnotationDuplicate}
        onDeleteSelectedAnnotation={onDeleteSelectedAnnotation}
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
        selectedAnnotationId={selectedAnnotationId}
        confirmationGuide={confirmationGuide}
        viewportRevision={viewportRevision}
        onAnnotationCreate={onAnnotationCreate}
        onAnnotationSelect={onAnnotationSelect}
        onAnnotationUpdate={onAnnotationUpdate}
        onOverlaySelect={onOverlaySelect}
        onOverlayCommandSelect={onOverlayCommandSelect}
      />
      <div className="chart-footnote">
        Pan and zoom freely. Turn on auto fetch when you want edge-triggered window extension.
      </div>
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
