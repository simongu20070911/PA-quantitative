import { useRef } from "react";

import {
  resolveFloatingSurfaceBounds,
  useDraggableFloatingSurface,
  useFloatingSurfacePosition,
} from "../lib/floatingSurface";
import type { AnnotationTool, FloatingPosition } from "../lib/types";

interface AnnotationRailProps {
  annotationTool: AnnotationTool;
  annotationCount: number;
  hasSelection: boolean;
  initialPosition: FloatingPosition;
  onPositionChange: (position: FloatingPosition) => void;
  onToolChange: (tool: AnnotationTool) => void;
  onDeleteSelected: () => void;
  onClearAll: () => void;
}

export function AnnotationRail({
  annotationTool,
  annotationCount,
  hasSelection,
  initialPosition,
  onPositionChange,
  onToolChange,
  onDeleteSelected,
  onClearAll,
}: AnnotationRailProps) {
  const railRef = useRef<HTMLElement | null>(null);
  const gripRef = useRef<HTMLButtonElement | null>(null);
  const { position, setPosition } = useFloatingSurfacePosition({
    initialPosition,
    onPositionChange,
  });

  useDraggableFloatingSurface({
    handleRef: gripRef,
    surfaceRef: railRef,
    setPosition,
    boundsResolver: (surface) => {
      const parent = surface.offsetParent;
      if (!(parent instanceof HTMLElement)) {
        return null;
      }
      return resolveFloatingSurfaceBounds(parent, {
        surfaceWidth: surface.offsetWidth,
        surfaceHeight: surface.offsetHeight,
        clampInset: 8,
      });
    },
  });

  return (
    <aside
      className="annotation-rail"
      ref={railRef}
      style={{ left: `${position.left}px`, top: `${position.top}px` }}
    >
      <button
        className="annotation-rail-grip"
        ref={gripRef}
        title="Drag tool panel"
        type="button"
      >
        <GripIcon />
      </button>
      <div className="annotation-rail-group">
        <button
          className={
            annotationTool === "none"
              ? "annotation-rail-button active"
              : "annotation-rail-button"
          }
          onClick={() => onToolChange("none")}
          title="Cursor"
          type="button"
        >
          <CursorIcon />
        </button>
        <button
          className={
            annotationTool === "line"
              ? "annotation-rail-button active"
              : "annotation-rail-button"
          }
          onClick={() => onToolChange("line")}
          title="Line"
          type="button"
        >
          <LineIcon />
        </button>
        <button
          className={
            annotationTool === "box"
              ? "annotation-rail-button active"
              : "annotation-rail-button"
          }
          onClick={() => onToolChange("box")}
          title="Box"
          type="button"
        >
          <BoxIcon />
        </button>
        <button
          className={
            annotationTool === "fib50"
              ? "annotation-rail-button active"
              : "annotation-rail-button"
          }
          onClick={() => onToolChange("fib50")}
          title="50% levels"
          type="button"
        >
          <Fib50Icon />
        </button>
      </div>

      <div className="annotation-rail-group">
        <button
          className="annotation-rail-button"
          disabled={!hasSelection}
          onClick={onDeleteSelected}
          title="Delete selected drawing"
          type="button"
        >
          <TrashIcon />
        </button>
        <button
          className="annotation-rail-button"
          disabled={annotationCount === 0}
          onClick={onClearAll}
          title="Clear drawings on this chart family"
          type="button"
        >
          <LayersIcon />
          <span className="annotation-rail-count">{annotationCount}</span>
        </button>
      </div>
    </aside>
  );
}

function GripIcon() {
  return (
    <svg
      aria-hidden="true"
      className="annotation-rail-icon"
      viewBox="0 0 20 20"
      fill="none"
    >
      <circle cx="7" cy="6" r="1.2" fill="currentColor" />
      <circle cx="13" cy="6" r="1.2" fill="currentColor" />
      <circle cx="7" cy="10" r="1.2" fill="currentColor" />
      <circle cx="13" cy="10" r="1.2" fill="currentColor" />
      <circle cx="7" cy="14" r="1.2" fill="currentColor" />
      <circle cx="13" cy="14" r="1.2" fill="currentColor" />
    </svg>
  );
}

function CursorIcon() {
  return (
    <svg
      aria-hidden="true"
      className="annotation-rail-icon"
      viewBox="0 0 20 20"
      fill="none"
    >
      <path
        d="M4 3.5L13.5 10.4L9.3 10.9L11.8 16.2L9.8 17.2L7.3 11.9L4.5 15.1L4 3.5Z"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function LineIcon() {
  return (
    <svg
      aria-hidden="true"
      className="annotation-rail-icon"
      viewBox="0 0 20 20"
      fill="none"
    >
      <path
        d="M4 15L15.5 4.5"
        stroke="currentColor"
        strokeWidth="1.7"
        strokeLinecap="round"
      />
      <circle cx="4" cy="15" r="2" fill="currentColor" />
      <circle cx="15.5" cy="4.5" r="2" fill="currentColor" />
    </svg>
  );
}

function BoxIcon() {
  return (
    <svg
      aria-hidden="true"
      className="annotation-rail-icon"
      viewBox="0 0 20 20"
      fill="none"
    >
      <rect
        x="4"
        y="5"
        width="12"
        height="10"
        rx="1.5"
        stroke="currentColor"
        strokeWidth="1.5"
      />
    </svg>
  );
}

function Fib50Icon() {
  return (
    <svg
      aria-hidden="true"
      className="annotation-rail-icon"
      viewBox="0 0 20 20"
      fill="none"
    >
      <path d="M4 5.5H16" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
      <path d="M6.5 10H13.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
      <path d="M4 14.5H16" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  );
}

function TrashIcon() {
  return (
    <svg
      aria-hidden="true"
      className="annotation-rail-icon"
      viewBox="0 0 20 20"
      fill="none"
    >
      <path
        d="M6.5 6H13.5L13 15.5H7L6.5 6Z"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinejoin="round"
      />
      <path
        d="M5 6H15M8 6V4.5H12V6"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function LayersIcon() {
  return (
    <svg
      aria-hidden="true"
      className="annotation-rail-icon"
      viewBox="0 0 20 20"
      fill="none"
    >
      <path
        d="M4 8L10 4L16 8L10 12L4 8Z"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinejoin="round"
      />
      <path
        d="M6 11.5L10 14L14 11.5M7 14L10 16L13 14"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}
