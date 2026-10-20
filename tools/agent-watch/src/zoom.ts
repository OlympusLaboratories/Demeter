export const MIN_ZOOM = 0.1;
export const MAX_ZOOM = 4;

const PIXELS_PER_LINE = 16;
const WHEEL_SENSITIVITY = 0.0012;
const PINCH_SENSITIVITY = 0.006;
const MAX_STEP = 1.08;

export interface WheelInput {
  deltaY: number;
  deltaMode?: number;
  ctrlKey?: boolean;
  pageHeight?: number;
}

export function pixelDelta(input: WheelInput): number {
  switch (input.deltaMode) {
    case 1:
      return input.deltaY * PIXELS_PER_LINE;
    case 2:
      return input.deltaY * (input.pageHeight ?? 800);
    default:
      return input.deltaY;
  }
}

export function zoomFactorFor(input: WheelInput, sensitivity = 1): number {
  const delta = pixelDelta(input);
  if (delta === 0) return 1;
  const base = input.ctrlKey === true ? PINCH_SENSITIVITY : WHEEL_SENSITIVITY;
  const factor = Math.exp(-delta * base * sensitivity);
  return Math.min(MAX_STEP, Math.max(1 / MAX_STEP, factor));
}

export function clampZoom(value: number): number {
  return Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, value));
}
