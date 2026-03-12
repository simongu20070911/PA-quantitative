import {
  useEffect,
  useRef,
  useState,
  type PointerEvent as ReactPointerEvent,
  type ReactNode,
  type RefObject,
  type SyntheticEvent,
} from "react";

import {
  clampFloatingPosition,
  resolveFloatingSurfaceBounds,
  resolveFloatingSurfaceDefaultPosition,
  useDraggableFloatingSurface,
  useFloatingSurfacePosition,
} from "../lib/floatingSurface";
import {
  ANNOTATION_LINE_STYLES,
  ANNOTATION_LINE_WIDTHS,
  lineDashForStyle,
} from "../lib/annotationStyle";
import type {
  AnnotationLineStyle,
  AnnotationToolbarPopover,
  FloatingPosition,
} from "../lib/types";

interface UseFloatingToolbarArgs {
  active: boolean;
  surfaceRef: RefObject<HTMLDivElement | null>;
  toolbarWidth: number;
  toolbarHeight: number;
  initialPosition: FloatingPosition | null;
  initialOpenPopover: AnnotationToolbarPopover;
  onPositionChange: (position: FloatingPosition | null) => void;
  onOpenPopoverChange: (popover: AnnotationToolbarPopover) => void;
  dragFromContainerBackground?: boolean;
  clampInset?: number;
}

export interface FloatingToolbarState {
  toolbarRef: RefObject<HTMLDivElement | null>;
  openPopover: AnnotationToolbarPopover;
  setOpenPopover: (popover: AnnotationToolbarPopover) => void;
  left: number;
  top: number;
  togglePopover: (key: AnnotationToolbarPopover) => void;
  swallowPointer: (event: SyntheticEvent<HTMLElement>) => void;
  activateButton: (event: ReactToolbarPointerEvent, action: () => void) => void;
}

type ReactToolbarPointerEvent = ReactPointerEvent<HTMLElement>;

export function useFloatingToolbar({
  active,
  surfaceRef,
  toolbarWidth,
  toolbarHeight,
  initialPosition,
  initialOpenPopover,
  onPositionChange,
  onOpenPopoverChange,
  dragFromContainerBackground = false,
  clampInset = 8,
}: UseFloatingToolbarArgs): FloatingToolbarState {
  const toolbarRef = useRef<HTMLDivElement | null>(null);
  const onOpenPopoverChangeRef = useRef(onOpenPopoverChange);
  const { position, setPosition } = useFloatingSurfacePosition({
    initialPosition,
    onPositionChange,
  });
  const [openPopover, setOpenPopover] =
    useState<AnnotationToolbarPopover>(initialOpenPopover);

  useEffect(() => {
    onOpenPopoverChangeRef.current = onOpenPopoverChange;
  }, [onOpenPopoverChange]);

  useEffect(() => {
    if (!active) {
      setOpenPopover(null);
    }
  }, [active]);

  useEffect(() => {
    onOpenPopoverChangeRef.current(openPopover);
  }, [openPopover]);

  useEffect(() => {
    const bounds = resolveFloatingSurfaceBounds(surfaceRef.current, {
      surfaceWidth: toolbarWidth,
      surfaceHeight: toolbarHeight,
      clampInset,
    });
    const defaultPosition = resolveFloatingSurfaceDefaultPosition(bounds);
    setPosition((current) =>
      current === null ? defaultPosition : clampFloatingPosition(current, bounds),
    );
  }, [active, clampInset, setPosition, surfaceRef, toolbarHeight, toolbarWidth]);

  useEffect(() => {
    if (!openPopover) {
      return;
    }
    const onPointerDown = (event: PointerEvent) => {
      const toolbar = toolbarRef.current;
      if (toolbar?.contains(event.target as Node)) {
        return;
      }
      setOpenPopover(null);
    };
    window.addEventListener("pointerdown", onPointerDown);
    return () => {
      window.removeEventListener("pointerdown", onPointerDown);
    };
  }, [openPopover]);

  useDraggableFloatingSurface({
    handleRef: toolbarRef,
    surfaceRef: toolbarRef,
    setPosition,
    boundsResolver: () =>
      resolveFloatingSurfaceBounds(surfaceRef.current, {
        surfaceWidth: toolbarWidth,
        surfaceHeight: toolbarHeight,
        clampInset,
      }),
    canStartDrag: (event) => {
      const toolbar = toolbarRef.current;
      if (!toolbar) {
        return false;
      }
      const target = event.target;
      if (!(target instanceof HTMLElement)) {
        return false;
      }
      if (target.closest("[data-floating-surface-interactive='true']")) {
        return false;
      }
      if (target.closest("[data-floating-surface-drag-handle='true']")) {
        return true;
      }
      return dragFromContainerBackground && target === toolbar;
    },
  });

  const bounds = resolveFloatingSurfaceBounds(surfaceRef.current, {
    surfaceWidth: toolbarWidth,
    surfaceHeight: toolbarHeight,
    clampInset,
  });
  const nextPosition = clampFloatingPosition(position ?? resolveFloatingSurfaceDefaultPosition(bounds), bounds);

  return {
    toolbarRef,
    openPopover,
    setOpenPopover,
    left: nextPosition.left,
    top: nextPosition.top,
    togglePopover: (key) => {
      setOpenPopover((current) => (current === key ? null : key));
    },
    swallowPointer: (event) => {
      event.stopPropagation();
    },
    activateButton: (event, action) => {
      event.preventDefault();
      event.stopPropagation();
      action();
    },
  };
}

export function FloatingToolbarShell({
  state,
  dragTitle,
  grip,
  children,
}: {
  state: FloatingToolbarState;
  dragTitle: string;
  grip: ReactNode;
  children: ReactNode;
}) {
  return (
    <div
      className="annotation-toolbar"
      onClick={state.swallowPointer}
      onDoubleClick={state.swallowPointer}
      onPointerDown={state.swallowPointer}
      onPointerMove={state.swallowPointer}
      onPointerUp={state.swallowPointer}
      ref={state.toolbarRef}
      style={{ left: `${state.left}px`, top: `${state.top}px` }}
    >
      <button
        className="annotation-toolbar-grip"
        data-floating-surface-drag-handle="true"
        title={dragTitle}
        type="button"
      >
        {grip}
      </button>
      {children}
    </div>
  );
}

export function ToolbarGripIcon() {
  return (
    <svg aria-hidden="true" className="annotation-toolbar-icon" viewBox="0 0 16 16">
      {[3, 8, 13].flatMap((y) =>
        [4, 8, 12].map((x) => (
          <circle cx={x} cy={y} fill="currentColor" key={`${x}-${y}`} r="1" />
        )),
      )}
    </svg>
  );
}

export function ToolbarButton({
  className,
  active = false,
  disabled = false,
  title,
  onPointerDown,
  children,
}: {
  className?: string;
  active?: boolean;
  disabled?: boolean;
  title: string;
  onPointerDown?: (event: ReactToolbarPointerEvent) => void;
  children: ReactNode;
}) {
  return (
    <button
      className={
        active
          ? ["annotation-toolbar-button", className, "active"].filter(Boolean).join(" ")
          : ["annotation-toolbar-button", className].filter(Boolean).join(" ")
      }
      data-floating-surface-interactive="true"
      disabled={disabled}
      onPointerDown={onPointerDown}
      title={title}
      type="button"
    >
      {children}
    </button>
  );
}

export function ColorPopover({
  title,
  colors,
  selectedColor,
  onSelect,
  wide = false,
}: {
  title: string;
  colors: string[];
  selectedColor: string;
  onSelect: (color: string) => void;
  wide?: boolean;
}) {
  return (
    <div
      className={
        wide
          ? "annotation-toolbar-popover annotation-toolbar-popover-wide"
          : "annotation-toolbar-popover"
      }
      data-floating-surface-interactive="true"
    >
      <div className="annotation-toolbar-popover-title">{title}</div>
      <div className="annotation-toolbar-color-grid">
        {colors.map((color) => (
          <button
            className={
              color === selectedColor
                ? "annotation-toolbar-color-swatch active"
                : "annotation-toolbar-color-swatch"
            }
            data-floating-surface-interactive="true"
            key={color}
            onPointerDown={(event) => {
              event.preventDefault();
              event.stopPropagation();
              onSelect(color);
            }}
            style={{ backgroundColor: color }}
            type="button"
          />
        ))}
      </div>
    </div>
  );
}

export function WidthPopover({
  selectedWidth,
  onSelect,
}: {
  selectedWidth: number;
  onSelect: (width: number) => void;
}) {
  return (
    <div className="annotation-toolbar-popover" data-floating-surface-interactive="true">
      <div className="annotation-toolbar-menu">
        {ANNOTATION_LINE_WIDTHS.map((widthValue) => (
          <button
            className={
              widthValue === selectedWidth
                ? "annotation-toolbar-menu-item active"
                : "annotation-toolbar-menu-item"
            }
            data-floating-surface-interactive="true"
            key={widthValue}
            onPointerDown={(event) => {
              event.preventDefault();
              event.stopPropagation();
              onSelect(widthValue);
            }}
            type="button"
          >
            <LineWidthPreview width={widthValue} />
            <span>{widthValue}px</span>
          </button>
        ))}
      </div>
    </div>
  );
}

export function StylePopover({
  selectedStyle,
  onSelect,
  showLabels = true,
  title,
}: {
  selectedStyle: AnnotationLineStyle;
  onSelect: (style: AnnotationLineStyle) => void;
  showLabels?: boolean;
  title?: string;
}) {
  return (
    <div className="annotation-toolbar-popover" data-floating-surface-interactive="true">
      {title ? <div className="annotation-toolbar-popover-title">{title}</div> : null}
      <div className="annotation-toolbar-menu">
        {ANNOTATION_LINE_STYLES.map((styleKey) => (
          <button
            className={
              styleKey === selectedStyle
                ? "annotation-toolbar-menu-item active"
                : "annotation-toolbar-menu-item"
            }
            data-floating-surface-interactive="true"
            key={styleKey}
            onPointerDown={(event) => {
              event.preventDefault();
              event.stopPropagation();
              onSelect(styleKey);
            }}
            type="button"
          >
            <LineStylePreview styleKey={styleKey} />
            {showLabels ? <span>{lineStyleLabel(styleKey)}</span> : null}
          </button>
        ))}
      </div>
    </div>
  );
}

export function SliderPopover({
  title,
  id,
  min,
  max,
  step,
  value,
  label,
  wide = false,
  onChange,
}: {
  title: string;
  id: string;
  min: number | string;
  max: number | string;
  step?: number | string;
  value: number | string;
  label: ReactNode;
  wide?: boolean;
  onChange: (value: string) => void;
}) {
  return (
    <div
      className={
        wide
          ? "annotation-toolbar-popover annotation-toolbar-popover-wide"
          : "annotation-toolbar-popover"
      }
      data-floating-surface-interactive="true"
    >
      <div className="annotation-toolbar-popover-title">{title}</div>
      <div className="annotation-toolbar-slider-block">
        <label className="annotation-toolbar-slider-label" htmlFor={id}>
          {label}
        </label>
        <input
          data-floating-surface-interactive="true"
          id={id}
          max={max}
          min={min}
          onChange={(event) => onChange(event.target.value)}
          onPointerDownCapture={(event) => event.stopPropagation()}
          step={step}
          type="range"
          value={value}
        />
      </div>
    </div>
  );
}

export function LineWidthPreview({ width }: { width: number }) {
  return (
    <svg aria-hidden="true" className="annotation-toolbar-line-preview" viewBox="0 0 36 12">
      <line
        stroke="currentColor"
        strokeLinecap="round"
        strokeWidth={width}
        x1="4"
        x2="32"
        y1="6"
        y2="6"
      />
    </svg>
  );
}

export function LineStylePreview({ styleKey }: { styleKey: AnnotationLineStyle }) {
  return (
    <svg aria-hidden="true" className="annotation-toolbar-line-preview" viewBox="0 0 36 12">
      <line
        stroke="currentColor"
        strokeDasharray={lineDashForStyle(styleKey).join(" ")}
        strokeLinecap="round"
        strokeWidth="2"
        x1="4"
        x2="32"
        y1="6"
        y2="6"
      />
    </svg>
  );
}

export function lineStyleLabel(styleKey: AnnotationLineStyle) {
  switch (styleKey) {
    case "solid":
      return "Solid";
    case "dashed":
      return "Dashed";
    case "dotted":
      return "Dotted";
    default:
      return styleKey;
  }
}
