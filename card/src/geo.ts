import type { Station } from './types';

export function haversineKm(lat1: number, lon1: number, lat2: number, lon2: number): number {
  const rad = Math.PI / 180;
  const dLat = (lat2 - lat1) * rad;
  const dLon = (lon2 - lon1) * rad;
  const a = Math.sin(dLat / 2) ** 2 + Math.cos(lat1 * rad) * Math.cos(lat2 * rad) * Math.sin(dLon / 2) ** 2;
  return 2 * 6371 * Math.asin(Math.sqrt(a));
}

export interface RankedStation {
  station: Station;
  km: number;
}

export function rankByDistance(stations: Station[], lat: number, lon: number): RankedStation[] {
  return stations
    .map((station) => ({ station, km: haversineKm(lat, lon, station.lat, station.lon) }))
    .sort((a, b) => a.km - b.km);
}

/** Lower-case and strip accents so "riviere" matches "Rivière". */
export function fold(text: string): string {
  return text
    .normalize('NFD')
    .replace(/\p{Diacritic}/gu, '')
    .toLowerCase();
}

export function searchStations(stations: Station[], query: string, lat: number, lon: number): RankedStation[] {
  const needle = fold(query.trim());
  if (!needle) return [];
  return rankByDistance(
    stations.filter((s) => fold(s.name).includes(needle) || s.code.includes(needle)),
    lat,
    lon,
  );
}

export function formatKm(km: number, locale: string): string {
  const digits = km < 10 ? 1 : 0;
  return `${new Intl.NumberFormat(locale, { maximumFractionDigits: digits, minimumFractionDigits: digits }).format(km)} km`;
}
