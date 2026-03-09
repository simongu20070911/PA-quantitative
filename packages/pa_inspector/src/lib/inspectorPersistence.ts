import type {
  AnnotationTool,
  AnnotationToolbarPopover,
  ChartAnnotation,
  ConfirmationGuide,
  EmaStyle,
  FloatingPosition,
  InspectorMode,
  InspectorToolbarPanel,
  OverlayLayer,
  ScreenPoint,
  SelectorMode,
  SessionProfile,
  StructureSourceProfile,
} from "./types";

const STORAGE_KEY = "pa_inspector.workspace.v1";
const STORAGE_VERSION = 5;

export interface PersistedInspectorState {
  apiBaseUrl: string;
  dataVersion: string;
  structureSource: StructureSourceProfile;
  symbol: string;
  timeframe: string;
  sessionProfile: SessionProfile;
  inspectorMode: InspectorMode;
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
  replayCursorBarId: number | null;
  replaySpeed: number;
  toolbarHidden: boolean;
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

const BASE_DEFAULT_INSPECTOR_STATE = {
  structureSource: "runtime_v0_2",
  symbol: "ES",
  timeframe: "1m",
  sessionProfile: "eth_full",
  inspectorMode: "explore",
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
  annotations: [],
  annotationTool: "none",
  selectedAnnotationId: null,
  selectedOverlayId: null,
  detailAnchor: null,
  confirmationGuide: null,
  replayCursorBarId: null,
  replaySpeed: 1,
  toolbarHidden: false,
  toolbarOpenPanel: null,
  annotationToolbarPosition: null,
  annotationToolbarOpenPopover: null,
  inspectorPanelManualPosition: false,
  viewport: null,
} satisfies Omit<
  PersistedInspectorState,
  | "apiBaseUrl"
  | "dataVersion"
  | "overlayLayers"
  | "annotationRailPosition"
  | "inspectorPanelPosition"
>;

type PersistedInspectorFieldValidators = {
  [Key in keyof PersistedInspectorState]: (
    value: unknown,
  ) => value is PersistedInspectorState[Key];
};

type PersistedInspectorFieldMigrators = Partial<{
  [Key in keyof PersistedInspectorState]: (
    value: PersistedInspectorState[Key],
    defaults: PersistedInspectorState,
  ) => PersistedInspectorState[Key];
}>;

export function buildDefaultInspectorState(args: {
  apiBaseUrl: string;
  dataVersion: string;
  overlayLayers: Record<OverlayLayer, boolean>;
  annotationRailPosition: FloatingPosition;
  inspectorPanelPosition: FloatingPosition;
}): PersistedInspectorState {
  return {
    ...BASE_DEFAULT_INSPECTOR_STATE,
    apiBaseUrl: args.apiBaseUrl,
    dataVersion: args.dataVersion,
    overlayLayers: args.overlayLayers,
    annotationRailPosition: args.annotationRailPosition,
    inspectorPanelPosition: args.inspectorPanelPosition,
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
    return restorePersistedInspectorState(parsed, defaults);
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
    PERSISTED_INSPECTOR_STATE_KEYS.every((key) =>
      PERSISTED_INSPECTOR_FIELD_VALIDATORS[key](value[key]),
    )
  );
}

const PERSISTED_INSPECTOR_FIELD_VALIDATORS: PersistedInspectorFieldValidators = {
  apiBaseUrl: isString,
  dataVersion: isString,
  structureSource: isStructureSourceProfile,
  symbol: isString,
  timeframe: isString,
  sessionProfile: isSessionProfile,
  inspectorMode: isInspectorMode,
  selectorMode: isSelectorMode,
  sessionDate: isString,
  centerBarId: isString,
  startTime: isString,
  endTime: isString,
  leftBars: isString,
  rightBars: isString,
  bufferBars: isString,
  emaLengths: isString,
  emaEnabled: isBoolean,
  emaStyles: isEmaStylesRecord,
  selectedEmaLength: isNullableFiniteNumber,
  emaToolbarPosition: isNullableFloatingPosition,
  emaToolbarOpenPopover: isAnnotationToolbarPopover,
  autoViewportFetch: isBoolean,
  overlayLayers: isOverlayLayerState,
  annotations: isChartAnnotations,
  annotationTool: isAnnotationTool,
  selectedAnnotationId: isNullableString,
  selectedOverlayId: isNullableString,
  detailAnchor: isNullableScreenPoint,
  confirmationGuide: isNullableConfirmationGuide,
  replayCursorBarId: isNullableFiniteNumber,
  replaySpeed: isReplaySpeed,
  toolbarHidden: isBoolean,
  toolbarOpenPanel: isInspectorToolbarPanel,
  annotationRailPosition: isFloatingPosition,
  annotationToolbarPosition: isNullableFloatingPosition,
  annotationToolbarOpenPopover: isAnnotationToolbarPopover,
  inspectorPanelPosition: isFloatingPosition,
  inspectorPanelManualPosition: isBoolean,
  viewport: isNullableViewportState,
};

const PERSISTED_INSPECTOR_FIELD_MIGRATORS: PersistedInspectorFieldMigrators = {
  structureSource: (value) =>
    value === "auto" || value === "artifact_v0_2" ? "runtime_v0_2" : value,
};

const PERSISTED_INSPECTOR_STATE_KEYS = Object.keys(
  PERSISTED_INSPECTOR_FIELD_VALIDATORS,
) as Array<keyof PersistedInspectorState>;

function restorePersistedInspectorState(
  envelope: PersistedInspectorEnvelope,
  defaults: PersistedInspectorState,
): PersistedInspectorState {
  const restored = { ...defaults };
  for (const key of PERSISTED_INSPECTOR_STATE_KEYS) {
    assignRestoredInspectorField(restored, envelope, defaults, key);
  }
  return restored;
}

function assignRestoredInspectorField<Key extends keyof PersistedInspectorState>(
  restored: PersistedInspectorState,
  envelope: PersistedInspectorEnvelope,
  defaults: PersistedInspectorState,
  key: Key,
): void {
  const value = envelope[key];
  const migrate = PERSISTED_INSPECTOR_FIELD_MIGRATORS[key];
  restored[key] = migrate ? migrate(value, defaults) : value;
}

function isOverlayLayerState(
  value: unknown,
): value is Record<OverlayLayer, boolean> {
  if (!isRecord(value)) {
    return false;
  }
  return (
    typeof value.pivot_st === "boolean" &&
    typeof value.pivot === "boolean" &&
    typeof value.leg === "boolean" &&
    typeof value.major_lh === "boolean" &&
    typeof value.breakout_start === "boolean"
  );
}

function isBoolean(value: unknown): value is boolean {
  return typeof value === "boolean";
}

function isString(value: unknown): value is string {
  return typeof value === "string";
}

function isChartAnnotations(value: unknown): value is ChartAnnotation[] {
  return Array.isArray(value) && value.every(isChartAnnotation);
}

function isEmaStylesRecord(value: unknown): value is Record<string, EmaStyle> {
  return isRecord(value) && Object.values(value).every(isEmaStyle);
}

function isStructureSourceProfile(value: unknown): value is StructureSourceProfile {
  return (
    value === "auto" ||
    value === "artifact_v0_1" ||
    value === "artifact_v0_2" ||
    value === "runtime_v0_2"
  );
}

function isInspectorMode(value: unknown): value is InspectorMode {
  return value === "explore" || value === "replay";
}

function isReplaySpeed(value: unknown): value is number {
  return (
    typeof value === "number" &&
    Number.isFinite(value) &&
    [0.5, 1, 2, 4].includes(value)
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
