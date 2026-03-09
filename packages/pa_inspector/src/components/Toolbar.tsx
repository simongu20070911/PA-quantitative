import { useMemo } from "react";

import { OVERLAY_LAYER_LABELS } from "../lib/overlayLayers";
import type {
  EmaStyle,
  InspectorMode,
  InspectorToolbarPanel,
  OverlayLayer,
  SelectorMode,
  SessionProfile,
  StructureSourceProfile,
} from "../lib/types";

const STRUCTURE_SOURCE_OPTIONS: StructureSourceProfile[] = [
  "auto",
  "artifact_v0_1",
  "runtime_v0_2",
];

const STRUCTURE_SOURCE_LABELS: Record<StructureSourceProfile, string> = {
  auto: "Auto",
  artifact_v0_1: "Rulebook v0.1",
  artifact_v0_2: "Rulebook v0.2 Artifacts",
  runtime_v0_2: "Rulebook v0.2 Runtime",
};

const STRUCTURE_SOURCE_HINTS: Record<StructureSourceProfile, string> = {
  auto: "Prefer shipped artifacts, then fall back to runtime v0.2 when needed.",
  artifact_v0_1: "Use only the canonical v0.1 artifact-backed rulebook chain.",
  artifact_v0_2: "Use only canonical v0.2 artifacts when they are materialized on disk.",
  runtime_v0_2: "Use only the live-computed v0.2 rulebook chain from pa_core.",
};

export interface ToolbarProps {
  apiBaseUrl: string;
  onApiBaseUrlChange: (value: string) => void;
  dataVersion: string;
  onDataVersionChange: (value: string) => void;
  hidden: boolean;
  onHiddenChange: (hidden: boolean) => void;
  structureSource: StructureSourceProfile;
  resolvedStructureSource: StructureSourceProfile | null;
  resolvedRulebookVersion: string | null;
  resolvedStructureVersion: string | null;
  onStructureSourceChange: (value: StructureSourceProfile) => void;
  symbol: string;
  timeframe: string;
  sessionProfile: SessionProfile;
  inspectorMode: InspectorMode;
  onSymbolChange: (value: string) => void;
  onTimeframeChange: (value: string) => void;
  onSessionProfileChange: (value: SessionProfile) => void;
  onInspectorModeChange: (value: InspectorMode) => void;
  selectorMode: SelectorMode;
  onSelectorModeChange: (value: SelectorMode) => void;
  sessionDate: string;
  centerBarId: string;
  startTime: string;
  endTime: string;
  onSessionDateChange: (value: string) => void;
  onCenterBarIdChange: (value: string) => void;
  onStartTimeChange: (value: string) => void;
  onEndTimeChange: (value: string) => void;
  leftBars: string;
  rightBars: string;
  bufferBars: string;
  emaLengths: string;
  emaEnabled: boolean;
  emaEntries: Array<{ length: number; style: EmaStyle; selected: boolean }>;
  onLeftBarsChange: (value: string) => void;
  onRightBarsChange: (value: string) => void;
  onBufferBarsChange: (value: string) => void;
  onEmaLengthsChange: (value: string) => void;
  onEmaEnabledChange: (value: boolean) => void;
  onEmaSelect: (length: number | null) => void;
  autoViewportFetch: boolean;
  onAutoViewportFetchChange: (value: boolean) => void;
  overlayLayerCounts: Record<OverlayLayer, number>;
  overlayLayers: Record<OverlayLayer, boolean>;
  onOverlayLayerChange: (layer: OverlayLayer, enabled: boolean) => void;
  openPanel: InspectorToolbarPanel;
  onOpenPanelChange: (panel: InspectorToolbarPanel) => void;
  loading: boolean;
  requestStatusMessage: string | null;
  requestStatusTone: "neutral" | "error" | "loading";
  onLoad: () => void;
}

export function Toolbar(props: ToolbarProps) {
  const selectorSummary = useMemo(() => {
    if (props.selectorMode === "session_date") {
      return `Session ${props.sessionDate || "default"}`;
    }
    if (props.selectorMode === "center_bar_id") {
      return `Bar ${props.centerBarId || "default"}`;
    }
    return props.startTime && props.endTime
      ? `Time ${props.startTime} -> ${props.endTime}`
      : "Time range";
  }, [
    props.centerBarId,
    props.endTime,
    props.selectorMode,
    props.sessionDate,
    props.startTime,
  ]);

  const windowSummary = `${props.leftBars}/${props.rightBars}/${props.bufferBars}`;
  const activeLayerCount = (
    Object.keys(props.overlayLayers) as OverlayLayer[]
  ).filter((layer) => props.overlayLayers[layer]).length;
  const resolvedStructureSource = props.resolvedStructureSource ?? props.structureSource;
  const structureSourceChanged =
    props.resolvedStructureSource !== null &&
    props.resolvedStructureSource !== props.structureSource;
  const structureVersionLabel =
    props.resolvedRulebookVersion && props.resolvedStructureVersion
      ? `${props.resolvedRulebookVersion} / ${props.resolvedStructureVersion}`
      : "Awaiting load";
  const sourceSummary = structureSourceChanged
    ? `Requested ${STRUCTURE_SOURCE_LABELS[props.structureSource]} -> ${STRUCTURE_SOURCE_LABELS[resolvedStructureSource]}`
    : `Using ${STRUCTURE_SOURCE_LABELS[resolvedStructureSource]}`;
  const requestStatusClass =
    props.requestStatusTone === "error"
      ? "toolbar-pill toolbar-pill-error"
      : props.requestStatusTone === "loading"
        ? "toolbar-pill toolbar-pill-loading"
        : "toolbar-pill";

  function togglePanel(panel: Exclude<InspectorToolbarPanel, null>) {
    props.onOpenPanelChange(props.openPanel === panel ? null : panel);
  }

  if (props.hidden) {
    const collapsedStatusClass =
      props.requestStatusTone === "error"
        ? "toolbar-tag toolbar-pill-error"
        : props.requestStatusTone === "loading"
          ? "toolbar-tag toolbar-pill-loading"
          : "toolbar-tag";
    return (
      <section className="toolbar-card toolbar-card-collapsed">
        <div className="toolbar-collapsed">
          <div className="toolbar-collapsed-brand">
            <p className="eyebrow">{props.inspectorMode === "replay" ? "Replay" : "Explore"}</p>
            <strong>Continuous Structure View</strong>
            <div className="toolbar-inline-meta">
              <span className="toolbar-tag toolbar-tag-strong">
                {props.symbol} {props.timeframe}
              </span>
              <span className="toolbar-tag">{STRUCTURE_SOURCE_LABELS[resolvedStructureSource]}</span>
              {props.requestStatusMessage ? (
                <span className={collapsedStatusClass}>{props.requestStatusMessage}</span>
              ) : null}
            </div>
          </div>
          <button
            className="toolbar-reveal-button"
            onClick={() => props.onHiddenChange(false)}
            type="button"
          >
            Show Controls
          </button>
        </div>
      </section>
    );
  }

  return (
    <section className="toolbar-card">
      <div className="toolbar-shell">
        <div className="toolbar-mainline">
          <div className="toolbar-brandline">
            <div className="toolbar-title-block">
              <p className="eyebrow">{props.inspectorMode === "replay" ? "Replay" : "Explore"}</p>
              <h1>Continuous Structure View</h1>
            </div>
            <div className="toolbar-inline-meta">
              <span className="toolbar-tag toolbar-tag-strong">
                {props.symbol} {props.timeframe}
              </span>
              <span className="toolbar-tag">{props.sessionProfile}</span>
              <span className="toolbar-tag">{selectorSummary}</span>
              <span className="toolbar-tag">Window {windowSummary}</span>
              <span className="toolbar-tag">{structureVersionLabel}</span>
            </div>
          </div>
          <div className="toolbar-controls">
          <div className="segmented toolbar-segmented-mode">
            {(["explore", "replay"] as InspectorMode[]).map((mode) => (
              <button
                className={mode === props.inspectorMode ? "segment active" : "segment"}
                key={mode}
                onClick={() => props.onInspectorModeChange(mode)}
                type="button"
              >
                {mode === "replay" ? "Replay" : "Explore"}
              </button>
            ))}
          </div>
          <div className="toolbar-actions">
            <button
              className={props.openPanel === "jump" ? "toolbar-action active" : "toolbar-action"}
              onClick={() => togglePanel("jump")}
              type="button"
            >
              Jump
            </button>
            <button
              className={
                props.openPanel === "display" ? "toolbar-action active" : "toolbar-action"
              }
              onClick={() => togglePanel("display")}
              type="button"
            >
              Display
            </button>
            <button
              className={
                props.openPanel === "versions" ? "toolbar-action active" : "toolbar-action"
              }
              onClick={() => togglePanel("versions")}
              type="button"
            >
              Version
            </button>
            <button
              className={
                props.openPanel === "layers" ? "toolbar-action active" : "toolbar-action"
              }
              onClick={() => togglePanel("layers")}
              type="button"
            >
              Layers
              <code>{activeLayerCount}</code>
            </button>
            <button
              className={props.openPanel === "data" ? "toolbar-action active" : "toolbar-action"}
              onClick={() => togglePanel("data")}
              type="button"
            >
              Data
            </button>
            <button
              className="toolbar-action toolbar-action-ghost"
              onClick={() => props.onHiddenChange(true)}
              type="button"
            >
              Hide
            </button>
            <button
              className="load-button"
              disabled={props.loading}
              onClick={props.onLoad}
              type="button"
            >
              {props.loading ? "Loading..." : "Load"}
            </button>
          </div>
        </div>
        </div>
        <div className="toolbar-strip">
          <div className="toolbar-strip-group">
            <span className="toolbar-strip-label">Source</span>
            <span className="toolbar-pill toolbar-pill-strong">
              {STRUCTURE_SOURCE_LABELS[resolvedStructureSource]}
            </span>
            <span className="toolbar-pill">Requested {STRUCTURE_SOURCE_LABELS[props.structureSource]}</span>
            {structureSourceChanged ? (
              <span className="toolbar-pill toolbar-pill-accent">Auto fallback</span>
            ) : null}
          </div>
          <div className="toolbar-strip-group">
            <span className="toolbar-strip-label">Display</span>
            <span className="toolbar-pill">{activeLayerCount} layers on</span>
            <span className="toolbar-pill">
              {props.emaEnabled ? props.emaLengths.trim() || "EMA On" : "EMA Off"}
            </span>
            <span className="toolbar-pill">Auto Fetch {props.autoViewportFetch ? "On" : "Off"}</span>
          </div>
          <div className="toolbar-strip-group">
            <span className="toolbar-strip-label">Status</span>
            <span className={requestStatusClass}>
              {props.requestStatusMessage ?? sourceSummary}
            </span>
          </div>
        </div>
      </div>

      {props.openPanel === "jump" ? (
        <div className="toolbar-popover">
          <div className="compact-row">
            <span className="mode-label">Selector</span>
            <div className="segmented">
              {(["session_date", "center_bar_id", "time_range"] as SelectorMode[]).map(
                (mode) => (
                  <button
                    className={mode === props.selectorMode ? "segment active" : "segment"}
                    key={mode}
                    onClick={() => props.onSelectorModeChange(mode)}
                    type="button"
                  >
                    {mode === "session_date"
                      ? "Session"
                      : mode === "center_bar_id"
                        ? "Bar"
                        : "Time"}
                  </button>
                ),
              )}
            </div>
          </div>

          <div className="toolbar-popover-grid">
            {props.selectorMode === "session_date" ? (
              <label className="field">
                <span>Session Date</span>
                <input
                  value={props.sessionDate}
                  onChange={(event) => props.onSessionDateChange(event.target.value)}
                  placeholder="20251117"
                />
              </label>
            ) : null}
            {props.selectorMode === "center_bar_id" ? (
              <label className="field">
                <span>Center Bar ID</span>
                <input
                  value={props.centerBarId}
                  onChange={(event) => props.onCenterBarIdChange(event.target.value)}
                  placeholder="29390399"
                />
              </label>
            ) : null}
            {props.selectorMode === "time_range" ? (
              <>
                <label className="field">
                  <span>Start Time (UTC s)</span>
                  <input
                    value={props.startTime}
                    onChange={(event) => props.onStartTimeChange(event.target.value)}
                    placeholder="1741228200"
                  />
                </label>
                <label className="field">
                  <span>End Time (UTC s)</span>
                  <input
                    value={props.endTime}
                    onChange={(event) => props.onEndTimeChange(event.target.value)}
                    placeholder="1741233600"
                  />
                </label>
              </>
            ) : null}
          </div>
        </div>
      ) : null}

      {props.openPanel === "display" ? (
        <div className="toolbar-popover">
          <div className="compact-grid">
            <label className="field">
              <span>Left Bars</span>
              <input
                value={props.leftBars}
                onChange={(event) => props.onLeftBarsChange(event.target.value)}
              />
            </label>
            <label className="field">
              <span>Right Bars</span>
              <input
                value={props.rightBars}
                onChange={(event) => props.onRightBarsChange(event.target.value)}
              />
            </label>
            <label className="field">
              <span>Buffer Bars</span>
              <input
                value={props.bufferBars}
                onChange={(event) => props.onBufferBarsChange(event.target.value)}
              />
            </label>
            <label className="field">
              <span>EMA Lengths</span>
              <input
                disabled={!props.emaEnabled}
                value={props.emaLengths}
                onChange={(event) => props.onEmaLengthsChange(event.target.value)}
                placeholder="9, 20, 50"
              />
            </label>
          </div>

          <div className="compact-row">
            <span className="mode-label">Indicators</span>
            <label className={props.emaEnabled ? "layer-pill active" : "layer-pill"}>
              <input
                checked={props.emaEnabled}
                onChange={(event) =>
                  props.onEmaEnabledChange(event.target.checked)
                }
                type="checkbox"
              />
              <span>EMA On</span>
            </label>
          </div>

          {props.emaEntries.length ? (
            <div className="compact-row">
              <span className="mode-label">Active EMAs</span>
              <div className="layer-pills">
                {props.emaEntries.map((entry) => (
                  <button
                    className={entry.selected ? "layer-pill active ema-pill-button" : "layer-pill ema-pill-button"}
                    key={entry.length}
                    onClick={() =>
                      props.onEmaSelect(entry.selected ? null : entry.length)
                    }
                    type="button"
                  >
                    <span
                      className="ema-pill-swatch"
                      style={{
                        backgroundColor: entry.style.strokeColor,
                        opacity: entry.style.visible ? entry.style.opacity : 0.28,
                      }}
                    />
                    <span>EMA {entry.length}</span>
                    <code>{entry.style.visible ? "On" : "Off"}</code>
                  </button>
                ))}
              </div>
            </div>
          ) : null}

          <div className="compact-row">
            <span className="mode-label">Viewport</span>
            <label className={props.autoViewportFetch ? "layer-pill active" : "layer-pill"}>
              <input
                checked={props.autoViewportFetch}
                onChange={(event) =>
                  props.onAutoViewportFetchChange(event.target.checked)
                }
                type="checkbox"
              />
              <span>Auto Fetch On Pan</span>
            </label>
          </div>
        </div>
      ) : null}

      {props.openPanel === "versions" ? (
        <div className="toolbar-popover">
          <p className="toolbar-note">
            Choose the rulebook explicitly. <code>Auto</code> prefers canonical artifacts when
            available and falls back to runtime v0.2 when they are not materialized. Canonical
            <code> v0.2 </code>
            artifacts are not materialized yet, so the live v0.2 path is currently
            <code> runtime_v0_2</code>.
          </p>
          <div className="source-grid">
            {STRUCTURE_SOURCE_OPTIONS.map((option) => {
              const selected = props.structureSource === option;
              const active = resolvedStructureSource === option;
              return (
                <button
                  className={selected ? "source-card selected" : "source-card"}
                  key={option}
                  onClick={() => props.onStructureSourceChange(option)}
                  type="button"
                >
                  <div className="source-card-head">
                    <strong>{STRUCTURE_SOURCE_LABELS[option]}</strong>
                    {active ? <span className="source-badge">Active</span> : null}
                  </div>
                  <p>{STRUCTURE_SOURCE_HINTS[option]}</p>
                </button>
              );
            })}
          </div>
          <div className="toolbar-callout">
            <span className="toolbar-status-label">Resolved Rulebook</span>
            <strong>{STRUCTURE_SOURCE_LABELS[resolvedStructureSource]}</strong>
            <span>
              Rulebook {props.resolvedRulebookVersion ?? "n/a"} · Structure{" "}
              {props.resolvedStructureVersion ?? "n/a"}
            </span>
          </div>
        </div>
      ) : null}

      {props.openPanel === "layers" ? (
        <div className="toolbar-popover">
          <p className="toolbar-note">
            Layer toggles follow the overlay payload returned by the backend for the current
            session/timeframe family and active structure source.
          </p>
          <div className="layer-pills">
            {(Object.keys(props.overlayLayers) as OverlayLayer[]).map((layer) => (
              <label
                className={props.overlayLayers[layer] ? "layer-pill active" : "layer-pill"}
                key={layer}
              >
                <input
                  checked={props.overlayLayers[layer]}
                  onChange={(event) =>
                    props.onOverlayLayerChange(layer, event.target.checked)
                  }
                  type="checkbox"
                />
                  <span>{OVERLAY_LAYER_LABELS[layer]}</span>
                <code>{props.overlayLayerCounts[layer]}</code>
              </label>
            ))}
          </div>
        </div>
      ) : null}

      {props.openPanel === "data" ? (
        <div className="toolbar-popover">
          <div className="compact-grid">
            <label className="field">
              <span>Symbol</span>
              <input
                value={props.symbol}
                onChange={(event) => props.onSymbolChange(event.target.value)}
              />
            </label>
            <label className="field">
              <span>Timeframe</span>
              <select
                value={props.timeframe}
                onChange={(event) => props.onTimeframeChange(event.target.value)}
              >
                {["1m", "2m", "3m", "5m", "10m", "15m"].map((option) => (
                  <option key={option} value={option}>
                    {option}
                  </option>
                ))}
              </select>
            </label>
            <label className="field">
              <span>Session Profile</span>
              <select
                value={props.sessionProfile}
                onChange={(event) =>
                  props.onSessionProfileChange(event.target.value as SessionProfile)
                }
              >
                <option value="eth_full">eth_full</option>
                <option value="rth">rth</option>
              </select>
            </label>
            <label className="field">
              <span>API Base</span>
              <input
                value={props.apiBaseUrl}
                onChange={(event) => props.onApiBaseUrlChange(event.target.value)}
              />
            </label>
            <label className="field">
              <span>Data Version</span>
              <input
                value={props.dataVersion}
                onChange={(event) => props.onDataVersionChange(event.target.value)}
              />
            </label>
          </div>
        </div>
      ) : null}
    </section>
  );
}
