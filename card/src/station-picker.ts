import { LitElement, html, css, nothing, TemplateResult } from 'lit';
import { customElement, property, state } from 'lit/decorators.js';

import type { HomeAssistant, Station } from './types';
import { NEAREST_COUNT, PICKER_TAG, SEARCH_LIMIT } from './const';
import { fetchStations } from './data/dfo';
import { RankedStation, formatKm, rankByDistance, searchStations } from './geo';
import { Lang, intlLocale, localize } from './localize/localize';

type GeoStatus = 'locating' | 'unavailable' | 'denied' | 'failed';

/**
 * Lists the stations nearest to home (or to the device's position), with a search
 * over all stations. Fires `station-picked` with the chosen Station.
 */
@customElement(PICKER_TAG)
export class MareStationPicker extends LitElement {
  @property({ attribute: false }) public hass!: HomeAssistant;
  @property() public lang: Lang = 'en';
  @property() public value?: string;

  @state() private _stations?: Station[];
  @state() private _failed = false;
  @state() private _position?: { lat: number; lon: number };
  @state() private _geo?: GeoStatus;
  @state() private _query = '';

  public connectedCallback(): void {
    super.connectedCallback();
    if (!this._stations) this._load();
  }

  private async _load(): Promise<void> {
    this._failed = false;
    try {
      this._stations = await fetchStations();
    } catch (err) {
      console.warn('mare-tide-card:', err);
      this._failed = true;
    }
  }

  private _origin(): { lat: number; lon: number } {
    return this._position ?? { lat: this.hass.config.latitude, lon: this.hass.config.longitude };
  }

  private _useGps(): void {
    if (!window.isSecureContext || !navigator.geolocation) {
      this._geo = 'unavailable';
      return;
    }
    this._geo = 'locating';
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        this._position = { lat: pos.coords.latitude, lon: pos.coords.longitude };
        this._geo = undefined;
      },
      (err) => {
        this._geo = err.code === err.PERMISSION_DENIED ? 'denied' : 'failed';
      },
      { enableHighAccuracy: false, timeout: 15_000, maximumAge: 300_000 },
    );
  }

  private _useHome(): void {
    this._position = undefined;
    this._geo = undefined;
  }

  private _pick(station: Station): void {
    this.dispatchEvent(new CustomEvent('station-picked', { detail: { station }, bubbles: true, composed: true }));
  }

  protected render(): TemplateResult {
    const t = (key: string) => localize(`picker.${key}`, this.lang);
    if (this._failed) {
      return html`<div class="status error">
        ${t('failed')} <button class="link" @click=${this._load}>${t('retry')}</button>
      </div>`;
    }
    if (!this._stations) return html`<div class="status">${t('loading')}</div>`;

    const { lat, lon } = this._origin();
    const searching = this._query.trim().length > 0;
    const rows: RankedStation[] = searching
      ? searchStations(this._stations, this._query, lat, lon).slice(0, SEARCH_LIMIT)
      : rankByDistance(this._stations, lat, lon).slice(0, NEAREST_COUNT);
    const selected = this.value ? this._stations.find((s) => s.id === this.value) : undefined;
    if (selected && !rows.some((r) => r.station.id === selected.id)) {
      rows.unshift(rankByDistance([selected], lat, lon)[0]);
    }

    return html`
      <div class="origin">
        <span class="caption">${searching ? t('search') : t(this._position ? 'near_me' : 'near_home')}</span>
        ${
          this._position
            ? html`<button class="link" @click=${this._useHome}>
                <ha-icon icon="mdi:home"></ha-icon>${t('use_home')}
              </button>`
            : html`<button class="link" @click=${this._useGps} ?disabled=${this._geo === 'locating'}>
                <ha-icon icon="mdi:crosshairs-gps"></ha-icon
                >${t(this._geo === 'locating' ? 'locating' : 'use_position')}
              </button>`
        }
      </div>
      ${
        this._geo && this._geo !== 'locating' ? html`<div class="status error">${t(`geo_${this._geo}`)}</div>` : nothing
      }
      <input
        type="search"
        .value=${this._query}
        placeholder="${t('search_placeholder')}"
        aria-label=${t('search')}
        @input=${(ev: Event) => (this._query = (ev.target as HTMLInputElement).value)}
      />
      <div class="list" role="listbox">
        ${
          rows.length
            ? rows.map(({ station, km }) => this._row(station, km))
            : html`<div class="status">${t('no_match')}</div>`
        }
      </div>
    `;
  }

  private _row(station: Station, km: number): TemplateResult {
    const active = station.id === this.value;
    return html`<button
      class="row ${active ? 'active' : ''}"
      role="option"
      aria-selected=${active ? 'true' : 'false'}
      @click=${() => this._pick(station)}
    >
      <ha-icon icon=${active ? 'mdi:radiobox-marked' : 'mdi:radiobox-blank'}></ha-icon>
      <span class="name">${station.name}</span>
      <span class="meta">${station.code} · ${formatKm(km, intlLocale(this.lang))}</span>
    </button>`;
  }

  static styles = css`
    :host {
      display: block;
    }
    .origin {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 8px;
      margin-bottom: 8px;
    }
    .caption {
      font-weight: 500;
      color: var(--primary-text-color);
    }
    button {
      font: inherit;
      color: inherit;
      background: none;
      border: none;
      cursor: pointer;
    }
    .link {
      display: inline-flex;
      align-items: center;
      gap: 4px;
      padding: 4px 6px;
      border-radius: 6px;
      color: var(--primary-color);
      font-size: 0.9em;
    }
    .link:hover {
      background: rgba(var(--rgb-primary-color, 3, 169, 244), 0.08);
    }
    .link[disabled] {
      opacity: 0.6;
      cursor: default;
    }
    .link ha-icon {
      --mdc-icon-size: 18px;
    }
    input {
      box-sizing: border-box;
      width: 100%;
      padding: 10px 12px;
      margin-bottom: 8px;
      font: inherit;
      color: var(--primary-text-color);
      background: var(--input-fill-color, var(--secondary-background-color));
      border: 1px solid var(--divider-color);
      border-radius: 8px;
      outline: none;
    }
    input:focus {
      border-color: var(--primary-color);
    }
    .list {
      display: flex;
      flex-direction: column;
      border: 1px solid var(--divider-color);
      border-radius: 8px;
      overflow: hidden;
      max-height: 320px;
      overflow-y: auto;
    }
    .row {
      display: grid;
      grid-template-columns: auto 1fr auto;
      align-items: center;
      gap: 10px;
      padding: 10px 12px;
      text-align: start;
      border-bottom: 1px solid var(--divider-color);
    }
    .row:last-child {
      border-bottom: none;
    }
    .row:hover {
      background: var(--secondary-background-color);
    }
    .row.active {
      background: rgba(var(--rgb-primary-color, 3, 169, 244), 0.1);
    }
    .row ha-icon {
      --mdc-icon-size: 20px;
      color: var(--secondary-text-color);
    }
    .row.active ha-icon {
      color: var(--primary-color);
    }
    .name {
      color: var(--primary-text-color);
    }
    .meta {
      color: var(--secondary-text-color);
      font-size: 0.85em;
      white-space: nowrap;
      font-variant-numeric: tabular-nums;
    }
    .status {
      padding: 8px 4px;
      color: var(--secondary-text-color);
    }
    .status.error {
      color: var(--warning-color, #b58100);
    }
  `;
}

declare global {
  interface HTMLElementTagNameMap {
    'mare-station-picker': MareStationPicker;
  }
}
