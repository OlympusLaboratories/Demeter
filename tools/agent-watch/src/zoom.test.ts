import { describe, expect, it } from 'vitest';
import { MAX_ZOOM, MIN_ZOOM, clampZoom, pixelDelta, zoomFactorFor } from './zoom';

describe('zoomFactorFor', () => {
  it('scales with how far the wheel actually moved', () => {
    const small = zoomFactorFor({ deltaY: -4 });
    const large = zoomFactorFor({ deltaY: -40 });
    expect(small).toBeGreaterThan(1);
    expect(large).toBeGreaterThan(small);
  });

  it('keeps a single trackpad tick nearly imperceptible', () => {
    const tick = zoomFactorFor({ deltaY: -4 });
    expect(tick).toBeLessThan(1.01);
  });

  it('needs a real gesture to double the zoom, not a flick', () => {
    let zoom = 1;
    for (let tick = 0; tick < 20; tick += 1) zoom *= zoomFactorFor({ deltaY: -4 });
    expect(zoom).toBeLessThan(1.15);
  });

  it('is symmetric, so scrolling back returns to where you started', () => {
    const inFactor = zoomFactorFor({ deltaY: -30 });
    const outFactor = zoomFactorFor({ deltaY: 30 });
    expect(inFactor * outFactor).toBeCloseTo(1, 10);
  });

  it('caps a single enormous delta so one flick cannot jump the view', () => {
    expect(zoomFactorFor({ deltaY: -100_000 })).toBeLessThanOrEqual(1.08);
    expect(zoomFactorFor({ deltaY: 100_000 })).toBeGreaterThanOrEqual(1 / 1.08);
  });

  it('treats a pinch as a deliberate zoom, so it responds faster than a scroll', () => {
    expect(zoomFactorFor({ deltaY: -5, ctrlKey: true })).toBeGreaterThan(
      zoomFactorFor({ deltaY: -5, ctrlKey: false }),
    );
  });

  it('does nothing for a horizontal-only gesture', () => {
    expect(zoomFactorFor({ deltaY: 0 })).toBe(1);
  });

  it('honours a sensitivity multiplier', () => {
    expect(zoomFactorFor({ deltaY: -20 }, 2)).toBeGreaterThan(zoomFactorFor({ deltaY: -20 }, 1));
    expect(zoomFactorFor({ deltaY: -20 }, 0)).toBe(1);
  });
});

describe('pixelDelta', () => {
  it('normalizes line and page scrolling to pixels', () => {
    expect(pixelDelta({ deltaY: 3, deltaMode: 0 })).toBe(3);
    expect(pixelDelta({ deltaY: 3, deltaMode: 1 })).toBe(48);
    expect(pixelDelta({ deltaY: 2, deltaMode: 2, pageHeight: 500 })).toBe(1000);
  });
});

describe('clampZoom', () => {
  it('bounds the zoom level', () => {
    expect(clampZoom(0.001)).toBe(MIN_ZOOM);
    expect(clampZoom(99)).toBe(MAX_ZOOM);
    expect(clampZoom(1.5)).toBe(1.5);
  });
});
