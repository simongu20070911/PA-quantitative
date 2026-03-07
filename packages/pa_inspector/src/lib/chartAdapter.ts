import {
  CandlestickSeries,
  ColorType,
  CrosshairMode,
  LineSeries,
  LineStyle,
  createChart,
  type IChartApi,
  type ISeriesApi,
  type LogicalRange,
  type MouseEventParams,
  type Time,
} from "lightweight-charts";

import { colorWithOpacity } from "./annotationStyle";
import { InspectorPrimitive } from "./inspectorPrimitive";
import type { InspectorPrimitiveState, InspectorRenderData } from "./inspectorScene";
import type { ChartBar, EmaLineStyle, RenderedEmaLine } from "./types";

const TIME_SCALE_MIN_BAR_SPACING = 3;
const TIME_SCALE_DEFAULT_BAR_SPACING = 8;
const TIME_SCALE_DEFAULT_RIGHT_OFFSET = 6;
const MAX_ZOOM_OUT_EPSILON = 0.01;

export interface ChartAdapter {
  chart: IChartApi;
  series: ISeriesApi<"Candlestick", Time>;
  resize: (width: number, height: number) => void;
    setBars: (
      bars: ChartBar[],
      emaLines: RenderedEmaLine[],
    options?: {
      preserveLogicalRange?: LogicalRange | null;
      preserveAnchorTime?: number | null;
      preserveAnchorBarId?: number | null;
      preserveAnchorOffset?: number;
    },
  ) => void;
  timeToCoordinate: (time: number) => number | null;
  priceToCoordinate: (price: number) => number | null;
  coordinateToPrice: (coordinate: number) => number | null;
  coordinateToLogical: (coordinate: number) => number | null;
  getVisibleLogicalRange: () => LogicalRange | null;
  getInspectorRenderData: () => InspectorRenderData;
  subscribeViewportChange: (callback: (range: LogicalRange | null) => void) => () => void;
  subscribeClick: (
    callback: (param: MouseEventParams<Time>) => void,
  ) => () => void;
  subscribeCrosshairMove: (
    callback: (param: MouseEventParams<Time>) => void,
  ) => () => void;
  setInspectorPrimitiveState: (state: InspectorPrimitiveState) => void;
  destroy: () => void;
}

export function createChartAdapter(container: HTMLDivElement): ChartAdapter {
  const chart = createChart(container, {
    autoSize: false,
    width: container.clientWidth,
    height: container.clientHeight,
    layout: {
      background: { type: ColorType.Solid, color: "#ffffff" },
      textColor: "#6b7280",
      attributionLogo: false,
    },
    localization: {
      locale: "en-US",
    },
    grid: {
      vertLines: { color: "rgba(0, 0, 0, 0)" },
      horzLines: { color: "rgba(0, 0, 0, 0)" },
    },
    rightPriceScale: {
      borderVisible: true,
      borderColor: "rgba(226, 232, 240, 0.95)",
      scaleMargins: { top: 0.04, bottom: 0.05 },
    },
    timeScale: {
      borderVisible: true,
      borderColor: "rgba(226, 232, 240, 0.95)",
      rightOffset: TIME_SCALE_DEFAULT_RIGHT_OFFSET,
      barSpacing: TIME_SCALE_DEFAULT_BAR_SPACING,
      minBarSpacing: TIME_SCALE_MIN_BAR_SPACING,
      rightBarStaysOnScroll: true,
      lockVisibleTimeRangeOnResize: true,
      timeVisible: true,
      secondsVisible: false,
      ticksVisible: true,
    },
    crosshair: {
      mode: CrosshairMode.Normal,
      vertLine: {
        visible: false,
        color: "rgba(148, 163, 184, 0.55)",
        width: 1,
        style: LineStyle.LargeDashed,
      },
      horzLine: {
        visible: false,
        color: "rgba(148, 163, 184, 0.45)",
        width: 1,
        style: LineStyle.LargeDashed,
      },
    },
    handleScale: {
      // Keep axis-drag and pinch behavior chart-native, but route wheel/trackpad
      // gestures ourselves so horizontal swipes pan and vertical deltas zoom.
      mouseWheel: false,
      pinch: false,
      axisPressedMouseMove: { time: true, price: true },
      axisDoubleClickReset: { time: true, price: true },
    },
    handleScroll: {
      mouseWheel: false,
      pressedMouseMove: true,
      horzTouchDrag: true,
      vertTouchDrag: true,
    },
  });

  const series = chart.addSeries(CandlestickSeries, {
    upColor: "#ffffff",
    downColor: "#f23645",
    wickUpColor: "#089981",
    wickDownColor: "#f23645",
    borderVisible: true,
    borderUpColor: "#089981",
    borderDownColor: "#f23645",
    priceLineVisible: true,
    priceLineColor: "#9ca3af",
    lastValueVisible: true,
  });
  const inspectorPrimitive = new InspectorPrimitive();
  const emaSeriesByLength = new Map<number, ISeriesApi<"Line", Time>>();
  series.attachPrimitive(inspectorPrimitive);
  const refreshInspectorRenderData = () => {
    inspectorPrimitive.refresh();
  };
  const handleVisibleLogicalRangeChange = () => {
    refreshInspectorRenderData();
  };
  chart.timeScale().subscribeVisibleLogicalRangeChange(handleVisibleLogicalRangeChange);

  const detachWheelGestures = attachWheelGestures(
    container,
    chart,
    series,
    refreshInspectorRenderData,
  );

  return {
    chart,
    series,
    resize(width: number, height: number) {
      chart.applyOptions({ width, height });
      refreshInspectorRenderData();
    },
    setBars(bars: ChartBar[], emaLines: RenderedEmaLine[], options) {
      series.setData(
        bars.map((bar) => ({
          time: bar.time as Time,
          open: bar.open,
          high: bar.high,
          low: bar.low,
          close: bar.close,
        })),
      );
      syncEmaSeries(chart, emaSeriesByLength, emaLines);
      if (bars.length === 0) {
        refreshInspectorRenderData();
        return;
      }

      const previousRange = options?.preserveLogicalRange ?? null;
      const preserveAnchorTime = options?.preserveAnchorTime ?? null;
      const preserveAnchorBarId = options?.preserveAnchorBarId ?? null;
      const preserveAnchorOffset = options?.preserveAnchorOffset ?? 0;
      if (previousRange && (preserveAnchorBarId !== null || preserveAnchorTime !== null)) {
        const anchorIndex =
          preserveAnchorBarId !== null
            ? bars.findIndex((bar) => bar.bar_id === preserveAnchorBarId)
            : bars.findIndex((bar) => bar.time === preserveAnchorTime);
        if (anchorIndex >= 0) {
          const span = Math.max(previousRange.to - previousRange.from, 1);
          const halfSpan = span / 2;
          const anchoredCenter = anchorIndex + preserveAnchorOffset;
          const targetRange = {
            from: anchoredCenter - halfSpan,
            to: anchoredCenter + halfSpan,
          };
          chart.timeScale().setVisibleLogicalRange(targetRange);
          window.requestAnimationFrame(() => {
            chart.timeScale().setVisibleLogicalRange(targetRange);
          });
          refreshInspectorRenderData();
          return;
        }
      }

      if (chart.timeScale().getVisibleLogicalRange() === null) {
        chart.timeScale().setVisibleLogicalRange({
          from: -0.5,
          to: Math.max(bars.length - 0.5, 1),
        });
      }
      refreshInspectorRenderData();
    },
    timeToCoordinate(time: number) {
      return chart.timeScale().timeToCoordinate(time as Time);
    },
    priceToCoordinate(price: number) {
      return series.priceToCoordinate(price);
    },
    coordinateToPrice(coordinate: number) {
      return series.coordinateToPrice(coordinate);
    },
    coordinateToLogical(coordinate: number) {
      const logical = chart.timeScale().coordinateToLogical(coordinate);
      return logical === null ? null : Number(logical);
    },
    getVisibleLogicalRange() {
      return chart.timeScale().getVisibleLogicalRange();
    },
    getInspectorRenderData() {
      return inspectorPrimitive.getRenderData();
    },
    subscribeViewportChange(callback) {
      const onRange = (range: LogicalRange | null) => {
        callback(range);
      };
      chart.timeScale().subscribeVisibleLogicalRangeChange(onRange);
      return () => {
        chart.timeScale().unsubscribeVisibleLogicalRangeChange(onRange);
      };
    },
    subscribeClick(callback) {
      chart.subscribeClick(callback);
      return () => {
        chart.unsubscribeClick(callback);
      };
    },
    subscribeCrosshairMove(callback) {
      chart.subscribeCrosshairMove(callback);
      return () => {
        chart.unsubscribeCrosshairMove(callback);
      };
    },
    setInspectorPrimitiveState(state) {
      inspectorPrimitive.setState(state);
    },
    destroy() {
      detachWheelGestures();
      for (const emaSeries of emaSeriesByLength.values()) {
        chart.removeSeries(emaSeries);
      }
      emaSeriesByLength.clear();
      series.detachPrimitive(inspectorPrimitive);
      chart.timeScale().unsubscribeVisibleLogicalRangeChange(handleVisibleLogicalRangeChange);
      chart.remove();
    },
  };
}

function syncEmaSeries(
  chart: IChartApi,
  emaSeriesByLength: Map<number, ISeriesApi<"Line", Time>>,
  emaLines: RenderedEmaLine[],
) {
  const visibleLines = emaLines.filter((line) => line.style.visible);
  const activeLengths = new Set(visibleLines.map((line) => line.length));
  for (const [length, series] of emaSeriesByLength.entries()) {
    if (activeLengths.has(length)) {
      continue;
    }
    chart.removeSeries(series);
    emaSeriesByLength.delete(length);
  }

  for (const line of visibleLines) {
    let emaSeries = emaSeriesByLength.get(line.length);
    if (!emaSeries) {
      emaSeries = chart.addSeries(LineSeries, resolveEmaSeriesOptions(line));
      emaSeriesByLength.set(line.length, emaSeries);
    }
    emaSeries.applyOptions(resolveEmaSeriesOptions(line));
    emaSeries.setData(
      line.points.map((point) => ({
        time: point.time as Time,
        value: point.value,
      })),
    );
  }
}

function resolveEmaSeriesOptions(line: RenderedEmaLine) {
  return {
    color: colorWithOpacity(line.style.strokeColor, line.style.opacity),
    lineWidth: Math.min(Math.max((line.selected ? line.style.lineWidth + 1 : line.style.lineWidth), 1), 4) as 1 | 2 | 3 | 4,
    lineStyle: resolveLineStyle(line.style.lineStyle),
    lineVisible: line.style.visible,
    lastValueVisible: line.selected,
    priceLineVisible: false,
    crosshairMarkerVisible: false,
    lastPriceAnimation: 0 as const,
  };
}

function resolveLineStyle(style: EmaLineStyle) {
  if (style === "dashed") {
    return LineStyle.Dashed;
  }
  if (style === "dotted") {
    return LineStyle.Dotted;
  }
  return LineStyle.Solid;
}

function attachWheelGestures(
  container: HTMLDivElement,
  chart: IChartApi,
  series: ISeriesApi<"Candlestick", Time>,
  notifyPresentationChange: () => void,
) {
  const axisDominanceRatio = 1.35;
  let priceAxisDragActive = false;
  let dragRafId: number | null = null;
  let wheelRafId: number | null = null;
  let pendingPanDelta = 0;
  let pendingZoomDelta = 0;
  let pendingZoomAnchorX = 0;
  let pendingZoomSamples = 0;

  const stopPriceAxisDragLoop = () => {
    priceAxisDragActive = false;
    if (dragRafId !== null) {
      window.cancelAnimationFrame(dragRafId);
      dragRafId = null;
    }
  };

  const startPriceAxisDragLoop = () => {
    if (priceAxisDragActive) {
      return;
    }
    priceAxisDragActive = true;
    const tick = () => {
      if (!priceAxisDragActive) {
        dragRafId = null;
        return;
      }
      notifyPresentationChange();
      dragRafId = window.requestAnimationFrame(tick);
    };
    dragRafId = window.requestAnimationFrame(tick);
  };

  const flushPendingWheelGesture = () => {
    wheelRafId = null;
    if (pendingPanDelta === 0 && pendingZoomDelta === 0) {
      return;
    }

    const visibleRange = chart.timeScale().getVisibleLogicalRange();
    if (visibleRange === null) {
      pendingPanDelta = 0;
      pendingZoomDelta = 0;
      pendingZoomAnchorX = 0;
      pendingZoomSamples = 0;
      return;
    }

    const plotWidth = getMainPlotWidth(container, chart);
    if (plotWidth <= 0) {
      pendingPanDelta = 0;
      pendingZoomDelta = 0;
      pendingZoomAnchorX = 0;
      pendingZoomSamples = 0;
      return;
    }

    let nextRange = {
      from: Number(visibleRange.from),
      to: Number(visibleRange.to),
    };
    let anchorLogical =
      resolveLogicalAtX(chart, pendingZoomAnchorX / Math.max(pendingZoomSamples, 1)) ??
      (nextRange.from + nextRange.to) / 2;
    if (pendingPanDelta !== 0) {
      const span = Math.max(nextRange.to - nextRange.from, 1);
      const logicalShift = (pendingPanDelta * span * 0.65) / plotWidth;
      nextRange = {
        from: nextRange.from + logicalShift,
        to: nextRange.to + logicalShift,
      };
      anchorLogical += logicalShift;
    }
    if (pendingZoomDelta !== 0) {
      nextRange = zoomLogicalRange(
        nextRange,
        anchorLogical,
        pendingZoomDelta,
        plotWidth / TIME_SCALE_MIN_BAR_SPACING,
      );
    }

    pendingPanDelta = 0;
    pendingZoomDelta = 0;
    pendingZoomAnchorX = 0;
    pendingZoomSamples = 0;

    const nextSpan = nextRange.to - nextRange.from;
    if (!Number.isFinite(nextRange.from) || !Number.isFinite(nextRange.to) || nextSpan <= 0) {
      return;
    }

    chart.timeScale().setVisibleLogicalRange(nextRange);
    notifyPresentationChange();
  };

  const scheduleWheelGesture = () => {
    if (wheelRafId !== null) {
      return;
    }
    wheelRafId = window.requestAnimationFrame(flushPendingWheelGesture);
  };

  const handlePlotWheel = (event: WheelEvent) => {
    const rect = container.getBoundingClientRect();
    const localX = clamp(event.clientX - rect.left, 0, getMainPlotWidth(container, chart));
    const rawDeltaX = event.ctrlKey ? 0 : normalizeWheelDelta(event.deltaX, event.deltaMode);
    const rawDeltaY = normalizeWheelDelta(event.deltaY, event.deltaMode);
    const absDeltaX = Math.abs(rawDeltaX);
    const absDeltaY = Math.abs(rawDeltaY);
    let normalizedDeltaX = 0;
    let normalizedDeltaY = 0;

    if (event.ctrlKey) {
      normalizedDeltaY = rawDeltaY !== 0 ? rawDeltaY : rawDeltaX;
    } else if (absDeltaX > absDeltaY * axisDominanceRatio) {
      normalizedDeltaX = rawDeltaX;
    } else {
      normalizedDeltaY = rawDeltaY;
    }

    if (normalizedDeltaX === 0 && normalizedDeltaY === 0) {
      return;
    }

    pendingPanDelta += normalizedDeltaX;
    pendingZoomDelta += normalizedDeltaY;
    pendingZoomAnchorX += localX;
    pendingZoomSamples += 1;
    scheduleWheelGesture();
  };

  const handleWheel = (event: WheelEvent) => {
    if (!event.cancelable) {
      return;
    }

    if (isChartUiTarget(event.target)) {
      consumeWheelEvent(event);
      return;
    }

    consumeWheelEvent(event);

    if (event.ctrlKey) {
      return;
    }

    if (isOverRightPriceAxis(container, chart, event.clientX, event.clientY)) {
      const rect = container.getBoundingClientRect();
      const localY = clamp(
        event.clientY - rect.top,
        0,
        Math.max(rect.height - chart.timeScale().height(), 0),
      );
      const priceScale = chart.priceScale("right");
      const anchorPrice = series.coordinateToPrice(localY);
      const visibleRange = priceScale.getVisibleRange();
      if (anchorPrice === null || visibleRange === null) {
        return;
      }

      const normalizedDelta = normalizeWheelDelta(
        event.deltaY !== 0 ? event.deltaY : event.deltaX,
        event.deltaMode,
      );
      if (normalizedDelta === 0) {
        return;
      }

      const zoomFactor = Math.exp(normalizedDelta * 0.0007);
      const nextFrom = anchorPrice - (anchorPrice - visibleRange.from) * zoomFactor;
      const nextTo = anchorPrice + (visibleRange.to - anchorPrice) * zoomFactor;
      const nextSpan = nextTo - nextFrom;
      if (!Number.isFinite(nextFrom) || !Number.isFinite(nextTo) || nextSpan <= 1e-6) {
        return;
      }

      priceScale.setAutoScale(false);
      priceScale.setVisibleRange({ from: nextFrom, to: nextTo });
      notifyPresentationChange();
      return;
    }

    handlePlotWheel(event);
  };

  const handlePointerDown = (event: PointerEvent) => {
    if (event.button !== 0) {
      return;
    }
    if (!isOverRightPriceAxis(container, chart, event.clientX, event.clientY)) {
      return;
    }
    startPriceAxisDragLoop();
  };

  const handlePointerUp = () => {
    stopPriceAxisDragLoop();
  };

  const handlePointerLeave = () => {
    stopPriceAxisDragLoop();
    if (wheelRafId !== null) {
      window.cancelAnimationFrame(wheelRafId);
      wheelRafId = null;
    }
    pendingPanDelta = 0;
    pendingZoomDelta = 0;
    pendingZoomAnchorX = 0;
    pendingZoomSamples = 0;
  };

  container.addEventListener("pointerdown", handlePointerDown);
  window.addEventListener("pointerup", handlePointerUp);
  window.addEventListener("pointercancel", handlePointerUp);
  container.addEventListener("pointerleave", handlePointerLeave);
  container.addEventListener("mouseleave", handlePointerLeave);
  container.addEventListener("wheel", handleWheel, { passive: false, capture: true });
  return () => {
    stopPriceAxisDragLoop();
    if (wheelRafId !== null) {
      window.cancelAnimationFrame(wheelRafId);
    }
    container.removeEventListener("pointerdown", handlePointerDown);
    window.removeEventListener("pointerup", handlePointerUp);
    window.removeEventListener("pointercancel", handlePointerUp);
    container.removeEventListener("pointerleave", handlePointerLeave);
    container.removeEventListener("mouseleave", handlePointerLeave);
    container.removeEventListener("wheel", handleWheel, true);
  };
}

function isOverRightPriceAxis(
  container: HTMLDivElement,
  chart: IChartApi,
  clientX: number,
  clientY: number,
): boolean {
  const rect = container.getBoundingClientRect();
  const localX = clientX - rect.left;
  const localY = clientY - rect.top;
  const priceScaleWidth = chart.priceScale("right").width();
  const timeScaleHeight = chart.timeScale().height();
  const pricePaneHeight = Math.max(rect.height - timeScaleHeight, 0);

  return !(
    priceScaleWidth <= 0 ||
    localX < rect.width - priceScaleWidth ||
    localX > rect.width ||
    localY < 0 ||
    localY > pricePaneHeight
  );
}

function consumeWheelEvent(event: WheelEvent) {
  event.preventDefault();
  event.stopPropagation();
  event.stopImmediatePropagation();
}

function isChartUiTarget(target: EventTarget | null): boolean {
  return target instanceof Element && target.closest(".annotation-rail") !== null;
}

function getMainPlotWidth(container: HTMLDivElement, chart: IChartApi): number {
  const plotWidth = container.clientWidth - chart.priceScale("right").width();
  return Math.max(plotWidth, 0);
}

function resolveLogicalAtX(chart: IChartApi, x: number): number | null {
  const logical = chart.timeScale().coordinateToLogical(x);
  return logical === null ? null : Number(logical);
}

function zoomLogicalRange(
  range: { from: number; to: number },
  anchorLogical: number,
  delta: number,
  maxSpan: number,
) {
  const currentSpan = range.to - range.from;
  if (delta > 0 && currentSpan >= maxSpan - MAX_ZOOM_OUT_EPSILON) {
    return range;
  }

  const zoomFactor = Math.exp(delta * 0.0025);
  const nextFrom = anchorLogical - (anchorLogical - range.from) * zoomFactor;
  const nextTo = anchorLogical + (range.to - anchorLogical) * zoomFactor;
  const nextSpan = nextTo - nextFrom;
  if (!Number.isFinite(nextFrom) || !Number.isFinite(nextTo) || nextSpan <= 1e-6) {
    return range;
  }
  if (delta > 0 && nextSpan >= maxSpan) {
    return range;
  }
  return { from: nextFrom, to: nextTo };
}

function normalizeWheelDelta(delta: number, deltaMode: number): number {
  const pageScale = window.innerHeight || 800;
  if (deltaMode === WheelEvent.DOM_DELTA_LINE) {
    return delta * 16;
  }
  if (deltaMode === WheelEvent.DOM_DELTA_PAGE) {
    return delta * pageScale;
  }
  return delta;
}

function clamp(value: number, min: number, max: number) {
  return Math.max(min, Math.min(max, value));
}
