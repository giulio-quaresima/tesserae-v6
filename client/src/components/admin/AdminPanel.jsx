import { useState } from 'react';
import { LoadingSpinner } from '../common';
import StatsTab from './tabs/StatsTab';
import FeedbackTab from './tabs/FeedbackTab';
import SettingsTab from './tabs/SettingsTab';
import AuditTab from './tabs/AuditTab';
import AnalyticsTab from './tabs/AnalyticsTab';
import CacheTab from './tabs/CacheTab';
import SourcesTab from './tabs/SourcesTab';
import MetadataTab from './tabs/MetadataTab';
import RequestsTab from './tabs/RequestsTab';

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
  const [loadError, setLoadError] = useState(null);
  const [bigramStats, setBigramStats] = useState({});

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
            <RequestsTab
              authHeaders={{ 'X-Admin-Password': password, 'X-Admin-Username': adminUsername }}
              textRequests={textRequests}
              onRefresh={loadAdminData}
            />
          )}

          {activeTab === 'feedback' && (
            <FeedbackTab feedback={feedback} />
          )}

          {activeTab === 'sources' && (
            <SourcesTab authHeaders={{ 'X-Admin-Password': password, 'X-Admin-Username': adminUsername }} />
          )}

          {activeTab === 'metadata' && (
            <MetadataTab authHeaders={{ 'X-Admin-Password': password, 'X-Admin-Username': adminUsername }} />
          )}

          {activeTab === 'cache' && (
            <CacheTab
              authHeaders={{ 'X-Admin-Password': password, 'X-Admin-Username': adminUsername }}
              cacheInfo={cacheInfo}
              bigramStats={bigramStats}
              onRefresh={loadAdminData}
              onBigramStatsUpdate={setBigramStats}
            />
          )}

          {activeTab === 'stats' && (
            <StatsTab corpusStats={corpusStats} />
          )}

          {activeTab === 'analytics' && (
            <AnalyticsTab analytics={analytics} />
          )}

          {activeTab === 'audit' && (
            <AuditTab authHeaders={{ 'X-Admin-Password': password, 'X-Admin-Username': adminUsername }} />
          )}

          {activeTab === 'settings' && (
            <SettingsTab authHeaders={{ 'X-Admin-Password': password, 'X-Admin-Username': adminUsername }} />
          )}
        </div>
      </div>
    </div>
  );
}
