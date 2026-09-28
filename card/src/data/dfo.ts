/**
 * Direct browser access to the DFO / MPO IWLS API (it allows cross-origin requests),
 * with in-memory and localStorage caching shared by every card on the page.
 */
import type { Station, TideData } from '../types';
import { classifyExtremes, parsePoints } from './model';

const BASE_URL = 'https://api-iwls.dfo-mpo.gc.ca/api/v1';
const STATIONS_KEY = 'mare-tide-card:stations:v1';
const STATIONS_TTL = 24 * 3_600_000;
const TIDES_TTL = 6 * 3_600_000;

interface CacheEntry<T> {
  saved: number;
  data: T;
}

function readCache<T>(key: string, ttl: number): T | null {
  try {
    const raw = localStorage.getItem(key);
    if (!raw) return null;
    const entry = JSON.parse(raw) as CacheEntry<T>;
    return Date.now() - entry.saved < ttl ? entry.data : null;
  } catch {
    return null;
  }
}

function writeCache<T>(key: string, data: T): void {
  try {
    localStorage.setItem(key, JSON.stringify({ saved: Date.now(), data }));
  } catch {
    // Storage full or blocked: the in-memory cache still works.
  }
}

async function getJson(path: string, params: Record<string, string> = {}): Promise<unknown[]> {
  const url = new URL(BASE_URL + path);
  Object.entries(params).forEach(([k, v]) => url.searchParams.set(k, v));
  const resp = await fetch(url.toString());
  if (!resp.ok) throw new Error(`DFO API HTTP ${resp.status}`);
  const payload = await resp.json();
  const list = Array.isArray(payload) ? payload : payload?.data;
  if (!Array.isArray(list)) throw new Error('Unexpected DFO API response');
  return list;
}

interface RawStation {
  id: string;
  code?: string;
  officialName?: string;
  latitude?: number;
  longitude?: number;
  timeSeries?: { code?: string }[];
}

let stationsPromise: Promise<Station[]> | null = null;

/** Stations that publish predictions and high/low predictions. */
export function fetchStations(): Promise<Station[]> {
  const cached = readCache<Station[]>(STATIONS_KEY, STATIONS_TTL);
  if (cached) return Promise.resolve(cached);
  if (!stationsPromise) {
    stationsPromise = getJson('/stations')
      .then((raw) => {
        const stations = (raw as RawStation[])
          .filter((s) => {
            const codes = new Set((s.timeSeries ?? []).map((ts) => ts.code));
            return codes.has('wlp') && codes.has('wlp-hilo');
          })
          .filter((s) => typeof s.latitude === 'number' && typeof s.longitude === 'number')
          .map((s) => ({
            id: s.id,
            code: s.code ?? '',
            name: s.officialName || s.code || s.id,
            lat: s.latitude as number,
            lon: s.longitude as number,
          }));
        writeCache(STATIONS_KEY, stations);
        return stations;
      })
      .finally(() => {
        stationsPromise = null;
      });
  }
  return stationsPromise;
}

const tidesInFlight = new Map<string, Promise<TideData>>();
const tidesMemory = new Map<string, CacheEntry<TideData>>();

function isoZ(t: number): string {
  return new Date(t).toISOString().replace(/\.\d{3}Z$/, 'Z');
}

/** 15-minute predictions and classified high/low points for [start, end]. */
export function fetchTides(stationId: string, start: number, end: number): Promise<TideData> {
  const key = `mare-tide-card:tides:${stationId}:${start}:${end}`;
  const mem = tidesMemory.get(key);
  if (mem && Date.now() - mem.saved < TIDES_TTL) return Promise.resolve(mem.data);
  const stored = readCache<TideData>(key, TIDES_TTL);
  if (stored) {
    tidesMemory.set(key, { saved: Date.now(), data: stored });
    return Promise.resolve(stored);
  }
  let pending = tidesInFlight.get(key);
  if (!pending) {
    const common = { from: isoZ(start), to: isoZ(end) };
    const path = `/stations/${encodeURIComponent(stationId)}/data`;
    pending = Promise.all([
      getJson(path, { ...common, 'time-series-code': 'wlp', resolution: 'FIFTEEN_MINUTES' }),
      getJson(path, { ...common, 'time-series-code': 'wlp-hilo' }),
    ])
      .then(([rawPoints, rawHilo]) => {
        const toRaw = (list: unknown[]) =>
          (list as { eventDate?: string; value?: number }[]).map((r) => ({ time: r.eventDate, value: r.value }));
        const points = parsePoints(toRaw(rawPoints));
        if (points.length < 2) throw new Error('No predictions for this station');
        const data: TideData = { points, extremes: classifyExtremes(parsePoints(toRaw(rawHilo)), points) };
        tidesMemory.set(key, { saved: Date.now(), data });
        writeCache(key, data);
        pruneTideCache(stationId, key);
        return data;
      })
      .finally(() => tidesInFlight.delete(key));
    tidesInFlight.set(key, pending);
  }
  return pending;
}

/** Keep only the latest window per station in localStorage. */
function pruneTideCache(stationId: string, keep: string): void {
  try {
    const prefix = `mare-tide-card:tides:${stationId}:`;
    for (let i = localStorage.length - 1; i >= 0; i--) {
      const k = localStorage.key(i);
      if (k && k.startsWith(prefix) && k !== keep) localStorage.removeItem(k);
    }
  } catch {
    // ignore
  }
}
