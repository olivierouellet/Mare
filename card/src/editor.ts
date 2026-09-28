import { LitElement, html, css, nothing, TemplateResult } from 'lit';
import { customElement, property, state } from 'lit/decorators.js';

import type { HomeAssistant, MareTideCardConfig, Station } from './types';
import { EDITOR_TAG, INTEGRATION_DOMAIN, MAX_HOURS, MIN_HOURS } from './const';
import { Lang, localize, resolveLanguage } from './localize/localize';
import './station-picker';

type Source = 'sensor' | 'direct';

/** Values the editor shows when the config does not set them (same as the card's defaults). */
const FORM_DEFAULTS: Partial<MareTideCardConfig> = {
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
};

interface FormSchema {
  name: string;
  type?: string;
  title?: string;
  flatten?: boolean;
  expanded?: boolean;
  selector?: Record<string, unknown>;
  schema?: FormSchema[];
}

@customElement(EDITOR_TAG)
export class MareTideCardEditor extends LitElement {
  @property({ attribute: false }) public hass!: HomeAssistant;

  @state() private _config?: MareTideCardConfig;
  @state() private _source?: Source;

  public setConfig(config: MareTideCardConfig): void {
    this._config = config;
    if (config.station_id) this._source = 'direct';
    else if (config.entity) this._source = 'sensor';
  }

  private get _lang(): Lang {
    return resolveLanguage(this._config?.language, this.hass);
  }

  private _t(key: string): string {
    return localize(key, this._lang);
  }

  /** Entities of the Mare integration that carry a tide curve (i.e. the tide level sensors). */
  private _tideSensors(): string[] {
    return Object.values(this.hass.states)
      .filter((s) => Array.isArray(s.attributes.tide_data))
      .map((s) => s.entity_id);
  }

  private _currentSource(): Source {
    if (this._source) return this._source;
    return this._tideSensors().length ? 'sensor' : 'direct';
  }

  protected render(): TemplateResult | typeof nothing {
    if (!this.hass || !this._config) return nothing;
    const source = this._currentSource();
    const sensors = this._tideSensors();

    return html`
      <ha-form
        .hass=${this.hass}
        .data=${{ source }}
        .schema=${[
          {
            name: 'source',
            selector: {
              select: {
                mode: 'list',
                options: [
                  { value: 'sensor', label: this._t('editor.source_sensor') },
                  { value: 'direct', label: this._t('editor.source_direct') },
                ],
              },
            },
          },
        ]}
        .computeLabel=${this._computeLabel}
        @value-changed=${this._sourceChanged}
      ></ha-form>

      <div class="source">${source === 'sensor' ? this._renderSensor(sensors) : this._renderDirect()}</div>

      <ha-form
        .hass=${this.hass}
        .data=${{ ...FORM_DEFAULTS, ...this._config }}
        .schema=${this._optionsSchema()}
        .computeLabel=${this._computeLabel}
        .computeHelper=${this._computeHelper}
        @value-changed=${this._optionsChanged}
      ></ha-form>
    `;
  }

  private _renderSensor(sensors: string[]): TemplateResult {
    if (!sensors.length) return html`<div class="note">${this._t('editor.no_sensor')}</div>`;
    return html`
      <ha-form
        .hass=${this.hass}
        .data=${{ entity: this._config!.entity }}
        .schema=${[{ name: 'entity', selector: { entity: { include_entities: sensors } } }]}
        .computeLabel=${this._computeLabel}
        @value-changed=${this._entityChanged}
      ></ha-form>
      <a class="link" href="/config/integrations/integration/${INTEGRATION_DOMAIN}" target="_blank" rel="noopener">
        <ha-icon icon="mdi:map-marker-radius"></ha-icon>${this._t('editor.change_station')}
      </a>
    `;
  }

  private _renderDirect(): TemplateResult {
    return html`<mare-station-picker
      .hass=${this.hass}
      .lang=${this._lang}
      .value=${this._config!.station_id}
      @station-picked=${this._stationPicked}
    ></mare-station-picker>`;
  }

  private _optionsSchema(): FormSchema[] {
    const t = (key: string) => this._t(`editor.${key}`);
    const rolling = this._config?.span === 'rolling';
    return [
      { name: 'title', selector: { text: {} } },
      {
        name: 'language',
        selector: {
          select: {
            mode: 'dropdown',
            options: [
              { value: 'auto', label: t('lang_auto') },
              { value: 'en', label: t('lang_en') },
              { value: 'fr', label: t('lang_fr') },
            ],
          },
        },
      },
      {
        name: '',
        type: 'expandable',
        flatten: true,
        expanded: true,
        title: t('section_range'),
        schema: [
          {
            name: 'span',
            selector: {
              select: {
                mode: 'list',
                options: [
                  { value: 'day', label: t('span_day') },
                  { value: 'rolling', label: t('span_rolling') },
                ],
              },
            },
          },
          {
            name: 'hours',
            selector: { number: { min: MIN_HOURS, max: MAX_HOURS, step: 1, mode: 'slider', unit_of_measurement: 'h' } },
          },
          ...(rolling
            ? [
                {
                  name: 'hours_before',
                  selector: { number: { min: 0, max: 24, step: 1, mode: 'slider', unit_of_measurement: 'h' } },
                },
              ]
            : []),
        ],
      },
      {
        name: '',
        type: 'expandable',
        flatten: true,
        title: t('section_display'),
        schema: [
          {
            name: '',
            type: 'grid',
            schema: [
              {
                name: 'height',
                selector: { number: { min: 120, max: 600, step: 10, mode: 'box', unit_of_measurement: 'px' } },
              },
              { name: 'precision', selector: { number: { min: 0, max: 3, step: 1, mode: 'box' } } },
            ],
          },
          { name: 'color', selector: { ui_color: { default_color: 'primary' } } },
          {
            name: 'extreme_label',
            selector: {
              select: {
                mode: 'dropdown',
                options: [
                  { value: 'height_time', label: t('label_height_time') },
                  { value: 'height', label: t('label_height') },
                  { value: 'time', label: t('label_time') },
                ],
              },
            },
          },
          {
            name: '',
            type: 'grid',
            schema: [
              { name: 'show_extremes', selector: { boolean: {} } },
              { name: 'show_now', selector: { boolean: {} } },
              { name: 'show_header', selector: { boolean: {} } },
              { name: 'show_current', selector: { boolean: {} } },
            ],
          },
        ],
      },
    ];
  }

  private _computeLabel = (schema: FormSchema): string => this._t(`editor.${schema.name}`);

  private _computeHelper = (schema: FormSchema): string | undefined =>
    schema.name === 'title' ? this._t('editor.title_helper') : undefined;

  private _sourceChanged(ev: CustomEvent): void {
    ev.stopPropagation();
    const source = ev.detail.value.source as Source;
    if (source === this._currentSource()) return;
    this._source = source;
    const config = { ...this._config! };
    if (source === 'sensor') {
      delete config.station_id;
      delete config.station_name;
      delete config.station_code;
      const first = this._tideSensors()[0];
      if (first) config.entity = first;
    } else {
      delete config.entity;
    }
    this._update(config);
  }

  private _entityChanged(ev: CustomEvent): void {
    ev.stopPropagation();
    const entity = ev.detail.value.entity as string | undefined;
    const config = { ...this._config! };
    if (entity) config.entity = entity;
    else delete config.entity;
    this._update(config);
  }

  private _stationPicked(ev: CustomEvent<{ station: Station }>): void {
    ev.stopPropagation();
    const { station } = ev.detail;
    const config = { ...this._config! };
    delete config.entity;
    config.station_id = station.id;
    config.station_name = station.name;
    config.station_code = station.code;
    this._update(config);
  }

  private _optionsChanged(ev: CustomEvent): void {
    ev.stopPropagation();
    const value = ev.detail.value as Partial<MareTideCardConfig>;
    const config: Record<string, unknown> = { ...this._config! };
    for (const [key, val] of Object.entries(value)) {
      const isDefault = (FORM_DEFAULTS as Record<string, unknown>)[key] === val;
      // Keep the YAML short: drop empty values and values equal to the defaults.
      if (val === undefined || val === '' || isDefault) delete config[key];
      else config[key] = val;
    }
    this._update(config as unknown as MareTideCardConfig);
  }

  private _update(config: MareTideCardConfig): void {
    this._config = config;
    this.dispatchEvent(new CustomEvent('config-changed', { detail: { config }, bubbles: true, composed: true }));
  }

  static styles = css`
    :host {
      display: block;
    }
    .source {
      margin: 8px 0 20px;
    }
    .link {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      margin-top: 8px;
      color: var(--primary-color);
      text-decoration: none;
      font-size: 0.9em;
    }
    .link ha-icon {
      --mdc-icon-size: 18px;
    }
    .note {
      padding: 8px 0;
      color: var(--secondary-text-color);
    }
  `;
}

declare global {
  interface HTMLElementTagNameMap {
    'mare-tide-card-editor': MareTideCardEditor;
  }
}
