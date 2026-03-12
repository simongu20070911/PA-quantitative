import { startTransition, useEffect, useMemo, useRef, useState } from "react";

import { ChartPane } from "./components/ChartPane";
import { InspectorPanel } from "./components/InspectorPanel";
import { ReplayTransport } from "./components/ReplayTransport";
import { Toolbar } from "./components/Toolbar";
import { fetchChartWindow, fetchStructureDetail } from "./lib/api";
import { defaultAnnotationStyle, getEmaStyle } from "./lib/annotationStyle";
import { createClientUuid } from "./lib/clientIds";
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
  ChartBar,
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
  PlaybackSequence,
  PlaybackStep,
  ReplayDelta,
  ReplaySequence,
  RenderedEmaLine,
  ScreenPoint,
  SelectorMode,
  SessionProfile,
  StructureEvent,
  StructureDetailResponse,
  StructureSummary,
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
  const latestWindowRequestIdRef = useRef(0);
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
    showReplayRetiredOverlays,
    overlayLayers,
    annotations,
    annotationTool,
    selectedAnnotationIds,
    selectedOverlayId,
    detailAnchor,
    confirmationGuide,
    replayCursorBarId,
    replayCursorStepId,
    replayCursorEventId,
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

  const replaySequence = windowData?.replay_sequence ?? null;
  const playbackSequence = windowData?.playback_sequence ?? null;
  const replayActiveAsOfBarId = inspectorMode === "replay" ? replayCursorBarId : null;
  const replayFrameState = useMemo(
    () =>
      resolveReplayFrameState({
        replaySequence,
        replayCursorBarId: replayActiveAsOfBarId,
        replayCursorEventId,
      }),
    [replayActiveAsOfBarId, replayCursorEventId, replaySequence],
  );
  const playbackFrameState = useMemo(
    () =>
      resolvePlaybackFrameState({
        playbackSequence,
        replayCursorStepId,
      }),
    [playbackSequence, replayCursorStepId],
  );
  const replayVisibleEmaBarId =
    inspectorMode === "replay"
      ? playbackFrameState?.asOfBarId ?? replayActiveAsOfBarId
      : null;
  const displayEmaLines = useMemo<RenderedEmaLine[]>(() => {
    if (replayVisibleEmaBarId === null) {
      return renderedEmaLines;
    }
    return renderedEmaLines
      .map((line) => ({
        ...line,
        points: line.points.filter((point) => point.bar_id <= replayVisibleEmaBarId),
      }))
      .filter((line) => line.points.length > 0);
  }, [renderedEmaLines, replayVisibleEmaBarId]);
  const selectedEmaLine = useMemo(
    () => displayEmaLines.find((line) => line.length === selectedEmaLength) ?? null,
    [displayEmaLines, selectedEmaLength],
  );
  const displayOverlays =
    inspectorMode === "replay" && replayActiveAsOfBarId !== null && replayFrameState !== null
      ? replayFrameState.overlays
      : (windowData?.overlays ?? []);
  const filteredDisplayOverlays = useMemo(
    () =>
      showReplayRetiredOverlays
        ? displayOverlays
        : displayOverlays.filter((overlay) => !isReplayRetiredOverlay(overlay)),
    [displayOverlays, showReplayRetiredOverlays],
  );

  const visibleOverlays = useMemo(() => {
    if (!filteredDisplayOverlays.length) {
      return [];
    }
    return filterOverlaysByEnabledLayers(filteredDisplayOverlays, overlayLayers);
  }, [filteredDisplayOverlays, overlayLayers]);

  const overlayLayerCounts = useMemo(() => {
    if (!filteredDisplayOverlays.length) {
      return EMPTY_OVERLAY_LAYER_COUNTS;
    }
    return countOverlaysByLayer(filteredDisplayOverlays);
  }, [filteredDisplayOverlays]);

  const visibleAnnotations = useMemo(
    () => annotations.filter((annotation) => annotation.familyKey === activeFamilyKey),
    [activeFamilyKey, annotations],
  );
  const allChartBars = windowData?.bars ?? [];
  const selectedAnnotations = useMemo(() => {
    if (!selectedAnnotationIds.length) {
      return [];
    }
    const selectedIdSet = new Set(selectedAnnotationIds);
    return visibleAnnotations.filter((annotation) => selectedIdSet.has(annotation.id));
  }, [selectedAnnotationIds, visibleAnnotations]);
  const selectedAnnotation = useMemo(
    () => selectedAnnotations[selectedAnnotations.length - 1] ?? null,
    [selectedAnnotations],
  );
  const selectedOverlay = useMemo(
    () =>
      filteredDisplayOverlays.find((overlay) => overlay.overlay_id === selectedOverlayId) ?? null,
    [filteredDisplayOverlays, selectedOverlayId],
  );
  const replayDisplayCursorBarId =
    inspectorMode === "replay"
      ? playbackFrameState?.displayCursorBarId ?? replayActiveAsOfBarId
      : null;
  const replayCursorIndex = useMemo(() => {
    if (!allChartBars.length || replayDisplayCursorBarId === null) {
      return null;
    }
    const index = allChartBars.findIndex((bar) => bar.bar_id === replayDisplayCursorBarId);
    return index >= 0 ? index : null;
  }, [allChartBars, replayDisplayCursorBarId]);
  const replayCursorBar =
    inspectorMode === "replay"
      ? playbackFrameState?.cursorBar ??
        (replayCursorIndex === null ? null : allChartBars[replayCursorIndex] ?? null)
      : null;
  const replayDisplayBars = useMemo(() => {
    if (inspectorMode !== "replay") {
      return allChartBars;
    }
    if (playbackFrameState !== null) {
      return playbackFrameState.displayBars;
    }
    if (replayCursorIndex === null) {
      return allChartBars;
    }
    return allChartBars.slice(0, replayCursorIndex + 1);
  }, [allChartBars, inspectorMode, playbackFrameState, replayCursorIndex]);
  const activeAsOfBarId = replayActiveAsOfBarId;
  const activeAsOfEventId = inspectorMode === "replay" ? replayCursorEventId : null;
  const replayBackendResolved =
    inspectorMode === "replay" &&
    replaySequence !== null &&
    replaySequence !== undefined;
  const hasReplayLifecycleEvents = (windowData?.events.length ?? 0) > 0;
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
    if (replayActiveAsOfBarId === null) {
      return;
    }
    if (allChartBars.some((bar) => bar.bar_id === replayActiveAsOfBarId)) {
      return;
    }
    patchWorkspace({
      replayCursorBarId: null,
      replayCursorStepId: null,
      replayCursorEventId: null,
    });
  }, [allChartBars, inspectorMode, replayActiveAsOfBarId]);

  useEffect(() => {
    if (inspectorMode !== "replay") {
      return;
    }
    if (!playbackSequence?.steps.length || replayCursorStepId !== null || replayCursorBarId === null) {
      return;
    }
    const alignedStepId = resolveClosingPlaybackStepId(playbackSequence, replayCursorBarId);
    if (alignedStepId === null) {
      return;
    }
    setWorkspaceField("replayCursorStepId", alignedStepId);
  }, [inspectorMode, playbackSequence, replayCursorBarId, replayCursorStepId]);

  useEffect(() => {
    if (inspectorMode !== "replay" || !replayPlaying) {
      return;
    }
    if (!replayBackendResolved) {
      return;
    }
    if (!playbackSequence?.steps.length) {
      setReplayPlaying(false);
      return;
    }
    const currentIndex = resolvePlaybackStepIndex(playbackSequence, replayCursorStepId);
    if (currentIndex >= playbackSequence.steps.length - 1) {
      setReplayPlaying(false);
      return;
    }
    const timeout = window.setTimeout(() => {
      const nextStep = playbackSequence.steps[currentIndex + 1];
      if (!nextStep) {
        setReplayPlaying(false);
        return;
      }
      patchWorkspace({
        replayCursorBarId: nextStep.as_of_bar_id ?? null,
        replayCursorStepId: nextStep.step_id,
        replayCursorEventId: null,
      });
    }, replayDelayMs(replaySpeed));
    return () => {
      window.clearTimeout(timeout);
    };
  }, [
    inspectorMode,
    playbackSequence,
    replayBackendResolved,
    replayCursorStepId,
    replayPlaying,
    replaySpeed,
  ]);

  useEffect(() => {
    lastAutoCenterRef.current = null;
  }, [dataVersion, selectorMode, sessionDate, centerBarId, startTime, endTime, sessionProfile, timeframe]);

  useEffect(() => {
    clearChartSelection();
    setWorkspaceField("confirmationGuide", null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionProfile, timeframe]);

  useEffect(() => {
    if (!selectedAnnotationIds.length) {
      return;
    }
    const visibleIdSet = new Set(visibleAnnotations.map((annotation) => annotation.id));
    const nextSelection = selectedAnnotationIds.filter((annotationId) =>
      visibleIdSet.has(annotationId),
    );
    if (nextSelection.length !== selectedAnnotationIds.length) {
      setWorkspaceField("selectedAnnotationIds", nextSelection);
    }
  }, [selectedAnnotationIds, visibleAnnotations]);

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
    if (!selectedAnnotationIds.length) {
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
  }, [selectedAnnotationIds]);

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
    void fetchStructureDetail(
      buildStructureDetailRequest(selectedOverlay.source_structure_id),
    )
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
  }, [activeAsOfBarId, activeAsOfEventId, apiBaseUrl, dataVersion, selectedOverlay, sessionProfile, structureSource, symbol, timeframe]);

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
    includeReplaySequence?: boolean;
    centerBarId?: string;
    sessionDate?: string;
    startTime?: string;
    endTime?: string;
  }) {
    const requestId = latestWindowRequestIdRef.current + 1;
    latestWindowRequestIdRef.current = requestId;
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
      if (requestId !== latestWindowRequestIdRef.current) {
        return;
      }
      startTransition(() => {
        setWindowData(response);
        setWindowLoading(false);
        setWindowNotice(null);
        if (args?.source !== "restore" && args?.source !== "replay") {
          patchWorkspace({
            selectedOverlayId: null,
            detailAnchor: null,
            selectedAnnotationIds: [],
            confirmationGuide: null,
            replayCursorStepId: null,
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
      if (requestId !== latestWindowRequestIdRef.current) {
        return;
      }
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
          selectedAnnotationIds: [],
          confirmationGuide: null,
          replayCursorStepId: null,
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
    includeReplaySequence?: boolean;
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
      includeReplaySequence: args?.includeReplaySequence ?? inspectorMode === "replay",
      emaLengths: emaEnabled ? configuredEmaLengths : [],
      selectorMode: args?.selectorMode ?? selectorMode,
      asOfBarId: null,
      asOfEventId: null,
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
          includeReplaySequence: false,
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
    setWorkspaceField("selectedAnnotationIds", []);
  }

  function deleteSelectedAnnotation() {
    if (!selectedAnnotationIds.length) {
      return;
    }
    const selectedIdSet = new Set(selectedAnnotationIds);
    setWorkspace((current) => ({
      ...current,
      annotations: current.annotations.filter(
        (annotation) => !selectedIdSet.has(annotation.id),
      ),
      selectedAnnotationIds: [],
    }));
  }

  function duplicateAnnotation(annotationIds: string[]) {
    const selectedIdSet = new Set(annotationIds);
    const sources = annotations.filter((annotation) => selectedIdSet.has(annotation.id));
    if (!sources.length) {
      return [];
    }
    const duplicateIds: string[] = [];
    const duplicates = sources.map((source) => {
      const duplicateId = buildAnnotationId(
        source.kind,
        source.start.bar_id,
        source.end.bar_id,
      );
      duplicateIds.push(duplicateId);
      return {
        ...source,
        id: duplicateId,
      } satisfies ChartAnnotation;
    });
    setWorkspace((current) => ({
      ...current,
      annotations: [...current.annotations, ...duplicates],
      selectedAnnotationIds: duplicateIds,
    }));
    return duplicateIds;
  }

  function patchAnnotationStyle(
    annotationIds: string[],
    patch: Partial<AnnotationStyle>,
  ) {
    if (!annotationIds.length) {
      return;
    }
    const selectedIdSet = new Set(annotationIds);
    setWorkspace((current) => ({
      ...current,
      annotations: current.annotations.map((annotation) =>
        selectedIdSet.has(annotation.id)
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
    setWorkspaceField("selectedAnnotationIds", []);
    try {
      const detail = await fetchStructureDetail(
        buildStructureDetailRequest(overlay.source_structure_id),
      );
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
      patchWorkspace({
        inspectorMode: mode,
        replayCursorStepId: null,
        replayCursorEventId: null,
      });
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
      replayCursorStepId: null,
      replayCursorEventId: null,
      selectedOverlayId: null,
      detailAnchor: null,
      confirmationGuide: null,
    });
    void requestWindow({
      source: "replay",
      includeReplaySequence: true,
    });
  }

  function buildStructureDetailRequest(structureId: string) {
    return {
      apiBaseUrl,
      structureId,
      symbol,
      timeframe,
      sessionProfile,
      dataVersion,
      structureSource,
      asOfBarId: activeAsOfBarId,
      asOfEventId: activeAsOfEventId,
      selectorMode,
      centerBarId,
      sessionDate,
      startTime,
      endTime,
      leftBars: Number(leftBars || 0),
      rightBars: Number(rightBars || 0),
      bufferBars: Number(bufferBars || 0),
    };
  }

  async function getReplayEventCatalog() {
    if (windowData?.events.length) {
      return windowData.events;
    }
    const request = {
      ...buildWindowRequest(),
      includeReplaySequence: true,
      asOfBarId: null,
      asOfEventId: null,
    };
    const cacheKey = buildWindowCacheKey(request);
    const cached = windowCacheRef.current.get(cacheKey);
    if (cached) {
      return cached.events;
    }
    const response = await getOrFetchWindow(cacheKey, request);
    rememberWindowCacheEntry(windowCacheRef.current, cacheKey, response);
    return response.events;
  }

  function resolveReplayEventIndex(
    events: StructureEvent[],
    eventIds: string[],
    replayBarId: number | null,
    replayEventId: string | null,
  ) {
    if (!eventIds.length) {
      return null;
    }
    if (replayEventId) {
      const index = eventIds.indexOf(replayEventId);
      if (index >= 0) {
        return index;
      }
    }
    if (replayBarId === null) {
      return null;
    }
    let currentIndex: number | null = null;
    for (let index = 0; index < events.length; index += 1) {
      if (events[index]?.event_bar_id <= replayBarId) {
        currentIndex = index;
      }
    }
    return currentIndex;
  }

  async function handleReplayStepEvent(direction: -1 | 1) {
    if (replayPlaying) {
      return;
    }
    const events = await getReplayEventCatalog();
    if (!events.length) {
      return;
    }
    const eventIds = events.map((event) => event.event_id);
    const currentIndex = resolveReplayEventIndex(
      events,
      eventIds,
      replayCursorBarId,
      replayCursorEventId,
    );
    const nextIndex =
      currentIndex === null
        ? direction < 0
          ? events.length - 1
          : 0
        : Math.max(0, Math.min(events.length - 1, currentIndex + direction));
    const nextEvent = events[nextIndex];
    if (!nextEvent) {
      return;
    }
    setReplayPlaying(false);
    const nextStepId = resolveClosingPlaybackStepId(playbackSequence, nextEvent.event_bar_id);
    patchWorkspace({
      replayCursorBarId: nextEvent.event_bar_id,
      replayCursorStepId: nextStepId,
      replayCursorEventId: nextEvent.event_id,
    });
  }

  function handleReplayCursorSelect(barId: number) {
    if (replayPlaying) {
      return;
    }
    patchWorkspace({
      replayCursorBarId: barId,
      replayCursorStepId: resolveClosingPlaybackStepId(playbackSequence, barId),
      replayCursorEventId: null,
    });
  }

  function handleReplayStepBar(direction: -1 | 1) {
    if (replayPlaying) {
      return;
    }
    if (!playbackSequence?.steps.length) {
      return;
    }
    const currentIndex = resolvePlaybackStepIndex(playbackSequence, replayCursorStepId);
    const nextIndex = Math.max(
      0,
      Math.min(playbackSequence.steps.length - 1, currentIndex + direction),
    );
    const nextStep = playbackSequence.steps[nextIndex];
    if (!nextStep) {
      return;
    }
    setReplayPlaying(false);
    patchWorkspace({
      replayCursorBarId: nextStep.as_of_bar_id ?? null,
      replayCursorStepId: nextStep.step_id,
      replayCursorEventId: null,
    });
  }

  function handleReplayJumpToLatest() {
    if (replayPlaying) {
      return;
    }
    if (!playbackSequence?.steps.length) {
      return;
    }
    const latestStep = playbackSequence.steps[playbackSequence.steps.length - 1];
    if (!latestStep) {
      return;
    }
    setReplayPlaying(false);
    patchWorkspace({
      replayCursorBarId: latestStep.as_of_bar_id ?? null,
      replayCursorStepId: latestStep.step_id,
      replayCursorEventId: null,
    });
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
      selectedAnnotationIds: [],
      selectedOverlayId: null,
      detailAnchor: null,
      confirmationGuide: null,
      replayCursorStepId: null,
      replayCursorEventId: null,
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
            selectedAnnotationIds: [],
            selectedEmaLength: length,
          });
        }}
        autoViewportFetch={autoViewportFetch}
        onAutoViewportFetchChange={(value) =>
          setWorkspaceField("autoViewportFetch", value)
        }
        showReplayRetiredOverlays={showReplayRetiredOverlays}
        onShowReplayRetiredOverlaysChange={(value) =>
          setWorkspaceField("showReplayRetiredOverlays", value)
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
            bars={allChartBars}
            displayBars={replayDisplayBars}
            emptyMessage={windowError ?? windowNotice ?? undefined}
            emaLines={displayEmaLines}
            overlays={visibleOverlays}
            annotations={visibleAnnotations}
            annotationTool={annotationTool}
            sessionProfile={windowData?.meta.session_profile ?? sessionProfile}
            enabledLayers={overlayLayers}
            selectedOverlayId={selectedOverlayId}
            selectedAnnotations={selectedAnnotations}
            selectedAnnotationIds={selectedAnnotationIds}
            confirmationGuide={confirmationGuide}
            replayEnabled={inspectorMode === "replay"}
            replayInteractionLocked={replayPlaying}
            replayCursorBarId={replayDisplayCursorBarId}
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
                selectedAnnotationIds: [nextAnnotation.id],
                annotationTool: "none",
              }));
            }}
            onAnnotationSelect={(annotationIds) => {
              setWorkspaceField("selectedAnnotationIds", annotationIds);
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
                selectedAnnotationIds: [],
              }));
            }}
            onOverlaySelect={(overlay, anchorPoint) => {
              setWorkspace((current) => ({
                ...current,
                confirmationGuide: null,
                selectedAnnotationIds: [],
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
            hasEvents={hasReplayLifecycleEvents}
            cursorBar={replayCursorBar}
            playing={replayPlaying}
            speed={replaySpeed}
            backendResolved={replayBackendResolved}
            playbackMode={playbackSequence?.mode ?? null}
            playbackStepTimeframe={playbackSequence?.step_timeframe ?? null}
            onTogglePlaying={() => {
              if (!replayCursorBar) {
                return;
              }
              setReplayPlaying((current) => !current);
            }}
            onStepBar={handleReplayStepBar}
            onStepEvent={handleReplayStepEvent}
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

function resolvePlaybackFrameState(args: {
  playbackSequence: PlaybackSequence | null;
  replayCursorStepId: string | null;
}): {
  displayBars: ChartBar[];
  cursorBar: ChartBar | null;
  displayCursorBarId: number | null;
  asOfBarId: number | null;
} | null {
  if (!args.playbackSequence?.steps.length || args.replayCursorStepId === null) {
    return null;
  }
  const targetIndex = args.playbackSequence.steps.findIndex(
    (step) => step.step_id === args.replayCursorStepId,
  );
  if (targetIndex < 0) {
    return null;
  }
  const displayBarsById = new Map(
    args.playbackSequence.base.display_bars.map((bar) => [bar.bar_id, bar]),
  );
  let lastAppliedStep: PlaybackStep | null = null;
  for (let index = 0; index <= targetIndex; index += 1) {
    const step = args.playbackSequence.steps[index];
    displayBarsById.set(step.display_bar.bar_id, step.display_bar);
    lastAppliedStep = step;
  }
  if (lastAppliedStep === null) {
    return null;
  }
  const displayBars = Array.from(displayBarsById.values()).sort((left, right) => left.bar_id - right.bar_id);
  return {
    displayBars,
    cursorBar: lastAppliedStep.display_bar,
    displayCursorBarId: lastAppliedStep.display_bar.bar_id,
    asOfBarId: lastAppliedStep.as_of_bar_id ?? null,
  };
}

function resolvePlaybackStepIndex(
  playbackSequence: PlaybackSequence,
  replayCursorStepId: string | null,
) {
  if (!playbackSequence.steps.length) {
    return -1;
  }
  if (replayCursorStepId === null) {
    return -1;
  }
  const index = playbackSequence.steps.findIndex((step) => step.step_id === replayCursorStepId);
  return index >= 0 ? index : -1;
}

function resolveClosingPlaybackStepId(
  playbackSequence: PlaybackSequence | null,
  barId: number,
) {
  if (!playbackSequence?.steps.length) {
    return null;
  }
  for (let index = playbackSequence.steps.length - 1; index >= 0; index -= 1) {
    const step = playbackSequence.steps[index];
    if (step.display_bar.bar_id === barId && step.closes_display_bar) {
      return step.step_id;
    }
  }
  return null;
}

function resolveReplayFrameState(args: {
  replaySequence: ReplaySequence | null;
  replayCursorBarId: number | null;
  replayCursorEventId: string | null;
}): { structures: StructureSummary[]; overlays: Overlay[] } | null {
  if (!args.replaySequence || args.replayCursorBarId === null) {
    return null;
  }
  const targetDeltaIndex =
    args.replayCursorEventId === null
      ? null
      : (() => {
          const index = args.replaySequence.deltas.findIndex(
            (delta) => delta.event_id === args.replayCursorEventId,
          );
          return index >= 0 ? index : null;
        })();
  const structuresById = new Map(
    args.replaySequence.base.structures.map((structure) => [structure.structure_id, structure]),
  );
  const overlaysById = new Map(
    args.replaySequence.base.overlays.map((overlay) => [overlay.overlay_id, overlay]),
  );
  for (let index = 0; index < args.replaySequence.deltas.length; index += 1) {
    const delta = args.replaySequence.deltas[index];
    if (
      !replayDeltaVisibleAtCursor(
        delta,
        index,
        targetDeltaIndex,
        args.replayCursorBarId,
      )
    ) {
      break;
    }
    for (const structureId of delta.remove_structure_ids) {
      structuresById.delete(structureId);
    }
    for (const structure of delta.upsert_structures) {
      structuresById.set(structure.structure_id, structure);
    }
    for (const overlayId of delta.remove_overlay_ids) {
      overlaysById.delete(overlayId);
    }
    for (const overlay of delta.upsert_overlays) {
      overlaysById.set(overlay.overlay_id, overlay);
    }
  }
  return {
    structures: Array.from(structuresById.values()).sort(compareReplayStructures),
    overlays: Array.from(overlaysById.values()).sort(compareReplayOverlays),
  };
}

function replayDeltaVisibleAtCursor(
  delta: ReplayDelta,
  deltaIndex: number,
  targetDeltaIndex: number | null,
  replayCursorBarId: number,
) {
  if (targetDeltaIndex !== null) {
    return deltaIndex <= targetDeltaIndex;
  }
  return delta.event_bar_id <= replayCursorBarId;
}

function compareReplayStructures(left: StructureSummary, right: StructureSummary) {
  return (
    left.start_bar_id - right.start_bar_id ||
    ((left.end_bar_id ?? left.start_bar_id) - (right.end_bar_id ?? right.start_bar_id)) ||
    left.kind.localeCompare(right.kind) ||
    left.structure_id.localeCompare(right.structure_id)
  );
}

function compareReplayOverlays(left: Overlay, right: Overlay) {
  return (
    replayOverlayZOrder(left.kind) - replayOverlayZOrder(right.kind) ||
    replayOverlayTierRank(left) - replayOverlayTierRank(right) ||
    ((left.anchor_bars[0] ?? -1) - (right.anchor_bars[0] ?? -1)) ||
    left.overlay_id.localeCompare(right.overlay_id)
  );
}

function replayOverlayZOrder(kind: string) {
  if (kind === "leg-line") {
    return 1;
  }
  if (kind === "pivot-marker") {
    return 2;
  }
  if (kind === "major-lh-marker") {
    return 3;
  }
  return 100;
}

function replayOverlayTierRank(overlay: Overlay) {
  if (overlay.meta.replay_event_type) {
    return -1;
  }
  if (overlay.style_key.startsWith("pivot_st.")) {
    return 0;
  }
  if (overlay.style_key.startsWith("pivot.")) {
    return 1;
  }
  return 0;
}

function isReplayRetiredOverlay(overlay: Overlay) {
  return overlay.meta.replay_event_type !== undefined && overlay.meta.replay_event_type !== null;
}

function buildWindowCacheKey(request: Parameters<typeof fetchChartWindow>[0]) {
  return JSON.stringify({
    apiBaseUrl: request.apiBaseUrl,
    symbol: request.symbol,
    timeframe: request.timeframe,
    dataVersion: request.dataVersion,
    structureSource: request.structureSource,
    includeReplaySequence: request.includeReplaySequence ?? false,
    asOfBarId: request.asOfBarId ?? null,
    asOfEventId: request.asOfEventId ?? null,
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
  return (
    (request.asOfBarId === null || request.asOfBarId === undefined) &&
    (request.asOfEventId === null || request.asOfEventId === undefined)
  );
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
  return `${kind}:${startBarId}:${endBarId}:${createClientUuid()}`;
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
