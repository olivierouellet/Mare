export const CARD_VERSION = '0.2.0';
export const CARD_TAG = 'mare-tide-card';
export const EDITOR_TAG = 'mare-tide-card-editor';
export const PICKER_TAG = 'mare-station-picker';

/** Integration domain of the companion Home Assistant integration. */
export const INTEGRATION_DOMAIN = 'dfo_tides';

/** Fetched window relative to local midnight today; mirrors the integration. */
export const WINDOW_DAYS_BEFORE = 1;
export const WINDOW_DAYS_AFTER = 4;

export const MIN_HOURS = 6;
export const MAX_HOURS = 72;
export const NEAREST_COUNT = 5;
export const SEARCH_LIMIT = 20;

/** Fallback station (Halifax) when nothing else is known. */
export const DEFAULT_STATION = { id: '5cebf1df3d0f4a073c4bbcbb', name: 'Halifax', code: '00490' };
