import { useEffect, useRef, useState, type RefObject } from "react";

import type { FloatingPosition } from "./types";

export interface FloatingSurfaceBounds {
  minLeft: number;
  maxLeft: number;
  minTop: number;
  maxTop: number;
}

interface UseFloatingSurfacePositionArgs<Position extends FloatingPosition | null> {
  initialPosition: Position;
  onPositionChange: (position: Position) => void;
}

interface UseDraggableFloatingSurfaceArgs<
  HandleElement extends HTMLElement,
  SurfaceElement extends HTMLElement,
> {
  handleRef: RefObject<HandleElement | null>;
  surfaceRef: RefObject<SurfaceElement | null>;
  setPosition: (position: FloatingPosition) => void;
  boundsResolver?: (surface: SurfaceElement) => FloatingSurfaceBounds | null;
  onDragStart?: () => void;
  canStartDrag?: (event: PointerEvent) => boolean;
}

export function useFloatingSurfacePosition<Position extends FloatingPosition | null>({
  initialPosition,
  onPositionChange,
}: UseFloatingSurfacePositionArgs<Position>) {
  const onPositionChangeRef = useRef(onPositionChange);
  const [position, setPosition] = useState<Position>(initialPosition);

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
  setPosition,
  boundsResolver,
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
      const bounds =
        boundsResolver?.(surface) ?? resolveOffsetParentBounds(surface);
      if (!bounds) {
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
        const nextPosition = clampFloatingPosition(
          {
            left: moveEvent.clientX - parentRect.left - offsetX,
            top: moveEvent.clientY - parentRect.top - offsetY,
          },
          bounds,
        );
        setPosition(nextPosition);
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
  }, [boundsResolver, canStartDrag, handleRef, onDragStart, setPosition, surfaceRef]);
}

export function resolveFloatingSurfaceBounds(
  container: HTMLElement | null,
  {
    surfaceWidth,
    surfaceHeight,
    clampInset,
  }: {
    surfaceWidth: number;
    surfaceHeight: number;
    clampInset: number;
  },
): FloatingSurfaceBounds {
  const containerWidth = Math.max(container?.clientWidth ?? 0, 0);
  const containerHeight = Math.max(container?.clientHeight ?? 0, 0);
  return {
    minLeft: clampInset,
    maxLeft: Math.max(clampInset, containerWidth - surfaceWidth - clampInset),
    minTop: clampInset,
    maxTop: Math.max(clampInset, containerHeight - surfaceHeight - clampInset),
  };
}

export function clampFloatingPosition(
  position: FloatingPosition,
  bounds: FloatingSurfaceBounds,
): FloatingPosition {
  return {
    left: clamp(position.left, bounds.minLeft, bounds.maxLeft),
    top: clamp(position.top, bounds.minTop, bounds.maxTop),
  };
}

export function resolveFloatingSurfaceDefaultPosition(
  bounds: FloatingSurfaceBounds,
  alignment: {
    horizontal?: "start" | "end";
    vertical?: "start" | "end";
  } = {},
): FloatingPosition {
  return {
    left: alignment.horizontal === "start" ? bounds.minLeft : bounds.maxLeft,
    top: alignment.vertical === "end" ? bounds.maxTop : bounds.minTop,
  };
}

function resolveOffsetParentBounds(
  surface: HTMLElement,
  clampInset = 0,
): FloatingSurfaceBounds | null {
  const parent = surface.offsetParent;
  if (!(parent instanceof HTMLElement)) {
    return null;
  }
  return {
    minLeft: clampInset,
    maxLeft: Math.max(clampInset, parent.clientWidth - surface.offsetWidth - clampInset),
    minTop: clampInset,
    maxTop: Math.max(clampInset, parent.clientHeight - surface.offsetHeight - clampInset),
  };
}

function clamp(value: number, min: number, max: number) {
  return Math.max(min, Math.min(max, value));
}
