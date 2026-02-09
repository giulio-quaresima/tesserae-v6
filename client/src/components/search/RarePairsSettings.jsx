const RarePairsSettings = ({ settings, setSettings }) => {
  const handleChange = (key, value) => {
    setSettings(prev => ({ ...prev, [key]: value }));
  };

  return (
    <div className="bg-gray-50 rounded-lg p-4">
      <div className="mb-3">
        <h4 className="font-medium text-gray-900">Rare Pairs Settings</h4>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Stoplist Basis
          </label>
          <select
            value={settings.stoplist_basis || 'source_target'}
            onChange={(e) => handleChange('stoplist_basis', e.target.value)}
            className="w-full border rounded px-2 py-2 text-sm"
          >
            <option value="none">No Stoplist</option>
            <option value="source_target">Source + Target</option>
            <option value="source">Source Only</option>
            <option value="target">Target Only</option>
          </select>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Stoplist Size
          </label>
          <input
            type="text"
            inputMode="numeric"
            value={settings.stoplist_size === 0 ? 'Default' : settings.stoplist_size}
            onChange={(e) => {
              const val = e.target.value.replace(/[^0-9]/g, '');
              if (val === '' || e.target.value.toLowerCase() === 'default') {
                handleChange('stoplist_size', 0);
              } else {
                handleChange('stoplist_size', Math.min(500, parseInt(val)));
              }
            }}
            onBlur={() => {
              if (settings.stoplist_size === '' || settings.stoplist_size === 'Default') {
                handleChange('stoplist_size', 0);
              }
            }}
            onFocus={(e) => {
              if (settings.stoplist_size === 0) {
                e.target.select();
              }
            }}
            disabled={settings.stoplist_basis === 'none'}
            placeholder="Default"
            className="w-full border rounded px-2 py-2 text-sm disabled:opacity-50"
          />
          <p className="text-xs text-gray-400 mt-1">Default = curated list + high-frequency words</p>
        </div>
      </div>
    </div>
  );
};

export default RarePairsSettings;
