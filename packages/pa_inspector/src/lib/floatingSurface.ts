import { useEffect, useRef, useState, type RefObject } from "react";

import type { FloatingPosition } from "./types";

interface UseFloatingSurfacePositionArgs {
  initialPosition: FloatingPosition;
  onPositionChange: (position: FloatingPosition) => void;
}

interface UseDraggableFloatingSurfaceArgs<
  HandleElement extends HTMLElement,
  SurfaceElement extends HTMLElement,
> {
  handleRef: RefObject<HandleElement | null>;
  surfaceRef: RefObject<SurfaceElement | null>;
  clampInset: number;
  setPosition: (position: FloatingPosition) => void;
  onDragStart?: () => void;
  canStartDrag?: (event: PointerEvent) => boolean;
}

export function useFloatingSurfacePosition({
  initialPosition,
  onPositionChange,
}: UseFloatingSurfacePositionArgs) {
  const onPositionChangeRef = useRef(onPositionChange);
  const [position, setPosition] = useState(initialPosition);

  useEffect(() => {
    onPositionChangeRef.current = onPositionChange;
  }, [onPositionChange]);

  useEffect(() => {
    onPositionChangeRef.current(position);
  }, [position]);

  return { position, setPosition };
}

export function useDraggableFloatingSurface<
  HandleElement extends HTMLElement,
  SurfaceElement extends HTMLElement,
>({
  handleRef,
  surfaceRef,
  clampInset,
  setPosition,
  onDragStart,
  canStartDrag,
}: UseDraggableFloatingSurfaceArgs<HandleElement, SurfaceElement>) {
  useEffect(() => {
    const handle = handleRef.current;
    const surface = surfaceRef.current;
    if (!handle || !surface) {
      return;
    }

    const onPointerDown = (event: PointerEvent) => {
      if (event.button !== 0) {
        return;
      }
      if (canStartDrag && !canStartDrag(event)) {
        return;
      }
      const parent = surface.offsetParent;
      if (!(parent instanceof HTMLElement)) {
        return;
      }
      const surfaceRect = surface.getBoundingClientRect();
      const parentRect = parent.getBoundingClientRect();
      const offsetX = event.clientX - surfaceRect.left;
      const offsetY = event.clientY - surfaceRect.top;

      onDragStart?.();
      handle.setPointerCapture(event.pointerId);

      const onPointerMove = (moveEvent: PointerEvent) => {
        const nextLeft = moveEvent.clientX - parentRect.left - offsetX;
        const nextTop = moveEvent.clientY - parentRect.top - offsetY;
        setPosition({
          left: clamp(
            nextLeft,
            clampInset,
            Math.max(clampInset, parentRect.width - surfaceRect.width - clampInset),
          ),
          top: clamp(
            nextTop,
            clampInset,
            Math.max(clampInset, parentRect.height - surfaceRect.height - clampInset),
          ),
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
  }, [canStartDrag, clampInset, handleRef, onDragStart, setPosition, surfaceRef]);
}

function clamp(value: number, min: number, max: number) {
  return Math.max(min, Math.min(max, value));
}
