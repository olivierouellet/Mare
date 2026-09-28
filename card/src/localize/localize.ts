import * as en from './languages/en.json';
import * as fr from './languages/fr.json';
import type { HomeAssistant, Language } from '../types';

export type Lang = 'en' | 'fr';

const languages: Record<Lang, Record<string, unknown>> = { en, fr };

/** The card's language: the `language` option, or Home Assistant's when "auto". */
export function resolveLanguage(option: Language | undefined, hass?: HomeAssistant): Lang {
  if (option === 'en' || option === 'fr') return option;
  const haLang = hass?.locale?.language ?? hass?.language ?? 'en';
  return haLang.toLowerCase().startsWith('fr') ? 'fr' : 'en';
}

/** Locale used for numbers, times and weekday names. */
export function intlLocale(lang: Lang): string {
  return lang === 'fr' ? 'fr-CA' : 'en-CA';
}

function lookup(path: string, dictionary: Record<string, unknown>): string | undefined {
  const value = path.split('.').reduce<unknown>((acc, key) => {
    if (acc && typeof acc === 'object' && key in (acc as Record<string, unknown>)) {
      return (acc as Record<string, unknown>)[key];
    }
    return undefined;
  }, dictionary);
  return typeof value === 'string' ? value : undefined;
}

/** Translate `key` (e.g. "card.now"), replacing {placeholders}; falls back to English, then the key. */
export function localize(key: string, lang: Lang, vars: Record<string, string> = {}): string {
  const text = lookup(key, languages[lang]) ?? lookup(key, languages.en) ?? key;
  return text.replace(/\{(\w+)\}/g, (match, name: string) => vars[name] ?? match);
}
