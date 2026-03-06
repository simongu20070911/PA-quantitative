import { startTransition, useEffect, useMemo, useRef, useState } from "react";

import { ChartPane } from "./components/ChartPane";
import { InspectorPanel } from "./components/InspectorPanel";
import { Toolbar } from "./components/Toolbar";
import { fetchChartWindow, fetchStructureDetail } from "./lib/api";
import { defaultAnnotationStyle } from "./lib/annotationStyle";
import {
  loadPersistedInspectorState,
  savePersistedInspectorState,
  type PersistedInspectorState,
} from "./lib/inspectorPersistence";
import type {
  AnnotationKind,
  AnnotationStyle,
  AnnotationToolbarPopover,
  AnnotationTool,
  ChartAnnotation,
  ConfirmationGuide,
  ChartWindowResponse,
  FloatingPosition,
  InspectorToolbarPanel,
  Overlay,
  OverlayLayer,
  ScreenPoint,
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
const DEFAULT_RAIL_POSITION: FloatingPosition = { left: 12, top: 12 };
const DEFAULT_PANEL_POSITION: FloatingPosition = { left: 24, top: 24 };

export default function App() {
  const windowCacheRef = useRef<Map<string, ChartWindowResponse>>(new Map());
  const inFlightRef = useRef<Map<string, Promise<ChartWindowResponse>>>(new Map());
  const lastAutoCenterRef = useRef<number | null>(null);
  const [initialState] = useState<PersistedInspectorState>(() =>
    loadPersistedInspectorState({
      apiBaseUrl: DEFAULT_API_BASE,
      dataVersion: DEFAULT_DATA_VERSION,
      symbol: "ES",
      timeframe: "1m",
      sessionProfile: "eth_full",
      selectorMode: "session_date",
      sessionDate: "20251117",
      centerBarId: "29390399",
      startTime: "",
      endTime: "",
      leftBars: "240",
      rightBars: "240",
      bufferBars: "120",
      autoViewportFetch: false,
      overlayLayers: INITIAL_LAYERS,
      annotations: [],
      annotationTool: "none",
      selectedAnnotationId: null,
      selectedOverlayId: null,
      detailAnchor: null,
      confirmationGuide: null,
      toolbarOpenPanel: null,
      annotationRailPosition: DEFAULT_RAIL_POSITION,
      annotationToolbarPosition: null,
      annotationToolbarOpenPopover: null,
      inspectorPanelPosition: DEFAULT_PANEL_POSITION,
      inspectorPanelManualPosition: false,
      viewport: null,
    }),
  );
  const viewportStateRef = useRef(initialState.viewport);
  const viewportPersistTimerRef = useRef<number | null>(null);
  const [apiBaseUrl, setApiBaseUrl] = useState(initialState.apiBaseUrl);
  const [dataVersion, setDataVersion] = useState(initialState.dataVersion);
  const [symbol, setSymbol] = useState(initialState.symbol);
  const [timeframe, setTimeframe] = useState(initialState.timeframe);
  const [sessionProfile, setSessionProfile] =
    useState<SessionProfile>(initialState.sessionProfile);
  const [selectorMode, setSelectorMode] =
    useState<SelectorMode>(initialState.selectorMode);
  const [sessionDate, setSessionDate] = useState(initialState.sessionDate);
  const [centerBarId, setCenterBarId] = useState(initialState.centerBarId);
  const [startTime, setStartTime] = useState(initialState.startTime);
  const [endTime, setEndTime] = useState(initialState.endTime);
  const [leftBars, setLeftBars] = useState(initialState.leftBars);
  const [rightBars, setRightBars] = useState(initialState.rightBars);
  const [bufferBars, setBufferBars] = useState(initialState.bufferBars);
  const [autoViewportFetch, setAutoViewportFetch] =
    useState(initialState.autoViewportFetch);
  const [overlayLayers, setOverlayLayers] =
    useState<Record<OverlayLayer, boolean>>(initialState.overlayLayers);
  const [windowData, setWindowData] = useState<ChartWindowResponse | null>(null);
  const [windowLoading, setWindowLoading] = useState(false);
  const [windowError, setWindowError] = useState<string | null>(null);
  const [selectedOverlayId, setSelectedOverlayId] = useState<string | null>(
    initialState.selectedOverlayId,
  );
  const [detailAnchor, setDetailAnchor] = useState<ScreenPoint | null>(
    initialState.detailAnchor,
  );
  const [detailData, setDetailData] = useState<StructureDetailResponse | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [annotationTool, setAnnotationTool] = useState<AnnotationTool>(
    initialState.annotationTool,
  );
  const [annotations, setAnnotations] = useState<ChartAnnotation[]>(
    initialState.annotations,
  );
  const [selectedAnnotationId, setSelectedAnnotationId] = useState<string | null>(
    initialState.selectedAnnotationId,
  );
  const [confirmationGuide, setConfirmationGuide] = useState<ConfirmationGuide | null>(
    initialState.confirmationGuide,
  );
  const [toolbarOpenPanel, setToolbarOpenPanel] = useState<InspectorToolbarPanel>(
    initialState.toolbarOpenPanel,
  );
  const [annotationRailPosition, setAnnotationRailPosition] = useState<FloatingPosition>(
    initialState.annotationRailPosition,
  );
  const [annotationToolbarPosition, setAnnotationToolbarPosition] =
    useState<FloatingPosition | null>(initialState.annotationToolbarPosition);
  const [annotationToolbarOpenPopover, setAnnotationToolbarOpenPopover] =
    useState<AnnotationToolbarPopover>(initialState.annotationToolbarOpenPopover);
  const [inspectorPanelPosition, setInspectorPanelPosition] =
    useState<FloatingPosition>(initialState.inspectorPanelPosition);
  const [inspectorPanelManualPosition, setInspectorPanelManualPosition] =
    useState(initialState.inspectorPanelManualPosition);
  const [viewportPersistRevision, setViewportPersistRevision] = useState(0);

  const activeFamilyKey = useMemo(
    () => buildAnnotationFamilyKey({ dataVersion, sessionProfile, timeframe }),
    [dataVersion, sessionProfile, timeframe],
  );

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

  const visibleAnnotations = useMemo(
    () => annotations.filter((annotation) => annotation.familyKey === activeFamilyKey),
    [activeFamilyKey, annotations],
  );
  const selectedAnnotation = useMemo(
    () =>
      visibleAnnotations.find((annotation) => annotation.id === selectedAnnotationId) ?? null,
    [selectedAnnotationId, visibleAnnotations],
  );
  const selectedOverlay = useMemo(
    () =>
      windowData?.overlays.find((overlay) => overlay.overlay_id === selectedOverlayId) ?? null,
    [selectedOverlayId, windowData],
  );

  useEffect(() => {
    void loadWindow("restore");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    lastAutoCenterRef.current = null;
  }, [dataVersion, selectorMode, sessionDate, centerBarId, startTime, endTime, sessionProfile, timeframe]);

  useEffect(() => {
    clearChartSelection();
    setConfirmationGuide(null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionProfile, timeframe]);

  useEffect(() => {
    if (!selectedAnnotationId) {
      return;
    }
    if (!visibleAnnotations.some((annotation) => annotation.id === selectedAnnotationId)) {
      setSelectedAnnotationId(null);
    }
  }, [selectedAnnotationId, visibleAnnotations]);

  useEffect(() => {
    if (!selectedAnnotationId) {
      return;
    }

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key !== "Delete" && event.key !== "Backspace") {
        return;
      }
      const target = event.target;
      if (
        target instanceof HTMLInputElement ||
        target instanceof HTMLTextAreaElement ||
        target instanceof HTMLSelectElement ||
        (target instanceof HTMLElement && target.isContentEditable)
      ) {
        return;
      }
      event.preventDefault();
      deleteSelectedAnnotation();
    };

    window.addEventListener("keydown", onKeyDown);
    return () => {
      window.removeEventListener("keydown", onKeyDown);
    };
  }, [selectedAnnotationId]);

  useEffect(() => {
    return () => {
      if (viewportPersistTimerRef.current !== null) {
        window.clearTimeout(viewportPersistTimerRef.current);
      }
    };
  }, []);

  useEffect(() => {
    savePersistedInspectorState({
      apiBaseUrl,
      dataVersion,
      symbol,
      timeframe,
      sessionProfile,
      selectorMode,
      sessionDate,
      centerBarId,
      startTime,
      endTime,
      leftBars,
      rightBars,
      bufferBars,
      autoViewportFetch,
      overlayLayers,
      annotations,
      annotationTool,
      selectedAnnotationId,
      selectedOverlayId,
      detailAnchor,
      confirmationGuide,
      toolbarOpenPanel,
      annotationRailPosition,
      annotationToolbarPosition,
      annotationToolbarOpenPopover,
      inspectorPanelPosition,
      inspectorPanelManualPosition,
      viewport: viewportStateRef.current,
    });
  }, [
    annotations,
    annotationRailPosition,
    annotationTool,
    annotationToolbarOpenPopover,
    annotationToolbarPosition,
    apiBaseUrl,
    autoViewportFetch,
    bufferBars,
    centerBarId,
    confirmationGuide,
    dataVersion,
    detailAnchor,
    endTime,
    inspectorPanelManualPosition,
    inspectorPanelPosition,
    leftBars,
    overlayLayers,
    rightBars,
    selectorMode,
    selectedAnnotationId,
    selectedOverlayId,
    sessionDate,
    sessionProfile,
    startTime,
    symbol,
    timeframe,
    toolbarOpenPanel,
    viewportPersistRevision,
  ]);

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

  async function loadWindow(source: "manual" | "restore" = "manual") {
    if (
      source === "restore" &&
      viewportStateRef.current?.familyKey === activeFamilyKey
    ) {
      await requestWindow({
        source,
        selectorMode: "center_bar_id",
        centerBarId: String(viewportStateRef.current.centerBarId),
      });
      return;
    }
    await requestWindow({ source });
  }

  async function requestWindow(args?: {
    source?: "manual" | "viewport" | "restore";
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
        if (args?.source !== "restore") {
          setSelectedOverlayId(null);
          setDetailAnchor(null);
          setDetailData(null);
          setDetailError(null);
          setDetailLoading(false);
          setSelectedAnnotationId(null);
          setConfirmationGuide(null);
        }
        if (args?.source !== "restore" && args?.selectorMode === "center_bar_id" && args.centerBarId) {
          setSelectorMode("center_bar_id");
          setCenterBarId(args.centerBarId);
        } else if (args?.source !== "restore" && args?.selectorMode === "session_date" && args.sessionDate) {
          setSelectorMode("session_date");
          setSessionDate(args.sessionDate);
        } else if (
          args?.source !== "restore" &&
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

  function clearOverlaySelection() {
    setSelectedOverlayId(null);
    setDetailAnchor(null);
    setDetailData(null);
    setDetailError(null);
    setDetailLoading(false);
    setInspectorPanelManualPosition(false);
  }

  function clearChartSelection() {
    clearOverlaySelection();
    setSelectedAnnotationId(null);
  }

  function deleteSelectedAnnotation() {
    if (!selectedAnnotationId) {
      return;
    }
    setAnnotations((current) =>
      current.filter((annotation) => annotation.id !== selectedAnnotationId),
    );
    setSelectedAnnotationId(null);
  }

  function duplicateAnnotation(annotationId: string) {
    const source = annotations.find((annotation) => annotation.id === annotationId);
    if (!source) {
      return null;
    }
    const duplicateId = buildAnnotationId(
      source.kind,
      source.start.bar_id,
      source.end.bar_id,
    );
    const duplicate: ChartAnnotation = {
      ...source,
      id: duplicateId,
    };
    setAnnotations((current) => [...current, duplicate]);
    setSelectedAnnotationId(duplicateId);
    return duplicateId;
  }

  function patchAnnotationStyle(
    annotationId: string,
    patch: Partial<AnnotationStyle>,
  ) {
    setAnnotations((current) =>
      current.map((annotation) =>
        annotation.id === annotationId
          ? {
              ...annotation,
              style: {
                ...annotation.style,
                ...patch,
              },
            }
          : annotation,
      ),
    );
  }

  async function handleOverlayCommandSelect(overlay: Overlay) {
    if (confirmationGuide?.sourceStructureId === overlay.source_structure_id) {
      setConfirmationGuide(null);
      return;
    }
    clearOverlaySelection();
    setSelectedAnnotationId(null);
    try {
      const detail = await fetchStructureDetail({
        apiBaseUrl,
        structureId: overlay.source_structure_id,
        symbol,
        timeframe,
        sessionProfile,
        dataVersion,
      });
      if (!detail.confirm_bar) {
        setConfirmationGuide(null);
        return;
      }
      setConfirmationGuide({
        sourceStructureId: overlay.source_structure_id,
        confirmBarId: detail.confirm_bar.bar_id,
        confirmPrice: detail.confirm_bar.close,
      });
    } catch (error) {
      console.warn("Failed to load confirmation guide", error);
      setConfirmationGuide(null);
    }
  }

  return (
    <div className="app-shell">
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
        initialOpenPanel={toolbarOpenPanel}
        onOpenPanelChange={setToolbarOpenPanel}
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
              clearOverlaySelection();
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
            annotations={visibleAnnotations}
            annotationTool={annotationTool}
            sessionProfile={windowData?.meta.session_profile ?? sessionProfile}
            enabledLayers={overlayLayers}
            selectedOverlayId={selectedOverlayId}
            selectedAnnotation={selectedAnnotation}
            selectedAnnotationId={selectedAnnotationId}
            confirmationGuide={confirmationGuide}
            annotationCount={visibleAnnotations.length}
            annotationRailPosition={annotationRailPosition}
            onAnnotationRailPositionChange={setAnnotationRailPosition}
            annotationToolbarPosition={annotationToolbarPosition}
            onAnnotationToolbarPositionChange={setAnnotationToolbarPosition}
            annotationToolbarOpenPopover={annotationToolbarOpenPopover}
            onAnnotationToolbarOpenPopoverChange={setAnnotationToolbarOpenPopover}
            viewportFamilyKey={activeFamilyKey}
            initialViewport={viewportStateRef.current}
            onViewportStateChange={(nextViewport) => {
              viewportStateRef.current = nextViewport;
              if (viewportPersistTimerRef.current !== null) {
                window.clearTimeout(viewportPersistTimerRef.current);
              }
              viewportPersistTimerRef.current = window.setTimeout(() => {
                setViewportPersistRevision((value) => value + 1);
                viewportPersistTimerRef.current = null;
              }, 220);
            }}
            onAnnotationCreate={(annotation) => {
              const nextAnnotation = {
                id: buildAnnotationId(
                  annotation.kind,
                  annotation.start.bar_id,
                  annotation.end.bar_id,
                ),
                familyKey: activeFamilyKey,
                kind: annotation.kind,
                start: annotation.start,
                end: annotation.end,
                style: defaultAnnotationStyle(annotation.kind),
              };
              setAnnotations((current) => [
                ...current,
                nextAnnotation,
              ]);
              setSelectedAnnotationId(nextAnnotation.id);
              setAnnotationTool("none");
            }}
            onAnnotationSelect={(annotationId) => {
              setSelectedAnnotationId(annotationId);
              clearOverlaySelection();
            }}
            onAnnotationUpdate={(annotationId, nextStart, nextEnd) => {
              setAnnotations((current) =>
                current.map((annotation) =>
                  annotation.id === annotationId
                    ? { ...annotation, start: nextStart, end: nextEnd }
                    : annotation,
                ),
              );
            }}
            onAnnotationDuplicate={duplicateAnnotation}
            onAnnotationStyleChange={patchAnnotationStyle}
            onAnnotationToolChange={(tool) => {
              setAnnotationTool(tool);
              if (tool !== "none") {
                clearChartSelection();
              }
            }}
            onDeleteSelectedAnnotation={deleteSelectedAnnotation}
            onClearAnnotations={() => {
              setAnnotations((current) =>
                current.filter((annotation) => annotation.familyKey !== activeFamilyKey),
              );
              setSelectedAnnotationId(null);
            }}
            onOverlaySelect={(overlay, anchorPoint) => {
              setConfirmationGuide(null);
              setSelectedAnnotationId(null);
              setSelectedOverlayId(overlay?.overlay_id ?? null);
              setDetailAnchor(anchorPoint);
              setInspectorPanelManualPosition(false);
            }}
            onOverlayCommandSelect={(overlay) => {
              void handleOverlayCommandSelect(overlay);
            }}
            onViewportBoundaryApproach={handleViewportBoundaryApproach}
          />
          <InspectorPanel
            overlay={selectedOverlay}
            anchorPoint={detailAnchor}
            initialPosition={inspectorPanelPosition}
            initialManualPosition={inspectorPanelManualPosition}
            onPositionChange={setInspectorPanelPosition}
            onManualPositionChange={setInspectorPanelManualPosition}
            detail={detailData}
            loading={detailLoading}
            error={detailError}
            onClose={clearOverlaySelection}
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

function buildAnnotationFamilyKey(args: {
  dataVersion: string;
  sessionProfile: SessionProfile;
  timeframe: string;
}) {
  return `${args.dataVersion}:${args.sessionProfile}:${args.timeframe}`;
}

function buildAnnotationId(kind: AnnotationKind, startBarId: number, endBarId: number) {
  return `${kind}:${startBarId}:${endBarId}:${crypto.randomUUID()}`;
}
