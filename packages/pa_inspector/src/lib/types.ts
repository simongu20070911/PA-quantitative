export type OverlayLayer =
  | "pivot_st"
  | "pivot"
  | "leg"
  | "major_lh";
export type SelectorMode = "session_date" | "center_bar_id" | "time_range";
export type SessionProfile = "eth_full" | "rth";
export type InspectorMode = "explore" | "replay";
export type StructureSourceProfile =
  | "auto"
  | "artifact_v0_1"
  | "artifact_v0_2"
  | "runtime_v0_2";
export type AnnotationTool = "none" | "line" | "box" | "fib50";
export type AnnotationKind = Exclude<AnnotationTool, "none">;
export type AnnotationLineStyle = "solid" | "dashed" | "dotted";
export type EmaLineStyle = AnnotationLineStyle;
export type InspectorToolbarPanel =
  | "jump"
  | "display"
  | "layers"
  | "versions"
  | "data"
  | null;
export type AnnotationToolbarPopover =
  | "stroke"
  | "fill"
  | "width"
  | "style"
  | "opacity"
  | null;

export interface FloatingPosition {
  left: number;
  top: number;
}

export interface ScreenPoint {
  x: number;
  y: number;
}

export interface ChartBar {
  bar_id: number;
  time: number;
  open: number;
  high: number;
  low: number;
  close: number;
  session_id: number;
  session_date: number;
}

export interface EmaPoint {
  bar_id: number;
  time: number;
  value: number;
}

export interface EmaStyle {
  strokeColor: string;
  lineWidth: number;
  lineStyle: EmaLineStyle;
  opacity: number;
  visible: boolean;
}

export interface EmaLine {
  length: number;
  points: EmaPoint[];
}

export interface RenderedEmaLine extends EmaLine {
  style: EmaStyle;
  selected: boolean;
}

export interface Overlay {
  overlay_id: string;
  kind: string;
  source_structure_id: string;
  anchor_bars: number[];
  anchor_prices: number[];
  style_key: string;
  rulebook_version: string;
  structure_version: string;
  data_version: string;
  overlay_version: string;
  meta: Record<string, unknown>;
}

export interface AnnotationAnchor {
  bar_id: number;
  price: number;
}

export interface AnnotationStyle {
  strokeColor: string;
  fillColor: string;
  lineWidth: number;
  lineStyle: AnnotationLineStyle;
  opacity: number;
  locked: boolean;
}

export interface ChartAnnotation {
  id: string;
  familyKey: string;
  kind: AnnotationKind;
  start: AnnotationAnchor;
  end: AnnotationAnchor;
  style: AnnotationStyle;
}

export interface ConfirmationGuide {
  sourceStructureId: string;
  confirmBarId: number;
  confirmPrice: number;
}

export interface ChartWindowMeta {
  data_version: string;
  source_data_version: string;
  aggregation_version: string;
  session_profile: SessionProfile;
  timeframe: string;
  feature_version: string | null;
  feature_params_hash: string | null;
  rulebook_version: string | null;
  structure_version: string | null;
  structure_source: StructureSourceProfile;
  overlay_version: string | null;
  ema_lengths: number[];
  as_of_bar_id?: number | null;
  as_of_event_id?: string | null;
  replay_source?: string | null;
  replay_completeness?: string | null;
}

export interface StructureEvent {
  event_id: string;
  structure_id: string;
  kind: string;
  event_type: string;
  event_bar_id: number;
  event_order: number;
  state_after_event: string;
  reason_codes: string[];
  start_bar_id: number;
  end_bar_id: number | null;
  confirm_bar_id: number | null;
  anchor_bar_ids: number[];
  predecessor_structure_id?: string | null;
  successor_structure_id?: string | null;
  payload_after?: Record<string, unknown> | null;
  changed_fields: string[];
}

export interface ReplayBase {
  as_of_bar_id?: number | null;
  structures: StructureSummary[];
  overlays: Overlay[];
}

export interface ReplayDelta {
  event_id: string;
  event_bar_id: number;
  event_order: number;
  event_type: string;
  structure_id: string;
  remove_structure_ids: string[];
  upsert_structures: StructureSummary[];
  remove_overlay_ids: string[];
  upsert_overlays: Overlay[];
}

export interface ReplaySequence {
  base: ReplayBase;
  deltas: ReplayDelta[];
}

export interface ChartWindowResponse {
  bars: ChartBar[];
  ema_lines: EmaLine[];
  structures: StructureSummary[];
  events: StructureEvent[];
  overlays: Overlay[];
  replay_sequence?: ReplaySequence | null;
  meta: ChartWindowMeta;
}

export interface StructureSummary {
  structure_id: string;
  kind: string;
  state: string;
  start_bar_id: number;
  end_bar_id: number | null;
  confirm_bar_id: number | null;
  anchor_bar_ids: number[];
  explanation_codes: string[];
  payload?: Record<string, unknown> | null;
}

export interface StructureDetailResponse {
  structure: StructureSummary;
  anchor_bars: ChartBar[];
  confirm_bar: ChartBar | null;
  feature_refs: string[];
  structure_refs: string[];
  versions: ChartWindowMeta;
}

export interface ChartWindowRequest {
  apiBaseUrl: string;
  symbol: string;
  timeframe: string;
  sessionProfile: SessionProfile;
  dataVersion: string;
  structureSource: StructureSourceProfile;
  featureVersion?: string;
  featureParamsHash?: string;
  overlayVersion?: string;
  emaLengths?: number[];
  selectorMode: SelectorMode;
  includeReplaySequence?: boolean;
  asOfBarId?: number | null;
  asOfEventId?: string | null;
  centerBarId?: string;
  sessionDate?: string;
  startTime?: string;
  endTime?: string;
  leftBars: number;
  rightBars: number;
  bufferBars: number;
  overlayLayers?: OverlayLayer[];
}
