import type {
  AnnotationKind,
  AnnotationLineStyle,
  AnnotationStyle,
  ChartAnnotation,
  EmaStyle,
} from "./types";

export const ANNOTATION_COLOR_PALETTE = [
  "#111827",
  "#475569",
  "#64748b",
  "#089981",
  "#16a34a",
  "#0ea5e9",
  "#2563eb",
  "#7c3aed",
  "#d97706",
  "#eab308",
  "#dc2626",
  "#ec4899",
];

export const ANNOTATION_LINE_WIDTHS = [1, 2, 3, 4] as const;
export const ANNOTATION_LINE_STYLES: AnnotationLineStyle[] = [
  "solid",
  "dashed",
  "dotted",
];

export function defaultAnnotationStyle(kind: AnnotationKind): AnnotationStyle {
  if (kind === "box") {
    return {
      strokeColor: "#9333ea",
      fillColor: "#c4b5fd",
      lineWidth: 2,
      lineStyle: "solid",
      opacity: 0.9,
      locked: false,
    };
  }
  if (kind === "fib50") {
    return {
      strokeColor: "#eab308",
      fillColor: "#eab308",
      lineWidth: 2,
      lineStyle: "solid",
      opacity: 0.95,
      locked: false,
    };
  }
  return {
    strokeColor: "#4ba69a",
    fillColor: "#4ba69a",
    lineWidth: 2,
    lineStyle: "solid",
    opacity: 0.95,
    locked: false,
  };
}

export function getAnnotationStyle(annotation: ChartAnnotation) {
  return annotation.style ?? defaultAnnotationStyle(annotation.kind);
}

export function lineDashForStyle(style: AnnotationLineStyle) {
  if (style === "dashed") {
    return [8, 6];
  }
  if (style === "dotted") {
    return [2, 5];
  }
  return [];
}

export function colorWithOpacity(color: string, opacity: number) {
  const normalizedOpacity = Math.max(0, Math.min(1, opacity));
  const hex = color.trim();
  const match = /^#([0-9a-f]{6}|[0-9a-f]{3})$/i.exec(hex);
  if (!match) {
    return color;
  }
  const raw = match[1];
  const expanded =
    raw.length === 3
      ? raw
          .split("")
          .map((part) => part + part)
          .join("")
      : raw;
  const r = Number.parseInt(expanded.slice(0, 2), 16);
  const g = Number.parseInt(expanded.slice(2, 4), 16);
  const b = Number.parseInt(expanded.slice(4, 6), 16);
  return `rgba(${r}, ${g}, ${b}, ${normalizedOpacity})`;
}

export function defaultEmaStyle(length: number): EmaStyle {
  return {
    strokeColor: ANNOTATION_COLOR_PALETTE[Math.abs(length) % ANNOTATION_COLOR_PALETTE.length],
    lineWidth: 2,
    lineStyle: "solid",
    opacity: 0.95,
    visible: true,
  };
}

export function getEmaStyle(length: number, style: EmaStyle | null | undefined): EmaStyle {
  return style ?? defaultEmaStyle(length);
}
