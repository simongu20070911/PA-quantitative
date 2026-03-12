import { useMemo, type ReactNode } from "react";

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
  showReplayRetiredOverlays: boolean;
  onShowReplayRetiredOverlaysChange: (value: boolean) => void;
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
            <span className="toolbar-menubar-mode">
              {props.inspectorMode === "replay" ? "Replay" : "Explore"}
            </span>
            <strong className="toolbar-menubar-title">Continuous Structure View</strong>
            <div className="toolbar-inline-meta">
              <span className="toolbar-tag toolbar-tag-strong toolbar-chip-tight">
                {props.symbol} {props.timeframe}
              </span>
              <span className="toolbar-tag toolbar-chip-tight">{props.sessionProfile}</span>
              {props.requestStatusMessage ? (
                <span className={`${collapsedStatusClass} toolbar-chip-tight`}>
                  {props.requestStatusMessage}
                </span>
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
      <div className="toolbar-menubar">
        <div className="toolbar-menubar-group toolbar-menubar-group-left">
          <span className="toolbar-menubar-mode">
            {props.inspectorMode === "replay" ? "Replay" : "Explore"}
          </span>
          <strong className="toolbar-menubar-title">Continuous Structure View</strong>
          <div className="toolbar-inline-meta toolbar-inline-meta-compact">
            <span className="toolbar-tag toolbar-tag-strong toolbar-chip-tight">
              {props.symbol} {props.timeframe} · {props.sessionProfile}
            </span>
            <span className="toolbar-tag toolbar-chip-tight">{selectorSummary}</span>
            <span className="toolbar-tag toolbar-chip-tight">Win {windowSummary}</span>
          </div>
        </div>

        <div className="toolbar-menubar-group toolbar-menubar-group-right">
          <div className="segmented toolbar-segmented-mode toolbar-segmented-mode-compact">
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

          <div className="toolbar-menu-actions" role="toolbar" aria-label="Inspector menus">
            <ToolbarMenuButton
              active={props.openPanel === "jump"}
              badge={props.selectorMode === "session_date" ? "S" : props.selectorMode === "center_bar_id" ? "#" : "T"}
              icon={<JumpIcon />}
              label="Jump"
              onClick={() => togglePanel("jump")}
            />
            <ToolbarMenuButton
              active={props.openPanel === "display"}
              badge={props.emaEnabled ? "EMA" : undefined}
              icon={<DisplayIcon />}
              label="Display"
              onClick={() => togglePanel("display")}
            />
            <ToolbarMenuButton
              active={props.openPanel === "versions"}
              badge={structureSourceChanged ? "Auto" : undefined}
              icon={<VersionIcon />}
              label="Version"
              onClick={() => togglePanel("versions")}
            />
            <ToolbarMenuButton
              active={props.openPanel === "layers"}
              badge={String(activeLayerCount)}
              icon={<LayersMenuIcon />}
              label="Layers"
              onClick={() => togglePanel("layers")}
            />
            <ToolbarMenuButton
              active={props.openPanel === "data"}
              icon={<DataIcon />}
              label="Data"
              onClick={() => togglePanel("data")}
            />
            <button
              className="toolbar-menu-button toolbar-menu-button-ghost"
              onClick={() => props.onHiddenChange(true)}
              type="button"
              title="Hide controls"
            >
              <EyeOffIcon />
            </button>
            <button
              className="load-button load-button-compact"
              disabled={props.loading}
              onClick={props.onLoad}
              type="button"
            >
              <LoadIcon />
              <span>{props.loading ? "Loading" : "Load"}</span>
            </button>
          </div>

          <div className="toolbar-statusline">
            <span className="toolbar-pill toolbar-chip-tight">{structureVersionLabel}</span>
            <span className="toolbar-pill toolbar-chip-tight toolbar-pill-strong">
              {STRUCTURE_SOURCE_LABELS[resolvedStructureSource]}
            </span>
            {structureSourceChanged ? (
              <span className="toolbar-pill toolbar-chip-tight toolbar-pill-accent">
                Requested {STRUCTURE_SOURCE_LABELS[props.structureSource]}
              </span>
            ) : null}
            <span className={`${requestStatusClass} toolbar-chip-tight`}>
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

          {props.inspectorMode === "replay" ? (
            <div className="compact-row">
              <span className="mode-label">Replay</span>
              <label
                className={
                  props.showReplayRetiredOverlays ? "layer-pill active" : "layer-pill"
                }
              >
                <input
                  checked={props.showReplayRetiredOverlays}
                  onChange={(event) =>
                    props.onShowReplayRetiredOverlaysChange(event.target.checked)
                  }
                  type="checkbox"
                />
                <span>Show Cancelled Pivots</span>
              </label>
            </div>
          ) : null}
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

interface ToolbarMenuButtonProps {
  active: boolean;
  badge?: string;
  icon: ReactNode;
  label: string;
  onClick: () => void;
}

function ToolbarMenuButton(props: ToolbarMenuButtonProps) {
  return (
    <button
      aria-label={props.label}
      className={props.active ? "toolbar-menu-button active" : "toolbar-menu-button"}
      onClick={props.onClick}
      title={props.label}
      type="button"
    >
      {props.icon}
      {props.badge ? <span className="toolbar-menu-badge">{props.badge}</span> : null}
    </button>
  );
}

function JumpIcon() {
  return (
    <svg aria-hidden="true" viewBox="0 0 18 18">
      <path
        d="M4 13.5 13.5 4m0 0H7m6.5 0V11"
        fill="none"
        stroke="currentColor"
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth="1.7"
      />
    </svg>
  );
}

function DisplayIcon() {
  return (
    <svg aria-hidden="true" viewBox="0 0 18 18">
      <path
        d="M4 5.5h10M6 9h8m-6 3.5h6"
        fill="none"
        stroke="currentColor"
        strokeLinecap="round"
        strokeWidth="1.8"
      />
      <circle cx="6" cy="5.5" r="1.5" fill="currentColor" />
      <circle cx="8" cy="9" r="1.5" fill="currentColor" />
      <circle cx="10" cy="12.5" r="1.5" fill="currentColor" />
    </svg>
  );
}

function VersionIcon() {
  return (
    <svg aria-hidden="true" viewBox="0 0 18 18">
      <path
        d="m4 11 3-4 2.25 2.5L14 5"
        fill="none"
        stroke="currentColor"
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth="1.8"
      />
      <path
        d="M4 14h10"
        fill="none"
        stroke="currentColor"
        strokeLinecap="round"
        strokeWidth="1.4"
      />
    </svg>
  );
}

function LayersMenuIcon() {
  return (
    <svg aria-hidden="true" viewBox="0 0 18 18">
      <path
        d="m9 3 5 2.8L9 8.6 4 5.8 9 3Zm0 5.4 5 2.8L9 14 4 11.2 9 8.4Z"
        fill="none"
        stroke="currentColor"
        strokeLinejoin="round"
        strokeWidth="1.5"
      />
    </svg>
  );
}

function DataIcon() {
  return (
    <svg aria-hidden="true" viewBox="0 0 18 18">
      <ellipse cx="9" cy="4.5" rx="4.75" ry="2.25" fill="none" stroke="currentColor" strokeWidth="1.5" />
      <path
        d="M4.25 4.5v5c0 1.25 2.13 2.25 4.75 2.25s4.75-1 4.75-2.25v-5"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.5"
      />
      <path
        d="M4.25 9.5v4c0 1.25 2.13 2.25 4.75 2.25s4.75-1 4.75-2.25v-4"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.5"
      />
    </svg>
  );
}

function EyeOffIcon() {
  return (
    <svg aria-hidden="true" viewBox="0 0 18 18">
      <path
        d="M3.5 3.5 14.5 14.5M6.2 6.2A6.8 6.8 0 0 1 9 5.6c3.1 0 5.6 2.1 6.75 3.4a.85.85 0 0 1 0 1.04 13.6 13.6 0 0 1-2.86 2.48M8 8a1.6 1.6 0 0 0 2 2"
        fill="none"
        stroke="currentColor"
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth="1.5"
      />
      <path
        d="M5.1 12.1A13.2 13.2 0 0 1 2.25 10.04a.85.85 0 0 1 0-1.04c.58-.66 1.5-1.49 2.68-2.18"
        fill="none"
        stroke="currentColor"
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth="1.5"
      />
    </svg>
  );
}

function LoadIcon() {
  return (
    <svg aria-hidden="true" viewBox="0 0 18 18">
      <path
        d="M9 3.5v7m0 0 2.8-2.8M9 10.5 6.2 7.7M4 13.8h10"
        fill="none"
        stroke="currentColor"
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth="1.7"
      />
    </svg>
  );
}
