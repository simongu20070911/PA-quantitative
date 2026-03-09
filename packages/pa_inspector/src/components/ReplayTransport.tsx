import type { ChartBar } from "../lib/types";

const SPEED_OPTIONS = [0.5, 1, 2, 4] as const;

export interface ReplayTransportProps {
  visible: boolean;
  hasBars: boolean;
  cursorBar: ChartBar | null;
  playing: boolean;
  speed: number;
  backendResolved: boolean;
  onTogglePlaying: () => void;
  onStepBar: (direction: -1 | 1) => void;
  onStepEvent: (direction: -1 | 1) => void;
  onSpeedChange: (speed: number) => void;
  onJumpToLatest: () => void;
}

export function ReplayTransport(props: ReplayTransportProps) {
  if (!props.visible) {
    return null;
  }

  const cursorLabel = props.cursorBar
    ? `bar ${props.cursorBar.bar_id}`
    : "No cursor";
  const cursorDate = props.cursorBar
    ? new Date(props.cursorBar.time * 1000).toLocaleString("en-US", {
        month: "short",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
        hour12: false,
        timeZone: "UTC",
      })
    : "Awaiting bars";

  return (
    <div className="replay-transport">
      <div className="replay-transport-main">
        <div className="replay-transport-controls">
          <button
            className="transport-button"
            disabled
            title="Replay event stepping will activate once backend lifecycle reads are wired."
            type="button"
            onClick={() => props.onStepEvent(-1)}
          >
            Prev Event
          </button>
          <button
            className="transport-button"
            disabled={!props.cursorBar}
            type="button"
            onClick={() => props.onStepBar(-1)}
          >
            Prev Bar
          </button>
          <button
            className="transport-button transport-button-primary"
            disabled={!props.cursorBar}
            type="button"
            onClick={props.onTogglePlaying}
          >
            {props.playing ? "Pause" : "Play"}
          </button>
          <button
            className="transport-button"
            disabled={!props.cursorBar}
            type="button"
            onClick={() => props.onStepBar(1)}
          >
            Next Bar
          </button>
          <button
            className="transport-button"
            disabled
            title="Replay event stepping will activate once backend lifecycle reads are wired."
            type="button"
            onClick={() => props.onStepEvent(1)}
          >
            Next Event
          </button>
          <button
            className="transport-button"
            disabled={!props.hasBars}
            type="button"
            onClick={props.onJumpToLatest}
          >
            Latest
          </button>
        </div>

        <div className="replay-transport-meta">
          <span className="transport-chip">
            Cursor <strong>{cursorLabel}</strong>
          </span>
          <span className="transport-chip">{cursorDate}</span>
          <label className="transport-speed">
            <span>Speed</span>
            <select
              value={String(props.speed)}
              onChange={(event) => props.onSpeedChange(Number(event.target.value))}
            >
              {SPEED_OPTIONS.map((speed) => (
                <option key={speed} value={String(speed)}>
                  {speed}x
                </option>
              ))}
            </select>
          </label>
        </div>
      </div>

      <p className="replay-transport-note">
        {props.backendResolved
          ? "Replay is showing backend-resolved structure state, and future bars are hidden after the active cursor."
          : props.cursorBar
            ? "Replay is waiting for the backend-resolved cursor load. Future bars will stay hidden once the replay snapshot arrives."
            : "Click empty chart space to choose a replay start point. Future bars stay visible only while you are choosing the cursor."}
      </p>
    </div>
  );
}
