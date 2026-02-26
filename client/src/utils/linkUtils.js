/**
 * Shared utilities for generating external reference links.
 */

export function getDictionaryUrl(word, language) {
  if (!word) return null;
  if (language === 'en') {
    return `https://en.wiktionary.org/wiki/${encodeURIComponent(word)}`;
  }
  // Latin and Greek both use Logeion
  return `https://logeion.uchicago.edu/${encodeURIComponent(word)}`;
}
