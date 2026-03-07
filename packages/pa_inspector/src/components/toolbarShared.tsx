import {
  useEffect,
  useRef,
  useState,
  type PointerEvent as ReactPointerEvent,
  type RefObject,
  type SyntheticEvent,
} from "react";

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
  hostRef: RefObject<HTMLElement | null>;
  surfaceRef: RefObject<HTMLDivElement | null>;
  toolbarWidth: number;
  toolbarHeight: number;
  initialPosition: FloatingPosition | null;
  initialOpenPopover: AnnotationToolbarPopover;
  onPositionChange: (position: FloatingPosition | null) => void;
  onOpenPopoverChange: (popover: AnnotationToolbarPopover) => void;
  dragFromContainerBackground?: boolean;
}

export function useFloatingToolbar({
  active,
  hostRef,
  surfaceRef,
  toolbarWidth,
  toolbarHeight,
  initialPosition,
  initialOpenPopover,
  onPositionChange,
  onOpenPopoverChange,
  dragFromContainerBackground = false,
}: UseFloatingToolbarArgs) {
  const toolbarRef = useRef<HTMLDivElement | null>(null);
  const dragCleanupRef = useRef<(() => void) | null>(null);
  const [position, setPosition] = useState<FloatingPosition | null>(initialPosition);
  const [openPopover, setOpenPopover] =
    useState<AnnotationToolbarPopover>(initialOpenPopover);

  useEffect(() => {
    if (!active) {
      setOpenPopover(null);
    }
  }, [active]);

  useEffect(() => {
    onPositionChange(position);
  }, [onPositionChange, position]);

  useEffect(() => {
    onOpenPopoverChange(openPopover);
  }, [onOpenPopoverChange, openPopover]);

  useEffect(() => {
    const host = hostRef.current;
    const surface = surfaceRef.current;
    if (!host || !surface) {
      return;
    }
    const bounds = resolveToolbarBounds(surface, toolbarWidth, toolbarHeight);
    const nextDefault = {
      left: bounds.maxLeft,
      top: bounds.minTop,
    };
    setPosition((current) =>
      current
        ? {
            left: clamp(current.left, bounds.minLeft, bounds.maxLeft),
            top: clamp(current.top, bounds.minTop, bounds.maxTop),
          }
        : nextDefault,
    );
  }, [active, hostRef, surfaceRef, toolbarHeight, toolbarWidth]);

  useEffect(() => {
    return () => {
      dragCleanupRef.current?.();
      dragCleanupRef.current = null;
    };
  }, []);

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

  const bounds = resolveToolbarBounds(
    surfaceRef.current,
    toolbarWidth,
    toolbarHeight,
  );
  const left = clamp(position?.left ?? bounds.maxLeft, bounds.minLeft, bounds.maxLeft);
  const top = clamp(position?.top ?? bounds.minTop, bounds.minTop, bounds.maxTop);

  const beginToolbarDrag = (event: ReactPointerEvent<HTMLElement>) => {
    if (event.button !== 0) {
      return;
    }
    const origin = { x: event.clientX, y: event.clientY };
    const startPosition = { left, top };
    event.preventDefault();
    event.stopPropagation();
    dragCleanupRef.current?.();

    let activeDrag = true;
    const onPointerMove = (moveEvent: PointerEvent) => {
      if (!activeDrag || moveEvent.buttons === 0) {
        stopDrag();
        return;
      }
      setPosition({
        left: clamp(
          startPosition.left + (moveEvent.clientX - origin.x),
          bounds.minLeft,
          bounds.maxLeft,
        ),
        top: clamp(
          startPosition.top + (moveEvent.clientY - origin.y),
          bounds.minTop,
          bounds.maxTop,
        ),
      });
    };

    const stopDrag = () => {
      if (!activeDrag) {
        return;
      }
      activeDrag = false;
      window.removeEventListener("pointermove", onPointerMove);
      window.removeEventListener("pointerup", stopDrag);
      window.removeEventListener("pointercancel", stopDrag);
      window.removeEventListener("mouseup", stopDrag);
      window.removeEventListener("blur", stopDrag);
      dragCleanupRef.current = null;
    };

    window.addEventListener("pointermove", onPointerMove);
    window.addEventListener("pointerup", stopDrag);
    window.addEventListener("pointercancel", stopDrag);
    window.addEventListener("mouseup", stopDrag);
    window.addEventListener("blur", stopDrag);
    dragCleanupRef.current = stopDrag;
  };

  const togglePopover = (key: AnnotationToolbarPopover) => {
    setOpenPopover((current) => (current === key ? null : key));
  };

  const swallowPointer = (event: SyntheticEvent<HTMLElement>) => {
    event.stopPropagation();
  };

  const activateButton = (
    event: ReactPointerEvent<HTMLElement>,
    action: () => void,
  ) => {
    event.preventDefault();
    event.stopPropagation();
    action();
  };

  const onToolbarPointerDown = (event: ReactPointerEvent<HTMLDivElement>) => {
    event.stopPropagation();
    if (dragFromContainerBackground && event.target === event.currentTarget) {
      beginToolbarDrag(event);
    }
  };

  return {
    toolbarRef,
    openPopover,
    setOpenPopover,
    left,
    top,
    beginToolbarDrag,
    togglePopover,
    swallowPointer,
    activateButton,
    onToolbarPointerDown,
  };
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
    <div className="annotation-toolbar-popover">
      <div className="annotation-toolbar-menu">
        {ANNOTATION_LINE_WIDTHS.map((widthValue) => (
          <button
            className={
              widthValue === selectedWidth
                ? "annotation-toolbar-menu-item active"
                : "annotation-toolbar-menu-item"
            }
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
    <div className="annotation-toolbar-popover">
      {title ? <div className="annotation-toolbar-popover-title">{title}</div> : null}
      <div className="annotation-toolbar-menu">
        {ANNOTATION_LINE_STYLES.map((styleKey) => (
          <button
            className={
              styleKey === selectedStyle
                ? "annotation-toolbar-menu-item active"
                : "annotation-toolbar-menu-item"
            }
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

export function lineStyleLabel(style: AnnotationLineStyle) {
  if (style === "dashed") {
    return "Dashed";
  }
  if (style === "dotted") {
    return "Dotted";
  }
  return "Solid";
}

function resolveToolbarBounds(
  surface: HTMLDivElement | null,
  toolbarWidth: number,
  toolbarHeight: number,
) {
  const minLeft = (surface?.offsetLeft ?? 0) + 12;
  const maxLeft = Math.max(
    minLeft,
    (surface?.offsetLeft ?? 0) +
      (surface?.clientWidth ?? toolbarWidth + 24) -
      toolbarWidth -
      12,
  );
  const minTop = (surface?.offsetTop ?? 0) + 12;
  const maxTop = Math.max(
    minTop,
    (surface?.offsetTop ?? 0) +
      (surface?.clientHeight ?? toolbarHeight + 24) -
      toolbarHeight -
      12,
  );
  return { minLeft, maxLeft, minTop, maxTop };
}

function clamp(value: number, min: number, max: number) {
  return Math.max(min, Math.min(max, value));
}
