import {messages} from './messages.mjs';
export const supportedLocales = Object.freeze(Object.keys(messages));
export function resolveLocale(locale='en') {
  const base = typeof locale === 'string' ? locale.trim().toLowerCase().replaceAll('_','-').split('-')[0] : '';
  return Object.hasOwn(messages,base) ? base : 'en';
}
export function message(code, locale='en', {limit}={}) {
  const catalog=messages[resolveLocale(locale)];
  if (!Object.hasOwn(catalog,code)) throw new RangeError('Unknown message code');
  if (code === 'UPLOAD_TOO_LARGE') {
    if (!Number.isSafeInteger(limit) || limit < 1) throw new RangeError('A positive integer MB limit is required');
    return catalog[code].replace('{limit}',String(limit));
  }
  return catalog[code];
}
