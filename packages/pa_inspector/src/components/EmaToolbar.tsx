import {
  type RefObject,
} from "react";

import {
  ANNOTATION_COLOR_PALETTE,
} from "../lib/annotationStyle";
import {
  ColorPopover,
  LineStylePreview,
  LineWidthPreview,
  StylePopover,
  WidthPopover,
  useFloatingToolbar,
} from "./toolbarShared";
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
  const {
    toolbarRef,
    openPopover,
    left,
    top,
    beginToolbarDrag,
    togglePopover,
    swallowPointer,
    activateButton,
    onToolbarPointerDown,
  } = useFloatingToolbar({
    active: emaLine !== null,
    hostRef,
    surfaceRef,
    toolbarWidth: TOOLBAR_WIDTH,
    toolbarHeight: TOOLBAR_HEIGHT,
    initialPosition,
    initialOpenPopover,
    onPositionChange,
    onOpenPopoverChange,
  });

  if (!emaLine) {
    return null;
  }

  const style = emaLine.style;

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
        <WidthPopover
          onSelect={(lineWidth) =>
            onEmaStyleChange(emaLine.length, { lineWidth })
          }
          selectedWidth={style.lineWidth}
        />
      ) : null}

      {openPopover === "style" ? (
        <StylePopover
          onSelect={(lineStyle) => onEmaStyleChange(emaLine.length, { lineStyle })}
          selectedStyle={style.lineStyle}
          showLabels={false}
          title="Line Style"
        />
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
