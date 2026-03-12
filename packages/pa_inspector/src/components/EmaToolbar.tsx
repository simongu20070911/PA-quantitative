import { ANNOTATION_COLOR_PALETTE } from "../lib/annotationStyle";
import {
  ColorPopover,
  FloatingToolbarShell,
  LineStylePreview,
  LineWidthPreview,
  SliderPopover,
  StylePopover,
  ToolbarButton,
  ToolbarGripIcon,
  WidthPopover,
  useFloatingToolbar,
} from "./toolbarShared";
import type {
  AnnotationToolbarPopover,
  EmaStyle,
  FloatingPosition,
  RenderedEmaLine,
} from "../lib/types";
import type { RefObject } from "react";

interface EmaToolbarProps {
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
  surfaceRef,
  emaLine,
  initialPosition,
  onPositionChange,
  initialOpenPopover,
  onOpenPopoverChange,
  onEmaStyleChange,
}: EmaToolbarProps) {
  const toolbar = useFloatingToolbar({
    active: emaLine !== null,
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
    <FloatingToolbarShell
      dragTitle="Drag EMA toolbar"
      grip={<ToolbarGripIcon />}
      state={toolbar}
    >
      <ToolbarButton disabled title={`EMA ${emaLine.length}`}>
        <span>EMA {emaLine.length}</span>
      </ToolbarButton>
      <ToolbarButton
        onPointerDown={(event) => toolbar.activateButton(event, () => toolbar.togglePopover("stroke"))}
        title="Stroke color"
      >
        <span>Color</span>
        <span
          className="annotation-toolbar-color-bar"
          style={{ backgroundColor: style.strokeColor }}
        />
      </ToolbarButton>
      <ToolbarButton
        className="annotation-toolbar-width"
        onPointerDown={(event) => toolbar.activateButton(event, () => toolbar.togglePopover("width"))}
        title="Line width"
      >
        <LineWidthPreview width={style.lineWidth} />
        <span>{style.lineWidth}px</span>
      </ToolbarButton>
      <ToolbarButton
        onPointerDown={(event) => toolbar.activateButton(event, () => toolbar.togglePopover("style"))}
        title="Line style"
      >
        <LineStylePreview styleKey={style.lineStyle} />
      </ToolbarButton>
      <ToolbarButton
        onPointerDown={(event) => toolbar.activateButton(event, () => toolbar.togglePopover("opacity"))}
        title="Opacity"
      >
        <span>{Math.round(style.opacity * 100)}%</span>
      </ToolbarButton>
      <ToolbarButton
        active={style.visible}
        onPointerDown={(event) =>
          toolbar.activateButton(event, () =>
            onEmaStyleChange(emaLine.length, { visible: !style.visible }),
          )
        }
        title="Toggle visibility"
      >
        <span>{style.visible ? "Shown" : "Hidden"}</span>
      </ToolbarButton>

      {toolbar.openPopover === "stroke" ? (
        <ColorPopover
          colors={ANNOTATION_COLOR_PALETTE}
          selectedColor={style.strokeColor}
          title="EMA Color"
          wide
          onSelect={(color) => onEmaStyleChange(emaLine.length, { strokeColor: color })}
        />
      ) : null}
      {toolbar.openPopover === "width" ? (
        <WidthPopover
          onSelect={(lineWidth) => onEmaStyleChange(emaLine.length, { lineWidth })}
          selectedWidth={style.lineWidth}
        />
      ) : null}
      {toolbar.openPopover === "style" ? (
        <StylePopover
          onSelect={(lineStyle) => onEmaStyleChange(emaLine.length, { lineStyle })}
          selectedStyle={style.lineStyle}
          showLabels={false}
          title="Line Style"
        />
      ) : null}
      {toolbar.openPopover === "opacity" ? (
        <SliderPopover
          id="ema-opacity-slider"
          label={`${Math.round(style.opacity * 100)}%`}
          max="1"
          min="0.1"
          onChange={(value) =>
            onEmaStyleChange(emaLine.length, {
              opacity: Number(value),
            })
          }
          step="0.05"
          title="Opacity"
          value={style.opacity}
        />
      ) : null}
    </FloatingToolbarShell>
  );
}
