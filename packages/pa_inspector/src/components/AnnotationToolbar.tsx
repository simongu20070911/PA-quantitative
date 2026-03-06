import {
  useEffect,
  useRef,
  useState,
  type PointerEvent as ReactPointerEvent,
  type RefObject,
} from "react";

import {
  ANNOTATION_COLOR_PALETTE,
  ANNOTATION_LINE_STYLES,
  ANNOTATION_LINE_WIDTHS,
  getAnnotationStyle,
  lineDashForStyle,
} from "../lib/annotationStyle";
import type {
  AnnotationLineStyle,
  AnnotationStyle,
  AnnotationToolbarPopover,
  ChartAnnotation,
  FloatingPosition,
} from "../lib/types";

interface AnnotationToolbarProps {
  hostRef: RefObject<HTMLElement | null>;
  surfaceRef: RefObject<HTMLDivElement | null>;
  annotation: ChartAnnotation | null;
  initialPosition: FloatingPosition | null;
  onPositionChange: (position: FloatingPosition | null) => void;
  initialOpenPopover: AnnotationToolbarPopover;
  onOpenPopoverChange: (popover: AnnotationToolbarPopover) => void;
  onAnnotationStyleChange: (
    annotationId: string,
    patch: Partial<AnnotationStyle>,
  ) => void;
  onAnnotationDuplicate: (annotationId: string) => string | null;
  onDeleteSelectedAnnotation: () => void;
}

const TOOLBAR_WIDTH = 496;
const TOOLBAR_HEIGHT = 52;

export function AnnotationToolbar({
  hostRef,
  surfaceRef,
  annotation,
  initialPosition,
  onPositionChange,
  initialOpenPopover,
  onOpenPopoverChange,
  onAnnotationStyleChange,
  onAnnotationDuplicate,
  onDeleteSelectedAnnotation,
}: AnnotationToolbarProps) {
  const toolbarRef = useRef<HTMLDivElement | null>(null);
  const dragCleanupRef = useRef<(() => void) | null>(null);
  const style = annotation ? getAnnotationStyle(annotation) : null;
  const [position, setPosition] = useState<FloatingPosition | null>(initialPosition);
  const [openPopover, setOpenPopover] =
    useState<AnnotationToolbarPopover>(initialOpenPopover);

  useEffect(() => {
    if (!annotation) {
      setOpenPopover(null);
    }
  }, [annotation]);

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
    const minLeft = surface.offsetLeft + 12;
    const maxLeft = Math.max(
      minLeft,
      surface.offsetLeft + surface.clientWidth - TOOLBAR_WIDTH - 12,
    );
    const minTop = surface.offsetTop + 12;
    const maxTop = Math.max(
      minTop,
      surface.offsetTop + surface.clientHeight - TOOLBAR_HEIGHT - 12,
    );
    const nextDefault = {
      left: maxLeft,
      top: minTop,
    };
    setPosition((current) =>
      current
        ? {
            left: clamp(current.left, minLeft, maxLeft),
            top: clamp(current.top, minTop, maxTop),
          }
        : nextDefault,
    );
  }, [annotation, hostRef, surfaceRef]);

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

  if (!annotation || !style) {
    return null;
  }

  const surface = surfaceRef.current;
  const minLeft = (surface?.offsetLeft ?? 0) + 12;
  const maxLeft = Math.max(
    minLeft,
    (surface?.offsetLeft ?? 0) + (surface?.clientWidth ?? TOOLBAR_WIDTH + 24) - TOOLBAR_WIDTH - 12,
  );
  const minTop = (surface?.offsetTop ?? 0) + 12;
  const maxTop = Math.max(
    minTop,
    (surface?.offsetTop ?? 0) + (surface?.clientHeight ?? TOOLBAR_HEIGHT + 24) - TOOLBAR_HEIGHT - 12,
  );
  const left = clamp(
    position?.left ?? maxLeft,
    minLeft,
    maxLeft,
  );
  const top = clamp(
    position?.top ?? minTop,
    minTop,
    maxTop,
  );

  const beginToolbarDrag = (
    event: ReactPointerEvent<HTMLElement>,
  ) => {
    if (event.button !== 0) {
      return;
    }
    const origin = { x: event.clientX, y: event.clientY };
    const startPosition = { left, top };
    event.preventDefault();
    event.stopPropagation();
    dragCleanupRef.current?.();

    let active = true;

    const onPointerMove = (moveEvent: PointerEvent) => {
      if (!active || moveEvent.buttons === 0) {
        stopDrag();
        return;
      }
      setPosition({
        left: clamp(
          startPosition.left + (moveEvent.clientX - origin.x),
          minLeft,
          maxLeft,
        ),
        top: clamp(
          startPosition.top + (moveEvent.clientY - origin.y),
          minTop,
          maxTop,
        ),
      });
    };

    const stopDrag = () => {
      if (!active) {
        return;
      }
      active = false;
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

  const swallowPointer = (event: ReactPointerEvent<HTMLDivElement>) => {
    event.stopPropagation();
  };

  const onToolbarPointerDown = (event: ReactPointerEvent<HTMLDivElement>) => {
    event.stopPropagation();
    if (event.target === event.currentTarget) {
      beginToolbarDrag(event);
    }
  };

  const activateButton = (
    event: ReactPointerEvent<HTMLElement>,
    action: () => void,
  ) => {
    event.preventDefault();
    event.stopPropagation();
    action();
  };

  return (
    <div
      className="annotation-toolbar"
      onClick={swallowPointer}
      onDoubleClick={swallowPointer}
      onPointerDown={onToolbarPointerDown}
      onPointerMove={swallowPointer}
      onPointerUp={swallowPointer}
      ref={toolbarRef}
      style={{ left: `${left}px`, top: `${top}px` }}
    >
      <button
        className="annotation-toolbar-grip"
        onPointerDown={beginToolbarDrag}
        title="Drag annotation toolbar"
        type="button"
      >
        <GripDotsIcon />
      </button>
      <button
        className="annotation-toolbar-button"
        onPointerDown={(event) => activateButton(event, () => togglePopover("stroke"))}
        title="Stroke color"
        type="button"
      >
        <StrokeIcon />
        <span
          className="annotation-toolbar-color-bar"
          style={{ backgroundColor: style.strokeColor }}
        />
      </button>
      <button
        className="annotation-toolbar-button"
        disabled={annotation.kind !== "box"}
        onPointerDown={(event) => activateButton(event, () => togglePopover("fill"))}
        title="Fill color"
        type="button"
      >
        <FillIcon />
        <span
          className="annotation-toolbar-color-bar"
          style={{
            backgroundColor: annotation.kind === "box" ? style.fillColor : "#cbd5e1",
          }}
        />
      </button>
      <button
        className="annotation-toolbar-button annotation-toolbar-width"
        onPointerDown={(event) => activateButton(event, () => togglePopover("width"))}
        title="Line width"
        type="button"
      >
        <LineWidthPreview width={style.lineWidth} />
        <span>{style.lineWidth}px</span>
      </button>
      <button
        className="annotation-toolbar-button"
        onPointerDown={(event) => activateButton(event, () => togglePopover("style"))}
        title="Line style"
        type="button"
      >
        <LineStylePreview styleKey={style.lineStyle} />
      </button>
      <button
        className="annotation-toolbar-button"
        onPointerDown={(event) => activateButton(event, () => togglePopover("opacity"))}
        title="Opacity"
        type="button"
      >
        <OpacityIcon />
        <span>{Math.round(style.opacity * 100)}%</span>
      </button>
      <button
        className="annotation-toolbar-button"
        onPointerDown={(event) =>
          activateButton(event, () => {
            const duplicateId = onAnnotationDuplicate(annotation.id);
            if (duplicateId) {
              setOpenPopover(null);
            }
          })
        }
        title="Duplicate"
        type="button"
      >
        <DuplicateIcon />
      </button>
      <button
        className={
          style.locked
            ? "annotation-toolbar-button active"
            : "annotation-toolbar-button"
        }
        onPointerDown={(event) =>
          activateButton(event, () =>
            onAnnotationStyleChange(annotation.id, { locked: !style.locked }),
          )
        }
        title={style.locked ? "Unlock drawing" : "Lock drawing"}
        type="button"
      >
        <LockIcon locked={style.locked} />
      </button>
      <button
        className="annotation-toolbar-button"
        onPointerDown={(event) => activateButton(event, onDeleteSelectedAnnotation)}
        title="Delete"
        type="button"
      >
        <TrashIcon />
      </button>

      {openPopover === "stroke" ? (
        <ColorPopover
          colors={ANNOTATION_COLOR_PALETTE}
          selectedColor={style.strokeColor}
          title="Stroke"
          onSelect={(color) => onAnnotationStyleChange(annotation.id, { strokeColor: color })}
        />
      ) : null}
      {openPopover === "fill" && annotation.kind === "box" ? (
        <ColorPopover
          colors={ANNOTATION_COLOR_PALETTE}
          selectedColor={style.fillColor}
          title="Fill"
          onSelect={(color) => onAnnotationStyleChange(annotation.id, { fillColor: color })}
        />
      ) : null}
      {openPopover === "width" ? (
        <div className="annotation-toolbar-popover">
          <div className="annotation-toolbar-menu">
            {ANNOTATION_LINE_WIDTHS.map((widthValue) => (
              <button
                className={
                  widthValue === style.lineWidth
                    ? "annotation-toolbar-menu-item active"
                    : "annotation-toolbar-menu-item"
                }
                key={widthValue}
                onPointerDown={(event) =>
                  activateButton(event, () =>
                    onAnnotationStyleChange(annotation.id, { lineWidth: widthValue }),
                  )
                }
                type="button"
              >
                <LineWidthPreview width={widthValue} />
                <span>{widthValue}px</span>
              </button>
            ))}
          </div>
        </div>
      ) : null}
      {openPopover === "style" ? (
        <div className="annotation-toolbar-popover">
          <div className="annotation-toolbar-menu">
            {ANNOTATION_LINE_STYLES.map((styleKey) => (
              <button
                className={
                  styleKey === style.lineStyle
                    ? "annotation-toolbar-menu-item active"
                    : "annotation-toolbar-menu-item"
                }
                key={styleKey}
                onPointerDown={(event) =>
                  activateButton(event, () =>
                    onAnnotationStyleChange(annotation.id, { lineStyle: styleKey }),
                  )
                }
                type="button"
              >
                <LineStylePreview styleKey={styleKey} />
                <span>{lineStyleLabel(styleKey)}</span>
              </button>
            ))}
          </div>
        </div>
      ) : null}
      {openPopover === "opacity" ? (
        <div className="annotation-toolbar-popover annotation-toolbar-popover-wide">
          <div className="annotation-toolbar-slider-block">
            <label className="annotation-toolbar-slider-label" htmlFor="annotation-opacity">
              Opacity
            </label>
            <input
              id="annotation-opacity"
              max="100"
              min="10"
              onPointerDownCapture={(event) => event.stopPropagation()}
              onChange={(event) =>
                onAnnotationStyleChange(annotation.id, {
                  opacity: Number(event.target.value) / 100,
                })
              }
              type="range"
              value={Math.round(style.opacity * 100)}
            />
          </div>
        </div>
      ) : null}
    </div>
  );
}

function ColorPopover({
  title,
  colors,
  selectedColor,
  onSelect,
}: {
  title: string;
  colors: string[];
  selectedColor: string;
  onSelect: (color: string) => void;
}) {
  return (
    <div className="annotation-toolbar-popover">
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

function lineStyleLabel(style: AnnotationLineStyle) {
  if (style === "dashed") {
    return "Dashed";
  }
  if (style === "dotted") {
    return "Dotted";
  }
  return "Solid";
}

function clamp(value: number, min: number, max: number) {
  return Math.max(min, Math.min(max, value));
}

function GripDotsIcon() {
  return (
    <svg aria-hidden="true" className="annotation-toolbar-icon" viewBox="0 0 16 16">
      {[3, 8, 13].flatMap((y) => [4, 8, 12].map((x) => (
        <circle cx={x} cy={y} fill="currentColor" key={`${x}-${y}`} r="1" />
      )))}
    </svg>
  );
}

function StrokeIcon() {
  return (
    <svg aria-hidden="true" className="annotation-toolbar-icon" viewBox="0 0 20 20" fill="none">
      <path d="M5 14L15 4" stroke="currentColor" strokeLinecap="round" strokeWidth="1.8" />
      <circle cx="5" cy="14" fill="currentColor" r="1.8" />
      <circle cx="15" cy="4" fill="currentColor" r="1.8" />
    </svg>
  );
}

function FillIcon() {
  return (
    <svg aria-hidden="true" className="annotation-toolbar-icon" viewBox="0 0 20 20" fill="none">
      <path
        d="M6 6.5L10 3L14 6.5V12.5L10 16L6 12.5V6.5Z"
        stroke="currentColor"
        strokeWidth="1.6"
      />
      <path d="M6.4 12.4H13.6" stroke="currentColor" strokeWidth="1.6" />
    </svg>
  );
}

function DuplicateIcon() {
  return (
    <svg aria-hidden="true" className="annotation-toolbar-icon" viewBox="0 0 20 20" fill="none">
      <rect height="9" rx="1.5" stroke="currentColor" strokeWidth="1.5" width="9" x="7" y="4" />
      <rect height="9" rx="1.5" stroke="currentColor" strokeWidth="1.5" width="9" x="4" y="7" />
    </svg>
  );
}

function LockIcon({ locked }: { locked: boolean }) {
  return (
    <svg aria-hidden="true" className="annotation-toolbar-icon" viewBox="0 0 20 20" fill="none">
      <path
        d="M6 9V7.6C6 5.61 7.57 4 9.5 4C11.43 4 13 5.61 13 7.6V9"
        stroke="currentColor"
        strokeWidth="1.5"
      />
      <rect
        height="8"
        rx="1.8"
        stroke="currentColor"
        strokeWidth="1.5"
        width="10"
        x="5"
        y="9"
      />
      {locked ? <circle cx="10" cy="13" fill="currentColor" r="1.2" /> : null}
    </svg>
  );
}

function TrashIcon() {
  return (
    <svg aria-hidden="true" className="annotation-toolbar-icon" viewBox="0 0 20 20" fill="none">
      <path d="M5 6H15" stroke="currentColor" strokeLinecap="round" strokeWidth="1.6" />
      <path d="M7 6V4.5H13V6" stroke="currentColor" strokeWidth="1.6" />
      <path d="M6.5 6L7.4 16H12.6L13.5 6" stroke="currentColor" strokeWidth="1.6" />
    </svg>
  );
}

function OpacityIcon() {
  return (
    <svg aria-hidden="true" className="annotation-toolbar-icon" viewBox="0 0 20 20" fill="none">
      <path
        d="M10 3C13.59 7.02 15 9.38 15 11.5C15 14.54 12.76 17 10 17C7.24 17 5 14.54 5 11.5C5 9.38 6.41 7.02 10 3Z"
        stroke="currentColor"
        strokeWidth="1.5"
      />
      <path d="M10 5.5V16.4" stroke="currentColor" strokeWidth="1.4" />
    </svg>
  );
}

function LineWidthPreview({ width }: { width: number }) {
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

function LineStylePreview({ styleKey }: { styleKey: AnnotationLineStyle }) {
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
