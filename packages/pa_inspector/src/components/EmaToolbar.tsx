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
  lineDashForStyle,
} from "../lib/annotationStyle";
import type {
  AnnotationToolbarPopover,
  EmaStyle,
  FloatingPosition,
  RenderedEmaLine,
} from "../lib/types";

interface EmaToolbarProps {
  hostRef: RefObject<HTMLElement | null>;
  surfaceRef: RefObject<HTMLDivElement | null>;
  emaLine: RenderedEmaLine | null;
  initialPosition: FloatingPosition | null;
  onPositionChange: (position: FloatingPosition | null) => void;
  initialOpenPopover: AnnotationToolbarPopover;
  onOpenPopoverChange: (popover: AnnotationToolbarPopover) => void;
  onEmaStyleChange: (length: number, patch: Partial<EmaStyle>) => void;
}

const TOOLBAR_WIDTH = 420;
const TOOLBAR_HEIGHT = 52;

export function EmaToolbar({
  hostRef,
  surfaceRef,
  emaLine,
  initialPosition,
  onPositionChange,
  initialOpenPopover,
  onOpenPopoverChange,
  onEmaStyleChange,
}: EmaToolbarProps) {
  const toolbarRef = useRef<HTMLDivElement | null>(null);
  const dragCleanupRef = useRef<(() => void) | null>(null);
  const [position, setPosition] = useState<FloatingPosition | null>(initialPosition);
  const [openPopover, setOpenPopover] =
    useState<AnnotationToolbarPopover>(initialOpenPopover);

  useEffect(() => {
    if (!emaLine) {
      setOpenPopover(null);
    }
  }, [emaLine]);

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
    const nextDefault = { left: maxLeft, top: minTop };
    setPosition((current) =>
      current
        ? {
            left: clamp(current.left, minLeft, maxLeft),
            top: clamp(current.top, minTop, maxTop),
          }
        : nextDefault,
    );
  }, [emaLine, hostRef, surfaceRef]);

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

  if (!emaLine) {
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
  const left = clamp(position?.left ?? maxLeft, minLeft, maxLeft);
  const top = clamp(position?.top ?? minTop, minTop, maxTop);

  const beginToolbarDrag = (event: ReactPointerEvent<HTMLElement>) => {
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
        left: clamp(startPosition.left + (moveEvent.clientX - origin.x), minLeft, maxLeft),
        top: clamp(startPosition.top + (moveEvent.clientY - origin.y), minTop, maxTop),
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

  const activateButton = (
    event: ReactPointerEvent<HTMLElement>,
    action: () => void,
  ) => {
    event.preventDefault();
    event.stopPropagation();
    action();
  };

  const swallowPointer = (event: ReactPointerEvent<HTMLDivElement>) => {
    event.stopPropagation();
  };

  const style = emaLine.style;

  return (
    <div
      className="annotation-toolbar"
      onClick={swallowPointer}
      onDoubleClick={swallowPointer}
      onPointerDown={swallowPointer}
      onPointerMove={swallowPointer}
      onPointerUp={swallowPointer}
      ref={toolbarRef}
      style={{ left: `${left}px`, top: `${top}px` }}
    >
      <button
        className="annotation-toolbar-grip"
        onPointerDown={beginToolbarDrag}
        title="Drag EMA toolbar"
        type="button"
      >
        ::
      </button>
      <button className="annotation-toolbar-button" disabled type="button">
        <span>EMA {emaLine.length}</span>
      </button>
      <button
        className="annotation-toolbar-button"
        onPointerDown={(event) => activateButton(event, () => togglePopover("stroke"))}
        title="Stroke color"
        type="button"
      >
        <span>Color</span>
        <span
          className="annotation-toolbar-color-bar"
          style={{ backgroundColor: style.strokeColor }}
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
        <span>{Math.round(style.opacity * 100)}%</span>
      </button>
      <button
        className={style.visible ? "annotation-toolbar-button active" : "annotation-toolbar-button"}
        onPointerDown={(event) =>
          activateButton(event, () =>
            onEmaStyleChange(emaLine.length, { visible: !style.visible }),
          )
        }
        title="Toggle visibility"
        type="button"
      >
        <span>{style.visible ? "Shown" : "Hidden"}</span>
      </button>

      {openPopover === "stroke" ? (
        <div className="annotation-toolbar-popover annotation-toolbar-popover-wide">
          <div className="annotation-toolbar-popover-title">EMA Color</div>
          <div className="annotation-toolbar-color-grid">
            {ANNOTATION_COLOR_PALETTE.map((color) => (
              <button
                className={
                  color === style.strokeColor
                    ? "annotation-toolbar-color-swatch active"
                    : "annotation-toolbar-color-swatch"
                }
                key={color}
                onPointerDown={(event) =>
                  activateButton(event, () => onEmaStyleChange(emaLine.length, { strokeColor: color }))
                }
                style={{ backgroundColor: color }}
                type="button"
              />
            ))}
          </div>
        </div>
      ) : null}

      {openPopover === "width" ? (
        <div className="annotation-toolbar-popover">
          <div className="annotation-toolbar-popover-title">Line Width</div>
          <div className="annotation-toolbar-menu">
            {ANNOTATION_LINE_WIDTHS.map((width) => (
              <button
                className={
                  width === style.lineWidth
                    ? "annotation-toolbar-menu-item active"
                    : "annotation-toolbar-menu-item"
                }
                key={width}
                onPointerDown={(event) =>
                  activateButton(event, () => onEmaStyleChange(emaLine.length, { lineWidth: width }))
                }
                type="button"
              >
                <LineWidthPreview width={width} />
                <span>{width}px</span>
              </button>
            ))}
          </div>
        </div>
      ) : null}

      {openPopover === "style" ? (
        <div className="annotation-toolbar-popover">
          <div className="annotation-toolbar-popover-title">Line Style</div>
          <div className="annotation-toolbar-menu">
            {ANNOTATION_LINE_STYLES.map((lineStyle) => (
              <button
                className={
                  lineStyle === style.lineStyle
                    ? "annotation-toolbar-menu-item active"
                    : "annotation-toolbar-menu-item"
                }
                key={lineStyle}
                onPointerDown={(event) =>
                  activateButton(event, () =>
                    onEmaStyleChange(emaLine.length, { lineStyle }),
                  )
                }
                type="button"
              >
                <LineStylePreview styleKey={lineStyle} />
              </button>
            ))}
          </div>
        </div>
      ) : null}

      {openPopover === "opacity" ? (
        <div className="annotation-toolbar-popover">
          <div className="annotation-toolbar-popover-title">Opacity</div>
          <div className="annotation-toolbar-slider-block">
            <label className="annotation-toolbar-slider-label" htmlFor="ema-opacity-slider">
              {Math.round(style.opacity * 100)}%
            </label>
            <input
              id="ema-opacity-slider"
              max="1"
              min="0.1"
              onChange={(event) =>
                onEmaStyleChange(emaLine.length, {
                  opacity: Number(event.target.value),
                })
              }
              step="0.05"
              type="range"
              value={style.opacity}
            />
          </div>
        </div>
      ) : null}
    </div>
  );
}

function clamp(value: number, min: number, max: number) {
  return Math.max(min, Math.min(max, value));
}

function LineWidthPreview({ width }: { width: number }) {
  return (
    <svg className="annotation-toolbar-line-preview" viewBox="0 0 36 12">
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

function LineStylePreview({ styleKey }: { styleKey: EmaStyle["lineStyle"] }) {
  return (
    <svg className="annotation-toolbar-line-preview" viewBox="0 0 36 12">
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
