/** The parts of Home Assistant's `hass` object this card uses. */
export interface HassEntity {
  entity_id: string;
  state: string;
  attributes: Record<string, unknown>;
  last_updated: string;
}

export interface HomeAssistant {
  states: Record<string, HassEntity>;
  config: { latitude: number; longitude: number; time_zone: string };
  language?: string;
  locale?: { language: string; time_format?: string; time_zone?: string };
  entities?: Record<string, { platform?: string }>;
}

export type Language = 'auto' | 'en' | 'fr';
export type TimeFormat = 'auto' | '12' | '24';
export type SpanMode = 'day' | 'rolling';
export type ExtremeLabel = 'height_time' | 'height' | 'time';

export interface MareTideCardConfig {
  type: string;
  entity?: string;
  station_id?: string;
  station_name?: string;
  station_code?: string;
  title?: string;
  show_header?: boolean;
  span?: SpanMode;
  hours?: number;
  hours_before?: number;
  height?: number;
  color?: string;
  show_extremes?: boolean;
  extreme_label?: ExtremeLabel;
  show_now?: boolean;
  show_current?: boolean;
  precision?: number;
  language?: Language;
  time_format?: TimeFormat;
}

export interface TidePoint {
  t: number; // epoch ms
  v: number; // metres
}

export interface TideExtreme extends TidePoint {
  type: 'high' | 'low';
}

/** One model for both data sources (sensor attributes or direct API). */
export interface TideData {
  points: TidePoint[];
  extremes: TideExtreme[];
  stationName?: string;
}

export interface Station {
  id: string;
  code: string;
  name: string;
  lat: number;
  lon: number;
}

declare global {
  interface HASSDomEvents {
    'config-changed': { config: MareTideCardConfig };
  }
}
