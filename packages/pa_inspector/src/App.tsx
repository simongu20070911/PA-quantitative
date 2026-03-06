import { startTransition, useEffect, useMemo, useRef, useState } from "react";

import { ChartPane } from "./components/ChartPane";
import { InspectorPanel } from "./components/InspectorPanel";
import { Toolbar } from "./components/Toolbar";
import { fetchChartWindow, fetchStructureDetail } from "./lib/api";
import type {
  ChartWindowResponse,
  Overlay,
  OverlayLayer,
  SelectorMode,
  SessionProfile,
  StructureDetailResponse,
} from "./lib/types";

const DEFAULT_API_BASE =
  import.meta.env.VITE_API_BASE_URL?.trim() || "/api";
const DEFAULT_DATA_VERSION =
  import.meta.env.VITE_DEFAULT_DATA_VERSION?.trim() ||
  "es_1m_v1_4f3eda8a678d3c41";

const INITIAL_LAYERS: Record<OverlayLayer, boolean> = {
  pivot: true,
  leg: true,
  major_lh: true,
  breakout_start: true,
};
const ALL_LAYERS = Object.keys(INITIAL_LAYERS) as OverlayLayer[];
const EMPTY_LAYER_COUNTS: Record<OverlayLayer, number> = {
  pivot: 0,
  leg: 0,
  major_lh: 0,
  breakout_start: 0,
};

export default function App() {
  const windowCacheRef = useRef<Map<string, ChartWindowResponse>>(new Map());
  const inFlightRef = useRef<Map<string, Promise<ChartWindowResponse>>>(new Map());
  const lastAutoCenterRef = useRef<number | null>(null);
  const [apiBaseUrl, setApiBaseUrl] = useState(DEFAULT_API_BASE);
  const [dataVersion, setDataVersion] = useState(DEFAULT_DATA_VERSION);
  const [symbol, setSymbol] = useState("ES");
  const [timeframe, setTimeframe] = useState("1m");
  const [sessionProfile, setSessionProfile] = useState<SessionProfile>("eth_full");
  const [selectorMode, setSelectorMode] = useState<SelectorMode>("session_date");
  const [sessionDate, setSessionDate] = useState("20251117");
  const [centerBarId, setCenterBarId] = useState("29390399");
  const [startTime, setStartTime] = useState("");
  const [endTime, setEndTime] = useState("");
  const [leftBars, setLeftBars] = useState("240");
  const [rightBars, setRightBars] = useState("240");
  const [bufferBars, setBufferBars] = useState("120");
  const [autoViewportFetch, setAutoViewportFetch] = useState(false);
  const [overlayLayers, setOverlayLayers] =
    useState<Record<OverlayLayer, boolean>>(INITIAL_LAYERS);
  const [windowData, setWindowData] = useState<ChartWindowResponse | null>(null);
  const [windowLoading, setWindowLoading] = useState(false);
  const [windowError, setWindowError] = useState<string | null>(null);
  const [selectedOverlay, setSelectedOverlay] = useState<Overlay | null>(null);
  const [detailAnchor, setDetailAnchor] = useState<{ x: number; y: number } | null>(null);
  const [detailData, setDetailData] = useState<StructureDetailResponse | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState<string | null>(null);

  const visibleOverlays = useMemo(() => {
    if (!windowData) {
      return [];
    }
    return windowData.overlays.filter((overlay) => {
      if (overlay.kind === "pivot-marker") {
        return overlayLayers.pivot;
      }
      if (overlay.kind === "leg-line") {
        return overlayLayers.leg;
      }
      if (overlay.kind === "major-lh-marker") {
        return overlayLayers.major_lh;
      }
      return overlayLayers.breakout_start;
    });
  }, [overlayLayers, windowData]);

  const overlayLayerCounts = useMemo(() => {
    if (!windowData) {
      return EMPTY_LAYER_COUNTS;
    }
    const counts = { ...EMPTY_LAYER_COUNTS };
    for (const overlay of windowData.overlays) {
      if (overlay.kind === "pivot-marker") {
        counts.pivot += 1;
      } else if (overlay.kind === "leg-line") {
        counts.leg += 1;
      } else if (overlay.kind === "major-lh-marker") {
        counts.major_lh += 1;
      } else if (overlay.kind === "breakout-marker") {
        counts.breakout_start += 1;
      }
    }
    return counts;
  }, [windowData]);

  useEffect(() => {
    void loadWindow();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    lastAutoCenterRef.current = null;
  }, [dataVersion, selectorMode, sessionDate, centerBarId, startTime, endTime, sessionProfile, timeframe]);

  useEffect(() => {
    clearSelection();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionProfile, timeframe]);

  useEffect(() => {
    if (!selectedOverlay) {
      setDetailData(null);
      setDetailError(null);
      setDetailLoading(false);
      return;
    }
    let active = true;
    setDetailLoading(true);
    setDetailError(null);
    void fetchStructureDetail({
      apiBaseUrl,
      structureId: selectedOverlay.source_structure_id,
      symbol,
      timeframe,
      sessionProfile,
      dataVersion,
    })
      .then((detail) => {
        if (!active) {
          return;
        }
        startTransition(() => {
          setDetailData(detail);
          setDetailLoading(false);
        });
      })
      .catch((error: unknown) => {
        if (!active) {
          return;
        }
        setDetailData(null);
        setDetailLoading(false);
        setDetailError(error instanceof Error ? error.message : "Failed to load detail.");
      });
    return () => {
      active = false;
    };
  }, [apiBaseUrl, dataVersion, selectedOverlay, sessionProfile, symbol, timeframe]);

  async function loadWindow() {
    await requestWindow({ source: "manual" });
  }

  async function requestWindow(args?: {
    source?: "manual" | "viewport";
    selectorMode?: SelectorMode;
    centerBarId?: string;
    sessionDate?: string;
    startTime?: string;
    endTime?: string;
  }) {
    const request = buildWindowRequest(args);
    const cacheKey = buildWindowCacheKey(request);
    setWindowLoading(true);
    setWindowError(null);
    try {
      const response = await getOrFetchWindow(cacheKey, request);
      startTransition(() => {
        setWindowData(response);
        setWindowLoading(false);
        setSelectedOverlay(null);
        setDetailAnchor(null);
        setDetailData(null);
        setDetailError(null);
        setDetailLoading(false);
        if (args?.selectorMode === "center_bar_id" && args.centerBarId) {
          setSelectorMode("center_bar_id");
          setCenterBarId(args.centerBarId);
        } else if (args?.selectorMode === "session_date" && args.sessionDate) {
          setSelectorMode("session_date");
          setSessionDate(args.sessionDate);
        } else if (
          args?.selectorMode === "time_range" &&
          args.startTime &&
          args.endTime
        ) {
          setSelectorMode("time_range");
          setStartTime(args.startTime);
          setEndTime(args.endTime);
        }
      });
      void prefetchAdjacentWindows(response);
    } catch (error) {
      setWindowLoading(false);
      setWindowError(
        error instanceof Error ? error.message : "Failed to load chart window.",
      );
    }
  }

  function buildWindowRequest(args?: {
    selectorMode?: SelectorMode;
    centerBarId?: string;
    sessionDate?: string;
    startTime?: string;
    endTime?: string;
  }) {
    return {
      apiBaseUrl,
      symbol,
      timeframe,
      sessionProfile,
      dataVersion,
      selectorMode: args?.selectorMode ?? selectorMode,
      sessionDate: args?.sessionDate ?? sessionDate,
      centerBarId: args?.centerBarId ?? centerBarId,
      startTime: args?.startTime ?? startTime,
      endTime: args?.endTime ?? endTime,
      leftBars: Number(leftBars || 0),
      rightBars: Number(rightBars || 0),
      bufferBars: Number(bufferBars || 0),
      overlayLayers: ALL_LAYERS,
    };
  }

  async function getOrFetchWindow(
    cacheKey: string,
    request: Parameters<typeof fetchChartWindow>[0],
  ) {
    const cached = windowCacheRef.current.get(cacheKey);
    if (cached) {
      return cached;
    }
    const inFlight = inFlightRef.current.get(cacheKey);
    if (inFlight) {
      return inFlight;
    }
    const fetchPromise = fetchChartWindow(request)
      .then((response) => {
        windowCacheRef.current.set(cacheKey, response);
        inFlightRef.current.delete(cacheKey);
        return response;
      })
      .catch((error) => {
        inFlightRef.current.delete(cacheKey);
        throw error;
      });
    inFlightRef.current.set(cacheKey, fetchPromise);
    return fetchPromise;
  }

  async function prefetchAdjacentWindows(response: ChartWindowResponse) {
    if (response.bars.length < 2) {
      return;
    }
    const firstBarId = response.bars[0]?.bar_id;
    const lastBarId = response.bars[response.bars.length - 1]?.bar_id;
    if (typeof firstBarId !== "number" || typeof lastBarId !== "number") {
      return;
    }
    const requests = [String(firstBarId), String(lastBarId)]
      .filter((value, index, array) => array.indexOf(value) === index)
      .map((value) =>
        buildWindowRequest({
          selectorMode: "center_bar_id",
          centerBarId: value,
        }),
      );

    await Promise.all(
      requests.map(async (request) => {
        const key = buildWindowCacheKey(request);
        if (windowCacheRef.current.has(key) || inFlightRef.current.has(key)) {
          return;
        }
        try {
          await getOrFetchWindow(key, request);
        } catch (error) {
          console.warn("Prefetch failed", error);
        }
      }),
    );
  }

  function handleViewportBoundaryApproach(nextCenterBarId: number) {
    if (!autoViewportFetch || windowLoading || !windowData) {
      return;
    }
    if (lastAutoCenterRef.current === nextCenterBarId) {
      return;
    }
    lastAutoCenterRef.current = nextCenterBarId;
    void requestWindow({
      source: "viewport",
      selectorMode: "center_bar_id",
      centerBarId: String(nextCenterBarId),
    });
  }

  function clearSelection() {
    setSelectedOverlay(null);
    setDetailAnchor(null);
    setDetailData(null);
    setDetailError(null);
    setDetailLoading(false);
  }

  return (
    <div className="app-shell">
      <div className="backdrop-orbit orbit-a" />
      <div className="backdrop-orbit orbit-b" />
      <Toolbar
        apiBaseUrl={apiBaseUrl}
        onApiBaseUrlChange={setApiBaseUrl}
        dataVersion={dataVersion}
        onDataVersionChange={setDataVersion}
        symbol={symbol}
        timeframe={timeframe}
        sessionProfile={sessionProfile}
        onSymbolChange={setSymbol}
        onTimeframeChange={setTimeframe}
        onSessionProfileChange={setSessionProfile}
        selectorMode={selectorMode}
        onSelectorModeChange={setSelectorMode}
        sessionDate={sessionDate}
        centerBarId={centerBarId}
        startTime={startTime}
        endTime={endTime}
        onSessionDateChange={setSessionDate}
        onCenterBarIdChange={setCenterBarId}
        onStartTimeChange={setStartTime}
        onEndTimeChange={setEndTime}
        leftBars={leftBars}
        rightBars={rightBars}
        bufferBars={bufferBars}
        onLeftBarsChange={setLeftBars}
        onRightBarsChange={setRightBars}
        onBufferBarsChange={setBufferBars}
        autoViewportFetch={autoViewportFetch}
        onAutoViewportFetchChange={setAutoViewportFetch}
        overlayLayerCounts={overlayLayerCounts}
        overlayLayers={overlayLayers}
        onOverlayLayerChange={(layer, enabled) => {
          setOverlayLayers((current) => ({ ...current, [layer]: enabled }));
          if (selectedOverlay) {
            const selectedLayer =
              selectedOverlay.kind === "pivot-marker"
                ? "pivot"
                : selectedOverlay.kind === "leg-line"
                  ? "leg"
                  : selectedOverlay.kind === "major-lh-marker"
                    ? "major_lh"
                    : "breakout_start";
            if (selectedLayer === layer && !enabled) {
              clearSelection();
            }
          }
        }}
        loading={windowLoading}
        onLoad={() => {
          void loadWindow();
        }}
      />

      <div className="workspace-main">
        {windowError ? <p className="panel-error floating-error">{windowError}</p> : null}
        <div className="chart-stage">
          <ChartPane
            bars={windowData?.bars ?? []}
            overlays={visibleOverlays}
            enabledLayers={overlayLayers}
            selectedOverlayId={selectedOverlay?.overlay_id ?? null}
            onOverlaySelect={(overlay, anchorPoint) => {
              setSelectedOverlay(overlay);
              setDetailAnchor(anchorPoint);
            }}
            onViewportBoundaryApproach={handleViewportBoundaryApproach}
          />
          <InspectorPanel
            overlay={selectedOverlay}
            anchorPoint={detailAnchor}
            detail={detailData}
            loading={detailLoading}
            error={detailError}
            onClose={clearSelection}
          />
        </div>
        <section className="status-strip">
          <div>
            <p className="eyebrow">Window Status</p>
            <strong>
              {windowData
                ? `${windowData.bars.length} bars · ${visibleOverlays.length} visible overlays`
                : "No window"}
            </strong>
          </div>
          <div className="status-meta">
            {windowData ? (
              <>
                <span>{windowCacheRef.current.size} cached</span>
                <span>{windowData.meta.data_version}</span>
                <span>{windowData.meta.rulebook_version}</span>
                <span>{windowData.meta.overlay_version}</span>
              </>
            ) : null}
          </div>
        </section>
      </div>
    </div>
  );
}

function buildWindowCacheKey(request: Parameters<typeof fetchChartWindow>[0]) {
  return JSON.stringify({
    apiBaseUrl: request.apiBaseUrl,
    symbol: request.symbol,
    timeframe: request.timeframe,
    dataVersion: request.dataVersion,
    selectorMode: request.selectorMode,
    centerBarId: request.centerBarId,
    sessionDate: request.sessionDate,
    startTime: request.startTime,
    endTime: request.endTime,
    sessionProfile: request.sessionProfile,
    leftBars: request.leftBars,
    rightBars: request.rightBars,
    bufferBars: request.bufferBars,
    overlayLayers: request.overlayLayers,
  });
}
