/**
 * Pure chart geometry: scales, the smoothed tide curve, axis ticks and the
 * placement of high/low labels. No DOM or Lit here, so it is easy to reason about.
 */
import type { ExtremeLabel, TideData, TideExtreme, TidePoint } from './types';
import { interpolate } from './data/model';
import { HOUR, startOfDay } from './time';

export interface ChartFormatters {
  height(v: number): string; // "1.84 m"
  value(v: number): string; // "1.84"
  axis(v: number): string; // "1.5"
  time(t: number): string; // "15:04"
  hour(t: number): string; // "15:00" / "15 h" / "3 p.m."
  day(t: number): string; // "Sat 27" / "sam. 27"
}

export interface ChartInput {
  data: TideData;
  start: number;
  end: number;
  now: number;
  width: number;
  height: number;
  tz?: string;
  showExtremes: boolean;
  extremeLabel: ExtremeLabel;
  showNow: boolean;
  fmt: ChartFormatters;
}

export interface ExtremeMark {
  t: number;
  v: number;
  type: 'high' | 'low';
  x: number;
  y: number;
  labelX: number;
  lines: { text: string; y: number; primary: boolean }[];
}

export interface ChartLayout {
  width: number;
  height: number;
  plot: { left: number; right: number; top: number; bottom: number };
  line: string;
  area: string;
  yTicks: { y: number; label: string }[];
  xTicks: { x: number; label: string; major: boolean }[];
  dayLines: number[];
  extremes: ExtremeMark[];
  now?: { x: number; y: number; value: number };
  xToTime(x: number): number;
  timeToX(t: number): number;
  valueToY(v: number): number;
}

const LINE_HEIGHT = 13;
const CHAR_WIDTH = 6.4; // average glyph width at the 11px label size
const AXIS_HEIGHT = 18;
const LABEL_GAP = 7;

export function layoutChart(input: ChartInput): ChartLayout | null {
  const { data, start, end, width, height, fmt } = input;
  const visible = pointsInSpan(data.points, start, end);
  if (visible.length < 2 || width < 50) return null;

  const labelLines = input.showExtremes ? (input.extremeLabel === 'height_time' ? 2 : 1) : 0;
  const labelSpace = labelLines ? labelLines * LINE_HEIGHT + LABEL_GAP : 6;
  const plot = { left: 0, right: width, top: labelSpace, bottom: height - AXIS_HEIGHT - labelSpace };

  const inSpan = visible.filter((p) => p.t >= start && p.t <= end);
  const values = (inSpan.length ? inSpan : visible).map((p) => p.v);
  let min = Math.min(...values);
  let max = Math.max(...values);
  if (max - min < 0.1) {
    min -= 0.05;
    max += 0.05;
  }

  const timeToX = (t: number) => plot.left + ((t - start) / (end - start)) * (plot.right - plot.left);
  const xToTime = (x: number) => start + ((x - plot.left) / (plot.right - plot.left)) * (end - start);
  const valueToY = (v: number) => plot.bottom - ((v - min) / (max - min)) * (plot.bottom - plot.top);

  const xy = visible.map((p) => [timeToX(p.t), valueToY(p.v)] as [number, number]);
  const line = monotonePath(xy);
  const area = `${line}L${xy[xy.length - 1][0].toFixed(1)},${plot.bottom}L${xy[0][0].toFixed(1)},${plot.bottom}Z`;

  const layout: ChartLayout = {
    width,
    height,
    plot,
    line,
    area,
    yTicks: yTicks(min, max).map((v) => ({ y: valueToY(v), label: fmt.axis(v) })),
    ...xAxis(input, timeToX),
    extremes: [],
    xToTime,
    timeToX,
    valueToY,
  };

  if (input.showExtremes) {
    const marks = data.extremes
      .filter((e) => e.t >= start && e.t <= end)
      .map((e) => ({ ...e, x: timeToX(e.t), y: valueToY(e.v) }));
    layout.extremes = [
      ...placeLabels(
        marks.filter((m) => m.type === 'high'),
        input,
        width,
      ),
      ...placeLabels(
        marks.filter((m) => m.type === 'low'),
        input,
        width,
      ),
    ];
  }

  if (input.showNow && input.now >= start && input.now <= end) {
    const value = interpolate(data.points, input.now);
    if (value !== null) layout.now = { x: timeToX(input.now), y: valueToY(value), value };
  }
  return layout;
}

/** Points inside the span plus one on each side, so the curve reaches the edges. */
function pointsInSpan(points: TidePoint[], start: number, end: number): TidePoint[] {
  const first = Math.max(0, points.findIndex((p) => p.t >= start) - 1);
  let last = points.findIndex((p) => p.t > end);
  last = last === -1 ? points.length - 1 : last;
  return points.slice(first, last + 1);
}

/** Monotone cubic interpolation (Fritsch–Carlson): smooth, never overshoots a high or low. */
export function monotonePath(pts: [number, number][]): string {
  const n = pts.length;
  if (n < 2) return '';
  const dx: number[] = [];
  const slope: number[] = [];
  for (let i = 0; i < n - 1; i++) {
    dx.push(pts[i + 1][0] - pts[i][0]);
    slope.push((pts[i + 1][1] - pts[i][1]) / (dx[i] || 1));
  }
  const tangent: number[] = [slope[0]];
  for (let i = 1; i < n - 1; i++) {
    const a = slope[i - 1];
    const b = slope[i];
    if (a * b <= 0) tangent.push(0);
    else {
      const w1 = 2 * dx[i] + dx[i - 1];
      const w2 = dx[i] + 2 * dx[i - 1];
      tangent.push((w1 + w2) / (w1 / a + w2 / b));
    }
  }
  tangent.push(slope[n - 2]);

  const f = (v: number) => v.toFixed(1);
  let d = `M${f(pts[0][0])},${f(pts[0][1])}`;
  for (let i = 0; i < n - 1; i++) {
    const [x0, y0] = pts[i];
    const [x1, y1] = pts[i + 1];
    const h = dx[i] / 3;
    d += `C${f(x0 + h)},${f(y0 + tangent[i] * h)},${f(x1 - h)},${f(y1 - tangent[i + 1] * h)},${f(x1)},${f(y1)}`;
  }
  return d;
}

function yTicks(min: number, max: number): number[] {
  const range = max - min;
  const step = [0.1, 0.2, 0.25, 0.5, 1, 2, 2.5, 5, 10].find((s) => range / s <= 4) ?? 10;
  const ticks: number[] = [];
  for (let v = Math.ceil(min / step) * step; v <= max + 1e-9; v += step) ticks.push(Math.round(v * 1000) / 1000);
  return ticks;
}

function xAxis(
  input: ChartInput,
  timeToX: (t: number) => number,
): { xTicks: ChartLayout['xTicks']; dayLines: number[] } {
  const { start, end, width, tz, fmt } = input;
  const hours = (end - start) / HOUR;
  const pxPerHour = width / hours;
  const step = [1, 2, 3, 6, 12, 24].find((s) => s * pxPerHour >= 48) ?? 24;
  const multiDay = hours > 24;
  const xTicks: ChartLayout['xTicks'] = [];
  const dayLines: number[] = [];

  for (let day = startOfDay(start, tz); day <= end; day = startOfDay(day + 36 * HOUR, tz)) {
    for (let h = 0; h < 24; h += step) {
      const t = day + h * HOUR;
      if (t < start || t > end) continue;
      const x = timeToX(t);
      const major = h === 0 && multiDay;
      if (h === 0 && t > start) dayLines.push(x);
      // Keep labels away from the edges so they are not clipped.
      const margin = major ? 22 : 15;
      if (x < margin || x > width - margin) continue;
      xTicks.push({ x, label: major ? fmt.day(t) : fmt.hour(t), major });
    }
  }
  return { xTicks, dayLines };
}

type Mark = TideExtreme & { x: number; y: number };
/** Label styles from most to least detailed; "value" is the bare number, e.g. "▲1.47". */
type Mode = ExtremeLabel | 'value';

function labelTexts(m: Mark, mode: Mode, fmt: ChartFormatters): { text: string; primary: boolean }[] {
  const arrow = m.type === 'high' ? '▲' : '▼';
  const heightText = { text: `${arrow} ${fmt.height(m.v)}`, primary: true };
  const timeText = { text: fmt.time(m.t), primary: false };
  if (mode === 'value') return [{ text: `${arrow}${fmt.value(m.v)}`, primary: true }];
  if (mode === 'height') return [heightText];
  if (mode === 'time') return [{ text: `${arrow} ${fmt.time(m.t)}`, primary: true }];
  // The primary line (height) sits closest to the point.
  return m.type === 'high' ? [timeText, heightText] : [heightText, timeText];
}

function labelWidth(lines: { text: string }[]): number {
  return Math.max(...lines.map((l) => l.text.length)) * CHAR_WIDTH + 6;
}

/**
 * Place labels for one row (all highs or all lows). When neighbours would overlap,
 * the whole row switches to a shorter style; if even the shortest style collides,
 * the most pronounced highs (or lows) keep their label and the others show only
 * their marker. A label is always drawn directly over (or under) its own point.
 */
function placeLabels(marks: Mark[], input: ChartInput, width: number): ExtremeMark[] {
  if (!marks.length) return [];
  const build = (mode: Mode) =>
    marks.map((m) => {
      const lines = labelTexts(m, mode, input.fmt);
      const w = labelWidth(lines);
      const labelX = Math.min(Math.max(m.x, w / 2), width - w / 2);
      return { m, lines, w, labelX, left: labelX - w / 2, right: labelX + w / 2 };
    });
  type Label = ReturnType<typeof build>[number];
  const clear = (a: Label, b: Label) => a.right + 4 <= b.left || b.right + 4 <= a.left;
  const overlaps = (row: Label[]) => row.some((cur, i) => i > 0 && !clear(cur, row[i - 1]));

  const modes: Mode[] =
    input.extremeLabel === 'height_time'
      ? ['height_time', 'height', 'value']
      : input.extremeLabel === 'height'
        ? ['height', 'value']
        : ['time'];
  let row = build(modes[0]);
  for (const mode of modes.slice(1)) {
    if (!overlaps(row)) break;
    row = build(mode);
  }

  // Most pronounced first: highest highs, lowest lows.
  const priority = [...row].sort((a, b) => (a.m.type === 'high' ? b.m.v - a.m.v : a.m.v - b.m.v));
  const kept: Label[] = [];
  for (const label of priority) {
    if (kept.every((k) => clear(k, label))) kept.push(label);
  }

  return row.map((label) => {
    const { m, lines, labelX } = label;
    const count = lines.length;
    return {
      t: m.t,
      v: m.v,
      type: m.type,
      x: m.x,
      y: m.y,
      labelX,
      lines: kept.includes(label)
        ? lines.map((l, i) => ({
            ...l,
            // Highs stack upwards from the point, lows downwards (baseline positions).
            y:
              m.type === 'high'
                ? m.y - LABEL_GAP - (count - 1 - i) * LINE_HEIGHT
                : m.y + LABEL_GAP + 9 + i * LINE_HEIGHT,
          }))
        : [],
    };
  });
}
