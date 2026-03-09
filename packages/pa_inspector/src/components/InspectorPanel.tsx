import { useEffect, useLayoutEffect, useRef, useState } from "react";

import type {
  ChartBar,
  FloatingPosition,
  InspectorMode,
  Overlay,
  StructureDetailResponse,
} from "../lib/types";

export interface InspectorPanelProps {
  overlay: Overlay | null;
  anchorPoint: { x: number; y: number } | null;
  initialPosition: FloatingPosition;
  initialManualPosition: boolean;
  onPositionChange: (position: FloatingPosition) => void;
  onManualPositionChange: (manual: boolean) => void;
  inspectorMode: InspectorMode;
  replayCursorBar: ChartBar | null;
  replayBackendResolved: boolean;
  detail: StructureDetailResponse | null;
  loading: boolean;
  error: string | null;
  onClose: () => void;
}

export function InspectorPanel({
  overlay,
  anchorPoint,
  initialPosition,
  initialManualPosition,
  onPositionChange,
  onManualPositionChange,
  inspectorMode,
  replayCursorBar,
  replayBackendResolved,
  detail,
  loading,
  error,
  onClose,
}: InspectorPanelProps) {
  const panelRef = useRef<HTMLElement | null>(null);
  const dragHandleRef = useRef<HTMLDivElement | null>(null);
  const hasInitializedOverlayRef = useRef(false);
  const onPositionChangeRef = useRef(onPositionChange);
  const onManualPositionChangeRef = useRef(onManualPositionChange);
  const [position, setPosition] = useState(initialPosition);
  const [manualPosition, setManualPosition] = useState(initialManualPosition);
  const overlayKey = overlay?.overlay_id ?? null;

  useEffect(() => {
    onPositionChangeRef.current = onPositionChange;
  }, [onPositionChange]);

  useEffect(() => {
    onManualPositionChangeRef.current = onManualPositionChange;
  }, [onManualPositionChange]);

  useEffect(() => {
    onPositionChangeRef.current(position);
  }, [position]);

  useEffect(() => {
    onManualPositionChangeRef.current(manualPosition);
  }, [manualPosition]);

  useLayoutEffect(() => {
    const panel = panelRef.current;
    if (!panel || !anchorPoint || manualPosition) {
      return;
    }
    const parent = panel.offsetParent;
    if (!(parent instanceof HTMLElement)) {
      return;
    }
    const panelRect = panel.getBoundingClientRect();
    const parentRect = parent.getBoundingClientRect();
    const gap = 14;
    const preferRight = anchorPoint.x + gap + panelRect.width <= parentRect.width - gap;
    const preferBelow = anchorPoint.y + gap + panelRect.height <= parentRect.height - gap;
    let left = preferRight
      ? anchorPoint.x + gap
      : anchorPoint.x - panelRect.width - gap;
    let top = preferBelow
      ? anchorPoint.y + gap
      : anchorPoint.y - panelRect.height - gap;
    left = Math.max(gap, Math.min(left, parentRect.width - panelRect.width - gap));
    top = Math.max(gap, Math.min(top, parentRect.height - panelRect.height - gap));
    setPosition({ left, top });
  }, [anchorPoint, detail, error, loading, manualPosition, overlay]);

  useEffect(() => {
    if (!hasInitializedOverlayRef.current) {
      hasInitializedOverlayRef.current = true;
      return;
    }
    setManualPosition(false);
  }, [anchorPoint, overlayKey]);

  useEffect(() => {
    const handle = dragHandleRef.current;
    const panel = panelRef.current;
    if (!handle || !panel) {
      return;
    }

    const onPointerDown = (event: PointerEvent) => {
      if (event.button !== 0) {
        return;
      }
      const target = event.target;
      if (target instanceof HTMLElement && target.closest("button")) {
        return;
      }
      const parent = panel.offsetParent;
      if (!(parent instanceof HTMLElement)) {
        return;
      }
      const panelRect = panel.getBoundingClientRect();
      const parentRect = parent.getBoundingClientRect();
      const offsetX = event.clientX - panelRect.left;
      const offsetY = event.clientY - panelRect.top;
      setManualPosition(true);
      handle.setPointerCapture(event.pointerId);

      const onPointerMove = (moveEvent: PointerEvent) => {
        const nextLeft = moveEvent.clientX - parentRect.left - offsetX;
        const nextTop = moveEvent.clientY - parentRect.top - offsetY;
        const gap = 14;
        setPosition({
          left: Math.max(gap, Math.min(nextLeft, parentRect.width - panelRect.width - gap)),
          top: Math.max(gap, Math.min(nextTop, parentRect.height - panelRect.height - gap)),
        });
      };

      const stopDrag = (endEvent: PointerEvent) => {
        if (handle.hasPointerCapture(endEvent.pointerId)) {
          handle.releasePointerCapture(endEvent.pointerId);
        }
        handle.removeEventListener("pointermove", onPointerMove);
        handle.removeEventListener("pointerup", stopDrag);
        handle.removeEventListener("pointercancel", stopDrag);
      };

      handle.addEventListener("pointermove", onPointerMove);
      handle.addEventListener("pointerup", stopDrag);
      handle.addEventListener("pointercancel", stopDrag);
    };

    handle.addEventListener("pointerdown", onPointerDown);
    return () => {
      handle.removeEventListener("pointerdown", onPointerDown);
    };
  }, []);

  if (!overlay && !detail && !loading && !error) {
    return null;
  }

  return (
    <aside
      className="panel-card panel-popup"
      ref={panelRef}
      style={{ left: `${position.left}px`, top: `${position.top}px` }}
    >
      <div className="panel-head panel-drag-handle" ref={dragHandleRef}>
        <div>
          <p className="eyebrow">Selection</p>
          <h2>Structure Detail</h2>
        </div>
        <div className="panel-actions">
          {overlay ? <span className="badge">{overlay.kind}</span> : null}
          <button className="panel-close" onClick={onClose} type="button">
            Close
          </button>
        </div>
      </div>

      {!overlay ? (
        <p className="panel-empty">
          Click an overlay marker or line to inspect the source structure and provenance.
        </p>
      ) : null}

      {overlay ? (
        <div className="stat-grid">
          <div className="stat-card">
            <span className="stat-label">Overlay ID</span>
            <code>{overlay.overlay_id}</code>
          </div>
          <div className="stat-card">
            <span className="stat-label">Structure ID</span>
            <code>{overlay.source_structure_id}</code>
          </div>
          <div className="stat-card">
            <span className="stat-label">Style</span>
            <code>{overlay.style_key}</code>
          </div>
          <div className="stat-card">
            <span className="stat-label">Overlay Version</span>
            <code>{overlay.overlay_version}</code>
          </div>
        </div>
      ) : null}

      {loading ? <p className="panel-status">Loading structure evidence...</p> : null}
      {error ? <p className="panel-error">{error}</p> : null}

      {detail ? (
        <div className="detail-stack">
          <div className="detail-block">
            <h3>Summary</h3>
            <dl className="detail-list">
              <div>
                <dt>Kind</dt>
                <dd>{detail.structure.kind}</dd>
              </div>
              <div>
                <dt>State</dt>
                <dd>{detail.structure.state}</dd>
              </div>
              <div>
                <dt>Anchor Bars</dt>
                <dd>{detail.structure.anchor_bar_ids.join(", ")}</dd>
              </div>
              <div>
                <dt>Confirm Bar</dt>
                <dd>{detail.structure.confirm_bar_id ?? "None"}</dd>
              </div>
            </dl>
          </div>

          {inspectorMode === "replay" ? (
            <div className="detail-block">
              <h3>Replay Context</h3>
              <dl className="detail-list">
                <div>
                  <dt>Cursor Bar</dt>
                  <dd>{replayCursorBar?.bar_id ?? "None"}</dd>
                </div>
                <div>
                  <dt>Cursor Time</dt>
                  <dd>
                    {replayCursorBar
                      ? new Date(replayCursorBar.time * 1000).toLocaleString("en-US", {
                          month: "short",
                          day: "2-digit",
                          hour: "2-digit",
                          minute: "2-digit",
                          hour12: false,
                          timeZone: "UTC",
                        })
                      : "None"}
                  </dd>
                </div>
                <div>
                  <dt>Replay State</dt>
                  <dd>{replayBackendResolved ? "Backend-resolved" : "UI transport preview"}</dd>
                </div>
              </dl>
            </div>
          ) : null}

          <div className="detail-block">
            <h3>Explanation Codes</h3>
            <div className="chip-row">
              {detail.structure.explanation_codes.map((code) => (
                <span className="chip" key={code}>
                  {code}
                </span>
              ))}
            </div>
          </div>

          <div className="detail-block">
            <h3>Versions</h3>
            <dl className="detail-list">
              <div>
                <dt>Data</dt>
                <dd>{detail.versions.data_version}</dd>
              </div>
              <div>
                <dt>Feature</dt>
                <dd>{detail.versions.feature_version}</dd>
              </div>
              <div>
                <dt>Params Hash</dt>
                <dd>{detail.versions.feature_params_hash}</dd>
              </div>
              <div>
                <dt>Rulebook</dt>
                <dd>{detail.versions.rulebook_version}</dd>
              </div>
              <div>
                <dt>Structure</dt>
                <dd>{detail.versions.structure_version}</dd>
              </div>
            </dl>
          </div>

          <div className="detail-block">
            <h3>Refs</h3>
            <p className="detail-caption">Feature refs: {detail.feature_refs.length}</p>
            <p className="detail-caption">Structure refs: {detail.structure_refs.length}</p>
          </div>
        </div>
      ) : null}
    </aside>
  );
}
