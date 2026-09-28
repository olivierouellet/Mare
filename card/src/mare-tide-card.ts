import { LitElement, html, svg, css, nothing, PropertyValues, TemplateResult } from 'lit';
import { customElement, property, state } from 'lit/decorators.js';

import type { HassEntity, HomeAssistant, MareTideCardConfig, TideData, TideExtreme } from './types';
import {
  CARD_TAG,
  CARD_VERSION,
  DEFAULT_STATION,
  EDITOR_TAG,
  MAX_HOURS,
  MIN_HOURS,
  WINDOW_DAYS_AFTER,
  WINDOW_DAYS_BEFORE,
} from './const';
import { fromEntity, interpolate } from './data/model';
import { fetchStations, fetchTides } from './data/dfo';
import { rankByDistance } from './geo';
import { ChartFormatters, ChartLayout, layoutChart } from './chart';
import { DAY, HOUR, resolveHour12, resolveTimeZone, startOfDay } from './time';
import { Lang, intlLocale, localize, resolveLanguage } from './localize/localize';

console.info(
  `%c  MARE-TIDE-CARD \n%c  Version ${CARD_VERSION}    `,
  'color: #0b6e99; font-weight: bold; background: #e6f4fa',
  'color: white; font-weight: bold; background: #0b6e99',
);

interface WindowWithCustomCards extends Window {
  customCards: Array<{ type: string; name: string; description: string; preview?: boolean; documentationURL?: string }>;
}
const w = window as unknown as WindowWithCustomCards;
w.customCards = w.customCards || [];
w.customCards.push({
  type: CARD_TAG,
  name: 'Mare Tide Card',
  description: 'Tides for Canadian stations (DFO / MPO) with every high and low tide. English / français.',
  preview: true,
});

const DEFAULTS = {
  show_header: true,
  span: 'day',
  hours: 24,
  hours_before: 6,
  height: 220,
  show_extremes: true,
  extreme_label: 'height_time',
  show_now: true,
  show_current: true,
  precision: 2,
  language: 'auto',
} as const;

type ResolvedConfig = MareTideCardConfig & Required<Pick<MareTideCardConfig, keyof typeof DEFAULTS>>;

/** HA "ui_color" names map to theme variables; anything else is used as a CSS color. */
const THEME_COLORS = new Set([
  'primary',
  'accent',
  'red',
  'pink',
  'purple',
  'deep-purple',
  'indigo',
  'blue',
  'light-blue',
  'cyan',
  'teal',
  'green',
  'light-green',
  'lime',
  'yellow',
  'amber',
  'orange',
  'deep-orange',
  'brown',
  'light-grey',
  'grey',
  'dark-grey',
  'blue-grey',
  'black',
  'white',
  'disabled',
]);

function cssColor(color?: string): string {
  if (!color) return 'var(--primary-color)';
  return THEME_COLORS.has(color) ? `var(--${color}-color)` : color;
}

let instanceCounter = 0;

@customElement(CARD_TAG)
export class MareTideCard extends LitElement {
  public static async getConfigElement(): Promise<HTMLElement> {
    await import('./editor');
    return document.createElement(EDITOR_TAG);
  }

  /** Default config when the card is added from the picker: a Mare sensor, else the station nearest home. */
  public static async getStubConfig(hass: HomeAssistant): Promise<Partial<MareTideCardConfig>> {
    const sensor = Object.values(hass.states).find((s) => Array.isArray(s.attributes.tide_data));
    if (sensor) return { entity: sensor.entity_id };
    try {
      const stations = await Promise.race([
        fetchStations(),
        new Promise<never>((_, reject) => setTimeout(() => reject(new Error('timeout')), 4000)),
      ]);
      const nearest = rankByDistance(stations, hass.config.latitude, hass.config.longitude)[0]?.station;
      if (nearest) return { station_id: nearest.id, station_name: nearest.name, station_code: nearest.code };
    } catch {
      // fall through to the default station
    }
    return { station_id: DEFAULT_STATION.id, station_name: DEFAULT_STATION.name, station_code: DEFAULT_STATION.code };
  }

  @property({ attribute: false }) public hass!: HomeAssistant;

  @state() private _config?: ResolvedConfig;
  @state() private _data: TideData | null = null;
  @state() private _error?: string;
  @state() private _width = 0;
  @state() private _height = 0;
  @state() private _now = Date.now();
  @state() private _hover?: { x: number; t: number; v: number };

  private _uid = `mare${++instanceCounter}`;
  private _stateObj?: HassEntity;
  private _fetchKey?: string;
  private _fetchedAt = 0;
  private _timer?: number;
  private _resizeObserver?: ResizeObserver;
  private _observed?: Element;

  public setConfig(config: MareTideCardConfig): void {
    if (!config) throw new Error('Invalid configuration');
    if (config.entity && config.station_id) throw new Error(localize('card.both_sources', 'en'));
    const hours = Math.min(Math.max(Number(config.hours ?? DEFAULTS.hours), MIN_HOURS), MAX_HOURS);
    const previous = this._config;
    this._config = { ...DEFAULTS, ...config, hours } as ResolvedConfig;
    if (previous?.entity !== config.entity || previous?.station_id !== config.station_id) {
      this._data = null;
      this._error = undefined;
      this._stateObj = undefined;
      this._fetchKey = undefined;
    }
  }

  public getCardSize(): number {
    const height = (this._config?.height ?? DEFAULTS.height) + (this._config?.show_header === false ? 0 : 70);
    return Math.ceil(height / 50);
  }

  public getGridOptions() {
    // Sections view: 4 rows by default, adjustable in the layout tab; the card fills
    // exactly that space. Below 3 rows the chart is unreadable.
    return { columns: 12, min_columns: 6, rows: 4, min_rows: 3 };
  }

  public connectedCallback(): void {
    super.connectedCallback();
    // Dashboards (masonry) detach and re-attach cards while laying out columns:
    // start watching the chart's width again once we are back in the page.
    this._observed = undefined;
    this.updateComplete.then(() => this._observeSize());
    this._timer = window.setInterval(() => {
      this._now = Date.now();
      if (this._config?.station_id && this._now - this._fetchedAt > HOUR) this._loadStation(true);
    }, 60_000);
  }

  public disconnectedCallback(): void {
    super.disconnectedCallback();
    window.clearInterval(this._timer);
    this._resizeObserver?.disconnect();
    this._observed = undefined;
  }

  protected firstUpdated(): void {
    this._observeSize();
  }

  protected updated(): void {
    // The chart container only exists once there is data.
    this._observeSize();
  }

  private _observeSize(): void {
    const el = this.shadowRoot?.querySelector('.chart') ?? undefined;
    if (el === this._observed) return;
    this._resizeObserver?.disconnect();
    this._observed = el;
    if (!el) return;
    this._resizeObserver = new ResizeObserver((entries) => {
      const { width, height } = entries[0].contentRect;
      if (Math.round(width) && Math.round(width) !== this._width) this._width = Math.round(width);
      if (Math.round(height) && Math.round(height) !== this._height) this._height = Math.round(height);
    });
    this._resizeObserver.observe(el);
  }

  protected willUpdate(changed: PropertyValues): void {
    if (!this._config || !this.hass) return;
    if (this._config.entity) {
      const stateObj = this.hass.states[this._config.entity];
      if (stateObj !== this._stateObj) {
        this._stateObj = stateObj;
        this._data = stateObj ? fromEntity(stateObj) : null;
      }
    } else if (this._config.station_id && (changed.has('_config') || !this._fetchKey)) {
      this._loadStation(false);
    }
  }

  private _tz(): string | undefined {
    return this.hass ? resolveTimeZone(this.hass) : undefined;
  }

  private async _loadStation(background: boolean): Promise<void> {
    const stationId = this._config?.station_id;
    if (!stationId) return;
    const midnight = startOfDay(Date.now(), this._tz());
    const start = midnight - WINDOW_DAYS_BEFORE * DAY;
    const end = midnight + WINDOW_DAYS_AFTER * DAY;
    const key = `${stationId}:${start}`;
    if (background && key === this._fetchKey && Date.now() - this._fetchedAt < HOUR) return;
    this._fetchKey = key;
    this._fetchedAt = Date.now();
    try {
      const data = await fetchTides(stationId, start, end);
      if (this._config?.station_id !== stationId) return;
      this._data = { ...data, stationName: this._config.station_name };
      this._error = undefined;
    } catch (err) {
      console.warn('mare-tide-card:', err);
      if (!this._data) this._error = 'card.fetch_failed';
    }
  }

  private _span(): { start: number; end: number } {
    const cfg = this._config!;
    const now = this._now;
    const start = cfg.span === 'rolling' ? now - cfg.hours_before * HOUR : startOfDay(now, this._tz());
    return { start, end: start + cfg.hours * HOUR };
  }

  private _formatters(lang: Lang): ChartFormatters & { current: Intl.NumberFormat } {
    const locale = intlLocale(lang);
    const timeZone = this._tz();
    const precision = Math.min(Math.max(this._config!.precision, 0), 3);
    const hour12Pref = resolveHour12(this.hass);
    const hour12 = hour12Pref ?? new Intl.DateTimeFormat(locale, { hour: 'numeric' }).resolvedOptions().hour12 ?? false;
    const num = new Intl.NumberFormat(locale, { minimumFractionDigits: precision, maximumFractionDigits: precision });
    const axis = new Intl.NumberFormat(locale, { maximumFractionDigits: 2 });
    const time = new Intl.DateTimeFormat(locale, { hour: 'numeric', minute: '2-digit', hour12, timeZone });
    // "15:00" in English 24 h, "15 h" in French, "3 p.m." in 12 h.
    const hour = new Intl.DateTimeFormat(
      locale,
      hour12 || lang === 'fr'
        ? { hour: 'numeric', hour12, timeZone }
        : { hour: '2-digit', minute: '2-digit', hour12, timeZone },
    );
    const day = new Intl.DateTimeFormat(locale, { weekday: 'short', day: 'numeric', timeZone });
    return {
      height: (v) => `${num.format(v)} m`,
      value: (v) => num.format(v),
      axis: (v) => axis.format(v),
      time: (t) => time.format(t),
      hour: (t) => hour.format(t),
      day: (t) => day.format(t),
      current: num,
    };
  }

  protected render(): TemplateResult | typeof nothing {
    if (!this._config || !this.hass) return nothing;
    const cfg = this._config;
    const lang = resolveLanguage(cfg.language, this.hass);
    const t = (key: string, vars?: Record<string, string>) => localize(key, lang, vars);

    let message: string | undefined;
    if (!cfg.entity && !cfg.station_id) message = t('card.no_source');
    else if (cfg.entity && !this.hass.states[cfg.entity]) message = t('card.entity_not_found', { entity: cfg.entity });
    else if (cfg.entity && !this._data) message = t('card.no_tide_data', { entity: cfg.entity });
    else if (this._error) message = t(this._error);

    const fmt = this._formatters(lang);
    const title = cfg.title || this._data?.stationName || cfg.station_name || t('card.default_title');

    return html`
      <ha-card style="--mare-color: ${cssColor(cfg.color)}">
        ${cfg.show_header ? this._renderHeader(title, lang, fmt) : nothing}
        ${
          message
            ? html`<div class="message">${message}</div>`
            : !this._data
              ? html`<div class="message muted chart-space" style="flex-basis:${cfg.height}px">
                  ${t('card.loading')}
                </div>`
              : this._renderChart(this._data, lang, fmt)
        }
      </ha-card>
    `;
  }

  private _renderHeader(
    title: string,
    lang: Lang,
    fmt: ChartFormatters & { current: Intl.NumberFormat },
  ): TemplateResult {
    const cfg = this._config!;
    const data = this._data;
    const t = (key: string) => localize(key, lang);
    const now = this._now;
    const current = data ? interpolate(data.points, now) : null;
    const next = (type: TideExtreme['type']) => data?.extremes.find((e) => e.type === type && e.t > now);
    const upcoming = [next('high'), next('low')].filter((e): e is TideExtreme => !!e).sort((a, b) => a.t - b.t);
    // Heading to a high means rising. Exact even right before a turn, unlike interpolating the curve.
    const rising = current !== null && upcoming.length ? upcoming[0].type === 'high' : undefined;
    const clickable = !!cfg.entity;

    return html`
      <div
        class="header ${clickable ? 'clickable' : ''}"
        @click=${clickable ? this._moreInfo : undefined}
        role=${clickable ? 'button' : nothing}
        tabindex=${clickable ? '0' : nothing}
      >
        <div class="title">${title}</div>
        ${
          cfg.show_current && current !== null
            ? html`<div class="current">
                <span class="level">${fmt.current.format(current)}<span class="unit"> m</span></span>
                ${
                  rising !== undefined
                    ? html`<span class="trend" title=${t(rising ? 'card.rising' : 'card.falling')}>
                        <ha-icon icon=${rising ? 'mdi:arrow-top-right' : 'mdi:arrow-bottom-right'}></ha-icon>
                        ${t(rising ? 'card.rising' : 'card.falling')}
                      </span>`
                    : nothing
                }
              </div>`
            : nothing
        }
        ${
          cfg.show_current && upcoming.length
            ? html`<div class="upcoming">
                ${upcoming.map(
                  (e) =>
                    html`<span
                      >${t(e.type === 'high' ? 'card.next_high' : 'card.next_low')} <b>${fmt.time(e.t)}</b> ·
                      ${fmt.height(e.v)}</span
                    >`,
                )}
              </div>`
            : nothing
        }
      </div>
    `;
  }

  private _renderChart(data: TideData, lang: Lang, fmt: ChartFormatters): TemplateResult {
    const cfg = this._config!;
    const { start, end } = this._span();
    const width = this._width || 0;
    // The measured height: the configured one, or the space given by a fixed number of rows.
    const height = this._height || cfg.height;
    const layout = width
      ? layoutChart({
          data,
          start,
          end,
          now: this._now,
          width,
          height,
          tz: this._tz(),
          showExtremes: cfg.show_extremes,
          // Short charts keep a single label line so the curve still has room.
          extremeLabel: cfg.extreme_label === 'height_time' && height < 170 ? 'height' : cfg.extreme_label,
          showNow: cfg.show_now,
          fmt,
        })
      : null;

    return html`
      <div
        class="chart chart-space"
        style="flex-basis:${cfg.height}px"
        @pointermove=${(ev: PointerEvent) => this._onPointer(ev, layout)}
        @pointerdown=${(ev: PointerEvent) => this._onPointer(ev, layout)}
        @pointerleave=${() => (this._hover = undefined)}
      >
        ${
          layout
            ? this._renderSvg(layout, lang)
            : width
              ? html`<div class="message muted">${localize('card.no_data_in_span', lang)}</div>`
              : nothing
        }
        ${layout && this._hover ? this._renderTooltip(layout, fmt) : nothing}
      </div>
    `;
  }

  private _renderSvg(layout: ChartLayout, lang: Lang): TemplateResult {
    const { plot, width, height } = layout;
    const gradient = `${this._uid}-fill`;
    const clip = `${this._uid}-clip`;
    const hover = this._hover;

    return html`<svg
      width="100%"
      height="100%"
      viewBox="0 0 ${width} ${height}"
      role="img"
      aria-label=${localize('card.default_title', lang)}
    >
      <defs>
        ${svg`<linearGradient id=${gradient} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" class="fill-top"></stop>
          <stop offset="1" class="fill-bottom"></stop>
        </linearGradient>
        <clipPath id=${clip}><rect x=${plot.left} y="0" width=${plot.right - plot.left} height=${height}></rect></clipPath>`}
      </defs>
      ${layout.yTicks.map(
        (tick) => svg`<line class="grid" x1=${plot.left} x2=${plot.right} y1=${tick.y} y2=${tick.y}></line>`,
      )}
      ${layout.dayLines.map(
        (x) => svg`<line class="day-line" x1=${x} x2=${x} y1=${plot.top - 4} y2=${plot.bottom + 4}></line>`,
      )}
      ${svg`<g clip-path="url(#${clip})">
        <path class="area" d=${layout.area} fill="url(#${gradient})"></path>
        <path class="line" d=${layout.line}></path>
      </g>`}
      ${layout.yTicks.map((tick) => svg`<text class="y-label" x=${plot.left + 2} y=${tick.y - 3}>${tick.label}</text>`)}
      ${
        layout.now
          ? svg`<line class="now-line" x1=${layout.now.x} x2=${layout.now.x} y1=${plot.top - 4} y2=${plot.bottom}></line>
            <circle class="now-dot" cx=${layout.now.x} cy=${layout.now.y} r="4.5"></circle>`
          : nothing
      }
      ${layout.extremes.map(
        (m) => svg`
          <circle class="extreme ${m.type}" cx=${m.x} cy=${m.y} r="3.5"></circle>
          ${m.lines.map(
            (l) =>
              svg`<text class="extreme-label ${l.primary ? 'primary' : ''}" x=${m.labelX} y=${l.y} text-anchor="middle">${l.text}</text>`,
          )}`,
      )}
      ${layout.xTicks.map(
        (tick) =>
          svg`<text class="x-label ${tick.major ? 'major' : ''}" x=${tick.x} y=${height - 5} text-anchor="middle">${tick.label}</text>`,
      )}
      ${
        hover
          ? svg`<line class="hover-line" x1=${hover.x} x2=${hover.x} y1=${plot.top - 4} y2=${plot.bottom}></line>
            <circle class="hover-dot" cx=${hover.x} cy=${layout.valueToY(hover.v)} r="4"></circle>`
          : nothing
      }
    </svg>`;
  }

  private _renderTooltip(layout: ChartLayout, fmt: ChartFormatters): TemplateResult {
    const hover = this._hover!;
    const alignRight = hover.x > layout.width / 2;
    const style = alignRight ? `right:${layout.width - hover.x + 8}px` : `left:${hover.x + 8}px`;
    return html`<div class="tooltip" style="${style}; top:${layout.plot.top}px">
      <div>${fmt.time(hover.t)}</div>
      <div class="tooltip-value">${fmt.height(hover.v)}</div>
    </div>`;
  }

  private _onPointer(ev: PointerEvent, layout: ChartLayout | null): void {
    if (!layout || !this._data) return;
    const rect = (ev.currentTarget as HTMLElement).getBoundingClientRect();
    const x = Math.min(Math.max(ev.clientX - rect.left, layout.plot.left), layout.plot.right);
    const t = layout.xToTime(x);
    const v = interpolate(this._data.points, t);
    this._hover = v === null ? undefined : { x, t, v };
  }

  private _moreInfo(): void {
    if (!this._config?.entity) return;
    this.dispatchEvent(
      new CustomEvent('hass-more-info', { detail: { entityId: this._config.entity }, bubbles: true, composed: true }),
    );
  }

  static styles = css`
    :host {
      --mare-color: var(--primary-color);
      display: block;
      height: 100%;
      min-width: 0;
    }
    ha-card {
      overflow: hidden;
      padding-bottom: 4px;
      box-sizing: border-box;
      height: 100%;
      display: flex;
      flex-direction: column;
    }
    .header {
      flex: 0 0 auto;
      display: flex;
      flex-wrap: wrap;
      align-items: baseline;
      justify-content: space-between;
      gap: 2px 12px;
      padding: 12px 16px 4px;
    }
    .header.clickable {
      cursor: pointer;
    }
    .title {
      flex: 1 1 8em;
      min-width: 0;
      font-size: 1.15em;
      font-weight: 500;
      color: var(--primary-text-color);
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
    .current {
      display: flex;
      flex-wrap: wrap;
      align-items: baseline;
      gap: 0 8px;
      min-width: 0;
    }
    .level,
    .trend,
    .upcoming b {
      white-space: nowrap;
    }
    .level {
      font-size: 1.6em;
      font-weight: 400;
      color: var(--primary-text-color);
      font-variant-numeric: tabular-nums;
    }
    .unit {
      font-size: 0.6em;
      color: var(--secondary-text-color);
    }
    .trend {
      display: inline-flex;
      align-items: center;
      gap: 2px;
      font-size: 0.85em;
      color: var(--secondary-text-color);
    }
    .trend ha-icon {
      --mdc-icon-size: 16px;
      color: var(--mare-color);
    }
    .upcoming {
      flex-basis: 100%;
      display: flex;
      flex-wrap: wrap;
      gap: 2px 16px;
      font-size: 0.85em;
      color: var(--secondary-text-color);
    }
    .upcoming b {
      font-weight: 500;
      color: var(--primary-text-color);
    }
    .chart-space {
      /* Configured height by default; grows or shrinks to fill a fixed number of rows. */
      flex: 1 1 auto;
      min-height: 60px;
      min-width: 0;
    }
    .chart {
      position: relative;
      margin: 0 12px;
      touch-action: pan-y;
      user-select: none;
    }
    svg {
      /* Out of the flow so the chart never widens or heightens its container. */
      position: absolute;
      inset: 0;
      display: block;
      overflow: visible;
      font-family: inherit;
    }
    .grid {
      stroke: var(--divider-color);
      stroke-width: 1;
      opacity: 0.6;
    }
    .day-line {
      stroke: var(--divider-color);
      stroke-width: 1;
      stroke-dasharray: 2 3;
    }
    .y-label,
    .extreme-label {
      /* A halo in the card colour keeps text readable over the curve and grid. */
      paint-order: stroke;
      stroke: var(--card-background-color, var(--ha-card-background, #fff));
      stroke-width: 3px;
      stroke-linejoin: round;
    }
    .y-label {
      font-size: 10px;
      fill: var(--secondary-text-color);
      opacity: 0.8;
    }
    .x-label {
      font-size: 11px;
      fill: var(--secondary-text-color);
    }
    .x-label.major {
      font-weight: 600;
      fill: var(--primary-text-color);
    }
    .fill-top {
      stop-color: var(--mare-color);
      stop-opacity: 0.35;
    }
    .fill-bottom {
      stop-color: var(--mare-color);
      stop-opacity: 0.03;
    }
    .line {
      fill: none;
      stroke: var(--mare-color);
      stroke-width: 2.5;
      stroke-linejoin: round;
      stroke-linecap: round;
    }
    .now-line {
      stroke: var(--primary-text-color);
      stroke-width: 1;
      stroke-dasharray: 3 3;
      opacity: 0.55;
    }
    .now-dot {
      fill: var(--card-background-color, var(--ha-card-background, #fff));
      stroke: var(--mare-color);
      stroke-width: 2.5;
    }
    .extreme {
      fill: var(--mare-color);
      stroke: var(--card-background-color, var(--ha-card-background, #fff));
      stroke-width: 1.5;
    }
    .extreme-label {
      font-size: 11px;
      fill: var(--secondary-text-color);
      font-variant-numeric: tabular-nums;
    }
    .extreme-label.primary {
      font-weight: 600;
      fill: var(--primary-text-color);
    }
    .hover-line {
      stroke: var(--mare-color);
      stroke-width: 1;
      opacity: 0.7;
    }
    .hover-dot {
      fill: var(--mare-color);
    }
    .tooltip {
      position: absolute;
      pointer-events: none;
      padding: 4px 8px;
      border-radius: 6px;
      background: var(--card-background-color, var(--ha-card-background, #fff));
      box-shadow: var(--ha-card-box-shadow, 0 1px 4px rgba(0, 0, 0, 0.2));
      border: 1px solid var(--divider-color);
      font-size: 12px;
      color: var(--secondary-text-color);
      white-space: nowrap;
    }
    .tooltip-value {
      font-weight: 600;
      color: var(--primary-text-color);
    }
    .message {
      display: flex;
      align-items: center;
      justify-content: center;
      text-align: center;
      padding: 16px;
      color: var(--warning-color, #b58100);
    }
    .message.muted {
      color: var(--secondary-text-color);
    }
  `;
}

declare global {
  interface HTMLElementTagNameMap {
    'mare-tide-card': MareTideCard;
  }
}
