import { useEffect, useMemo, useRef, useState } from "react";

import { createChartAdapter, type ChartAdapter } from "../lib/chartAdapter";
import type { ChartBar, Overlay, OverlayLayer } from "../lib/types";
import { OverlayCanvas } from "./OverlayCanvas";

export interface ChartPaneProps {
  bars: ChartBar[];
  overlays: Overlay[];
  enabledLayers: Record<OverlayLayer, boolean>;
  selectedOverlayId: string | null;
  onOverlaySelect: (
    overlay: Overlay | null,
    anchorPoint: { x: number; y: number } | null,
  ) => void;
  onViewportBoundaryApproach: (centerBarId: number) => void;
}

export function ChartPane({
  bars,
  overlays,
  enabledLayers,
  selectedOverlayId,
  onOverlaySelect,
  onViewportBoundaryApproach,
}: ChartPaneProps) {
  const shellRef = useRef<HTMLElement | null>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);
  const adapterRef = useRef<ChartAdapter | null>(null);
  const lastViewportCenterRef = useRef<number | null>(null);
  const barsRef = useRef<ChartBar[]>(bars);
  const onViewportBoundaryApproachRef = useRef(onViewportBoundaryApproach);
  const [size, setSize] = useState({ width: 0, height: 0 });
  const [viewportRevision, setViewportRevision] = useState(0);

  useEffect(() => {
    onViewportBoundaryApproachRef.current = onViewportBoundaryApproach;
  }, [onViewportBoundaryApproach]);

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
      resizeObserver.disconnect();
      adapter.destroy();
      adapterRef.current = null;
    };
  }, []);

  useEffect(() => {
    const adapter = adapterRef.current;
    const previousBars = barsRef.current;
    const previousRange = adapter?.getVisibleLogicalRange() ?? null;
    const previousCenterTime = resolveVisibleCenterTime(previousBars, previousRange);
    adapter?.setBars(bars, {
      preserveLogicalRange: previousRange,
      preserveAnchorTime: previousCenterTime,
    });
    barsRef.current = bars;
    lastViewportCenterRef.current = null;
    setViewportRevision((value) => value + 1);
  }, [bars]);

  const empty = useMemo(() => bars.length === 0, [bars.length]);

  return (
    <section className="chart-shell" ref={shellRef}>
      <div className="chart-header">
        <div>
          <p className="eyebrow">Explore</p>
          <h2>Continuous Structure View</h2>
        </div>
        <p className="chart-meta">
          {bars.length
            ? `${bars[0].session_date} -> ${bars[bars.length - 1].session_date} · ${bars.length} bars`
            : "No window loaded"}
        </p>
      </div>
      <div className="chart-surface" ref={containerRef}>
        {empty ? (
          <div className="chart-empty">
            <p>Load a chart window to start inspecting bars and overlays.</p>
          </div>
        ) : null}
        <OverlayCanvas
          shellRef={shellRef}
          adapter={adapterRef.current}
          width={size.width}
          height={size.height}
          bars={bars}
          overlays={overlays}
          enabledLayers={enabledLayers}
          selectedOverlayId={selectedOverlayId}
          viewportRevision={viewportRevision}
          onOverlaySelect={onOverlaySelect}
        />
      </div>
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
