import { startTransition, useEffect, useMemo, useRef, useState } from "react";

import { ChartPane } from "./components/ChartPane";
import { InspectorPanel } from "./components/InspectorPanel";
import { ReplayTransport } from "./components/ReplayTransport";
import { Toolbar } from "./components/Toolbar";
import { fetchChartWindow, fetchStructureDetail } from "./lib/api";
import { defaultAnnotationStyle, getEmaStyle } from "./lib/annotationStyle";
import {
  countOverlaysByLayer,
  EMPTY_OVERLAY_LAYER_COUNTS,
  filterOverlaysByEnabledLayers,
  INITIAL_OVERLAY_LAYERS,
  overlayToLayer,
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
  InspectorMode,
  InspectorToolbarPanel,
  Overlay,
  OverlayLayer,
  RenderedEmaLine,
  ScreenPoint,
  SelectorMode,
  SessionProfile,
  StructureDetailResponse,
  StructureSourceProfile,
} from "./lib/types";

const DEFAULT_API_BASE =
  import.meta.env.VITE_API_BASE_URL?.trim() || "/api";
const DEFAULT_DATA_VERSION =
  import.meta.env.VITE_DEFAULT_DATA_VERSION?.trim() ||
  "es_1m_v1_4f3eda8a678d3c41";

const DEFAULT_RAIL_POSITION: FloatingPosition = { left: 12, top: 12 };
const DEFAULT_PANEL_POSITION: FloatingPosition = { left: 24, top: 24 };
const MAX_WINDOW_CACHE_ENTRIES = 12;

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
  const [windowNotice, setWindowNotice] = useState<string | null>(null);
  const [detailData, setDetailData] = useState<StructureDetailResponse | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [replayPlaying, setReplayPlaying] = useState(false);
  const [viewportPersistRevision, setViewportPersistRevision] = useState(0);
  const {
    apiBaseUrl,
    dataVersion,
    structureSource,
    symbol,
    timeframe,
    sessionProfile,
    inspectorMode,
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
    replayCursorBarId,
    replaySpeed,
    toolbarHidden,
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
  const allChartBars = windowData?.bars ?? [];
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
  const replayCursorIndex = useMemo(() => {
    if (!allChartBars.length || replayCursorBarId === null) {
      return null;
    }
    const index = allChartBars.findIndex((bar) => bar.bar_id === replayCursorBarId);
    return index >= 0 ? index : null;
  }, [allChartBars, replayCursorBarId]);
  const replayCursorBar =
    replayCursorIndex === null ? null : allChartBars[replayCursorIndex] ?? null;
  const chartBars = useMemo(() => {
    if (inspectorMode !== "replay" || replayCursorIndex === null) {
      return allChartBars;
    }
    return allChartBars.slice(0, replayCursorIndex + 1);
  }, [allChartBars, inspectorMode, replayCursorIndex]);
  const activeAsOfBarId = inspectorMode === "replay" ? replayCursorBarId : null;
  const replayBackendResolved =
    inspectorMode === "replay" &&
    activeAsOfBarId !== null &&
    windowData?.meta.as_of_bar_id === activeAsOfBarId &&
    windowData.meta.replay_source !== null &&
    windowData.meta.replay_source !== undefined;
  const resolvedStructureSource = windowData?.meta.structure_source ?? null;
  const resolvedRulebookVersion = windowData?.meta.rulebook_version ?? null;
  const resolvedStructureVersion = windowData?.meta.structure_version ?? null;

  function patchWorkspace(patch: Partial<PersistedInspectorState>) {
    setWorkspace((current) => {
      const entries = Object.entries(patch) as Array<
        [keyof PersistedInspectorState, PersistedInspectorState[keyof PersistedInspectorState]]
      >;
      if (entries.every(([key, value]) => Object.is(current[key], value))) {
        return current;
      }
      return { ...current, ...patch };
    });
  }

  function setWorkspaceField<Key extends keyof PersistedInspectorState>(
    key: Key,
    value: PersistedInspectorState[Key],
  ) {
    setWorkspace((current) =>
      Object.is(current[key], value)
        ? current
        : { ...current, [key]: value },
    );
  }

  useEffect(() => {
    void loadWindow("restore");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (inspectorMode !== "replay") {
      setReplayPlaying(false);
      return;
    }
    if (replayCursorBarId === null) {
      return;
    }
    if (allChartBars.some((bar) => bar.bar_id === replayCursorBarId)) {
      return;
    }
    setWorkspaceField("replayCursorBarId", null);
  }, [allChartBars, inspectorMode, replayCursorBarId]);

  useEffect(() => {
    if (inspectorMode !== "replay" || !replayPlaying) {
      return;
    }
    if (!allChartBars.length || replayCursorIndex === null) {
      setReplayPlaying(false);
      return;
    }
    if (replayCursorIndex >= allChartBars.length - 1) {
      setReplayPlaying(false);
      return;
    }
    const timeout = window.setTimeout(() => {
      const nextBar = allChartBars[replayCursorIndex + 1];
      if (!nextBar) {
        setReplayPlaying(false);
        return;
      }
      setWorkspaceField("replayCursorBarId", nextBar.bar_id);
    }, replayDelayMs(replaySpeed));
    return () => {
      window.clearTimeout(timeout);
    };
  }, [allChartBars, inspectorMode, replayCursorIndex, replayPlaying, replaySpeed]);

  useEffect(() => {
    if (inspectorMode !== "replay") {
      if (windowData?.meta.as_of_bar_id !== null && windowData?.meta.as_of_bar_id !== undefined) {
        void requestWindow({ source: "replay" });
      }
      return;
    }
    if (replayCursorBarId === null) {
      if (windowData?.meta.as_of_bar_id !== null && windowData?.meta.as_of_bar_id !== undefined) {
        void requestWindow({ source: "replay" });
      }
      return;
    }
    if (
      windowData?.meta.as_of_bar_id === replayCursorBarId &&
      windowData.meta.structure_source === structureSource
    ) {
      return;
    }
    void requestWindow({ source: "replay" });
  }, [inspectorMode, replayCursorBarId, structureSource, windowData?.meta.as_of_bar_id, windowData?.meta.structure_source]);

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
      structureSource,
      asOfBarId: activeAsOfBarId,
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
  }, [activeAsOfBarId, apiBaseUrl, dataVersion, selectedOverlay, sessionProfile, structureSource, symbol, timeframe]);

  async function loadWindow(source: "manual" | "restore" | "replay" = "manual") {
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
    source?: "manual" | "viewport" | "restore" | "replay";
    structureSource?: StructureSourceProfile;
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
    setWindowNotice(null);
    try {
      const response = await getOrFetchWindow(cacheKey, request);
      startTransition(() => {
        setWindowData(response);
        setWindowLoading(false);
        setWindowNotice(null);
        if (args?.source !== "restore" && args?.source !== "replay") {
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
      void prefetchAdjacentWindows(response, request.structureSource);
    } catch (error) {
      setWindowLoading(false);
      const rawMessage =
        error instanceof Error ? error.message : "Failed to load chart window.";
      const fallbackSource = resolveUnavailableStructureSourceFallback({
        requestedSource: request.structureSource,
        message: rawMessage,
      });
      if (fallbackSource !== null) {
        setWindowNotice("Canonical v0.2 artifacts are not materialized yet. Switched to runtime v0.2.");
        patchWorkspace({
          structureSource: fallbackSource,
          toolbarOpenPanel: null,
          selectedOverlayId: null,
          detailAnchor: null,
          confirmationGuide: null,
        });
        void requestWindow({
          ...(args ?? {}),
          source: "manual",
          structureSource: fallbackSource,
        });
        return;
      }
      const message = formatWindowLoadMessage(rawMessage, args?.source ?? "manual");
      if ((args?.source ?? "manual") === "restore") {
        setWindowNotice(message);
        return;
      }
      setWindowError(message);
    }
  }

  function buildWindowRequest(args?: {
    structureSource?: StructureSourceProfile;
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
      structureSource: args?.structureSource ?? structureSource,
      emaLengths: emaEnabled ? configuredEmaLengths : [],
      selectorMode: args?.selectorMode ?? selectorMode,
      asOfBarId: activeAsOfBarId,
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
    const cacheable = shouldCacheWindowRequest(request);
    if (cacheable) {
      const cached = windowCacheRef.current.get(cacheKey);
      if (cached) {
        // Refresh insertion order to keep the cache LRU-like.
        windowCacheRef.current.delete(cacheKey);
        windowCacheRef.current.set(cacheKey, cached);
        return cached;
      }
    }
    const inFlight = inFlightRef.current.get(cacheKey);
    if (inFlight) {
      return inFlight;
    }
    const fetchPromise = fetchChartWindow(request)
      .then((response) => {
        if (cacheable) {
          rememberWindowCacheEntry(windowCacheRef.current, cacheKey, response);
        }
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

  async function prefetchAdjacentWindows(
    response: ChartWindowResponse,
    requestStructureSource: StructureSourceProfile,
  ) {
    if (response.meta.as_of_bar_id !== null && response.meta.as_of_bar_id !== undefined) {
      return;
    }
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
          structureSource: requestStructureSource,
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
      structureSource,
      asOfBarId: activeAsOfBarId,
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

  function handleInspectorModeChange(mode: InspectorMode) {
    if (mode !== "replay") {
      setWorkspaceField("inspectorMode", mode);
      setReplayPlaying(false);
      if (windowData?.meta.as_of_bar_id !== null && windowData?.meta.as_of_bar_id !== undefined) {
        void requestWindow({ source: "replay" });
      }
      return;
    }
    setReplayPlaying(false);
    patchWorkspace({
      inspectorMode: mode,
      replayCursorBarId: null,
      selectedOverlayId: null,
      detailAnchor: null,
      confirmationGuide: null,
    });
  }

  function handleReplayCursorSelect(barId: number) {
    setReplayPlaying(false);
    setWorkspaceField("replayCursorBarId", barId);
  }

  function handleReplayStepBar(direction: -1 | 1) {
    if (!allChartBars.length) {
      return;
    }
    const currentIndex =
      replayCursorIndex ?? (direction < 0 ? allChartBars.length - 1 : 0);
    const nextIndex = Math.max(
      0,
      Math.min(allChartBars.length - 1, currentIndex + direction),
    );
    setReplayPlaying(false);
    setWorkspaceField("replayCursorBarId", allChartBars[nextIndex]?.bar_id ?? null);
  }

  function handleReplayJumpToLatest() {
    if (!allChartBars.length) {
      return;
    }
    setReplayPlaying(false);
    setWorkspaceField("replayCursorBarId", allChartBars[allChartBars.length - 1]?.bar_id ?? null);
  }

  function handleStructureSourceChange(nextSource: StructureSourceProfile) {
    if (nextSource === structureSource) {
      return;
    }
    windowCacheRef.current.clear();
    inFlightRef.current.clear();
    setWindowData(null);
    setWindowError(null);
    setWindowNotice(null);
    setDetailData(null);
    setDetailError(null);
    setDetailLoading(false);
    patchWorkspace({
      structureSource: nextSource,
      selectedAnnotationId: null,
      selectedOverlayId: null,
      detailAnchor: null,
      confirmationGuide: null,
      toolbarOpenPanel: null,
    });
    void requestWindow({
      source: "manual",
      structureSource: nextSource,
    });
  }

  return (
    <div className="app-shell">
      <Toolbar
        apiBaseUrl={apiBaseUrl}
        onApiBaseUrlChange={(value) => setWorkspaceField("apiBaseUrl", value)}
        dataVersion={dataVersion}
        onDataVersionChange={(value) => setWorkspaceField("dataVersion", value)}
        hidden={toolbarHidden}
        onHiddenChange={(hidden) =>
          patchWorkspace({
            toolbarHidden: hidden,
            toolbarOpenPanel: hidden ? null : toolbarOpenPanel,
          })
        }
        structureSource={structureSource}
        resolvedStructureSource={resolvedStructureSource}
        resolvedRulebookVersion={resolvedRulebookVersion}
        resolvedStructureVersion={resolvedStructureVersion}
        onStructureSourceChange={handleStructureSourceChange}
        symbol={symbol}
        timeframe={timeframe}
        sessionProfile={sessionProfile}
        inspectorMode={inspectorMode}
        onSymbolChange={(value) => setWorkspaceField("symbol", value)}
        onTimeframeChange={(value) => setWorkspaceField("timeframe", value)}
        onSessionProfileChange={(value) => setWorkspaceField("sessionProfile", value)}
        onInspectorModeChange={handleInspectorModeChange}
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
            const selectedLayer = overlayToLayer(selectedOverlay);
            if (selectedLayer === layer && !enabled) {
              clearOverlaySelection();
            }
          }
        }}
        loading={windowLoading}
        requestStatusMessage={
          windowLoading ? "Loading chart..." : windowError ?? windowNotice
        }
        requestStatusTone={
          windowLoading ? "loading" : windowError ? "error" : "neutral"
        }
        onLoad={() => {
          void loadWindow();
        }}
      />

      <div className="workspace-main">
        <div className="chart-stage">
          <ChartPane
            bars={chartBars}
            emptyMessage={windowError ?? windowNotice ?? undefined}
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
            replayEnabled={inspectorMode === "replay"}
            replayCursorBarId={replayCursorBarId}
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
            onReplayCursorSelect={handleReplayCursorSelect}
            onViewportBoundaryApproach={handleViewportBoundaryApproach}
          />
          <ReplayTransport
            visible={inspectorMode === "replay"}
            hasBars={allChartBars.length > 0}
            cursorBar={replayCursorBar}
            playing={replayPlaying}
            speed={replaySpeed}
            backendResolved={replayBackendResolved}
            onTogglePlaying={() => {
              if (!replayCursorBar) {
                return;
              }
              setReplayPlaying((current) => !current);
            }}
            onStepBar={handleReplayStepBar}
            onStepEvent={() => {
              setReplayPlaying(false);
            }}
            onSpeedChange={(speed) => setWorkspaceField("replaySpeed", speed)}
            onJumpToLatest={handleReplayJumpToLatest}
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
            inspectorMode={inspectorMode}
            replayCursorBar={replayCursorBar}
            replayBackendResolved={replayBackendResolved}
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
    structureSource: request.structureSource,
    asOfBarId: request.asOfBarId ?? null,
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

function shouldCacheWindowRequest(request: Parameters<typeof fetchChartWindow>[0]) {
  return request.asOfBarId === null || request.asOfBarId === undefined;
}

function rememberWindowCacheEntry(
  cache: Map<string, ChartWindowResponse>,
  key: string,
  response: ChartWindowResponse,
) {
  cache.set(key, response);
  while (cache.size > MAX_WINDOW_CACHE_ENTRIES) {
    const oldestKey = cache.keys().next().value;
    if (typeof oldestKey !== "string") {
      break;
    }
    cache.delete(oldestKey);
  }
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

function replayDelayMs(speed: number) {
  const baseDelayMs = 680;
  return Math.max(120, Math.round(baseDelayMs / speed));
}

function formatWindowLoadMessage(
  message: string,
  source: "manual" | "viewport" | "restore" | "replay",
) {
  if (source === "restore") {
    if (message.startsWith("Request timed out")) {
      return "Restore skipped because the backend did not respond in time. Press Load when the API is ready.";
    }
    return `Restore skipped: ${message}`;
  }
  if (source === "replay") {
    return `Replay load failed: ${message}`;
  }
  return message;
}

function resolveUnavailableStructureSourceFallback(args: {
  requestedSource: StructureSourceProfile;
  message: string;
}): StructureSourceProfile | null {
  if (
    args.requestedSource === "artifact_v0_2" &&
    args.message.includes("structure_source=artifact_v0_2 is not materialized")
  ) {
    return "runtime_v0_2";
  }
  return null;
}
