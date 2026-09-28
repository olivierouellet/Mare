/**
 * Dev harness: renders several card configurations and the editor with a mock `hass`,
 * plus minimal stand-ins for ha-card, ha-icon and ha-form. Run with `yarn start`.
 */
import '../src/mare-tide-card';
import '../src/editor';
import type { HomeAssistant, MareTideCardConfig } from '../src/types';
import wlp from './halifax_wlp.json';
import hilo from './halifax_hilo.json';
import { classifyExtremes, parsePoints } from '../src/data/model';

/* ---------- stand-ins for Home Assistant elements ---------- */

class HaCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: 'open' }).innerHTML = `<style>:host{display:block;background:var(--card-background-color);
      border-radius:var(--ha-card-border-radius);box-shadow:var(--ha-card-box-shadow);color:var(--primary-text-color)}</style><slot></slot>`;
  }
}
customElements.define('ha-card', HaCard);

const ICONS: Record<string, string> = {
  'mdi:arrow-top-right': '↗',
  'mdi:arrow-bottom-right': '↘',
  'mdi:crosshairs-gps': '⌖',
  'mdi:home': '⌂',
  'mdi:radiobox-marked': '◉',
  'mdi:radiobox-blank': '○',
  'mdi:map-marker-radius': '⌖',
};
class HaIcon extends HTMLElement {
  static observedAttributes = ['icon'];
  attributeChangedCallback() {
    this.textContent = ICONS[this.getAttribute('icon') ?? ''] ?? '•';
  }
}
customElements.define('ha-icon', HaIcon);

interface Schema {
  name: string;
  type?: string;
  title?: string;
  selector?: Record<string, Record<string, unknown>>;
  schema?: Schema[];
}

/** Very small ha-form: enough to exercise the editor's schema, labels and value-changed events. */
class HaForm extends HTMLElement {
  data: Record<string, unknown> = {};
  schema: Schema[] = [];
  computeLabel?: (s: Schema) => string;
  computeHelper?: (s: Schema) => string | undefined;
  hass?: unknown;
  private _raf = 0;

  connectedCallback() {
    this._schedule();
  }

  _schedule() {
    cancelAnimationFrame(this._raf);
    this._raf = requestAnimationFrame(() => this._render());
  }

  private _emit(name: string, value: unknown) {
    const data = { ...this.data, [name]: value };
    this.dispatchEvent(new CustomEvent('value-changed', { detail: { value: data } }));
  }

  private _field(s: Schema): HTMLElement {
    const wrap = document.createElement('div');
    wrap.style.cssText = 'margin:6px 0;display:flex;flex-direction:column;gap:2px;font-size:14px';
    if (s.type === 'expandable' || s.type === 'grid') {
      if (s.title) {
        const h = document.createElement('div');
        h.textContent = `▾ ${s.title}`;
        h.style.cssText = 'font-weight:600;margin-top:10px';
        wrap.append(h);
      }
      const inner = document.createElement('div');
      inner.style.cssText =
        s.type === 'grid' ? 'display:grid;grid-template-columns:1fr 1fr;gap:4px 12px' : 'padding-left:8px';
      (s.schema ?? []).forEach((c) => inner.append(this._field(c)));
      wrap.append(inner);
      return wrap;
    }
    const label = document.createElement('label');
    label.textContent = this.computeLabel?.(s) ?? s.name;
    label.style.color = 'var(--secondary-text-color)';
    wrap.append(label);
    const [kind, cfg] = Object.entries(s.selector ?? { text: {} })[0];
    const value = this.data[s.name];
    let input: HTMLElement;
    if (kind === 'boolean') {
      const cb = document.createElement('input');
      cb.type = 'checkbox';
      cb.checked = !!value;
      cb.onchange = () => this._emit(s.name, cb.checked);
      label.prepend(cb);
      return wrap;
    } else if (kind === 'select' || kind === 'entity') {
      const options =
        kind === 'entity'
          ? ((cfg.include_entities as string[]) ?? []).map((e) => ({ value: e, label: e }))
          : (cfg.options as { value: string; label: string }[]);
      const sel = document.createElement('select');
      options.forEach((o) => sel.append(new Option(o.label, o.value, false, o.value === value)));
      sel.onchange = () => this._emit(s.name, sel.value);
      input = sel;
    } else if (kind === 'number') {
      const num = document.createElement('input');
      num.type = cfg.mode === 'slider' ? 'range' : 'number';
      Object.assign(num, { min: String(cfg.min), max: String(cfg.max), step: String(cfg.step ?? 1) });
      num.value = String(value ?? '');
      num.onchange = () => this._emit(s.name, Number(num.value));
      input = num;
      const out = document.createElement('span');
      out.textContent = `${value ?? ''} ${cfg.unit_of_measurement ?? ''}`;
      wrap.append(out);
    } else if (kind === 'ui_color') {
      const sel = document.createElement('select');
      ['', 'primary', 'accent', 'blue', 'teal', '#8e44ad'].forEach((c) =>
        sel.append(new Option(c || '(default)', c, false, c === (value ?? ''))),
      );
      sel.onchange = () => this._emit(s.name, sel.value || undefined);
      input = sel;
    } else {
      const txt = document.createElement('input');
      txt.value = String(value ?? '');
      txt.onchange = () => this._emit(s.name, txt.value);
      input = txt;
    }
    wrap.append(input);
    const helper = this.computeHelper?.(s);
    if (helper) {
      const h = document.createElement('small');
      h.textContent = helper;
      wrap.append(h);
    }
    return wrap;
  }

  private _render() {
    this.replaceChildren(...this.schema.map((s) => this._field(s)));
  }
}
// Re-render whenever Lit assigns data/schema.
for (const prop of ['data', 'schema']) {
  const key = `__${prop}`;
  Object.defineProperty(HaForm.prototype, prop, {
    get() {
      return this[key];
    },
    set(v) {
      this[key] = v;
      this._schedule?.();
    },
  });
}
customElements.define('ha-form', HaForm);

/* ---------- mock hass ---------- */

const points = parsePoints(
  (wlp as { eventDate: string; value: number }[]).map((r) => ({ time: r.eventDate, value: r.value })),
);
const extremes = classifyExtremes(
  parsePoints((hilo as { eventDate: string; value: number }[]).map((r) => ({ time: r.eventDate, value: r.value }))),
  points,
);

function makeHass(lang: string, timeFormat: string): HomeAssistant {
  return {
    language: lang,
    locale: { language: lang, time_format: timeFormat, time_zone: 'server' },
    config: { latitude: 44.6488, longitude: -63.5752, time_zone: 'America/Halifax' },
    states: {
      'sensor.halifax_tide_level': {
        entity_id: 'sensor.halifax_tide_level',
        state: '1.04',
        last_updated: new Date().toISOString(),
        attributes: {
          station_name: 'Halifax',
          tide_data: points.map((p) => ({ time: new Date(p.t).toISOString(), value: p.v })),
          tide_extremes: extremes.map((e) => ({ time: new Date(e.t).toISOString(), value: e.v, type: e.type })),
        },
      },
      'sensor.old_style': {
        entity_id: 'sensor.old_style',
        state: '1.04',
        last_updated: new Date().toISOString(),
        attributes: { tide_data: points.map((p) => ({ time: new Date(p.t).toISOString(), value: p.v })) },
      },
    },
  };
}

/* ---------- page ---------- */

const CASES: { title: string; config: Partial<MareTideCardConfig> }[] = [
  { title: 'Sensor · today (24 h)', config: { entity: 'sensor.halifax_tide_level' } },
  {
    title: 'Sensor · rolling 48 h, 6 h back',
    config: { entity: 'sensor.halifax_tide_level', span: 'rolling', hours: 48 },
  },
  { title: 'Sensor · 72 h from midnight', config: { entity: 'sensor.halifax_tide_level', hours: 72, color: 'teal' } },
  { title: 'Sensor without tide_extremes (detected)', config: { entity: 'sensor.old_style', language: 'fr' } },
  {
    title: 'Direct from DFO (live API) · Bedford',
    config: {
      station_id: '5cebf1e23d0f4a073c4bbfac',
      station_name: 'Bedford Institute',
      hours: 36,
      span: 'rolling',
      hours_before: 3,
    },
  },
  { title: 'Errors: missing entity', config: { entity: 'sensor.nope' } },
];

const $ = <T extends HTMLElement>(id: string) => document.getElementById(id) as T;
const cards: HTMLElement[] = [];
let hass = makeHass('en', 'language');
let editorConfig: MareTideCardConfig = { type: 'custom:mare-tide-card', entity: 'sensor.halifax_tide_level' };

function build() {
  const root = $('cards');
  root.replaceChildren();
  cards.length = 0;
  const width = $<HTMLSelectElement>('width').value;
  root.style.gridTemplateColumns = width ? `repeat(auto-fill, ${width}px)` : '';
  for (const c of CASES) {
    const cell = document.createElement('div');
    cell.className = 'cell';
    cell.innerHTML = `<h3>${c.title}</h3>`;
    const card = document.createElement('mare-tide-card') as HTMLElement & {
      setConfig(c: MareTideCardConfig): void;
      hass: HomeAssistant;
    };
    card.setConfig({ type: 'custom:mare-tide-card', ...c.config });
    card.hass = hass;
    cell.append(card);
    root.append(cell);
    cards.push(card);
  }
  // Editor + live preview
  const cell = document.createElement('div');
  cell.className = 'cell';
  cell.innerHTML = '<h3>Editor → preview</h3>';
  const preview = document.createElement('mare-tide-card') as HTMLElement & {
    setConfig(c: MareTideCardConfig): void;
    hass: HomeAssistant;
  };
  preview.setConfig(editorConfig);
  preview.hass = hass;
  const editor = document.createElement('mare-tide-card-editor') as HTMLElement & {
    setConfig(c: MareTideCardConfig): void;
    hass: HomeAssistant;
  };
  editor.className = 'editor';
  editor.hass = hass;
  editor.setConfig(editorConfig);
  const yaml = document.createElement('pre');
  yaml.textContent = JSON.stringify(editorConfig, null, 2);
  editor.addEventListener('config-changed', (ev) => {
    editorConfig = (ev as CustomEvent).detail.config;
    yaml.textContent = JSON.stringify(editorConfig, null, 2);
    try {
      preview.setConfig(editorConfig);
    } catch (err) {
      yaml.textContent += `\n${err}`;
    }
    editor.setConfig(editorConfig);
  });
  cell.append(preview, yaml, editor);
  root.append(cell);
  cards.push(preview, editor);
}

function applyHass() {
  hass = makeHass($<HTMLSelectElement>('lang').value, $<HTMLSelectElement>('tf').value);
  cards.forEach((c) => ((c as unknown as { hass: HomeAssistant }).hass = hass));
}

// Optional frozen "now" so the fixture window (26 Sep – 1 Oct 2026) is always in range.
const realNow = Date.now.bind(Date);
const nowInput = $<HTMLInputElement>('now');
const fixtureNow = Date.parse('2026-09-27T15:00:00Z');
const initialNow = realNow() > points[0].t && realNow() < points[points.length - 1].t ? realNow() : fixtureNow;
let offset = initialNow - realNow();
Date.now = () => realNow() + offset;
nowInput.value = new Date(initialNow - new Date(initialNow).getTimezoneOffset() * 60000).toISOString().slice(0, 16);
nowInput.onchange = () => {
  offset = new Date(nowInput.value).getTime() - realNow();
  build();
};

// URL parameters for screenshots: ?dark&lang=fr&tf=24&width=320&direct&only=editor
const params = new URLSearchParams(location.search);
if (params.has('dark')) {
  $<HTMLInputElement>('dark').checked = true;
  document.body.classList.add('dark');
}
if (params.get('lang')) $<HTMLSelectElement>('lang').value = params.get('lang')!;
if (params.get('tf')) $<HTMLSelectElement>('tf').value = params.get('tf')!;
if (params.get('width')) $<HTMLSelectElement>('width').value = params.get('width')!;
if (params.has('direct')) {
  editorConfig = { type: 'custom:mare-tide-card', station_id: '5cebf1df3d0f4a073c4bbcbb', station_name: 'Halifax' };
}
if (params.get('only') === 'editor') CASES.length = 0;
hass = makeHass($<HTMLSelectElement>('lang').value, $<HTMLSelectElement>('tf').value);

$<HTMLInputElement>('dark').onchange = (ev) =>
  document.body.classList.toggle('dark', (ev.target as HTMLInputElement).checked);
$('lang').onchange = applyHass;
$('tf').onchange = applyHass;
$('width').onchange = build;
build();
