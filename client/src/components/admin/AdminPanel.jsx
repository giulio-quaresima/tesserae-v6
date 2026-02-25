import { useState, useEffect } from 'react';
import { LoadingSpinner } from '../common';
import { LANG_NAMES, CACHE_IMPACT_INFO } from './adminConstants';
import StatsTab from './tabs/StatsTab';
import FeedbackTab from './tabs/FeedbackTab';
import SettingsTab from './tabs/SettingsTab';
import AuditTab from './tabs/AuditTab';

export default function AdminPanel() {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [adminUsername, setAdminUsername] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [authError, setAuthError] = useState('');
  const [activeTab, setActiveTab] = useState('requests');
  const [loading, setLoading] = useState(false);
  
  const [textRequests, setTextRequests] = useState([]);
  const [feedback, setFeedback] = useState([]);
  const [corpusStats, setCorpusStats] = useState(null);
  const [analytics, setAnalytics] = useState(null);
  const [cacheInfo, setCacheInfo] = useState(null);
  

  
  const [confirmModal, setConfirmModal] = useState(null);
  const [clearingCache, setClearingCache] = useState(null);
  const [cacheError, setCacheError] = useState(null);
  const [loadError, setLoadError] = useState(null);
  
  const [selectedRequest, setSelectedRequest] = useState(null);
  const [editingRequest, setEditingRequest] = useState(null);
  const [savingRequest, setSavingRequest] = useState(false);
  const [tessPreview, setTessPreview] = useState('');
  
  
  const [sourcesData, setSourcesData] = useState([]);
  const [sourcesLoading, setSourcesLoading] = useState(false);
  const [sourcesFilter, setSourcesFilter] = useState('');
  const [editingSource, setEditingSource] = useState(null);
  const [addingSource, setAddingSource] = useState(false);
  const [newSource, setNewSource] = useState({ author: '', work: '', e_source: '', e_source_url: '', print_source: '', added_by: '' });
  const [sourcesSaving, setSourcesSaving] = useState(false);
  const [sourcesMessage, setSourcesMessage] = useState(null);
  
  const [bigramStats, setBigramStats] = useState({});
  const [buildingBigram, setBuildingBigram] = useState(null);
  const [bigramError, setBigramError] = useState(null);
  const [bigramSuccess, setBigramSuccess] = useState(null);

  const [corpusTexts, setCorpusTexts] = useState([]);
  const [corpusTextsLoading, setCorpusTextsLoading] = useState(false);
  const [corpusTextsFilter, setCorpusTextsFilter] = useState('');
  const [corpusTextsLang, setCorpusTextsLang] = useState('');
  const [corpusTextsTypeFilter, setCorpusTextsTypeFilter] = useState('');
  const [editingMetadata, setEditingMetadata] = useState(null);
  const [metadataSaving, setMetadataSaving] = useState(false);
  const [metadataMessage, setMetadataMessage] = useState(null);

  const handleLogin = async () => {
    setAuthError('');
    if (!adminUsername.trim()) {
      setAuthError('Please enter your username');
      return;
    }
    try {
      const res = await fetch('/api/admin/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ password, username: adminUsername })
      });
      const data = await res.json();
      if (data.success) {
        setIsAuthenticated(true);
        loadAdminData();
      } else {
        setAuthError('Invalid password');
      }
    } catch (err) {
      setAuthError('Authentication failed');
    }
  };

  const loadAdminData = async () => {
    setLoading(true);
    setLoadError(null);
    try {
      const headers = { 'X-Admin-Password': password, 'X-Admin-Username': adminUsername };
      const [requestsRes, feedbackRes, corpusRes, analyticsRes, lemmaCacheRes, searchCacheRes, frequencyCacheRes, bigramRes] = await Promise.all([
        fetch('/api/admin/requests', { headers }),
        fetch('/api/admin/feedback', { headers }),
        fetch('/api/corpus-status'),
        fetch('/api/admin/analytics', { headers }),
        fetch('/api/admin/lemma-cache/stats', { headers }),
        fetch('/api/admin/search-cache/stats', { headers }),
        fetch('/api/admin/frequency-cache/stats', { headers }),
        fetch('/api/admin/bigram-cache/stats', { headers })
      ]);
      
      const requests = await requestsRes.json();
      const feedbackData = feedbackRes.ok ? await feedbackRes.json() : [];
      const corpus = corpusRes.ok ? await corpusRes.json() : null;
      const analyticsData = analyticsRes.ok ? await analyticsRes.json() : null;
      const lemmaCache = lemmaCacheRes.ok ? await lemmaCacheRes.json() : {};
      const searchCache = searchCacheRes.ok ? await searchCacheRes.json() : {};
      const frequencyCache = frequencyCacheRes.ok ? await frequencyCacheRes.json() : {};
      const bigramData = bigramRes.ok ? await bigramRes.json() : {};
      
      setTextRequests(requests.requests || []);
      setFeedback(Array.isArray(feedbackData) ? feedbackData : []);
      setCorpusStats(corpus?.summary?.total_texts || null);
      setAnalytics(analyticsData);
      setCacheInfo({
        lemma_cache_size: lemmaCache.total_count || 0,
        search_cache_size: searchCache.cached_searches || 0,
        frequency_cache_size: frequencyCache.total_entries || 0
      });
      setBigramStats(bigramData);
    } catch (err) {
      console.error('Failed to load admin data:', err);
      setLoadError('Failed to load some admin data. Some statistics may be unavailable.');
    }
    setLoading(false);
  };



  const approveRequest = async (requestId) => {
    try {
      await fetch(`/api/admin/requests/${requestId}/approve`, {
        method: 'POST',
        headers: { 'X-Admin-Password': password, 'X-Admin-Username': adminUsername }
      });
      loadAdminData();
    } catch (err) {
      console.error('Failed to approve request:', err);
    }
  };

  const deleteRequest = async (requestId) => {
    if (!window.confirm('Are you sure you want to delete this text request? This cannot be undone.')) {
      return;
    }
    try {
      await fetch(`/api/admin/requests/${requestId}`, {
        method: 'DELETE',
        headers: { 
          'X-Admin-Password': password,
          'X-Admin-Username': adminUsername
        }
      });
      loadAdminData();
      setSelectedRequest(null);
    } catch (err) {
      console.error('Failed to delete request:', err);
    }
  };

  const openRequestDetails = (request) => {
    setSelectedRequest(request);
    setEditingRequest({
      official_author: request.official_author || request.author || '',
      official_work: request.official_work || request.work || '',
      approved_filename: request.approved_filename || request.suggested_filename || '',
      text_date: request.text_date || '',
      admin_notes: request.admin_notes || '',
      content: request.content || '',
      author_era: request.author_era || '',
      author_year: request.author_year != null ? String(request.author_year) : '',
      e_source: request.e_source || '',
      e_source_url: request.e_source_url || '',
      print_source: request.print_source || '',
      added_by: request.added_by || ''
    });
    updateTessPreview(request.content || '', request.official_author || request.author, request.official_work || request.work);
  };

  const updateTessPreview = (rawContent, author, work) => {
    if (!rawContent || !author || !work) {
      setTessPreview('');
      return;
    }
    const safeAuthor = author.toLowerCase().replace(/\s+/g, '_').replace(/[^a-z0-9._-]/g, '');
    const safeWork = work.toLowerCase().replace(/\s+/g, '_').replace(/[^a-z0-9._-]/g, '');
    const lines = rawContent.split('\n').filter(l => l.trim());
    const formatted = lines.slice(0, 10).map((line, idx) => {
      return `<${safeAuthor}.${safeWork}.${idx + 1}> ${line.trim()}`;
    });
    if (lines.length > 10) {
      formatted.push(`... and ${lines.length - 10} more lines`);
    }
    setTessPreview(formatted.join('\n'));
  };

  const saveRequestChanges = async () => {
    if (!selectedRequest || !editingRequest) return;
    setSavingRequest(true);
    try {
      await fetch(`/api/admin/requests/${selectedRequest.id}`, {
        method: 'PUT',
        headers: { 
          'Content-Type': 'application/json',
          'X-Admin-Password': password,
          'X-Admin-Username': adminUsername
        },
        body: JSON.stringify(editingRequest)
      });
      loadAdminData();
      setSelectedRequest(null);
    } catch (err) {
      console.error('Failed to save request changes:', err);
    }
    setSavingRequest(false);
  };

  const approveWithEdits = async () => {
    if (!selectedRequest || !editingRequest) return;
    setSavingRequest(true);
    try {
      await fetch(`/api/admin/requests/${selectedRequest.id}`, {
        method: 'PUT',
        headers: { 
          'Content-Type': 'application/json',
          'X-Admin-Password': password,
          'X-Admin-Username': adminUsername
        },
        body: JSON.stringify({
          ...editingRequest,
          status: 'approved'
        })
      });
      await fetch(`/api/admin/requests/${selectedRequest.id}/approve`, {
        method: 'POST',
        headers: { 
          'Content-Type': 'application/json',
          'X-Admin-Password': password,
          'X-Admin-Username': adminUsername
        },
        body: JSON.stringify({ content: editingRequest.content })
      });
      loadAdminData();
      setSelectedRequest(null);
    } catch (err) {
      console.error('Failed to approve request:', err);
    }
    setSavingRequest(false);
  };

  const generateFilename = () => {
    if (!editingRequest) return;
    const author = editingRequest.official_author || '';
    const work = editingRequest.official_work || '';
    const safeAuthor = author.toLowerCase().replace(/\s+/g, '_').replace(/[^a-z0-9._-]/g, '');
    const safeWork = work.toLowerCase().replace(/\s+/g, '_').replace(/[^a-z0-9._-]/g, '');
    setEditingRequest(prev => ({ ...prev, approved_filename: `${safeAuthor}.${safeWork}.tess` }));
  };

  const showCacheConfirmation = (cacheType) => {
    const info = CACHE_IMPACT_INFO[cacheType];
    if (!info) return;
    
    const entryCount = cacheType === 'search' 
      ? cacheInfo?.search_cache_size 
      : cacheType === 'lemma' 
        ? cacheInfo?.lemma_cache_size 
        : cacheInfo?.frequency_cache_size;
    
    setCacheError(null);
    setConfirmModal({
      cacheType,
      ...info,
      entryCount: entryCount || 0
    });
  };

  const clearCache = async (cacheType) => {
    setClearingCache(cacheType);
    setCacheError(null);
    try {
      let endpoint;
      switch (cacheType) {
        case 'search':
          endpoint = '/api/admin/search-cache/clear';
          break;
        case 'lemma':
          endpoint = '/api/admin/lemma-cache/clear';
          break;
        case 'frequency':
          endpoint = '/api/admin/frequency-cache/clear';
          break;
        default:
          endpoint = '/api/admin/lemma-cache/clear';
      }
      
      const response = await fetch(endpoint, {
        method: 'POST',
        headers: { 
          'Content-Type': 'application/json',
          'X-Admin-Password': password,
          'X-Admin-Username': adminUsername
        },
        body: JSON.stringify({})
      });
      
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.error || `Failed to clear ${cacheType} cache`);
      }
      
      await loadAdminData();
      setConfirmModal(null);
    } catch (err) {
      console.error('Failed to clear cache:', err);
      setCacheError(`Failed to clear ${cacheType} cache: ${err.message}`);
    }
    setClearingCache(null);
  };

  const recalculateFrequencies = async () => {
    try {
      await fetch('/api/frequencies/recalculate', {
        method: 'POST',
        headers: { 'X-Admin-Password': password, 'X-Admin-Username': adminUsername }
      });
      alert('Frequency recalculation started');
    } catch (err) {
      console.error('Failed to recalculate frequencies:', err);
    }
  };

  const buildBigramIndex = async (language) => {
    setBuildingBigram(language);
    setBigramError(null);
    setBigramSuccess(null);
    try {
      const res = await fetch('/api/admin/bigram-cache/build', {
        method: 'POST',
        headers: { 
          'Content-Type': 'application/json',
          'X-Admin-Password': password, 
          'X-Admin-Username': adminUsername 
        },
        body: JSON.stringify({ language })
      });
      const data = await res.json();
      if (res.ok) {
        setBigramSuccess(`${LANG_NAMES[language]} bigram index built: ${data.unique_bigrams?.toLocaleString() || 0} unique pairs`);
        const bigramRes = await fetch('/api/admin/bigram-cache/stats', {
          headers: { 'X-Admin-Password': password, 'X-Admin-Username': adminUsername }
        });
        if (bigramRes.ok) {
          setBigramStats(await bigramRes.json());
        }
      } else {
        setBigramError(data.error || 'Failed to build bigram index');
      }
    } catch (err) {
      console.error('Failed to build bigram index:', err);
      setBigramError('Failed to build bigram index: ' + err.message);
    }
    setBuildingBigram(null);
  };


  useEffect(() => {
    if (isAuthenticated && activeTab === 'sources') {
      loadSources();
    }
  }, [isAuthenticated, activeTab]);

  useEffect(() => {
    if (isAuthenticated && activeTab === 'metadata') {
      loadCorpusTexts();
    }
  }, [isAuthenticated, activeTab, corpusTextsLang]);

  const loadCorpusTexts = async () => {
    setCorpusTextsLoading(true);
    try {
      const params = corpusTextsLang ? `?language=${corpusTextsLang}` : '';
      const res = await fetch(`/api/admin/corpus-texts${params}`, {
        headers: { 'X-Admin-Password': password, 'X-Admin-Username': adminUsername }
      });
      const data = await res.json();
      setCorpusTexts(data.texts || []);
    } catch (e) {
      console.error('Failed to load corpus texts:', e);
    }
    setCorpusTextsLoading(false);
  };

  const saveMetadataOverride = async (textId, fields) => {
    setMetadataSaving(true);
    setMetadataMessage(null);
    try {
      const res = await fetch(`/api/admin/text-metadata/${textId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json', 'X-Admin-Password': password, 'X-Admin-Username': adminUsername },
        body: JSON.stringify(fields)
      });
      if (res.ok) {
        setMetadataMessage({ type: 'success', text: `Metadata updated for ${textId}` });
        setEditingMetadata(null);
        loadCorpusTexts();
      } else {
        const err = await res.json();
        setMetadataMessage({ type: 'error', text: err.error || 'Failed to save' });
      }
    } catch (e) {
      setMetadataMessage({ type: 'error', text: e.message });
    }
    setMetadataSaving(false);
  };

  const clearMetadataOverride = async (textId) => {
    if (!window.confirm(`Remove all metadata overrides for ${textId}? It will revert to auto-detected values.`)) return;
    await saveMetadataOverride(textId, {});
  };

  const filteredCorpusTexts = corpusTexts.filter(t => {
    const q = corpusTextsFilter.toLowerCase();
    const matchesText = !q || t.author?.toLowerCase().includes(q) || t.title?.toLowerCase().includes(q) || t.id?.toLowerCase().includes(q);
    const matchesLang = !corpusTextsLang || t.language === corpusTextsLang;
    const matchesType = !corpusTextsTypeFilter || t.text_type === corpusTextsTypeFilter;
    return matchesText && matchesLang && matchesType;
  });

  const loadSources = async () => {
    setSourcesLoading(true);
    try {
      const res = await fetch('/api/admin/sources', {
        headers: { 'X-Admin-Password': password, 'X-Admin-Username': adminUsername }
      });
      const data = await res.json();
      setSourcesData(data.sources || []);
    } catch (e) {
      console.error('Failed to load sources:', e);
    }
    setSourcesLoading(false);
  };

  const saveSource = async (id, updates) => {
    setSourcesSaving(true);
    setSourcesMessage(null);
    try {
      const res = await fetch(`/api/admin/sources/${id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json', 'X-Admin-Password': password, 'X-Admin-Username': adminUsername },
        body: JSON.stringify(updates)
      });
      if (res.ok) {
        setSourcesMessage({ type: 'success', text: 'Source updated successfully' });
        setEditingSource(null);
        loadSources();
      } else {
        const err = await res.json();
        setSourcesMessage({ type: 'error', text: err.error || 'Failed to update' });
      }
    } catch (e) {
      setSourcesMessage({ type: 'error', text: e.message });
    }
    setSourcesSaving(false);
  };

  const deleteSource = async (id, author, work) => {
    if (!window.confirm(`Delete source entry for "${author} - ${work}"?`)) return;
    try {
      const res = await fetch(`/api/admin/sources/${id}`, {
        method: 'DELETE',
        headers: { 'X-Admin-Password': password, 'X-Admin-Username': adminUsername }
      });
      if (res.ok) {
        setSourcesMessage({ type: 'success', text: 'Source deleted' });
        loadSources();
      }
    } catch (e) {
      setSourcesMessage({ type: 'error', text: e.message });
    }
  };

  const addNewSource = async () => {
    if (!newSource.author && !newSource.work) return;
    setSourcesSaving(true);
    setSourcesMessage(null);
    try {
      const res = await fetch('/api/admin/sources', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-Admin-Password': password, 'X-Admin-Username': adminUsername },
        body: JSON.stringify(newSource)
      });
      if (res.ok) {
        setSourcesMessage({ type: 'success', text: 'Source added successfully' });
        setNewSource({ author: '', work: '', e_source: '', e_source_url: '', print_source: '', added_by: '' });
        setAddingSource(false);
        loadSources();
      } else {
        const err = await res.json();
        setSourcesMessage({ type: 'error', text: err.error || 'Failed to add' });
      }
    } catch (e) {
      setSourcesMessage({ type: 'error', text: e.message });
    }
    setSourcesSaving(false);
  };

  const filteredSources = sourcesData.filter(s => {
    if (!sourcesFilter.trim()) return true;
    const q = sourcesFilter.toLowerCase();
    return (s.author || '').toLowerCase().includes(q) ||
           (s.work || '').toLowerCase().includes(q) ||
           (s.e_source || '').toLowerCase().includes(q);
  });

  if (!isAuthenticated) {
    return (
      <div className="max-w-md mx-auto mt-12">
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-xl font-semibold text-gray-900 mb-4">Admin Login</h2>
          <div className="space-y-4">
            <div>
              <label className="block text-sm text-gray-600 mb-1">Username</label>
              <input
                type="text"
                value={adminUsername}
                onChange={e => setAdminUsername(e.target.value)}
                className="w-full border rounded px-3 py-2"
                placeholder="Enter your admin username"
              />
            </div>
            <div>
              <label className="block text-sm text-gray-600 mb-1">Password</label>
              <div className="relative">
                <input
                  type={showPassword ? "text" : "password"}
                  value={password}
                  onChange={e => setPassword(e.target.value)}
                  onKeyDown={e => e.key === 'Enter' && handleLogin()}
                  className="w-full border rounded px-3 py-2 pr-10"
                  placeholder="Enter admin password"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-500 hover:text-gray-700 text-sm"
                >
                  {showPassword ? 'Hide' : 'Show'}
                </button>
              </div>
            </div>
            {authError && (
              <div className="text-red-600 text-sm">{authError}</div>
            )}
            <button
              onClick={handleLogin}
              className="w-full px-4 py-2 bg-red-700 text-white rounded hover:bg-red-800"
            >
              Login
            </button>
          </div>
        </div>
      </div>
    );
  }

  if (loading) {
    return <LoadingSpinner text="Loading admin data..." />;
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold text-gray-900">Admin Panel</h2>
        <button
          onClick={() => setIsAuthenticated(false)}
          className="text-sm text-gray-500 hover:text-gray-700"
        >
          Logout
        </button>
      </div>

      {loadError && (
        <div className="bg-amber-50 border border-amber-300 rounded-lg p-4 flex items-start gap-3">
          <span className="text-amber-600">⚠️</span>
          <div>
            <div className="font-medium text-amber-800">Warning</div>
            <p className="text-sm text-amber-700">{loadError}</p>
          </div>
        </div>
      )}

      <div className="bg-white rounded-lg shadow">
        <div className="border-b">
          <nav className="flex flex-wrap">
            {['requests', 'feedback', 'sources', 'metadata', 'cache', 'stats', 'analytics', 'audit', 'settings'].map(tab => (
              <button
                key={tab}
                onClick={() => setActiveTab(tab)}
                className={`px-4 py-3 text-sm font-medium border-b-2 ${
                  activeTab === tab 
                    ? 'border-red-700 text-red-700' 
                    : 'border-transparent text-gray-500 hover:text-gray-700'
                }`}
              >
                {tab === 'requests' ? 'Text Requests' : 
                 tab === 'feedback' ? 'Feedback' :
                 tab === 'sources' ? 'Sources' :
                 tab === 'metadata' ? 'Corpus Metadata' :
                 tab === 'cache' ? 'Cache Management' : 
                 tab === 'stats' ? 'Corpus Stats' :
                 tab === 'analytics' ? 'User Analytics' :
                 tab === 'audit' ? 'Audit Log' : 'Settings'}
              </button>
            ))}
          </nav>
        </div>

        <div className="p-4">
          {activeTab === 'requests' && (
            <div className="space-y-4">
              <div className="flex justify-between items-center">
                <h3 className="font-medium text-gray-900">Text Requests</h3>
                <div className="text-sm text-gray-500">
                  {textRequests.filter(r => r.status === 'pending').length} pending
                </div>
              </div>
              
              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-gray-200">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">Status</th>
                      <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">Author</th>
                      <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">Work</th>
                      <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">Language</th>
                      <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">Date Submitted</th>
                      <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">Last Edit</th>
                      <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="bg-white divide-y divide-gray-200">
                    {textRequests.length === 0 ? (
                      <tr>
                        <td colSpan="7" className="px-3 py-8 text-center text-sm text-gray-500">
                          No text requests
                        </td>
                      </tr>
                    ) : textRequests.map(request => (
                      <tr key={request.id} className="hover:bg-gray-50 cursor-pointer" onClick={() => openRequestDetails(request)}>
                        <td className="px-3 py-2 whitespace-nowrap">
                          <span className={`px-2 py-0.5 text-xs rounded ${
                            request.status === 'approved' ? 'bg-amber-100 text-amber-700' :
                            request.status === 'rejected' ? 'bg-red-100 text-red-700' :
                            'bg-amber-100 text-amber-700'
                          }`}>
                            {request.status || 'pending'}
                          </span>
                        </td>
                        <td className="px-3 py-2 text-sm text-gray-900">{request.author}</td>
                        <td className="px-3 py-2 text-sm text-gray-900">{request.work}</td>
                        <td className="px-3 py-2 text-sm text-gray-500">{LANG_NAMES[request.language] || request.language}</td>
                        <td className="px-3 py-2 text-sm text-gray-500">
                          {request.created_at ? new Date(request.created_at).toLocaleString() : '-'}
                        </td>
                        <td className="px-3 py-2 text-sm text-gray-500">
                          {request.admin_updated_at ? new Date(request.admin_updated_at).toLocaleString() : '-'}
                        </td>
                        <td className="px-3 py-2 whitespace-nowrap">
                          <button
                            onClick={(e) => { e.stopPropagation(); openRequestDetails(request); }}
                            className="px-2 py-1 text-xs bg-blue-100 text-blue-700 rounded hover:bg-blue-200"
                          >
                            Review
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {activeTab === 'feedback' && (
            <FeedbackTab feedback={feedback} />
          )}

          {activeTab === 'sources' && (
            <div className="space-y-4">
              <div className="flex flex-wrap justify-between items-center gap-3">
                <h3 className="font-medium text-gray-900">Text Sources (Sources Page)</h3>
                <div className="flex items-center gap-3">
                  <span className="text-sm text-gray-500">{filteredSources.length} of {sourcesData.length} entries</span>
                  <button
                    onClick={() => { setAddingSource(true); setSourcesMessage(null); }}
                    className="px-3 py-1.5 bg-red-700 text-white rounded text-sm hover:bg-red-800"
                  >
                    + Add Source
                  </button>
                </div>
              </div>

              {sourcesMessage && (
                <div className={`text-sm p-2 rounded ${sourcesMessage.type === 'success' ? 'bg-amber-100 text-amber-700' : 'bg-red-100 text-red-700'}`}>
                  {sourcesMessage.text}
                </div>
              )}

              <input
                type="text"
                placeholder="Filter by author, work, or source..."
                value={sourcesFilter}
                onChange={e => setSourcesFilter(e.target.value)}
                className="w-full sm:w-80 px-3 py-2 border border-gray-300 rounded text-sm focus:outline-none focus:ring-2 focus:ring-red-500"
              />

              {addingSource && (
                <div className="bg-amber-50 border border-amber-200 rounded-lg p-4 space-y-3">
                  <h4 className="font-medium text-amber-900">Add New Source Entry</h4>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                    <div>
                      <label className="block text-xs font-medium text-gray-700 mb-1">Author</label>
                      <input type="text" value={newSource.author} onChange={e => setNewSource(p => ({...p, author: e.target.value}))} className="w-full border rounded px-2 py-1.5 text-sm" placeholder="e.g., Vergil" />
                    </div>
                    <div>
                      <label className="block text-xs font-medium text-gray-700 mb-1">Work</label>
                      <input type="text" value={newSource.work} onChange={e => setNewSource(p => ({...p, work: e.target.value}))} className="w-full border rounded px-2 py-1.5 text-sm" placeholder="e.g., Aeneid" />
                    </div>
                    <div>
                      <label className="block text-xs font-medium text-gray-700 mb-1">e-Source</label>
                      <input type="text" value={newSource.e_source} onChange={e => setNewSource(p => ({...p, e_source: e.target.value}))} className="w-full border rounded px-2 py-1.5 text-sm" placeholder="e.g., The Latin Library" />
                    </div>
                    <div>
                      <label className="block text-xs font-medium text-gray-700 mb-1">e-Source URL</label>
                      <input type="text" value={newSource.e_source_url} onChange={e => setNewSource(p => ({...p, e_source_url: e.target.value}))} className="w-full border rounded px-2 py-1.5 text-sm" placeholder="https://..." />
                    </div>
                    <div className="md:col-span-2">
                      <label className="block text-xs font-medium text-gray-700 mb-1">Print Source (citation)</label>
                      <input type="text" value={newSource.print_source} onChange={e => setNewSource(p => ({...p, print_source: e.target.value}))} className="w-full border rounded px-2 py-1.5 text-sm" placeholder="e.g., R. Mynors, OCT, 1969" />
                    </div>
                    <div>
                      <label className="block text-xs font-medium text-gray-700 mb-1">Added by</label>
                      <input type="text" value={newSource.added_by} onChange={e => setNewSource(p => ({...p, added_by: e.target.value}))} className="w-full border rounded px-2 py-1.5 text-sm" placeholder="Name" />
                    </div>
                  </div>
                  <div className="flex gap-2 pt-1">
                    <button onClick={addNewSource} disabled={sourcesSaving || (!newSource.author && !newSource.work)} className="px-3 py-1.5 bg-red-700 text-white rounded text-sm hover:bg-red-800 disabled:opacity-50">
                      {sourcesSaving ? 'Adding...' : 'Add'}
                    </button>
                    <button onClick={() => setAddingSource(false)} className="px-3 py-1.5 bg-gray-200 text-gray-700 rounded text-sm hover:bg-gray-300">
                      Cancel
                    </button>
                  </div>
                </div>
              )}

              {sourcesLoading ? (
                <div className="text-center py-8"><LoadingSpinner /></div>
              ) : (
                <div className="border border-gray-200 rounded-lg overflow-hidden">
                  <table className="w-full divide-y divide-gray-200 text-sm table-fixed">
                    <thead className="bg-gray-50">
                      <tr>
                        <th className="w-[14%] px-2 py-2 text-left font-semibold text-gray-700">Author</th>
                        <th className="w-[16%] px-2 py-2 text-left font-semibold text-gray-700">Work</th>
                        <th className="w-[10%] px-2 py-2 text-left font-semibold text-gray-700">e-Source</th>
                        <th className="w-[30%] px-2 py-2 text-left font-semibold text-gray-700">Print Source</th>
                        <th className="w-[14%] px-2 py-2 text-left font-semibold text-gray-700">Added by</th>
                        <th className="w-[16%] px-2 py-2 text-right font-semibold text-gray-700">Actions</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-100">
                      {filteredSources.map(entry => (
                        <tr key={entry.id} className="hover:bg-gray-50">
                          {editingSource && editingSource.id === entry.id ? (
                            <>
                              <td className="px-2 py-1.5"><input type="text" value={editingSource.author} onChange={e => setEditingSource(p => ({...p, author: e.target.value}))} className="w-full border rounded px-2 py-1 text-sm" /></td>
                              <td className="px-2 py-1.5"><input type="text" value={editingSource.work} onChange={e => setEditingSource(p => ({...p, work: e.target.value}))} className="w-full border rounded px-2 py-1 text-sm" /></td>
                              <td className="px-2 py-1.5">
                                <input type="text" value={editingSource.e_source} onChange={e => setEditingSource(p => ({...p, e_source: e.target.value}))} className="w-full border rounded px-2 py-1 text-sm mb-1" placeholder="Source name" />
                                <input type="text" value={editingSource.e_source_url} onChange={e => setEditingSource(p => ({...p, e_source_url: e.target.value}))} className="w-full border rounded px-2 py-1 text-xs text-gray-500" placeholder="URL" />
                              </td>
                              <td className="px-2 py-1.5"><input type="text" value={editingSource.print_source} onChange={e => setEditingSource(p => ({...p, print_source: e.target.value}))} className="w-full border rounded px-2 py-1 text-sm" /></td>
                              <td className="px-2 py-1.5"><input type="text" value={editingSource.added_by} onChange={e => setEditingSource(p => ({...p, added_by: e.target.value}))} className="w-full border rounded px-2 py-1 text-sm" /></td>
                              <td className="px-2 py-1.5 text-right whitespace-nowrap">
                                <button onClick={() => saveSource(editingSource.id, editingSource)} disabled={sourcesSaving} className="text-red-700 hover:text-red-900 text-xs font-medium mr-2">
                                  {sourcesSaving ? 'Saving...' : 'Save'}
                                </button>
                                <button onClick={() => setEditingSource(null)} className="text-gray-500 hover:text-gray-700 text-xs">
                                  Cancel
                                </button>
                              </td>
                            </>
                          ) : (
                            <>
                              <td className="px-2 py-2 text-gray-900 font-medium truncate" title={entry.author}>{entry.author}</td>
                              <td className="px-2 py-2 text-gray-700 truncate" title={entry.work}>{entry.work}</td>
                              <td className="px-2 py-2 truncate">
                                {entry.e_source_url ? (
                                  <a href={entry.e_source_url} target="_blank" rel="noopener noreferrer" className="text-red-700 hover:underline text-xs">{entry.e_source}</a>
                                ) : (
                                  <span className="text-gray-700 text-xs">{entry.e_source}</span>
                                )}
                              </td>
                              <td className="px-2 py-2 text-gray-600 text-xs truncate" title={entry.print_source}>{entry.print_source}</td>
                              <td className="px-2 py-2 text-gray-600 text-xs truncate" title={entry.added_by}>{entry.added_by}</td>
                              <td className="px-2 py-2 text-right whitespace-nowrap">
                                <button onClick={() => setEditingSource({...entry})} className="text-blue-600 hover:text-blue-800 text-xs font-medium mr-2">
                                  Edit
                                </button>
                                <button onClick={() => deleteSource(entry.id, entry.author, entry.work)} className="text-red-600 hover:text-red-800 text-xs font-medium">
                                  Delete
                                </button>
                              </td>
                            </>
                          )}
                        </tr>
                      ))}
                      {filteredSources.length === 0 && (
                        <tr><td colSpan={6} className="px-4 py-8 text-center text-gray-500">No entries found.</td></tr>
                      )}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}

          {activeTab === 'metadata' && (
            <div className="space-y-4">
              <div className="flex flex-wrap justify-between items-center gap-3">
                <h3 className="font-medium text-gray-900">Corpus Metadata</h3>
                <span className="text-sm text-gray-500">
                  {filteredCorpusTexts.length} of {corpusTexts.length} texts
                  {corpusTexts.filter(t => t.override).length > 0 && (
                    <span className="ml-2 text-amber-600">
                      ({corpusTexts.filter(t => t.override).length} with overrides)
                    </span>
                  )}
                </span>
              </div>

              <p className="text-sm text-gray-500">
                Edit text classification (poetry/prose), display names, dates, and eras. 
                Changes are saved to a tracked overrides file and will persist across deployments.
              </p>

              {metadataMessage && (
                <div className={`text-sm p-2 rounded ${metadataMessage.type === 'success' ? 'bg-amber-100 text-amber-700' : 'bg-red-100 text-red-700'}`}>
                  {metadataMessage.text}
                </div>
              )}

              <div className="flex flex-wrap gap-2">
                <input
                  type="text"
                  placeholder="Filter by author, title, or filename..."
                  value={corpusTextsFilter}
                  onChange={e => setCorpusTextsFilter(e.target.value)}
                  className="flex-1 min-w-[200px] px-3 py-2 border border-gray-300 rounded text-sm focus:outline-none focus:ring-2 focus:ring-red-500"
                />
                <select
                  value={corpusTextsLang}
                  onChange={e => { setCorpusTextsLang(e.target.value); }}
                  className="px-3 py-2 border border-gray-300 rounded text-sm"
                >
                  <option value="">All Languages</option>
                  <option value="la">Latin</option>
                  <option value="grc">Greek</option>
                  <option value="en">English</option>
                </select>
                <select
                  value={corpusTextsTypeFilter}
                  onChange={e => setCorpusTextsTypeFilter(e.target.value)}
                  className="px-3 py-2 border border-gray-300 rounded text-sm"
                >
                  <option value="">All Types</option>
                  <option value="poetry">Poetry</option>
                  <option value="prose">Prose</option>
                </select>
              </div>

              {editingMetadata && (
                <div className="bg-amber-50 border border-amber-200 rounded-lg p-4 space-y-3">
                  <h4 className="font-medium text-amber-900">
                    Edit Metadata: <span className="font-mono text-sm">{editingMetadata.id}</span>
                  </h4>
                  <p className="text-xs text-gray-500">
                    Leave fields blank to use auto-detected values. Only fill in fields you want to override.
                  </p>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                    <div>
                      <label className="block text-xs font-medium text-gray-700 mb-1">Text Type</label>
                      <select
                        value={editingMetadata.text_type || ''}
                        onChange={e => setEditingMetadata(p => ({...p, text_type: e.target.value}))}
                        className="w-full border rounded px-2 py-1.5 text-sm"
                      >
                        <option value="">Auto-detect ({editingMetadata._auto_text_type || 'poetry'})</option>
                        <option value="poetry">Poetry</option>
                        <option value="prose">Prose</option>
                      </select>
                    </div>
                    <div>
                      <label className="block text-xs font-medium text-gray-700 mb-1">Display Author</label>
                      <input
                        type="text"
                        value={editingMetadata.display_author || ''}
                        onChange={e => setEditingMetadata(p => ({...p, display_author: e.target.value}))}
                        className="w-full border rounded px-2 py-1.5 text-sm"
                        placeholder={editingMetadata._auto_author || 'Auto-detected'}
                      />
                    </div>
                    <div>
                      <label className="block text-xs font-medium text-gray-700 mb-1">Display Work Title</label>
                      <input
                        type="text"
                        value={editingMetadata.display_work || ''}
                        onChange={e => setEditingMetadata(p => ({...p, display_work: e.target.value}))}
                        className="w-full border rounded px-2 py-1.5 text-sm"
                        placeholder={editingMetadata._auto_work || 'Auto-detected'}
                      />
                    </div>
                    <div>
                      <label className="block text-xs font-medium text-gray-700 mb-1">Year</label>
                      <input
                        type="number"
                        value={editingMetadata.year ?? ''}
                        onChange={e => setEditingMetadata(p => ({...p, year: e.target.value === '' ? null : parseInt(e.target.value)}))}
                        className="w-full border rounded px-2 py-1.5 text-sm"
                        placeholder={editingMetadata._auto_year || 'From author_dates.json'}
                      />
                      <p className="text-xs text-gray-400 mt-0.5">Negative for BCE (e.g., -70 for 70 BCE)</p>
                    </div>
                    <div>
                      <label className="block text-xs font-medium text-gray-700 mb-1">Era</label>
                      <input
                        type="text"
                        value={editingMetadata.era || ''}
                        onChange={e => setEditingMetadata(p => ({...p, era: e.target.value}))}
                        className="w-full border rounded px-2 py-1.5 text-sm"
                        placeholder={editingMetadata._auto_era || 'From author_dates.json'}
                      />
                    </div>
                    <div>
                      <label className="block text-xs font-medium text-gray-700 mb-1">Notes</label>
                      <input
                        type="text"
                        value={editingMetadata.notes || ''}
                        onChange={e => setEditingMetadata(p => ({...p, notes: e.target.value}))}
                        className="w-full border rounded px-2 py-1.5 text-sm"
                        placeholder="Optional notes about this override"
                      />
                    </div>
                  </div>
                  <div className="flex gap-2 pt-1">
                    <button
                      onClick={() => saveMetadataOverride(editingMetadata.id, {
                        text_type: editingMetadata.text_type || undefined,
                        display_author: editingMetadata.display_author || undefined,
                        display_work: editingMetadata.display_work || undefined,
                        year: editingMetadata.year ?? undefined,
                        era: editingMetadata.era || undefined,
                        notes: editingMetadata.notes || undefined
                      })}
                      disabled={metadataSaving}
                      className="px-3 py-1.5 bg-red-700 text-white rounded text-sm hover:bg-red-800 disabled:opacity-50"
                    >
                      {metadataSaving ? 'Saving...' : 'Save Override'}
                    </button>
                    <button
                      onClick={() => { setEditingMetadata(null); setMetadataMessage(null); }}
                      className="px-3 py-1.5 bg-gray-200 text-gray-700 rounded text-sm hover:bg-gray-300"
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              )}

              {corpusTextsLoading ? (
                <div className="text-center py-8"><LoadingSpinner /></div>
              ) : (
                <div className="border border-gray-200 rounded-lg overflow-hidden">
                  <div className="max-h-[600px] overflow-y-auto">
                    <table className="w-full divide-y divide-gray-200 text-sm table-fixed">
                      <thead className="bg-gray-50 sticky top-0">
                        <tr>
                          <th className="w-[14%] px-2 py-2 text-left font-semibold text-gray-700">Author</th>
                          <th className="w-[20%] px-2 py-2 text-left font-semibold text-gray-700">Work</th>
                          <th className="w-[6%] px-2 py-2 text-left font-semibold text-gray-700">Lang</th>
                          <th className="w-[8%] px-2 py-2 text-left font-semibold text-gray-700">Type</th>
                          <th className="w-[8%] px-2 py-2 text-left font-semibold text-gray-700">Year</th>
                          <th className="w-[10%] px-2 py-2 text-left font-semibold text-gray-700">Era</th>
                          <th className="w-[8%] px-2 py-2 text-left font-semibold text-gray-700">Status</th>
                          <th className="w-[10%] px-2 py-2 text-right font-semibold text-gray-700">Actions</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-gray-100">
                        {filteredCorpusTexts.map(text => (
                          <tr key={text.id} className={`hover:bg-gray-50 ${text.has_override ? 'bg-amber-50' : ''}`}>
                            <td className="px-2 py-1.5 truncate" title={text.author}>{text.author}</td>
                            <td className="px-2 py-1.5 truncate" title={text.title}>{text.title}</td>
                            <td className="px-2 py-1.5">{text.language === 'la' ? 'Latin' : text.language === 'grc' ? 'Greek' : 'English'}</td>
                            <td className="px-2 py-1.5">
                              <span className={`px-1.5 py-0.5 rounded text-xs ${text.text_type === 'prose' ? 'bg-blue-100 text-blue-700' : 'bg-purple-100 text-purple-700'}`}>
                                {text.text_type}
                              </span>
                            </td>
                            <td className="px-2 py-1.5 text-gray-600">{text.year ? (text.year < 0 ? `${Math.abs(text.year)} BCE` : `${text.year} CE`) : '—'}</td>
                            <td className="px-2 py-1.5 text-gray-600 truncate" title={text.era}>{text.era || '—'}</td>
                            <td className="px-2 py-1.5">
                              {text.has_override ? (
                                <span className="text-xs text-amber-600 font-medium">Overridden</span>
                              ) : (
                                <span className="text-xs text-gray-400">Auto</span>
                              )}
                            </td>
                            <td className="px-2 py-1.5 text-right whitespace-nowrap">
                              <button
                                onClick={() => {
                                  const ovr = text.override || {};
                                  setEditingMetadata({
                                    id: text.id,
                                    text_type: ovr.text_type || '',
                                    display_author: ovr.display_author || '',
                                    display_work: ovr.display_work || '',
                                    year: ovr.year ?? null,
                                    era: ovr.era || '',
                                    notes: ovr.notes || '',
                                    _auto_text_type: text.override ? undefined : text.text_type,
                                    _auto_author: text.author,
                                    _auto_work: text.work,
                                    _auto_year: text.year?.toString(),
                                    _auto_era: text.era
                                  });
                                  setMetadataMessage(null);
                                }}
                                className="text-red-700 hover:text-red-800 text-xs font-medium mr-2"
                              >
                                Edit
                              </button>
                              {text.has_override && (
                                <button
                                  onClick={() => clearMetadataOverride(text.id)}
                                  className="text-gray-500 hover:text-red-600 text-xs"
                                >
                                  Clear
                                </button>
                              )}
                            </td>
                          </tr>
                        ))}
                        {filteredCorpusTexts.length === 0 && (
                          <tr>
                            <td colSpan={8} className="px-4 py-8 text-center text-gray-500">
                              {corpusTexts.length === 0 ? 'No texts found in corpus' : 'No texts match the current filters'}
                            </td>
                          </tr>
                        )}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </div>
          )}

          {activeTab === 'cache' && (
            <div className="space-y-4">
              <h3 className="font-medium text-gray-900">Cache Management</h3>
              <p className="text-sm text-gray-500">
                Click "Clear" to see what will be affected before confirming.
              </p>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="bg-amber-50 border border-amber-200 p-4 rounded">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-sm text-gray-600">Search Cache</span>
                    <span className="text-xs px-1.5 py-0.5 bg-amber-100 text-amber-700 rounded">Low Risk</span>
                  </div>
                  <div className="text-2xl font-bold text-gray-900">
                    {cacheInfo?.search_cache_size || 0} entries
                  </div>
                  <p className="text-xs text-gray-500 mt-1 mb-2">Cached search results</p>
                  <button
                    onClick={() => showCacheConfirmation('search')}
                    className="text-sm text-red-600 hover:text-red-800 font-medium"
                  >
                    Clear...
                  </button>
                </div>
                <div className="bg-red-50 border border-red-200 p-4 rounded">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-sm text-gray-600">Lemma Cache</span>
                    <span className="text-xs px-1.5 py-0.5 bg-red-100 text-red-700 rounded">High Risk</span>
                  </div>
                  <div className="text-2xl font-bold text-gray-900">
                    {cacheInfo?.lemma_cache_size || 0} entries
                  </div>
                  <p className="text-xs text-gray-500 mt-1 mb-2">Lemmatized text data</p>
                  <button
                    onClick={() => showCacheConfirmation('lemma')}
                    className="text-sm text-red-600 hover:text-red-800 font-medium"
                  >
                    Clear...
                  </button>
                </div>
                <div className="bg-amber-50 border border-amber-200 p-4 rounded">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-sm text-gray-600">Frequency Cache</span>
                    <span className="text-xs px-1.5 py-0.5 bg-amber-100 text-amber-700 rounded">Medium Risk</span>
                  </div>
                  <div className="text-2xl font-bold text-gray-900">
                    {cacheInfo?.frequency_cache_size || 0} entries
                  </div>
                  <p className="text-xs text-gray-500 mt-1 mb-2">Word frequency data</p>
                  <button
                    onClick={() => showCacheConfirmation('frequency')}
                    className="text-sm text-red-600 hover:text-red-800 font-medium"
                  >
                    Clear...
                  </button>
                </div>
              </div>
              <div className="pt-4">
                <button
                  onClick={recalculateFrequencies}
                  className="px-4 py-2 bg-amber-100 text-amber-700 rounded hover:bg-amber-200"
                >
                  Recalculate Corpus Frequencies
                </button>
              </div>
              
              <div className="pt-6 border-t mt-6">
                <h4 className="font-medium text-gray-900 mb-2">Bigram Index (for Rare Pairs Search)</h4>
                <p className="text-sm text-gray-500 mb-4">
                  Build bigram indexes to enable the Rare Pairs search feature. This may take several minutes per language.
                </p>
                {bigramError && (
                  <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded text-red-700 text-sm">
                    {bigramError}
                  </div>
                )}
                {bigramSuccess && (
                  <div className="mb-4 p-3 bg-amber-50 border border-amber-200 rounded text-amber-700 text-sm">
                    {bigramSuccess}
                  </div>
                )}
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  {['la', 'grc', 'en'].map(lang => (
                    <div key={lang} className={`p-4 rounded border ${bigramStats[lang] ? 'bg-amber-50 border-amber-200' : 'bg-gray-50 border-gray-200'}`}>
                      <div className="flex items-center justify-between mb-2">
                        <span className="font-medium text-gray-900">{LANG_NAMES[lang]}</span>
                        {bigramStats[lang] && (
                          <span className="text-xs px-1.5 py-0.5 bg-amber-100 text-amber-700 rounded">Built</span>
                        )}
                      </div>
                      {bigramStats[lang] ? (
                        <div className="text-sm text-gray-600 mb-2">
                          {bigramStats[lang].unique_bigrams?.toLocaleString() || 0} unique pairs
                        </div>
                      ) : (
                        <div className="text-sm text-gray-500 mb-2">Not built yet</div>
                      )}
                      <button
                        onClick={() => buildBigramIndex(lang)}
                        disabled={buildingBigram !== null}
                        className={`w-full px-3 py-1.5 text-sm rounded ${
                          buildingBigram === lang 
                            ? 'bg-blue-100 text-blue-700 cursor-wait' 
                            : bigramStats[lang]
                              ? 'bg-amber-100 text-amber-700 hover:bg-amber-200'
                              : 'bg-blue-100 text-blue-700 hover:bg-blue-200'
                        } ${buildingBigram !== null && buildingBigram !== lang ? 'opacity-50 cursor-not-allowed' : ''}`}
                      >
                        {buildingBigram === lang ? 'Building...' : bigramStats[lang] ? 'Rebuild' : 'Build Index'}
                      </button>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {activeTab === 'stats' && (
            <StatsTab corpusStats={corpusStats} />
          )}

          {activeTab === 'analytics' && (
            <div className="space-y-6">
              <h3 className="font-medium text-gray-900">User Analytics</h3>
              {analytics ? (
                <>
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    <div className="bg-blue-50 p-4 rounded">
                      <div className="text-sm text-gray-600">Total Searches</div>
                      <div className="text-2xl font-bold text-gray-900">{(analytics.total_searches || 0).toLocaleString()}</div>
                    </div>
                    <div className="bg-amber-50 p-4 rounded">
                      <div className="text-sm text-gray-600">Searches Today</div>
                      <div className="text-2xl font-bold text-gray-900">
                        {analytics.per_day?.find(d => d.date === new Date().toISOString().split('T')[0])?.count || 0}
                      </div>
                    </div>
                    <div className="bg-amber-50 p-4 rounded">
                      <div className="text-sm text-gray-600">Unique Users</div>
                      <div className="text-2xl font-bold text-gray-900">{analytics.unique_users || 'N/A'}</div>
                    </div>
                  </div>
                  
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                    <div>
                      <h4 className="text-sm font-medium text-gray-700 mb-2">Searches by Type</h4>
                      <div className="bg-gray-50 rounded p-3 space-y-2">
                        {analytics.by_type?.map(item => (
                          <div key={item.type} className="flex justify-between text-sm">
                            <span className="text-gray-600">{item.type}</span>
                            <span className="font-medium">{item.count}</span>
                          </div>
                        )) || <p className="text-gray-500 text-sm">No data</p>}
                      </div>
                    </div>
                    <div>
                      <h4 className="text-sm font-medium text-gray-700 mb-2">Searches by Language</h4>
                      <div className="bg-gray-50 rounded p-3 space-y-2">
                        {analytics.by_language?.map(item => (
                          <div key={item.language} className="flex justify-between text-sm">
                            <span className="text-gray-600">{LANG_NAMES[item.language] || item.language}</span>
                            <span className="font-medium">{item.count}</span>
                          </div>
                        )) || <p className="text-gray-500 text-sm">No data</p>}
                      </div>
                    </div>
                  </div>
                  
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                    <div>
                      <h4 className="text-sm font-medium text-gray-700 mb-2">Top Source Texts</h4>
                      <div className="bg-gray-50 rounded p-3 space-y-2 max-h-48 overflow-y-auto">
                        {analytics.top_sources?.map((item, i) => (
                          <div key={i} className="flex justify-between text-sm">
                            <span className="text-gray-600 truncate max-w-[200px]" title={item.text}>{item.text}</span>
                            <span className="font-medium">{item.count}</span>
                          </div>
                        )) || <p className="text-gray-500 text-sm">No data</p>}
                      </div>
                    </div>
                    <div>
                      <h4 className="text-sm font-medium text-gray-700 mb-2">Top Target Texts</h4>
                      <div className="bg-gray-50 rounded p-3 space-y-2 max-h-48 overflow-y-auto">
                        {analytics.top_targets?.map((item, i) => (
                          <div key={i} className="flex justify-between text-sm">
                            <span className="text-gray-600 truncate max-w-[200px]" title={item.text}>{item.text}</span>
                            <span className="font-medium">{item.count}</span>
                          </div>
                        )) || <p className="text-gray-500 text-sm">No data</p>}
                      </div>
                    </div>
                  </div>
                  
                  <div>
                    <h4 className="text-sm font-medium text-gray-700 mb-2">Daily Search Activity (Last 30 Days)</h4>
                    <div className="bg-gray-50 rounded p-3 max-h-48 overflow-y-auto">
                      {analytics.per_day?.length > 0 ? (
                        <div className="space-y-1">
                          {analytics.per_day.slice(0, 14).map(item => (
                            <div key={item.date} className="flex justify-between text-sm">
                              <span className="text-gray-600">{item.date}</span>
                              <span className="font-medium">{item.count}</span>
                            </div>
                          ))}
                        </div>
                      ) : (
                        <p className="text-gray-500 text-sm">No recent searches</p>
                      )}
                    </div>
                  </div>
                  
                  <div className="border-t pt-6">
                    <h4 className="text-sm font-medium text-gray-700 mb-4">Geographic Distribution</h4>
                    
                    {(analytics.top_cities?.length > 0 || analytics.top_countries?.length > 0) ? (
                      <>
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
                          <div>
                            <h5 className="text-xs font-medium text-gray-500 uppercase mb-2">Top Countries</h5>
                            <div className="bg-gray-50 rounded p-3 space-y-2">
                              {analytics.top_countries?.map((item, i) => (
                                <div key={i} className="flex justify-between text-sm">
                                  <span className="text-gray-600">{item.country}</span>
                                  <span className="font-medium">{item.count}</span>
                                </div>
                              )) || <p className="text-gray-500 text-sm">No data</p>}
                            </div>
                          </div>
                          <div>
                            <h5 className="text-xs font-medium text-gray-500 uppercase mb-2">Top Cities</h5>
                            <div className="bg-gray-50 rounded p-3 space-y-2 max-h-48 overflow-y-auto">
                              {analytics.top_cities?.map((item, i) => (
                                <div key={i} className="flex justify-between text-sm">
                                  <span className="text-gray-600">{item.city}{item.country ? `, ${item.country}` : ''}</span>
                                  <span className="font-medium">{item.count}</span>
                                </div>
                              )) || <p className="text-gray-500 text-sm">No data</p>}
                            </div>
                          </div>
                        </div>
                        
                        <div className="bg-gradient-to-br from-blue-50 to-indigo-50 rounded-lg p-4 border border-blue-100">
                          <h5 className="text-sm font-medium text-gray-700 mb-3">User Distribution Map</h5>
                          <div className="relative bg-white rounded p-4 min-h-[200px] flex flex-col items-center justify-center">
                            {analytics.top_cities?.length > 0 ? (
                              <div className="w-full">
                                <div className="flex flex-wrap gap-2 justify-center">
                                  {analytics.top_cities.slice(0, 10).map((city, idx) => {
                                    const maxCount = Math.max(...analytics.top_cities.map(c => c.count));
                                    const size = Math.max(24, Math.min(80, (city.count / maxCount) * 80));
                                    const opacity = 0.4 + (city.count / maxCount) * 0.6;
                                    return (
                                      <div 
                                        key={idx} 
                                        className="flex flex-col items-center group cursor-pointer"
                                        title={`${city.city}, ${city.country}: ${city.count} searches`}
                                      >
                                        <div 
                                          className="rounded-full bg-red-500 flex items-center justify-center text-white text-xs font-bold shadow-lg transition-transform hover:scale-110"
                                          style={{ 
                                            width: size, 
                                            height: size,
                                            opacity: opacity
                                          }}
                                        >
                                          {city.count}
                                        </div>
                                        <span className="text-xs text-gray-600 mt-1 max-w-[60px] truncate text-center">
                                          {city.city}
                                        </span>
                                      </div>
                                    );
                                  })}
                                </div>
                                <p className="text-xs text-gray-500 text-center mt-4">
                                  Circle size indicates relative search volume. Hover for details.
                                </p>
                              </div>
                            ) : (
                              <p className="text-gray-500 text-sm">No geographic data available yet</p>
                            )}
                          </div>
                        </div>
                      </>
                    ) : (
                      <div className="bg-gray-50 rounded p-4 text-center">
                        <p className="text-gray-500 text-sm">No geographic data available yet.</p>
                        <p className="text-gray-400 text-xs mt-1">User locations are tracked via IP geolocation when searches are performed.</p>
                      </div>
                    )}
                  </div>
                </>
              ) : (
                <p className="text-gray-500 text-sm">Loading analytics...</p>
              )}
            </div>
          )}

          {activeTab === 'audit' && (
            <AuditTab authHeaders={{ 'X-Admin-Password': password, 'X-Admin-Username': adminUsername }} />
          )}

          {activeTab === 'settings' && (
            <SettingsTab authHeaders={{ 'X-Admin-Password': password, 'X-Admin-Username': adminUsername }} />
          )}
        </div>
      </div>

      {confirmModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-lg shadow-xl max-w-lg w-full max-h-[90vh] overflow-y-auto">
            <div className={`px-6 py-4 border-b ${
              confirmModal.severity === 'high' 
                ? 'bg-red-50 border-red-200' 
                : confirmModal.severity === 'medium' 
                  ? 'bg-amber-50 border-amber-200' 
                  : 'bg-amber-50 border-amber-200'
            }`}>
              <h3 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
                {confirmModal.severity === 'high' && <span className="text-red-600">⚠️</span>}
                {confirmModal.severity === 'medium' && <span className="text-amber-600">⚡</span>}
                Clear {confirmModal.title}?
              </h3>
              <p className="text-sm text-gray-600 mt-1">{confirmModal.description}</p>
            </div>
            
            <div className="px-6 py-4 space-y-4">
              <div className="bg-gray-50 rounded p-3">
                <div className="text-sm font-medium text-gray-700 mb-1">Current Size</div>
                <div className="text-2xl font-bold text-gray-900">{confirmModal.entryCount.toLocaleString()} entries</div>
              </div>
              
              <div>
                <div className={`text-sm font-medium mb-2 ${
                  confirmModal.severity === 'high' 
                    ? 'text-red-700' 
                    : confirmModal.severity === 'medium' 
                      ? 'text-amber-700' 
                      : 'text-gray-700'
                }`}>
                  What will happen if you clear this cache:
                </div>
                <ul className="space-y-2">
                  {confirmModal.impact.map((item, i) => (
                    <li key={i} className="flex items-start gap-2 text-sm text-gray-700">
                      <span className={`mt-1 flex-shrink-0 ${
                        confirmModal.severity === 'high' 
                          ? 'text-red-500' 
                          : confirmModal.severity === 'medium' 
                            ? 'text-amber-500' 
                            : 'text-gray-400'
                      }`}>•</span>
                      {item}
                    </li>
                  ))}
                </ul>
              </div>
              
              <div className="bg-blue-50 border border-blue-200 rounded p-3">
                <div className="text-sm font-medium text-blue-800 mb-1">How to Rebuild</div>
                <p className="text-sm text-blue-700">{confirmModal.rebuildTime}</p>
              </div>
              
              {cacheError && (
                <div className="bg-red-50 border border-red-300 rounded p-3">
                  <div className="text-sm font-medium text-red-800">Error</div>
                  <p className="text-sm text-red-700">{cacheError}</p>
                </div>
              )}
            </div>
            
            <div className="px-6 py-4 bg-gray-50 border-t flex justify-end gap-3">
              <button
                onClick={() => setConfirmModal(null)}
                className="px-4 py-2 text-gray-700 bg-white border border-gray-300 rounded hover:bg-gray-50"
                disabled={clearingCache}
              >
                Cancel
              </button>
              <button
                onClick={() => clearCache(confirmModal.cacheType)}
                disabled={clearingCache}
                className={`px-4 py-2 text-white rounded disabled:opacity-50 ${
                  confirmModal.severity === 'high' 
                    ? 'bg-red-600 hover:bg-red-700' 
                    : confirmModal.severity === 'medium' 
                      ? 'bg-amber-600 hover:bg-amber-700' 
                      : 'bg-gray-600 hover:bg-gray-700'
                }`}
              >
                {clearingCache ? 'Clearing...' : 'Yes, Clear Cache'}
              </button>
            </div>
          </div>
        </div>
      )}

      {selectedRequest && editingRequest && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-lg shadow-xl max-w-4xl w-full max-h-[90vh] overflow-hidden flex flex-col">
            <div className="px-6 py-4 border-b bg-gray-50 flex justify-between items-center">
              <div>
                <h3 className="text-lg font-semibold text-gray-900">Review Text Request</h3>
                <p className="text-sm text-gray-500">
                  Submitted by {selectedRequest.name || 'Anonymous'} 
                  {selectedRequest.email && ` (${selectedRequest.email})`}
                </p>
              </div>
              <button
                onClick={() => setSelectedRequest(null)}
                className="text-gray-400 hover:text-gray-600 text-2xl"
              >
                &times;
              </button>
            </div>
            
            <div className="p-6 overflow-y-auto flex-1 space-y-6">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Official Author Name</label>
                  <input
                    type="text"
                    value={editingRequest.official_author}
                    onChange={e => {
                      setEditingRequest(prev => ({ ...prev, official_author: e.target.value }));
                      updateTessPreview(editingRequest.content, e.target.value, editingRequest.official_work);
                    }}
                    className="w-full border rounded px-3 py-2 text-sm"
                    placeholder="e.g., Vergil"
                  />
                  <p className="text-xs text-gray-400 mt-1">Original: {selectedRequest.author}</p>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Official Work Title</label>
                  <input
                    type="text"
                    value={editingRequest.official_work}
                    onChange={e => {
                      setEditingRequest(prev => ({ ...prev, official_work: e.target.value }));
                      updateTessPreview(editingRequest.content, editingRequest.official_author, e.target.value);
                    }}
                    className="w-full border rounded px-3 py-2 text-sm"
                    placeholder="e.g., Aeneid"
                  />
                  <p className="text-xs text-gray-400 mt-1">Original: {selectedRequest.work}</p>
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Language</label>
                  <div className="px-3 py-2 bg-gray-100 rounded text-sm">
                    {LANG_NAMES[selectedRequest.language] || selectedRequest.language}
                  </div>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Era</label>
                  <select
                    value={editingRequest.author_era}
                    onChange={e => setEditingRequest(prev => ({ ...prev, author_era: e.target.value }))}
                    className="w-full border rounded px-3 py-2 text-sm"
                  >
                    <option value="">Select era...</option>
                    <option value="Archaic">Archaic</option>
                    <option value="Classical">Classical</option>
                    <option value="Hellenistic">Hellenistic</option>
                    <option value="Republic">Republic</option>
                    <option value="Augustan">Augustan</option>
                    <option value="Early Imperial">Early Imperial</option>
                    <option value="Later Imperial">Later Imperial</option>
                    <option value="Late Antique">Late Antique</option>
                    <option value="Early Medieval">Early Medieval</option>
                    <option value="Unknown">Unknown</option>
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Year (negative = BCE)</label>
                  <input
                    type="number"
                    value={editingRequest.author_year}
                    onChange={e => setEditingRequest(prev => ({ ...prev, author_year: e.target.value }))}
                    className="w-full border rounded px-3 py-2 text-sm"
                    placeholder="e.g., -19 for 19 BCE"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">.tess Filename</label>
                  <div className="flex gap-2">
                    <input
                      type="text"
                      value={editingRequest.approved_filename}
                      onChange={e => setEditingRequest(prev => ({ ...prev, approved_filename: e.target.value }))}
                      className="flex-1 border rounded px-3 py-2 text-sm font-mono"
                    />
                    <button
                      onClick={generateFilename}
                      className="px-2 py-1 bg-gray-100 text-gray-600 rounded text-xs hover:bg-gray-200"
                      title="Auto-generate from author/work"
                    >
                      Auto
                    </button>
                  </div>
                </div>
              </div>

              <div className="border border-amber-200 rounded-lg p-4 bg-amber-50">
                <h4 className="text-sm font-semibold text-amber-900 mb-3">Sources Entry (for Sources page)</h4>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-xs font-medium text-gray-700 mb-1">e-Source</label>
                    <select
                      value={editingRequest.e_source}
                      onChange={e => setEditingRequest(prev => ({ ...prev, e_source: e.target.value }))}
                      className="w-full border rounded px-3 py-2 text-sm"
                    >
                      <option value="">Select source...</option>
                      <option value="Perseus">Perseus</option>
                      <option value="The Latin Library">The Latin Library</option>
                      <option value="DigilibLT">DigilibLT</option>
                      <option value="Open Greek and Latin">Open Greek and Latin</option>
                      <option value="MQDQ">MQDQ (Musisque Deoque)</option>
                      <option value="Corpus Scriptorum Latinorum">Corpus Scriptorum Latinorum</option>
                      <option value="Bibliotheca Augustana">Bibliotheca Augustana</option>
                      <option value="Forum Romanum">Forum Romanum</option>
                      <option value="Divus Angelus">Divus Angelus</option>
                      <option value="Moby Shakespeare">Moby Shakespeare</option>
                      <option value="User Submission">User Submission</option>
                      <option value="Other">Other</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-gray-700 mb-1">e-Source URL</label>
                    <input
                      type="url"
                      value={editingRequest.e_source_url}
                      onChange={e => setEditingRequest(prev => ({ ...prev, e_source_url: e.target.value }))}
                      className="w-full border rounded px-3 py-2 text-sm"
                      placeholder="https://..."
                    />
                  </div>
                  <div className="md:col-span-2">
                    <label className="block text-xs font-medium text-gray-700 mb-1">Print Source (citation)</label>
                    <input
                      type="text"
                      value={editingRequest.print_source}
                      onChange={e => setEditingRequest(prev => ({ ...prev, print_source: e.target.value }))}
                      className="w-full border rounded px-3 py-2 text-sm"
                      placeholder="e.g., Rudolf Hercher, Erotici Scriptores Graeci, Vol 1. Leipzig: Teubneri, 1858."
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-gray-700 mb-1">Added by</label>
                    <input
                      type="text"
                      value={editingRequest.added_by}
                      onChange={e => setEditingRequest(prev => ({ ...prev, added_by: e.target.value }))}
                      className="w-full border rounded px-3 py-2 text-sm"
                      placeholder="Name of person who added this text"
                    />
                  </div>
                </div>
              </div>

              {selectedRequest.notes && (
                <div className="bg-amber-50 border border-amber-200 rounded p-3">
                  <div className="text-sm font-medium text-amber-800">Submitter Notes</div>
                  <p className="text-sm text-amber-700 mt-1">{selectedRequest.notes}</p>
                </div>
              )}

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Admin Notes</label>
                <textarea
                  value={editingRequest.admin_notes}
                  onChange={e => setEditingRequest(prev => ({ ...prev, admin_notes: e.target.value }))}
                  className="w-full border rounded px-3 py-2 text-sm"
                  rows={2}
                  placeholder="Internal notes about this request..."
                />
              </div>

              <div className="border-t pt-4">
                <div className="flex justify-between items-center mb-2">
                  <label className="block text-sm font-medium text-gray-700">Text Content (Raw)</label>
                  <div className="flex items-center gap-3">
                    <button
                      onClick={() => {
                        if (!editingRequest.content || !editingRequest.official_author || !editingRequest.official_work) return;
                        const author = editingRequest.official_author.toLowerCase().replace(/\s+/g, '_').replace(/[^a-z0-9._-]/g, '');
                        const work = editingRequest.official_work.toLowerCase().replace(/\s+/g, '_').replace(/[^a-z0-9._-]/g, '');
                        const lines = editingRequest.content.split('\n').filter(l => l.trim());
                        const formatted = lines.map((line, idx) => {
                          const trimmed = line.trim();
                          if (trimmed.startsWith('<') && trimmed.includes('>')) return trimmed;
                          return `<${author}.${work}.${idx + 1}> ${trimmed}`;
                        }).join('\n');
                        setEditingRequest(prev => ({ ...prev, content: formatted }));
                        updateTessPreview(formatted, editingRequest.official_author, editingRequest.official_work);
                      }}
                      className="px-2 py-1 text-xs bg-red-100 text-red-700 rounded hover:bg-red-200"
                      title="Add .tess tags to each line"
                    >
                      Add .tess Tags
                    </button>
                    <span className="text-xs text-gray-500">
                      {editingRequest.content ? editingRequest.content.split('\n').filter(l => l.trim()).length : 0} lines
                    </span>
                  </div>
                </div>
                <textarea
                  value={editingRequest.content}
                  onChange={e => {
                    setEditingRequest(prev => ({ ...prev, content: e.target.value }));
                    updateTessPreview(e.target.value, editingRequest.official_author, editingRequest.official_work);
                  }}
                  className="w-full border rounded px-3 py-2 text-sm font-mono"
                  rows={8}
                  placeholder="Paste or edit the text content here..."
                />
              </div>

              <div className="bg-gray-900 rounded p-4">
                <div className="flex justify-between items-center mb-2">
                  <span className="text-xs font-medium text-gray-400 uppercase">.tess Preview</span>
                  <span className="text-xs text-gray-500">First 10 lines</span>
                </div>
                <pre className="text-amber-400 text-sm font-mono whitespace-pre-wrap overflow-x-auto">
                  {tessPreview || 'Enter author, work, and content to see preview...'}
                </pre>
              </div>
            </div>
            
            <div className="px-6 py-4 bg-gray-50 border-t flex justify-between">
              <div className="flex gap-2">
                <button
                  onClick={() => deleteRequest(selectedRequest.id)}
                  disabled={savingRequest}
                  className="px-4 py-2 bg-red-100 text-red-700 rounded hover:bg-red-200 disabled:opacity-50"
                >
                  Delete
                </button>
              </div>
              <div className="flex gap-2">
                <button
                  onClick={() => setSelectedRequest(null)}
                  className="px-4 py-2 text-gray-700 bg-white border border-gray-300 rounded hover:bg-gray-50"
                >
                  Cancel
                </button>
                <button
                  onClick={saveRequestChanges}
                  disabled={savingRequest}
                  className="px-4 py-2 bg-red-700 text-white rounded hover:bg-red-800 disabled:opacity-50"
                >
                  {savingRequest ? 'Saving...' : 'Save Changes'}
                </button>
                <button
                  onClick={approveWithEdits}
                  disabled={savingRequest || !editingRequest.content}
                  className="px-4 py-2 bg-red-800 text-white rounded hover:bg-red-900 disabled:opacity-50"
                >
                  {savingRequest ? 'Processing...' : 'Approve & Add to Corpus'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
