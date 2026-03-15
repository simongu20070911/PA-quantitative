import { useEffect, useRef, useState, type ReactNode } from "react";

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

type LineTool = Extract<
  AnnotationTool,
  "line" | "parallel_lines" | "horizontal_line" | "vertical_line"
>;

const LINE_TOOL_OPTIONS: Array<{
  tool: LineTool;
  label: string;
  description: string;
  icon: ReactNode;
}> = [
  {
    tool: "line",
    label: "Trend Line",
    description: "Two-point line",
    icon: <LineIcon />,
  },
  {
    tool: "parallel_lines",
    label: "Parallel Lines",
    description: "Twin parallel guides",
    icon: <ParallelLinesIcon />,
  },
  {
    tool: "horizontal_line",
    label: "Horizontal Line",
    description: "Level across chart",
    icon: <HorizontalLineIcon />,
  },
  {
    tool: "vertical_line",
    label: "Vertical Line",
    description: "Time marker",
    icon: <VerticalLineIcon />,
  },
];

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
  const lineMenuRef = useRef<HTMLDivElement | null>(null);
  const [lineMenuOpen, setLineMenuOpen] = useState(false);
  const [lastLineTool, setLastLineTool] = useState<LineTool>("line");
  const { position, setPosition } = useFloatingSurfacePosition({
    initialPosition,
    onPositionChange,
  });

  useEffect(() => {
    if (isLineTool(annotationTool)) {
      setLastLineTool(annotationTool);
    }
  }, [annotationTool]);

  useEffect(() => {
    if (!lineMenuOpen) {
      return;
    }
    const onPointerDown = (event: PointerEvent) => {
      const rail = railRef.current;
      const menu = lineMenuRef.current;
      if (
        event.target instanceof Node &&
        ((rail && rail.contains(event.target)) || (menu && menu.contains(event.target)))
      ) {
        return;
      }
      setLineMenuOpen(false);
    };
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setLineMenuOpen(false);
      }
    };
    window.addEventListener("pointerdown", onPointerDown);
    window.addEventListener("keydown", onKeyDown);
    return () => {
      window.removeEventListener("pointerdown", onPointerDown);
      window.removeEventListener("keydown", onKeyDown);
    };
  }, [lineMenuOpen]);

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

  const lineToolActive =
    annotationTool === "line" ||
    annotationTool === "parallel_lines" ||
    annotationTool === "horizontal_line" ||
    annotationTool === "vertical_line";

  const activeLineTool = isLineTool(annotationTool) ? annotationTool : lastLineTool;
  const activeLineOption =
    LINE_TOOL_OPTIONS.find((option) => option.tool === activeLineTool) ?? LINE_TOOL_OPTIONS[0];

  const selectLineTool = (tool: LineTool) => {
    setLastLineTool(tool);
    onToolChange(tool);
    setLineMenuOpen(false);
  };

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
          onClick={() => {
            setLineMenuOpen(false);
            onToolChange("none");
          }}
          title="Cursor"
          type="button"
        >
          <CursorIcon />
        </button>
        <div className="annotation-rail-button-slot">
          <button
            className={
              lineToolActive || lineMenuOpen
                ? "annotation-rail-button annotation-rail-button-line-main active"
                : "annotation-rail-button annotation-rail-button-line-main"
            }
            onClick={() => {
              setLineMenuOpen(false);
              onToolChange(activeLineTool);
            }}
            title={activeLineOption.label}
            type="button"
          >
            {activeLineOption.icon}
          </button>
          <button
            aria-expanded={lineMenuOpen}
            aria-haspopup="menu"
            className={
              lineMenuOpen
                ? "annotation-rail-button-corner annotation-rail-button-corner-active"
                : "annotation-rail-button-corner"
            }
            onPointerDown={(event) => {
              event.preventDefault();
              event.stopPropagation();
              setLineMenuOpen((open) => !open);
            }}
            title="Open line tools"
            type="button"
          >
            <MiniChevronIcon />
          </button>
          {lineMenuOpen ? (
            <div
              className="annotation-rail-flyout annotation-rail-flyout-line"
              ref={lineMenuRef}
              role="menu"
              aria-label="Line tools"
            >
              {LINE_TOOL_OPTIONS.map((option) => {
                const active = annotationTool === option.tool;
                return (
                  <button
                    key={option.tool}
                    className={
                      active
                        ? "annotation-rail-flyout-item active"
                        : "annotation-rail-flyout-item"
                    }
                    onClick={() => selectLineTool(option.tool)}
                    type="button"
                  >
                    <span className="annotation-rail-flyout-icon">{option.icon}</span>
                    <span className="annotation-rail-flyout-copy">
                      <span className="annotation-rail-flyout-label">{option.label}</span>
                      <span className="annotation-rail-flyout-description">
                        {option.description}
                      </span>
                    </span>
                  </button>
                );
              })}
            </div>
          ) : null}
        </div>
        <button
          className={
            annotationTool === "box"
              ? "annotation-rail-button active"
              : "annotation-rail-button"
          }
          onClick={() => {
            setLineMenuOpen(false);
            onToolChange("box");
          }}
          title="Range box"
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
          onClick={() => {
            setLineMenuOpen(false);
            onToolChange("fib50");
          }}
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

function isLineTool(tool: AnnotationTool): tool is LineTool {
  return (
    tool === "line" ||
    tool === "parallel_lines" ||
    tool === "horizontal_line" ||
    tool === "vertical_line"
  );
}

function GripIcon() {
  return (
    <svg aria-hidden="true" className="annotation-rail-icon" viewBox="0 0 20 20" fill="none">
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
    <svg aria-hidden="true" className="annotation-rail-icon" viewBox="0 0 20 20" fill="none">
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
    <svg aria-hidden="true" className="annotation-rail-icon" viewBox="0 0 20 20" fill="none">
      <path d="M4 15L15.5 4.5" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" />
      <circle cx="4" cy="15" r="2" fill="currentColor" />
      <circle cx="15.5" cy="4.5" r="2" fill="currentColor" />
    </svg>
  );
}

function HorizontalLineIcon() {
  return (
    <svg aria-hidden="true" className="annotation-rail-icon" viewBox="0 0 20 20" fill="none">
      <path d="M3.5 10H16.5" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" />
      <circle cx="10" cy="10" r="1.8" fill="currentColor" />
    </svg>
  );
}

function ParallelLinesIcon() {
  return (
    <svg aria-hidden="true" className="annotation-rail-icon" viewBox="0 0 20 20" fill="none">
      <path d="M4.5 14.5L13.5 5.5" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
      <path d="M6.5 16.5L15.5 7.5" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
      <circle cx="4.5" cy="14.5" r="1.6" fill="currentColor" />
      <circle cx="13.5" cy="5.5" r="1.6" fill="currentColor" />
    </svg>
  );
}

function VerticalLineIcon() {
  return (
    <svg aria-hidden="true" className="annotation-rail-icon" viewBox="0 0 20 20" fill="none">
      <path d="M10 3.5V16.5" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" />
      <circle cx="10" cy="10" r="1.8" fill="currentColor" />
    </svg>
  );
}

function MiniChevronIcon() {
  return (
    <svg aria-hidden="true" className="annotation-rail-mini-icon" viewBox="0 0 12 12" fill="none">
      <path
        d="M3.5 4.5L6 7L8.5 4.5"
        stroke="currentColor"
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth="1.4"
      />
    </svg>
  );
}

function BoxIcon() {
  return (
    <svg aria-hidden="true" className="annotation-rail-icon" viewBox="0 0 20 20" fill="none">
      <rect x="4" y="5" width="12" height="10" rx="1.5" stroke="currentColor" strokeWidth="1.5" />
    </svg>
  );
}

function Fib50Icon() {
  return (
    <svg aria-hidden="true" className="annotation-rail-icon" viewBox="0 0 20 20" fill="none">
      <path d="M4 5.5H16" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
      <path d="M6.5 10H13.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
      <path d="M4 14.5H16" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  );
}

function TrashIcon() {
  return (
    <svg aria-hidden="true" className="annotation-rail-icon" viewBox="0 0 20 20" fill="none">
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
    <svg aria-hidden="true" className="annotation-rail-icon" viewBox="0 0 20 20" fill="none">
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
