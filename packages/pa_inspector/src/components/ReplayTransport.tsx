import type { ChartBar } from "../lib/types";

const SPEED_OPTIONS = [0.5, 1, 2, 4] as const;

export interface ReplayTransportProps {
  visible: boolean;
  hasBars: boolean;
  hasEvents: boolean;
  cursorBar: ChartBar | null;
  playing: boolean;
  speed: number;
  backendResolved: boolean;
  playbackMode: string | null;
  playbackStepTimeframe: string | null;
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
  const stepLabel =
    props.playbackStepTimeframe && props.playbackStepTimeframe !== "1m"
      ? props.playbackStepTimeframe
      : props.playbackStepTimeframe ?? "step";
  const stepDescription =
    props.playbackMode === "lower_family_steps" && props.playbackStepTimeframe
      ? `${props.playbackStepTimeframe} playback`
      : props.playbackMode === "selected_family_steps"
        ? "bar-close playback"
        : "playback";

  return (
    <div className="replay-transport">
      <div className="replay-transport-main">
        <div className="replay-transport-controls">
          <button
            className="transport-button"
            disabled={!props.hasEvents || !props.backendResolved || props.playing}
            type="button"
            onClick={() => props.onStepEvent(-1)}
          >
            Prev Event
          </button>
          <button
            className="transport-button"
            disabled={!props.cursorBar || !props.backendResolved || props.playing}
            type="button"
            onClick={() => props.onStepBar(-1)}
          >
            Prev {stepLabel}
          </button>
          <button
            className="transport-button transport-button-primary"
            disabled={!props.cursorBar || !props.backendResolved}
            type="button"
            onClick={props.onTogglePlaying}
          >
            {props.playing ? "Pause" : "Play"}
          </button>
          <button
            className="transport-button"
            disabled={!props.cursorBar || !props.backendResolved || props.playing}
            type="button"
            onClick={() => props.onStepBar(1)}
          >
            Next {stepLabel}
          </button>
          <button
            className="transport-button"
            disabled={!props.hasEvents || !props.backendResolved || props.playing}
            type="button"
            onClick={() => props.onStepEvent(1)}
          >
            Next Event
          </button>
          <button
            className="transport-button"
            disabled={!props.hasBars || props.playing}
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
          <span className="transport-chip">{stepDescription}</span>
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
        {!props.cursorBar
          ? "Click empty chart space to choose a replay start point. Future bars stay visible only while you are choosing the cursor."
          : props.playing
            ? "Replay is running. Pause first before moving the replay cursor or jumping around the timeline."
          : props.backendResolved
            ? "Replay is showing backend-authored playback steps plus backend-resolved structure state. Future bars stay hidden after the active cursor."
            : "Replay is waiting for backend replay frames for this window. Future bars will stay hidden once the replay view is ready."}
      </p>
    </div>
  );
}
