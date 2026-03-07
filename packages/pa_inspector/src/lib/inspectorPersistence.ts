import type {
  AnnotationTool,
  AnnotationToolbarPopover,
  ChartAnnotation,
  ConfirmationGuide,
  EmaStyle,
  FloatingPosition,
  InspectorToolbarPanel,
  OverlayLayer,
  ScreenPoint,
  SelectorMode,
  SessionProfile,
} from "./types";

const STORAGE_KEY = "pa_inspector.workspace.v1";
const STORAGE_VERSION = 1;

export interface PersistedInspectorState {
  apiBaseUrl: string;
  dataVersion: string;
  symbol: string;
  timeframe: string;
  sessionProfile: SessionProfile;
  selectorMode: SelectorMode;
  sessionDate: string;
  centerBarId: string;
  startTime: string;
  endTime: string;
  leftBars: string;
  rightBars: string;
  bufferBars: string;
  emaLengths: string;
  emaEnabled: boolean;
  emaStyles: Record<string, EmaStyle>;
  selectedEmaLength: number | null;
  emaToolbarPosition: FloatingPosition | null;
  emaToolbarOpenPopover: AnnotationToolbarPopover;
  autoViewportFetch: boolean;
  overlayLayers: Record<OverlayLayer, boolean>;
  annotations: ChartAnnotation[];
  annotationTool: AnnotationTool;
  selectedAnnotationId: string | null;
  selectedOverlayId: string | null;
  detailAnchor: ScreenPoint | null;
  confirmationGuide: ConfirmationGuide | null;
  toolbarOpenPanel: InspectorToolbarPanel;
  annotationRailPosition: FloatingPosition;
  annotationToolbarPosition: FloatingPosition | null;
  annotationToolbarOpenPopover: AnnotationToolbarPopover;
  inspectorPanelPosition: FloatingPosition;
  inspectorPanelManualPosition: boolean;
  viewport:
    | {
        familyKey: string;
        centerBarId: number;
        span: number;
      }
    | null;
}

interface PersistedInspectorEnvelope extends PersistedInspectorState {
  version: number;
}

export function buildDefaultInspectorState(args: {
  apiBaseUrl: string;
  dataVersion: string;
  overlayLayers: Record<OverlayLayer, boolean>;
  annotationRailPosition: FloatingPosition;
  inspectorPanelPosition: FloatingPosition;
}): PersistedInspectorState {
  return {
    apiBaseUrl: args.apiBaseUrl,
    dataVersion: args.dataVersion,
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
    emaLengths: "",
    emaEnabled: false,
    emaStyles: {},
    selectedEmaLength: null,
    emaToolbarPosition: null,
    emaToolbarOpenPopover: null,
    autoViewportFetch: false,
    overlayLayers: args.overlayLayers,
    annotations: [],
    annotationTool: "none",
    selectedAnnotationId: null,
    selectedOverlayId: null,
    detailAnchor: null,
    confirmationGuide: null,
    toolbarOpenPanel: null,
    annotationRailPosition: args.annotationRailPosition,
    annotationToolbarPosition: null,
    annotationToolbarOpenPopover: null,
    inspectorPanelPosition: args.inspectorPanelPosition,
    inspectorPanelManualPosition: false,
    viewport: null,
  };
}

export function loadPersistedInspectorState(
  defaults: PersistedInspectorState,
): PersistedInspectorState {
  if (typeof window === "undefined") {
    return defaults;
  }
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) {
      return defaults;
    }
    const parsed = JSON.parse(raw) as unknown;
    if (!isPersistedEnvelope(parsed)) {
      return defaults;
    }
    return {
      apiBaseUrl: parsed.apiBaseUrl,
      dataVersion: parsed.dataVersion,
      symbol: parsed.symbol,
      timeframe: parsed.timeframe,
      sessionProfile: parsed.sessionProfile,
      selectorMode: parsed.selectorMode,
      sessionDate: parsed.sessionDate,
      centerBarId: parsed.centerBarId,
      startTime: parsed.startTime,
      endTime: parsed.endTime,
      leftBars: parsed.leftBars,
      rightBars: parsed.rightBars,
      bufferBars: parsed.bufferBars,
      emaLengths: parsed.emaLengths,
      emaEnabled: parsed.emaEnabled,
      emaStyles: parsed.emaStyles,
      selectedEmaLength: parsed.selectedEmaLength,
      emaToolbarPosition: parsed.emaToolbarPosition,
      emaToolbarOpenPopover: parsed.emaToolbarOpenPopover,
      autoViewportFetch: parsed.autoViewportFetch,
      overlayLayers: parsed.overlayLayers,
      annotations: parsed.annotations,
      annotationTool: parsed.annotationTool,
      selectedAnnotationId: parsed.selectedAnnotationId,
      selectedOverlayId: parsed.selectedOverlayId,
      detailAnchor: parsed.detailAnchor,
      confirmationGuide: parsed.confirmationGuide,
      toolbarOpenPanel: parsed.toolbarOpenPanel,
      annotationRailPosition: parsed.annotationRailPosition,
      annotationToolbarPosition: parsed.annotationToolbarPosition,
      annotationToolbarOpenPopover: parsed.annotationToolbarOpenPopover,
      inspectorPanelPosition: parsed.inspectorPanelPosition,
      inspectorPanelManualPosition: parsed.inspectorPanelManualPosition,
      viewport: parsed.viewport,
    };
  } catch (error) {
    console.warn("Failed to load persisted inspector state", error);
    return defaults;
  }
}

export function savePersistedInspectorState(state: PersistedInspectorState) {
  if (typeof window === "undefined") {
    return;
  }
  const envelope: PersistedInspectorEnvelope = {
    version: STORAGE_VERSION,
    ...state,
  };
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(envelope));
  } catch (error) {
    console.warn("Failed to persist inspector state", error);
  }
}

function isPersistedEnvelope(value: unknown): value is PersistedInspectorEnvelope {
  if (!isRecord(value)) {
    return false;
  }
  return (
    value.version === STORAGE_VERSION &&
    typeof value.apiBaseUrl === "string" &&
    typeof value.dataVersion === "string" &&
    typeof value.symbol === "string" &&
    typeof value.timeframe === "string" &&
    isSessionProfile(value.sessionProfile) &&
    isSelectorMode(value.selectorMode) &&
    typeof value.sessionDate === "string" &&
    typeof value.centerBarId === "string" &&
    typeof value.startTime === "string" &&
    typeof value.endTime === "string" &&
    typeof value.leftBars === "string" &&
    typeof value.rightBars === "string" &&
    typeof value.bufferBars === "string" &&
    typeof value.emaLengths === "string" &&
    typeof value.emaEnabled === "boolean" &&
    isRecord(value.emaStyles) &&
    Object.values(value.emaStyles).every(isEmaStyle) &&
    isNullableFiniteNumber(value.selectedEmaLength) &&
    isNullableFloatingPosition(value.emaToolbarPosition) &&
    isAnnotationToolbarPopover(value.emaToolbarOpenPopover) &&
    typeof value.autoViewportFetch === "boolean" &&
    isOverlayLayerState(value.overlayLayers) &&
    Array.isArray(value.annotations) &&
    value.annotations.every(isChartAnnotation) &&
    isAnnotationTool(value.annotationTool) &&
    isNullableString(value.selectedAnnotationId) &&
    isNullableString(value.selectedOverlayId) &&
    isNullableScreenPoint(value.detailAnchor) &&
    isNullableConfirmationGuide(value.confirmationGuide) &&
    isInspectorToolbarPanel(value.toolbarOpenPanel) &&
    isFloatingPosition(value.annotationRailPosition) &&
    isNullableFloatingPosition(value.annotationToolbarPosition) &&
    isAnnotationToolbarPopover(value.annotationToolbarOpenPopover) &&
    isFloatingPosition(value.inspectorPanelPosition) &&
    typeof value.inspectorPanelManualPosition === "boolean" &&
    isNullableViewportState(value.viewport)
  );
}

function isOverlayLayerState(
  value: unknown,
): value is Record<OverlayLayer, boolean> {
  if (!isRecord(value)) {
    return false;
  }
  return (
    typeof value.pivot === "boolean" &&
    typeof value.leg === "boolean" &&
    typeof value.major_lh === "boolean" &&
    typeof value.breakout_start === "boolean"
  );
}

function isChartAnnotation(value: unknown): value is ChartAnnotation {
  if (!isRecord(value)) {
    return false;
  }
  return (
    typeof value.id === "string" &&
    typeof value.familyKey === "string" &&
    isAnnotationKind(value.kind) &&
    isAnnotationAnchor(value.start) &&
    isAnnotationAnchor(value.end) &&
    isAnnotationStyle(value.style)
  );
}

function isAnnotationAnchor(value: unknown): value is ChartAnnotation["start"] {
  return (
    isRecord(value) &&
    typeof value.bar_id === "number" &&
    Number.isFinite(value.bar_id) &&
    typeof value.price === "number" &&
    Number.isFinite(value.price)
  );
}

function isAnnotationStyle(value: unknown): value is ChartAnnotation["style"] {
  return (
    isRecord(value) &&
    typeof value.strokeColor === "string" &&
    typeof value.fillColor === "string" &&
    typeof value.lineWidth === "number" &&
    Number.isFinite(value.lineWidth) &&
    (value.lineStyle === "solid" ||
      value.lineStyle === "dashed" ||
      value.lineStyle === "dotted") &&
    typeof value.opacity === "number" &&
    Number.isFinite(value.opacity) &&
    typeof value.locked === "boolean"
  );
}

function isEmaStyle(value: unknown): value is EmaStyle {
  return (
    isRecord(value) &&
    typeof value.strokeColor === "string" &&
    typeof value.lineWidth === "number" &&
    Number.isFinite(value.lineWidth) &&
    (value.lineStyle === "solid" ||
      value.lineStyle === "dashed" ||
      value.lineStyle === "dotted") &&
    typeof value.opacity === "number" &&
    Number.isFinite(value.opacity) &&
    typeof value.visible === "boolean"
  );
}

function isAnnotationKind(value: unknown): value is ChartAnnotation["kind"] {
  return value === "line" || value === "box" || value === "fib50";
}

function isAnnotationTool(value: unknown): value is AnnotationTool {
  return value === "none" || isAnnotationKind(value);
}

function isSessionProfile(value: unknown): value is SessionProfile {
  return value === "eth_full" || value === "rth";
}

function isSelectorMode(value: unknown): value is SelectorMode {
  return value === "session_date" || value === "center_bar_id" || value === "time_range";
}

function isInspectorToolbarPanel(value: unknown): value is InspectorToolbarPanel {
  return value === null || value === "jump" || value === "display" || value === "layers" || value === "data";
}

function isAnnotationToolbarPopover(value: unknown): value is AnnotationToolbarPopover {
  return (
    value === null ||
    value === "stroke" ||
    value === "fill" ||
    value === "width" ||
    value === "style" ||
    value === "opacity"
  );
}

function isNullableString(value: unknown): value is string | null {
  return value === null || typeof value === "string";
}

function isNullableFiniteNumber(value: unknown): value is number | null {
  return value === null || (typeof value === "number" && Number.isFinite(value));
}

function isFloatingPosition(value: unknown): value is FloatingPosition {
  return (
    isRecord(value) &&
    typeof value.left === "number" &&
    Number.isFinite(value.left) &&
    typeof value.top === "number" &&
    Number.isFinite(value.top)
  );
}

function isNullableFloatingPosition(value: unknown): value is FloatingPosition | null {
  return value === null || isFloatingPosition(value);
}

function isScreenPoint(value: unknown): value is ScreenPoint {
  return (
    isRecord(value) &&
    typeof value.x === "number" &&
    Number.isFinite(value.x) &&
    typeof value.y === "number" &&
    Number.isFinite(value.y)
  );
}

function isNullableScreenPoint(value: unknown): value is ScreenPoint | null {
  return value === null || isScreenPoint(value);
}

function isNullableConfirmationGuide(value: unknown): value is ConfirmationGuide | null {
  return (
    value === null ||
    (isRecord(value) &&
      typeof value.sourceStructureId === "string" &&
      typeof value.confirmBarId === "number" &&
      Number.isFinite(value.confirmBarId) &&
      typeof value.confirmPrice === "number" &&
      Number.isFinite(value.confirmPrice))
  );
}

function isNullableViewportState(
  value: unknown,
): value is PersistedInspectorState["viewport"] {
  return (
    value === null ||
    (isRecord(value) &&
      typeof value.familyKey === "string" &&
      typeof value.centerBarId === "number" &&
      Number.isFinite(value.centerBarId) &&
      typeof value.span === "number" &&
      Number.isFinite(value.span))
  );
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}
