import {
  CandlestickSeries,
  ColorType,
  CrosshairMode,
  LineStyle,
  createChart,
  type IChartApi,
  type ISeriesApi,
  type LogicalRange,
  type MouseEventParams,
  type Time,
} from "lightweight-charts";

import { InspectorPrimitive } from "./inspectorPrimitive";
import type { InspectorPrimitiveState } from "./inspectorScene";
import type { ChartBar } from "./types";

export interface ChartAdapter {
  chart: IChartApi;
  series: ISeriesApi<"Candlestick", Time>;
  resize: (width: number, height: number) => void;
  setBars: (
    bars: ChartBar[],
    options?: {
      preserveLogicalRange?: LogicalRange | null;
      preserveAnchorTime?: number | null;
      preserveAnchorBarId?: number | null;
    },
  ) => void;
  timeToCoordinate: (time: number) => number | null;
  priceToCoordinate: (price: number) => number | null;
  coordinateToPrice: (coordinate: number) => number | null;
  coordinateToLogical: (coordinate: number) => number | null;
  getVisibleLogicalRange: () => LogicalRange | null;
  subscribeViewportChange: (callback: (range: LogicalRange | null) => void) => () => void;
  subscribePresentationChange: (callback: () => void) => () => void;
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
  const presentationCallbacks = new Set<() => void>();
  const notifyPresentationChange = () => {
    presentationCallbacks.forEach((callback) => callback());
  };
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
      rightOffset: 6,
      barSpacing: 8,
      minBarSpacing: 3,
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
      // Keep chart-surface interactions close to TradingView defaults:
      // wheel zooms the time scale, pinch zooms on touch devices, and
      // axis drags rescale along their respective dimensions.
      mouseWheel: true,
      pinch: true,
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
  series.attachPrimitive(inspectorPrimitive);

  const detachPriceAxisWheelZoom = attachPriceAxisWheelZoom(
    container,
    chart,
    series,
    notifyPresentationChange,
  );

  return {
    chart,
    series,
    resize(width: number, height: number) {
      chart.applyOptions({ width, height });
    },
    setBars(bars: ChartBar[], options) {
      series.setData(
        bars.map((bar) => ({
          time: bar.time as Time,
          open: bar.open,
          high: bar.high,
          low: bar.low,
          close: bar.close,
        })),
      );
      if (bars.length === 0) {
        return;
      }

      const previousRange = options?.preserveLogicalRange ?? null;
      const preserveAnchorTime = options?.preserveAnchorTime ?? null;
      const preserveAnchorBarId = options?.preserveAnchorBarId ?? null;
      if (previousRange && (preserveAnchorBarId !== null || preserveAnchorTime !== null)) {
        const anchorIndex =
          preserveAnchorBarId !== null
            ? bars.findIndex((bar) => bar.bar_id === preserveAnchorBarId)
            : bars.findIndex((bar) => bar.time === preserveAnchorTime);
        if (anchorIndex >= 0) {
          const span = Math.max(previousRange.to - previousRange.from, 1);
          const halfSpan = span / 2;
          const targetRange = {
            from: anchorIndex - halfSpan,
            to: anchorIndex + halfSpan,
          };
          chart.timeScale().setVisibleLogicalRange(targetRange);
          window.requestAnimationFrame(() => {
            chart.timeScale().setVisibleLogicalRange(targetRange);
          });
          return;
        }
      }

      if (chart.timeScale().getVisibleLogicalRange() === null) {
        chart.timeScale().setVisibleLogicalRange({
          from: -0.5,
          to: Math.max(bars.length - 0.5, 1),
        });
      }
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
    subscribeViewportChange(callback) {
      const onRange = (range: LogicalRange | null) => {
        callback(range);
      };
      chart.timeScale().subscribeVisibleLogicalRangeChange(onRange);
      return () => {
        chart.timeScale().unsubscribeVisibleLogicalRangeChange(onRange);
      };
    },
    subscribePresentationChange(callback) {
      presentationCallbacks.add(callback);
      return () => {
        presentationCallbacks.delete(callback);
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
      detachPriceAxisWheelZoom();
      series.detachPrimitive(inspectorPrimitive);
      chart.remove();
    },
  };
}

function attachPriceAxisWheelZoom(
  container: HTMLDivElement,
  chart: IChartApi,
  series: ISeriesApi<"Candlestick", Time>,
  notifyPresentationChange: () => void,
) {
  let mouseWheelEnabled = true;
  let priceAxisDragActive = false;
  let rafId: number | null = null;

  const stopPriceAxisDragLoop = () => {
    priceAxisDragActive = false;
    if (rafId !== null) {
      window.cancelAnimationFrame(rafId);
      rafId = null;
    }
  };

  const startPriceAxisDragLoop = () => {
    if (priceAxisDragActive) {
      return;
    }
    priceAxisDragActive = true;
    const tick = () => {
      if (!priceAxisDragActive) {
        rafId = null;
        return;
      }
      notifyPresentationChange();
      rafId = window.requestAnimationFrame(tick);
    };
    rafId = window.requestAnimationFrame(tick);
  };

  const updateMouseWheelMode = (event: PointerEvent | MouseEvent) => {
    const overPriceAxis = isOverRightPriceAxis(container, chart, event.clientX, event.clientY);
    const nextEnabled = !overPriceAxis;
    if (mouseWheelEnabled === nextEnabled) {
      return;
    }
    mouseWheelEnabled = nextEnabled;
    chart.applyOptions({
      handleScale: {
        mouseWheel: nextEnabled,
      },
    });
  };

  const handleWheel = (event: WheelEvent) => {
    if (!event.cancelable) {
      return;
    }

    if (!isOverRightPriceAxis(container, chart, event.clientX, event.clientY)) {
      return;
    }

    const rect = container.getBoundingClientRect();
    const localY = event.clientY - rect.top;
    const priceScale = chart.priceScale("right");
    const anchorPrice = series.coordinateToPrice(localY);
    const visibleRange = priceScale.getVisibleRange();
    if (anchorPrice === null || visibleRange === null) {
      return;
    }

    event.preventDefault();
    event.stopPropagation();
    event.stopImmediatePropagation();

    const normalizedDelta = normalizeWheelDelta(event);
    if (normalizedDelta === 0) {
      return;
    }

    const zoomFactor = Math.exp(normalizedDelta * 0.0025);
    const nextFrom = anchorPrice - (anchorPrice - visibleRange.from) * zoomFactor;
    const nextTo = anchorPrice + (visibleRange.to - anchorPrice) * zoomFactor;
    const nextSpan = nextTo - nextFrom;
    if (!Number.isFinite(nextFrom) || !Number.isFinite(nextTo) || nextSpan <= 1e-6) {
      return;
    }

    priceScale.setAutoScale(false);
    priceScale.setVisibleRange({ from: nextFrom, to: nextTo });
    notifyPresentationChange();
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
    if (!mouseWheelEnabled) {
      mouseWheelEnabled = true;
      chart.applyOptions({
        handleScale: {
          mouseWheel: true,
        },
      });
    }
  };

  container.addEventListener("pointermove", updateMouseWheelMode);
  container.addEventListener("mousemove", updateMouseWheelMode);
  container.addEventListener("pointerdown", handlePointerDown);
  window.addEventListener("pointerup", handlePointerUp);
  window.addEventListener("pointercancel", handlePointerUp);
  container.addEventListener("pointerleave", handlePointerLeave);
  container.addEventListener("mouseleave", handlePointerLeave);
  container.addEventListener("wheel", handleWheel, { passive: false, capture: true });
  return () => {
    stopPriceAxisDragLoop();
    container.removeEventListener("pointermove", updateMouseWheelMode);
    container.removeEventListener("mousemove", updateMouseWheelMode);
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

function normalizeWheelDelta(event: WheelEvent): number {
  const pageScale = window.innerHeight || 800;
  if (event.deltaMode === WheelEvent.DOM_DELTA_LINE) {
    return event.deltaY * 16;
  }
  if (event.deltaMode === WheelEvent.DOM_DELTA_PAGE) {
    return event.deltaY * pageScale;
  }
  return event.deltaY;
}
