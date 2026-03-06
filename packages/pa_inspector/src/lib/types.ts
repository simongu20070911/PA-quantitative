export type OverlayLayer = "pivot" | "leg" | "major_lh" | "breakout_start";
export type SelectorMode = "session_date" | "center_bar_id" | "time_range";
export type SessionProfile = "eth_full" | "rth";
export type AnnotationTool = "none" | "line" | "box" | "fib50";
export type AnnotationKind = Exclude<AnnotationTool, "none">;
export type AnnotationLineStyle = "solid" | "dashed" | "dotted";
export type InspectorToolbarPanel = "jump" | "display" | "layers" | "data" | null;
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
  overlay_version: string | null;
}

export interface ChartWindowResponse {
  bars: ChartBar[];
  overlays: Overlay[];
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
  featureVersion?: string;
  featureParamsHash?: string;
  overlayVersion?: string;
  selectorMode: SelectorMode;
  centerBarId?: string;
  sessionDate?: string;
  startTime?: string;
  endTime?: string;
  leftBars: number;
  rightBars: number;
  bufferBars: number;
  overlayLayers?: OverlayLayer[];
}
