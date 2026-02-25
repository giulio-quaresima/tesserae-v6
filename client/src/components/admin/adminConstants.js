export const LANG_NAMES = { la: 'Latin', grc: 'Greek', en: 'English' };

export const CACHE_IMPACT_INFO = {
  search: {
    title: 'Search Results Cache',
    description: 'Stores results of recent text comparisons',
    impact: [
      'Previously cached search results will need to be recomputed',
      'Next searches between the same texts may be slower initially',
      'Does NOT affect lemma data, frequencies, or corpus structure'
    ],
    severity: 'low',
    rebuildTime: 'Rebuilds automatically as users run searches'
  },
  lemma: {
    title: 'Lemma Cache',
    description: 'Stores lemmatized (dictionary form) versions of all texts',
    impact: [
      'ALL text processing will need to be redone on next search',
      'First searches after clearing will be VERY slow (minutes per text)',
      'Each text must be re-processed before its words can be matched',
      'Consider rebuilding cache before heavy usage'
    ],
    severity: 'high',
    rebuildTime: 'Rebuilds automatically but slowly when texts are searched. For faster recovery, manually rebuild for each language.'
  },
  frequency: {
    title: 'Frequency Cache',
    description: 'Stores word frequency statistics for IDF scoring',
    impact: [
      'Search scoring will use default weights until recalculated',
      'Stoplist generation may be less accurate',
      'Rare word detection will be affected',
      'Results may be less relevant until frequencies are recalculated'
    ],
    severity: 'medium',
    rebuildTime: 'Use "Recalculate Corpus Frequencies" button to rebuild'
  }
};
