/**
 * Time-zone helpers. `tz` undefined means the browser's zone; otherwise an IANA name
 * (Home Assistant's server zone when the user profile asks for it).
 */
import type { HomeAssistant } from './types';

export const HOUR = 3_600_000;
export const DAY = 24 * HOUR;

export function resolveTimeZone(hass: HomeAssistant): string | undefined {
  return hass.locale?.time_zone === 'server' ? hass.config.time_zone : undefined;
}

/** 12/24-hour clock from the HA profile; undefined lets the language decide. */
export function resolveHour12(hass: HomeAssistant): boolean | undefined {
  const pref = hass.locale?.time_format;
  if (pref === '12') return true;
  if (pref === '24') return false;
  return undefined;
}

const partsFormatters = new Map<string, Intl.DateTimeFormat>();

function wallClock(t: number, tz: string): { y: number; m: number; d: number; h: number; min: number; s: number } {
  let fmt = partsFormatters.get(tz);
  if (!fmt) {
    fmt = new Intl.DateTimeFormat('en-US', {
      timeZone: tz,
      hourCycle: 'h23',
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    });
    partsFormatters.set(tz, fmt);
  }
  const p: Record<string, number> = {};
  for (const part of fmt.formatToParts(new Date(t))) {
    if (part.type !== 'literal') p[part.type] = Number(part.value);
  }
  return { y: p.year, m: p.month, d: p.day, h: p.hour, min: p.minute, s: p.second };
}

/** Offset of `tz` from UTC at instant `t`, in ms. */
function offsetMs(t: number, tz: string): number {
  const w = wallClock(t, tz);
  return Date.UTC(w.y, w.m - 1, w.d, w.h, w.min, w.s) - Math.floor(t / 1000) * 1000;
}

/** Local midnight (in `tz`) of the day containing `t`. */
export function startOfDay(t: number, tz?: string): number {
  if (!tz) {
    const d = new Date(t);
    d.setHours(0, 0, 0, 0);
    return d.getTime();
  }
  const w = wallClock(t, tz);
  const guess = Date.UTC(w.y, w.m - 1, w.d);
  let result = guess - offsetMs(guess, tz);
  // Correct once if a DST change happens between the guess and midnight.
  result = guess - offsetMs(result, tz);
  return result;
}

/** Midnight of the day after the one containing `t`. */
export function nextMidnight(t: number, tz?: string): number {
  return startOfDay(startOfDay(t, tz) + 36 * HOUR, tz);
}
