import { useState, useEffect } from 'react';

const LANG_LABELS = { la: 'Latin', grc: 'Greek', en: 'English' };

export default function TextCredits() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [expandedSources, setExpandedSources] = useState({});
  const [filterLang, setFilterLang] = useState('all');

  useEffect(() => {
    fetch('/api/text-credits')
      .then(res => res.json())
      .then(d => { setData(d); setLoading(false); })
      .catch(err => { setError(err.message); setLoading(false); });
  }, []);

  const toggleSource = (key) => {
    setExpandedSources(prev => ({ ...prev, [key]: !prev[key] }));
  };

  const formatDate = (dateStr) => {
    if (!dateStr) return '';
    try {
      const d = new Date(dateStr);
      return d.toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' });
    } catch { return dateStr; }
  };

  if (loading) {
    return (
      <div className="bg-white rounded-lg shadow p-8 text-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-red-700 mx-auto mb-4"></div>
        <p className="text-gray-600">Loading text credits...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-white rounded-lg shadow p-8">
        <p className="text-red-600">Failed to load text credits: {error}</p>
      </div>
    );
  }

  const sources = data?.sources || [];

  const filteredSources = sources.map(source => {
    if (filterLang === 'all') return source;
    const filtered = source.texts.filter(t => t.language === filterLang);
    if (filtered.length === 0) return null;
    return { ...source, texts: filtered, text_count: filtered.length };
  }).filter(Boolean);

  return (
    <div className="bg-white rounded-lg shadow p-4 sm:p-8">
      <h2 className="text-2xl font-semibold text-gray-900 mb-2">Text Credits & Provenance</h2>
      <p className="text-gray-600 mb-6">
        This page acknowledges the sources and contributors of the texts in the Tesserae corpus.
        Each text's provenance is tracked to credit the projects and institutions that make these
        resources available for scholarly research.
      </p>

      <div className="flex flex-wrap items-center gap-4 mb-6">
        <div className="bg-red-50 rounded-lg px-4 py-2">
          <span className="text-2xl font-bold text-red-700">{data?.total_texts || 0}</span>
          <span className="text-sm text-gray-600 ml-2">Total Texts</span>
        </div>
        <div className="bg-amber-50 rounded-lg px-4 py-2">
          <span className="text-2xl font-bold text-amber-700">{filteredSources.length}</span>
          <span className="text-sm text-gray-600 ml-2">Sources</span>
        </div>
        <div className="ml-auto flex items-center gap-2">
          <label className="text-sm text-gray-600">Filter:</label>
          <select
            value={filterLang}
            onChange={(e) => setFilterLang(e.target.value)}
            className="text-sm border border-gray-300 rounded px-2 py-1"
          >
            <option value="all">All Languages</option>
            <option value="la">Latin</option>
            <option value="grc">Greek</option>
            <option value="en">English</option>
          </select>
        </div>
      </div>

      <div className="space-y-4">
        {filteredSources.map((source) => {
          const isExpanded = expandedSources[source.source_key];
          return (
            <div key={source.source_key} className="border border-gray-200 rounded-lg overflow-hidden">
              <button
                onClick={() => toggleSource(source.source_key)}
                className="w-full flex items-center justify-between px-4 py-3 bg-gray-50 hover:bg-gray-100 text-left"
              >
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-3">
                    <h3 className="font-semibold text-gray-900 truncate">{source.source_name}</h3>
                    <span className="flex-shrink-0 bg-red-100 text-red-700 text-xs font-medium px-2 py-0.5 rounded-full">
                      {source.text_count} {source.text_count === 1 ? 'text' : 'texts'}
                    </span>
                  </div>
                  {source.description && (
                    <p className="text-sm text-gray-500 mt-0.5 truncate">{source.description}</p>
                  )}
                  {source.source_url && (
                    <a
                      href={source.source_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-xs text-amber-600 hover:underline"
                      onClick={(e) => e.stopPropagation()}
                    >
                      {source.source_url}
                    </a>
                  )}
                </div>
                <svg
                  className={`w-5 h-5 text-gray-400 flex-shrink-0 ml-2 transition-transform ${isExpanded ? 'rotate-180' : ''}`}
                  fill="none" viewBox="0 0 24 24" stroke="currentColor"
                >
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                </svg>
              </button>

              {isExpanded && (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="bg-gray-50 border-t border-gray-200">
                        <th className="text-left px-4 py-2 font-medium text-gray-600">Author</th>
                        <th className="text-left px-4 py-2 font-medium text-gray-600">Work</th>
                        <th className="text-left px-4 py-2 font-medium text-gray-600">Language</th>
                        <th className="text-left px-4 py-2 font-medium text-gray-600">Date Added</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-100">
                      {source.texts.map((text) => (
                        <tr key={text.id} className="hover:bg-gray-50">
                          <td className="px-4 py-2 text-gray-900">{text.author}</td>
                          <td className="px-4 py-2 text-gray-700">{text.title}</td>
                          <td className="px-4 py-2">
                            <span className={`text-xs px-1.5 py-0.5 rounded ${
                              text.language === 'la' ? 'bg-red-50 text-red-700' :
                              text.language === 'grc' ? 'bg-amber-50 text-amber-700' :
                              'bg-green-50 text-green-700'
                            }`}>
                              {LANG_LABELS[text.language] || text.language}
                            </span>
                          </td>
                          <td className="px-4 py-2 text-gray-500 text-xs">{formatDate(text.date_added)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
