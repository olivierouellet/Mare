import type { HassEntity, TideData, TideExtreme, TidePoint } from '../types';
import { HOUR } from '../time';

interface RawPoint {
  time?: string;
  value?: number;
  type?: string;
}

/** Build TideData from the integration's tide level sensor, or null if it has no curve. */
export function fromEntity(stateObj: HassEntity): TideData | null {
  const raw = stateObj.attributes.tide_data;
  if (!Array.isArray(raw) || raw.length < 2) return null;
  const points = parsePoints(raw as RawPoint[]);
  if (points.length < 2) return null;
  const rawExtremes = stateObj.attributes.tide_extremes;
  // The type sent by the sensor is not trusted: each point is checked against the curve.
  const extremes = Array.isArray(rawExtremes)
    ? classifyExtremes(parsePoints(rawExtremes as RawPoint[]), points)
    : detectExtremes(points);
  const stationName = stateObj.attributes.station_name;
  return { points, extremes, stationName: typeof stationName === 'string' ? stationName : undefined };
}

export function parsePoints(raw: RawPoint[]): TidePoint[] {
  return raw
    .map((p) => ({ t: Date.parse(p.time ?? ''), v: Number(p.value) }))
    .filter((p) => Number.isFinite(p.t) && Number.isFinite(p.v))
    .sort((a, b) => a.t - b.t);
}

/** Linear interpolation of the level at time t; null outside the data. */
export function interpolate(points: TidePoint[], t: number): number | null {
  if (!points.length || t < points[0].t || t > points[points.length - 1].t) return null;
  let lo = 0;
  let hi = points.length - 1;
  while (hi - lo > 1) {
    const mid = (lo + hi) >> 1;
    if (points[mid].t <= t) lo = mid;
    else hi = mid;
  }
  const a = points[lo];
  const b = points[hi];
  if (b.t === a.t) return a.v;
  return a.v + ((b.v - a.v) * (t - a.t)) / (b.t - a.t);
}

/**
 * Label official high/low points as "high" or "low". The curve is the reference:
 * a high sits above the curve two hours before and after it. Neighbouring points
 * (highs and lows alternate) are only used when the curve does not cover the point.
 */
export function classifyExtremes(hilo: TidePoint[], points: TidePoint[]): TideExtreme[] {
  const out: TideExtreme[] = [];
  hilo.forEach((p, i) => {
    let ref = [interpolate(points, p.t - 2 * HOUR), interpolate(points, p.t + 2 * HOUR)].filter(
      (v): v is number => v !== null,
    );
    if (!ref.length) ref = [hilo[i - 1], hilo[i + 1]].filter((n): n is TidePoint => !!n).map((n) => n.v);
    if (!ref.length) return;
    const avg = ref.reduce((sum, v) => sum + v, 0) / ref.length;
    out.push({ ...p, type: p.v > avg ? 'high' : 'low' });
  });
  return out;
}

/** Fallback when the sensor has no tide_extremes: local maxima/minima of the curve. */
export function detectExtremes(points: TidePoint[]): TideExtreme[] {
  const out: TideExtreme[] = [];
  for (let i = 1; i < points.length - 1; i++) {
    const prev = points[i - 1].v;
    const cur = points[i].v;
    // Look past flat runs so a plateau yields a single point.
    let j = i + 1;
    while (j < points.length - 1 && points[j].v === cur) j++;
    const next = points[j].v;
    if (cur > prev && cur > next) out.push({ ...points[i], type: 'high' });
    else if (cur < prev && cur < next) out.push({ ...points[i], type: 'low' });
  }
  return out;
}
