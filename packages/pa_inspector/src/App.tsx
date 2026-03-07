import { startTransition, useEffect, useMemo, useRef, useState } from "react";

import { ChartPane } from "./components/ChartPane";
import { InspectorPanel } from "./components/InspectorPanel";
import { Toolbar } from "./components/Toolbar";
import { fetchChartWindow, fetchStructureDetail } from "./lib/api";
import { defaultAnnotationStyle, getEmaStyle } from "./lib/annotationStyle";
import {
  countOverlaysByLayer,
  EMPTY_OVERLAY_LAYER_COUNTS,
  filterOverlaysByEnabledLayers,
  INITIAL_OVERLAY_LAYERS,
  overlayKindToLayer,
  OVERLAY_LAYER_ORDER,
} from "./lib/overlayLayers";
import {
  buildDefaultInspectorState,
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
  EmaStyle,
  FloatingPosition,
  InspectorToolbarPanel,
  Overlay,
  OverlayLayer,
  RenderedEmaLine,
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

const DEFAULT_RAIL_POSITION: FloatingPosition = { left: 12, top: 12 };
const DEFAULT_PANEL_POSITION: FloatingPosition = { left: 24, top: 24 };

export default function App() {
  const windowCacheRef = useRef<Map<string, ChartWindowResponse>>(new Map());
  const inFlightRef = useRef<Map<string, Promise<ChartWindowResponse>>>(new Map());
  const lastAutoCenterRef = useRef<number | null>(null);
  const [workspace, setWorkspace] = useState<PersistedInspectorState>(() =>
    loadPersistedInspectorState(
      buildDefaultInspectorState({
        apiBaseUrl: DEFAULT_API_BASE,
        dataVersion: DEFAULT_DATA_VERSION,
        overlayLayers: INITIAL_OVERLAY_LAYERS,
        annotationRailPosition: DEFAULT_RAIL_POSITION,
        inspectorPanelPosition: DEFAULT_PANEL_POSITION,
      }),
    ),
  );
  const viewportStateRef = useRef(workspace.viewport);
  const viewportPersistTimerRef = useRef<number | null>(null);
  const [windowData, setWindowData] = useState<ChartWindowResponse | null>(null);
  const [windowLoading, setWindowLoading] = useState(false);
  const [windowError, setWindowError] = useState<string | null>(null);
  const [detailData, setDetailData] = useState<StructureDetailResponse | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [viewportPersistRevision, setViewportPersistRevision] = useState(0);
  const {
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
    emaLengths,
    emaEnabled,
    emaStyles,
    selectedEmaLength,
    emaToolbarPosition,
    emaToolbarOpenPopover,
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
  } = workspace;

  const activeFamilyKey = useMemo(
    () => buildAnnotationFamilyKey({ dataVersion, sessionProfile, timeframe }),
    [dataVersion, sessionProfile, timeframe],
  );

  const configuredEmaLengths = useMemo(() => {
    try {
      return parseEmaLengthsInput(emaLengths);
    } catch {
      return [];
    }
  }, [emaLengths]);

  const renderedEmaLines = useMemo<RenderedEmaLine[]>(() => {
    if (!windowData) {
      return [];
    }
    return windowData.ema_lines.map((line) => {
      const style = getEmaStyle(line.length, emaStyles[String(line.length)]);
      return {
        ...line,
        style,
        selected: selectedEmaLength === line.length,
      };
    });
  }, [emaStyles, selectedEmaLength, windowData]);

  const selectedEmaLine = useMemo(
    () => renderedEmaLines.find((line) => line.length === selectedEmaLength) ?? null,
    [renderedEmaLines, selectedEmaLength],
  );

  const visibleOverlays = useMemo(() => {
    if (!windowData) {
      return [];
    }
    return filterOverlaysByEnabledLayers(windowData.overlays, overlayLayers);
  }, [overlayLayers, windowData]);

  const overlayLayerCounts = useMemo(() => {
    if (!windowData) {
      return EMPTY_OVERLAY_LAYER_COUNTS;
    }
    return countOverlaysByLayer(windowData.overlays);
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

  function patchWorkspace(patch: Partial<PersistedInspectorState>) {
    setWorkspace((current) => ({ ...current, ...patch }));
  }

  function setWorkspaceField<Key extends keyof PersistedInspectorState>(
    key: Key,
    value: PersistedInspectorState[Key],
  ) {
    setWorkspace((current) => ({ ...current, [key]: value }));
  }

  useEffect(() => {
    void loadWindow("restore");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    lastAutoCenterRef.current = null;
  }, [dataVersion, selectorMode, sessionDate, centerBarId, startTime, endTime, sessionProfile, timeframe]);

  useEffect(() => {
    clearChartSelection();
    setWorkspaceField("confirmationGuide", null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionProfile, timeframe]);

  useEffect(() => {
    if (!selectedAnnotationId) {
      return;
    }
    if (!visibleAnnotations.some((annotation) => annotation.id === selectedAnnotationId)) {
      setWorkspaceField("selectedAnnotationId", null);
    }
  }, [selectedAnnotationId, visibleAnnotations]);

  useEffect(() => {
    if (!emaEnabled) {
      setWorkspaceField("selectedEmaLength", null);
      return;
    }
    if (
      selectedEmaLength !== null &&
      !configuredEmaLengths.includes(selectedEmaLength) &&
      !renderedEmaLines.some((line) => line.length === selectedEmaLength)
    ) {
      setWorkspaceField("selectedEmaLength", null);
    }
  }, [configuredEmaLengths, emaEnabled, renderedEmaLines, selectedEmaLength]);

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
      ...workspace,
      viewport: viewportStateRef.current,
    });
  }, [
    workspace,
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
    let request: ReturnType<typeof buildWindowRequest>;
    try {
      request = buildWindowRequest(args);
    } catch (error) {
      setWindowError(
        error instanceof Error ? error.message : "Failed to build chart window request.",
      );
      return;
    }
    const cacheKey = buildWindowCacheKey(request);
    setWindowLoading(true);
    setWindowError(null);
    try {
      const response = await getOrFetchWindow(cacheKey, request);
      startTransition(() => {
        setWindowData(response);
        setWindowLoading(false);
        if (args?.source !== "restore") {
          patchWorkspace({
            selectedOverlayId: null,
            detailAnchor: null,
            selectedAnnotationId: null,
            confirmationGuide: null,
          });
          setDetailData(null);
          setDetailError(null);
          setDetailLoading(false);
        }
        if (args?.source !== "restore" && args?.selectorMode === "center_bar_id" && args.centerBarId) {
          patchWorkspace({
            selectorMode: "center_bar_id",
            centerBarId: args.centerBarId,
          });
        } else if (args?.source !== "restore" && args?.selectorMode === "session_date" && args.sessionDate) {
          patchWorkspace({
            selectorMode: "session_date",
            sessionDate: args.sessionDate,
          });
        } else if (
          args?.source !== "restore" &&
          args?.selectorMode === "time_range" &&
          args.startTime &&
          args.endTime
        ) {
          patchWorkspace({
            selectorMode: "time_range",
            startTime: args.startTime,
            endTime: args.endTime,
          });
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
      emaLengths: emaEnabled ? configuredEmaLengths : [],
      selectorMode: args?.selectorMode ?? selectorMode,
      sessionDate: args?.sessionDate ?? sessionDate,
      centerBarId: args?.centerBarId ?? centerBarId,
      startTime: args?.startTime ?? startTime,
      endTime: args?.endTime ?? endTime,
      leftBars: Number(leftBars || 0),
      rightBars: Number(rightBars || 0),
      bufferBars: Number(bufferBars || 0),
      overlayLayers: OVERLAY_LAYER_ORDER,
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
    patchWorkspace({
      selectedOverlayId: null,
      detailAnchor: null,
      inspectorPanelManualPosition: false,
    });
    setDetailData(null);
    setDetailError(null);
    setDetailLoading(false);
  }

  function clearEmaSelection() {
    setWorkspaceField("selectedEmaLength", null);
  }

  function clearChartSelection() {
    clearOverlaySelection();
    clearEmaSelection();
    setWorkspaceField("selectedAnnotationId", null);
  }

  function deleteSelectedAnnotation() {
    if (!selectedAnnotationId) {
      return;
    }
    setWorkspace((current) => ({
      ...current,
      annotations: current.annotations.filter(
        (annotation) => annotation.id !== selectedAnnotationId,
      ),
      selectedAnnotationId: null,
    }));
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
    setWorkspace((current) => ({
      ...current,
      annotations: [...current.annotations, duplicate],
      selectedAnnotationId: duplicateId,
    }));
    return duplicateId;
  }

  function patchAnnotationStyle(
    annotationId: string,
    patch: Partial<AnnotationStyle>,
  ) {
    setWorkspace((current) => ({
      ...current,
      annotations: current.annotations.map((annotation) =>
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
    }));
  }

  function patchEmaStyle(length: number, patch: Partial<EmaStyle>) {
    setWorkspace((current) => {
      const key = String(length);
      return {
        ...current,
        emaStyles: {
          ...current.emaStyles,
          [key]: {
            ...getEmaStyle(length, current.emaStyles[key]),
            ...patch,
          },
        },
      };
    });
  }

  async function handleOverlayCommandSelect(overlay: Overlay) {
    if (confirmationGuide?.sourceStructureId === overlay.source_structure_id) {
      setWorkspaceField("confirmationGuide", null);
      return;
    }
    clearOverlaySelection();
    clearEmaSelection();
    setWorkspaceField("selectedAnnotationId", null);
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
        setWorkspaceField("confirmationGuide", null);
        return;
      }
      setWorkspaceField("confirmationGuide", {
        sourceStructureId: overlay.source_structure_id,
        confirmBarId: detail.confirm_bar.bar_id,
        confirmPrice: detail.confirm_bar.close,
      });
    } catch (error) {
      console.warn("Failed to load confirmation guide", error);
      setWorkspaceField("confirmationGuide", null);
    }
  }

  return (
    <div className="app-shell">
      <Toolbar
        apiBaseUrl={apiBaseUrl}
        onApiBaseUrlChange={(value) => setWorkspaceField("apiBaseUrl", value)}
        dataVersion={dataVersion}
        onDataVersionChange={(value) => setWorkspaceField("dataVersion", value)}
        symbol={symbol}
        timeframe={timeframe}
        sessionProfile={sessionProfile}
        onSymbolChange={(value) => setWorkspaceField("symbol", value)}
        onTimeframeChange={(value) => setWorkspaceField("timeframe", value)}
        onSessionProfileChange={(value) => setWorkspaceField("sessionProfile", value)}
        selectorMode={selectorMode}
        onSelectorModeChange={(value) => setWorkspaceField("selectorMode", value)}
        sessionDate={sessionDate}
        centerBarId={centerBarId}
        startTime={startTime}
        endTime={endTime}
        onSessionDateChange={(value) => setWorkspaceField("sessionDate", value)}
        onCenterBarIdChange={(value) => setWorkspaceField("centerBarId", value)}
        onStartTimeChange={(value) => setWorkspaceField("startTime", value)}
        onEndTimeChange={(value) => setWorkspaceField("endTime", value)}
        leftBars={leftBars}
        rightBars={rightBars}
        bufferBars={bufferBars}
        emaLengths={emaLengths}
        emaEnabled={emaEnabled}
        emaEntries={
          emaEnabled
            ? configuredEmaLengths.map((length) => ({
                length,
                style: getEmaStyle(length, emaStyles[String(length)]),
                selected: selectedEmaLength === length,
              }))
            : []
        }
        onLeftBarsChange={(value) => setWorkspaceField("leftBars", value)}
        onRightBarsChange={(value) => setWorkspaceField("rightBars", value)}
        onBufferBarsChange={(value) => setWorkspaceField("bufferBars", value)}
        onEmaLengthsChange={(value) => setWorkspaceField("emaLengths", value)}
        onEmaEnabledChange={(enabled) => {
          setWorkspaceField("emaEnabled", enabled);
          if (!enabled) {
            clearEmaSelection();
          }
        }}
        onEmaSelect={(length) => {
          clearOverlaySelection();
          patchWorkspace({
            selectedAnnotationId: null,
            selectedEmaLength: length,
          });
        }}
        autoViewportFetch={autoViewportFetch}
        onAutoViewportFetchChange={(value) =>
          setWorkspaceField("autoViewportFetch", value)
        }
        overlayLayerCounts={overlayLayerCounts}
        overlayLayers={overlayLayers}
        openPanel={toolbarOpenPanel}
        onOpenPanelChange={(panel) => setWorkspaceField("toolbarOpenPanel", panel)}
        onOverlayLayerChange={(layer, enabled) => {
          setWorkspace((current) => ({
            ...current,
            overlayLayers: {
              ...current.overlayLayers,
              [layer]: enabled,
            },
          }));
          if (selectedOverlay) {
            const selectedLayer = overlayKindToLayer(selectedOverlay.kind);
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
            emaLines={renderedEmaLines}
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
            onAnnotationRailPositionChange={(position) =>
              setWorkspaceField("annotationRailPosition", position)
            }
            annotationToolbarPosition={annotationToolbarPosition}
            onAnnotationToolbarPositionChange={(position) =>
              setWorkspaceField("annotationToolbarPosition", position)
            }
            annotationToolbarOpenPopover={annotationToolbarOpenPopover}
            onAnnotationToolbarOpenPopoverChange={(popover) =>
              setWorkspaceField("annotationToolbarOpenPopover", popover)
            }
            selectedEmaLine={selectedEmaLine}
            emaToolbarPosition={emaToolbarPosition}
            onEmaToolbarPositionChange={(position) =>
              setWorkspaceField("emaToolbarPosition", position)
            }
            emaToolbarOpenPopover={emaToolbarOpenPopover}
            onEmaToolbarOpenPopoverChange={(popover) =>
              setWorkspaceField("emaToolbarOpenPopover", popover)
            }
            onEmaStyleChange={patchEmaStyle}
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
              setWorkspace((current) => ({
                ...current,
                annotations: [...current.annotations, nextAnnotation],
                selectedAnnotationId: nextAnnotation.id,
                annotationTool: "none",
              }));
            }}
            onAnnotationSelect={(annotationId) => {
              setWorkspaceField("selectedAnnotationId", annotationId);
              clearEmaSelection();
              clearOverlaySelection();
            }}
            onAnnotationUpdate={(annotationId, nextStart, nextEnd) => {
              setWorkspace((current) => ({
                ...current,
                annotations: current.annotations.map((annotation) =>
                  annotation.id === annotationId
                    ? { ...annotation, start: nextStart, end: nextEnd }
                    : annotation,
                ),
              }));
            }}
            onAnnotationDuplicate={duplicateAnnotation}
            onAnnotationStyleChange={patchAnnotationStyle}
            onAnnotationToolChange={(tool) => {
              setWorkspaceField("annotationTool", tool);
              if (tool !== "none") {
                clearChartSelection();
              }
            }}
            onDeleteSelectedAnnotation={deleteSelectedAnnotation}
            onClearAnnotations={() => {
              setWorkspace((current) => ({
                ...current,
                annotations: current.annotations.filter(
                  (annotation) => annotation.familyKey !== activeFamilyKey,
                ),
                selectedAnnotationId: null,
              }));
            }}
            onOverlaySelect={(overlay, anchorPoint) => {
              setWorkspace((current) => ({
                ...current,
                confirmationGuide: null,
                selectedAnnotationId: null,
                selectedOverlayId: overlay?.overlay_id ?? null,
                detailAnchor: anchorPoint,
                inspectorPanelManualPosition: false,
              }));
              clearEmaSelection();
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
            onPositionChange={(position) =>
              setWorkspaceField("inspectorPanelPosition", position)
            }
            onManualPositionChange={(manual) =>
              setWorkspaceField("inspectorPanelManualPosition", manual)
            }
            detail={detailData}
            loading={detailLoading}
            error={detailError}
            onClose={clearOverlaySelection}
          />
        </div>
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
    emaLengths: request.emaLengths,
    overlayLayers: request.overlayLayers,
  });
}

function parseEmaLengthsInput(value: string): number[] {
  const trimmed = value.trim();
  if (!trimmed) {
    return [];
  }

  const parts = trimmed
    .split(",")
    .map((part) => part.trim())
    .filter((part) => part.length > 0);
  if (parts.length === 0) {
    return [];
  }

  const lengths: number[] = [];
  for (const part of parts) {
    if (!/^\d+$/.test(part)) {
      throw new Error("EMA lengths must be a comma-separated list of positive integers.");
    }
    const length = Number(part);
    if (!Number.isInteger(length) || length <= 0) {
      throw new Error("EMA lengths must be a comma-separated list of positive integers.");
    }
    if (!lengths.includes(length)) {
      lengths.push(length);
    }
  }
  return lengths;
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
