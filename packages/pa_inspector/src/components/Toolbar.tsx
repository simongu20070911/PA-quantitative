import { useEffect, useMemo, useState } from "react";

import type {
  EmaStyle,
  InspectorToolbarPanel,
  OverlayLayer,
  SelectorMode,
  SessionProfile,
} from "../lib/types";

const OVERLAY_LABELS: Record<OverlayLayer, string> = {
  pivot: "Pivots",
  leg: "Legs",
  major_lh: "Major LH",
  breakout_start: "Breakouts",
};

export interface ToolbarProps {
  apiBaseUrl: string;
  onApiBaseUrlChange: (value: string) => void;
  dataVersion: string;
  onDataVersionChange: (value: string) => void;
  symbol: string;
  timeframe: string;
  sessionProfile: SessionProfile;
  onSymbolChange: (value: string) => void;
  onTimeframeChange: (value: string) => void;
  onSessionProfileChange: (value: SessionProfile) => void;
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
  initialOpenPanel: InspectorToolbarPanel;
  onOpenPanelChange: (panel: InspectorToolbarPanel) => void;
  loading: boolean;
  onLoad: () => void;
}

export function Toolbar(props: ToolbarProps) {
  const [openPanel, setOpenPanel] = useState<InspectorToolbarPanel>(
    props.initialOpenPanel,
  );

  useEffect(() => {
    props.onOpenPanelChange(openPanel);
  }, [openPanel, props]);

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

  function togglePanel(panel: Exclude<InspectorToolbarPanel, null>) {
    setOpenPanel((current) => (current === panel ? null : panel));
  }

  return (
    <section className="toolbar-card">
      <div className="toolbar-bar">
        <div className="toolbar-brand">
          <div>
            <p className="eyebrow">Explore</p>
            <h1>Continuous Structure View</h1>
          </div>
          <div className="toolbar-summary">
            <span className="toolbar-chip">
              <strong>{props.symbol}</strong>
              <code>{props.timeframe}</code>
            </span>
            <span className="toolbar-chip">{props.sessionProfile}</span>
            <span className="toolbar-chip">{selectorSummary}</span>
            <span className="toolbar-chip">Window {windowSummary}</span>
            <span className="toolbar-chip">
              EMA{" "}
              {props.emaEnabled
                ? props.emaLengths.trim() || "On"
                : "Off"}
            </span>
            <span className="toolbar-chip">
              Auto Fetch {props.autoViewportFetch ? "On" : "Off"}
            </span>
          </div>
        </div>

        <div className="toolbar-actions">
          <button
            className={openPanel === "jump" ? "toolbar-action active" : "toolbar-action"}
            onClick={() => togglePanel("jump")}
            type="button"
          >
            Jump
          </button>
          <button
            className={
              openPanel === "display" ? "toolbar-action active" : "toolbar-action"
            }
            onClick={() => togglePanel("display")}
            type="button"
          >
            Display
          </button>
          <button
            className={
              openPanel === "layers" ? "toolbar-action active" : "toolbar-action"
            }
            onClick={() => togglePanel("layers")}
            type="button"
          >
            Layers
            <code>{activeLayerCount}</code>
          </button>
          <button
            className={openPanel === "data" ? "toolbar-action active" : "toolbar-action"}
            onClick={() => togglePanel("data")}
            type="button"
          >
            Data
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

      {openPanel === "jump" ? (
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

      {openPanel === "display" ? (
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

      {openPanel === "layers" ? (
        <div className="toolbar-popover">
          <p className="toolbar-note">
            Layer toggles follow the overlay payload returned by the backend for the
            current session/timeframe family.
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
                <span>{OVERLAY_LABELS[layer]}</span>
                <code>{props.overlayLayerCounts[layer]}</code>
              </label>
            ))}
          </div>
        </div>
      ) : null}

      {openPanel === "data" ? (
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
