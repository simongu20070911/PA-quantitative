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
    },
  ) => void;
  timeToCoordinate: (time: number) => number | null;
  priceToCoordinate: (price: number) => number | null;
  getVisibleLogicalRange: () => LogicalRange | null;
  subscribeViewportChange: (callback: (range: LogicalRange | null) => void) => () => void;
  subscribeClick: (
    callback: (param: MouseEventParams<Time>) => void,
  ) => () => void;
  subscribeCrosshairMove: (
    callback: (param: MouseEventParams<Time>) => void,
  ) => () => void;
  destroy: () => void;
}

export function createChartAdapter(container: HTMLDivElement): ChartAdapter {
  const chart = createChart(container, {
    autoSize: false,
    width: container.clientWidth,
    height: container.clientHeight,
    layout: {
      background: { type: ColorType.Solid, color: "#f6f7f9" },
      textColor: "#4b525e",
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
      borderVisible: false,
      scaleMargins: { top: 0.04, bottom: 0.05 },
    },
    timeScale: {
      borderVisible: false,
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
        color: "rgba(126, 191, 181, 0.48)",
        width: 1,
        style: LineStyle.LargeDashed,
      },
      horzLine: {
        color: "rgba(126, 191, 181, 0.42)",
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
    upColor: "rgba(255, 255, 255, 0.98)",
    downColor: "#eb534f",
    wickUpColor: "#80c6bb",
    wickDownColor: "#f07c78",
    borderVisible: true,
    borderUpColor: "#80c6bb",
    borderDownColor: "#eb534f",
    priceLineVisible: true,
    priceLineColor: "#69c2b5",
    lastValueVisible: true,
  });

  const detachPriceAxisWheelZoom = attachPriceAxisWheelZoom(container, chart, series);

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
      if (previousRange && preserveAnchorTime !== null) {
        const anchorIndex = bars.findIndex((bar) => bar.time === preserveAnchorTime);
        if (anchorIndex >= 0) {
          const span = Math.max(previousRange.to - previousRange.from, 1);
          const halfSpan = span / 2;
          chart.timeScale().setVisibleLogicalRange({
            from: anchorIndex - halfSpan,
            to: anchorIndex + halfSpan,
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
    destroy() {
      detachPriceAxisWheelZoom();
      chart.remove();
    },
  };
}

function attachPriceAxisWheelZoom(
  container: HTMLDivElement,
  chart: IChartApi,
  series: ISeriesApi<"Candlestick", Time>,
) {
  let mouseWheelEnabled = true;

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
  };

  const handlePointerLeave = () => {
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
  container.addEventListener("pointerleave", handlePointerLeave);
  container.addEventListener("mouseleave", handlePointerLeave);
  container.addEventListener("wheel", handleWheel, { passive: false, capture: true });
  return () => {
    container.removeEventListener("pointermove", updateMouseWheelMode);
    container.removeEventListener("mousemove", updateMouseWheelMode);
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
