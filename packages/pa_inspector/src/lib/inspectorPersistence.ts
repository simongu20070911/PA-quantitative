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
const STORAGE_VERSION = 8;

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
  showReplayRetiredOverlays: boolean;
  overlayLayers: Record<OverlayLayer, boolean>;
  annotations: ChartAnnotation[];
  annotationTool: AnnotationTool;
  selectedAnnotationIds: string[];
  selectedOverlayId: string | null;
  detailAnchor: ScreenPoint | null;
  confirmationGuide: ConfirmationGuide | null;
  replayCursorBarId: number | null;
  replayCursorEventId: string | null;
  replaySpeed: number;
  toolbarHidden: boolean;
  toolbarOpenPanel: InspectorToolbarPanel;
  annotationRailPosition: FloatingPosition;
  annotationToolbarPosition: FloatingPosition | null;
  annotationToolbarOpenPopover: AnnotationToolbarPopover;
  inspectorPanelPosition: FloatingPosition;
  inspectorPanelManualPosition: boolean;
  viewport: PersistedViewportState | null;
}

export interface PersistedViewportState {
  familyKey: string;
  centerBarId: number;
  span: number;
}

interface PersistedInspectorEnvelope extends PersistedInspectorState {
  version: number;
}

interface PersistedInspectorEnvelopeV7
  extends Omit<PersistedInspectorState, "selectedAnnotationIds"> {
  version: 7;
  selectedAnnotationId: string | null;
}

interface PersistedInspectorDefaultsArgs {
  apiBaseUrl: string;
  dataVersion: string;
  overlayLayers: Record<OverlayLayer, boolean>;
  annotationRailPosition: FloatingPosition;
  inspectorPanelPosition: FloatingPosition;
}

type PersistedInspectorFieldSpec<Key extends keyof PersistedInspectorState> = {
  key: Key;
  defaultValue: (
    args: PersistedInspectorDefaultsArgs,
  ) => PersistedInspectorState[Key];
  validate: (value: unknown) => value is PersistedInspectorState[Key];
  migrate?: (
    value: PersistedInspectorState[Key],
    defaults: PersistedInspectorState,
  ) => PersistedInspectorState[Key];
};

const PERSISTED_INSPECTOR_FIELD_SPECS = [
  field({
    key: "apiBaseUrl",
    defaultValue: (args) => args.apiBaseUrl,
    validate: isString,
  }),
  field({
    key: "dataVersion",
    defaultValue: (args) => args.dataVersion,
    validate: isString,
  }),
  field({
    key: "structureSource",
    defaultValue: () => "runtime_v0_2",
    validate: isStructureSourceProfile,
    migrate: (value) =>
      value === "auto" || value === "artifact_v0_2" ? "runtime_v0_2" : value,
  }),
  field({
    key: "symbol",
    defaultValue: () => "ES",
    validate: isString,
  }),
  field({
    key: "timeframe",
    defaultValue: () => "1m",
    validate: isString,
  }),
  field({
    key: "sessionProfile",
    defaultValue: () => "eth_full",
    validate: isSessionProfile,
  }),
  field({
    key: "inspectorMode",
    defaultValue: () => "explore",
    validate: isInspectorMode,
  }),
  field({
    key: "selectorMode",
    defaultValue: () => "session_date",
    validate: isSelectorMode,
  }),
  field({
    key: "sessionDate",
    defaultValue: () => "20251117",
    validate: isString,
  }),
  field({
    key: "centerBarId",
    defaultValue: () => "29390399",
    validate: isString,
  }),
  field({
    key: "startTime",
    defaultValue: () => "",
    validate: isString,
  }),
  field({
    key: "endTime",
    defaultValue: () => "",
    validate: isString,
  }),
  field({
    key: "leftBars",
    defaultValue: () => "240",
    validate: isString,
  }),
  field({
    key: "rightBars",
    defaultValue: () => "240",
    validate: isString,
  }),
  field({
    key: "bufferBars",
    defaultValue: () => "120",
    validate: isString,
  }),
  field({
    key: "emaLengths",
    defaultValue: () => "",
    validate: isString,
  }),
  field({
    key: "emaEnabled",
    defaultValue: () => false,
    validate: isBoolean,
  }),
  field({
    key: "emaStyles",
    defaultValue: () => ({}),
    validate: isEmaStylesRecord,
  }),
  field({
    key: "selectedEmaLength",
    defaultValue: () => null,
    validate: isNullableFiniteNumber,
  }),
  field({
    key: "emaToolbarPosition",
    defaultValue: () => null,
    validate: isNullableFloatingPosition,
  }),
  field({
    key: "emaToolbarOpenPopover",
    defaultValue: () => null,
    validate: isAnnotationToolbarPopover,
  }),
  field({
    key: "autoViewportFetch",
    defaultValue: () => false,
    validate: isBoolean,
  }),
  field({
    key: "showReplayRetiredOverlays",
    defaultValue: () => true,
    validate: isBoolean,
  }),
  field({
    key: "overlayLayers",
    defaultValue: (args) => args.overlayLayers,
    validate: isOverlayLayerState,
  }),
  field({
    key: "annotations",
    defaultValue: () => [],
    validate: isChartAnnotations,
  }),
  field({
    key: "annotationTool",
    defaultValue: () => "none",
    validate: isAnnotationTool,
  }),
  field({
    key: "selectedAnnotationIds",
    defaultValue: () => [],
    validate: isStringArray,
  }),
  field({
    key: "selectedOverlayId",
    defaultValue: () => null,
    validate: isNullableString,
  }),
  field({
    key: "detailAnchor",
    defaultValue: () => null,
    validate: isNullableScreenPoint,
  }),
  field({
    key: "confirmationGuide",
    defaultValue: () => null,
    validate: isNullableConfirmationGuide,
  }),
  field({
    key: "replayCursorBarId",
    defaultValue: () => null,
    validate: isNullableFiniteNumber,
  }),
  field({
    key: "replayCursorEventId",
    defaultValue: () => null,
    validate: isNullableString,
  }),
  field({
    key: "replaySpeed",
    defaultValue: () => 1,
    validate: isReplaySpeed,
  }),
  field({
    key: "toolbarHidden",
    defaultValue: () => false,
    validate: isBoolean,
  }),
  field({
    key: "toolbarOpenPanel",
    defaultValue: () => null,
    validate: isInspectorToolbarPanel,
  }),
  field({
    key: "annotationRailPosition",
    defaultValue: (args) => args.annotationRailPosition,
    validate: isFloatingPosition,
  }),
  field({
    key: "annotationToolbarPosition",
    defaultValue: () => null,
    validate: isNullableFloatingPosition,
  }),
  field({
    key: "annotationToolbarOpenPopover",
    defaultValue: () => null,
    validate: isAnnotationToolbarPopover,
  }),
  field({
    key: "inspectorPanelPosition",
    defaultValue: (args) => args.inspectorPanelPosition,
    validate: isFloatingPosition,
  }),
  field({
    key: "inspectorPanelManualPosition",
    defaultValue: () => false,
    validate: isBoolean,
  }),
  field({
    key: "viewport",
    defaultValue: () => null,
    validate: isNullableViewportState,
  }),
] as const;

export function buildDefaultInspectorState(
  args: PersistedInspectorDefaultsArgs,
): PersistedInspectorState {
  const state = {} as PersistedInspectorState;
  const writableState =
    state as Record<
      keyof PersistedInspectorState,
      PersistedInspectorState[keyof PersistedInspectorState]
    >;
  for (const spec of listFieldSpecs()) {
    writableState[spec.key] = spec.defaultValue(args);
  }
  return state;
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
    if (isPersistedEnvelope(parsed)) {
      return restorePersistedInspectorState(parsed, defaults);
    }
    if (isPersistedEnvelopeV7(parsed)) {
      return restorePersistedInspectorStateV7(parsed, defaults);
    }
    if (!isPersistedEnvelope(parsed)) {
      return defaults;
    }
    return defaults;
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
  return (
    isRecord(value) &&
    value.version === STORAGE_VERSION &&
    PERSISTED_INSPECTOR_FIELD_SPECS.every((spec) => spec.validate(value[spec.key]))
  );
}

function isPersistedEnvelopeV7(value: unknown): value is PersistedInspectorEnvelopeV7 {
  if (!isRecord(value) || value.version !== 7) {
    return false;
  }
  return (
    PERSISTED_INSPECTOR_FIELD_SPECS.every((spec) => {
      if (spec.key === "selectedAnnotationIds") {
        return isNullableString(value.selectedAnnotationId);
      }
      return spec.validate(value[spec.key]);
    })
  );
}

function restorePersistedInspectorState(
  envelope: PersistedInspectorEnvelope,
  defaults: PersistedInspectorState,
): PersistedInspectorState {
  const restored = { ...defaults };
  const writableRestored =
    restored as Record<
      keyof PersistedInspectorState,
      PersistedInspectorState[keyof PersistedInspectorState]
    >;
  for (const spec of listFieldSpecs()) {
    const value = envelope[spec.key];
    writableRestored[spec.key] = spec.migrate ? spec.migrate(value, defaults) : value;
  }
  return restored;
}

function restorePersistedInspectorStateV7(
  envelope: PersistedInspectorEnvelopeV7,
  defaults: PersistedInspectorState,
): PersistedInspectorState {
  const restored = { ...defaults };
  const writableRestored =
    restored as Record<
      keyof PersistedInspectorState,
      PersistedInspectorState[keyof PersistedInspectorState]
    >;
  for (const spec of listFieldSpecs()) {
    if (spec.key === "selectedAnnotationIds") {
      writableRestored.selectedAnnotationIds =
        envelope.selectedAnnotationId === null ? [] : [envelope.selectedAnnotationId];
      continue;
    }
    const value = envelope[spec.key];
    writableRestored[spec.key] = spec.migrate ? spec.migrate(value, defaults) : value;
  }
  return restored;
}

function field<Key extends keyof PersistedInspectorState>(
  spec: PersistedInspectorFieldSpec<Key>,
): PersistedInspectorFieldSpec<Key> {
  return spec;
}

function listFieldSpecs() {
  return PERSISTED_INSPECTOR_FIELD_SPECS as ReadonlyArray<
    PersistedInspectorFieldSpec<keyof PersistedInspectorState>
  >;
}

function isOverlayLayerState(
  value: unknown,
): value is Record<OverlayLayer, boolean> {
  return (
    isRecord(value) &&
    typeof value.pivot_st === "boolean" &&
    typeof value.pivot === "boolean" &&
    typeof value.leg === "boolean" &&
    typeof value.major_lh === "boolean"
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
  return isOneOf(value, ["auto", "artifact_v0_1", "artifact_v0_2", "runtime_v0_2"]);
}

function isInspectorMode(value: unknown): value is InspectorMode {
  return isOneOf(value, ["explore", "replay"]);
}

function isReplaySpeed(value: unknown): value is number {
  return (
    typeof value === "number" &&
    Number.isFinite(value) &&
    [0.5, 1, 2, 4].includes(value)
  );
}

function isChartAnnotation(value: unknown): value is ChartAnnotation {
  return (
    isRecord(value) &&
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
    isOneOf(value.lineStyle, ["solid", "dashed", "dotted"]) &&
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
    isOneOf(value.lineStyle, ["solid", "dashed", "dotted"]) &&
    typeof value.opacity === "number" &&
    Number.isFinite(value.opacity) &&
    typeof value.visible === "boolean"
  );
}

function isAnnotationKind(value: unknown): value is ChartAnnotation["kind"] {
  return isOneOf(value, ["line", "box", "fib50"]);
}

function isAnnotationTool(value: unknown): value is AnnotationTool {
  return value === "none" || isAnnotationKind(value);
}

function isSessionProfile(value: unknown): value is SessionProfile {
  return isOneOf(value, ["eth_full", "rth"]);
}

function isSelectorMode(value: unknown): value is SelectorMode {
  return isOneOf(value, ["session_date", "center_bar_id", "time_range"]);
}

function isInspectorToolbarPanel(value: unknown): value is InspectorToolbarPanel {
  return isOneOf(value, ["jump", "display", "layers", "versions", "data", null]);
}

function isAnnotationToolbarPopover(value: unknown): value is AnnotationToolbarPopover {
  return isOneOf(value, ["stroke", "fill", "width", "style", "opacity", null]);
}

function isNullableString(value: unknown): value is string | null {
  return value === null || typeof value === "string";
}

function isStringArray(value: unknown): value is string[] {
  return Array.isArray(value) && value.every((item) => typeof item === "string");
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

function isNullableViewportState(value: unknown): value is PersistedViewportState | null {
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

function isOneOf<const Values extends readonly unknown[]>(
  value: unknown,
  values: Values,
): value is Values[number] {
  return values.includes(value);
}
