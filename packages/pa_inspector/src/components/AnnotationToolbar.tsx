import { type RefObject } from "react";

import {
  ANNOTATION_COLOR_PALETTE,
  getAnnotationStyle,
} from "../lib/annotationStyle";
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
  AnnotationStyle,
  AnnotationToolbarPopover,
  ChartAnnotation,
  FloatingPosition,
} from "../lib/types";

interface AnnotationToolbarProps {
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
  const style = annotation ? getAnnotationStyle(annotation) : null;
  const toolbar = useFloatingToolbar({
    active: annotation !== null,
    surfaceRef,
    toolbarWidth: TOOLBAR_WIDTH,
    toolbarHeight: TOOLBAR_HEIGHT,
    initialPosition,
    initialOpenPopover,
    onPositionChange,
    onOpenPopoverChange,
    dragFromContainerBackground: true,
  });

  if (!annotation || !style) {
    return null;
  }

  return (
    <FloatingToolbarShell
      dragTitle="Drag annotation toolbar"
      grip={<ToolbarGripIcon />}
      state={toolbar}
    >
      <ToolbarButton
        onPointerDown={(event) => toolbar.activateButton(event, () => toolbar.togglePopover("stroke"))}
        title="Stroke color"
      >
        <StrokeIcon />
        <span
          className="annotation-toolbar-color-bar"
          style={{ backgroundColor: style.strokeColor }}
        />
      </ToolbarButton>
      <ToolbarButton
        disabled={annotation.kind !== "box"}
        onPointerDown={(event) => toolbar.activateButton(event, () => toolbar.togglePopover("fill"))}
        title="Fill color"
      >
        <FillIcon />
        <span
          className="annotation-toolbar-color-bar"
          style={{
            backgroundColor: annotation.kind === "box" ? style.fillColor : "#cbd5e1",
          }}
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
        <OpacityIcon />
        <span>{Math.round(style.opacity * 100)}%</span>
      </ToolbarButton>
      <ToolbarButton
        onPointerDown={(event) =>
          toolbar.activateButton(event, () => {
            const duplicateId = onAnnotationDuplicate(annotation.id);
            if (duplicateId) {
              toolbar.setOpenPopover(null);
            }
          })
        }
        title="Duplicate"
      >
        <DuplicateIcon />
      </ToolbarButton>
      <ToolbarButton
        active={style.locked}
        onPointerDown={(event) =>
          toolbar.activateButton(event, () =>
            onAnnotationStyleChange(annotation.id, { locked: !style.locked }),
          )
        }
        title={style.locked ? "Unlock drawing" : "Lock drawing"}
      >
        <LockIcon locked={style.locked} />
      </ToolbarButton>
      <ToolbarButton
        onPointerDown={(event) => toolbar.activateButton(event, onDeleteSelectedAnnotation)}
        title="Delete"
      >
        <TrashIcon />
      </ToolbarButton>

      {toolbar.openPopover === "stroke" ? (
        <ColorPopover
          colors={ANNOTATION_COLOR_PALETTE}
          selectedColor={style.strokeColor}
          title="Stroke"
          onSelect={(color) => onAnnotationStyleChange(annotation.id, { strokeColor: color })}
        />
      ) : null}
      {toolbar.openPopover === "fill" && annotation.kind === "box" ? (
        <ColorPopover
          colors={ANNOTATION_COLOR_PALETTE}
          selectedColor={style.fillColor}
          title="Fill"
          onSelect={(color) => onAnnotationStyleChange(annotation.id, { fillColor: color })}
        />
      ) : null}
      {toolbar.openPopover === "width" ? (
        <WidthPopover
          onSelect={(lineWidth) => onAnnotationStyleChange(annotation.id, { lineWidth })}
          selectedWidth={style.lineWidth}
        />
      ) : null}
      {toolbar.openPopover === "style" ? (
        <StylePopover
          onSelect={(lineStyle) => onAnnotationStyleChange(annotation.id, { lineStyle })}
          selectedStyle={style.lineStyle}
        />
      ) : null}
      {toolbar.openPopover === "opacity" ? (
        <SliderPopover
          id="annotation-opacity"
          label="Opacity"
          max="100"
          min="10"
          onChange={(value) =>
            onAnnotationStyleChange(annotation.id, { opacity: Number(value) / 100 })
          }
          title="Opacity"
          value={Math.round(style.opacity * 100)}
          wide
        />
      ) : null}
    </FloatingToolbarShell>
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
