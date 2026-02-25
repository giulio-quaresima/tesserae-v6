/**
 * Shared Greek text utilities for display and normalization.
 */

export const displayGreekWithFinalSigma = (text) => {
  if (!text) return text;
  return text.replace(/σ(?=\s|$|[,.;:!?])/g, 'ς');
};

export const normalizeGreek = (text) => {
  if (!text) return '';
  return text
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
    .replace(/ς/g, 'σ');
};
