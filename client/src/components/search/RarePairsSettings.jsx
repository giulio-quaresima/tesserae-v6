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
            Sort By
          </label>
          <select
            value={settings.sort_by || 'rarity'}
            onChange={(e) => handleChange('sort_by', e.target.value)}
            className="w-full border rounded px-2 py-2 text-sm"
          >
            <option value="rarity">Sort by Rarity</option>
            <option value="occurrence">Sort by Occurrence</option>
          </select>
        </div>

        <div className="flex items-end">
          <label className="flex items-center gap-2 text-sm text-gray-700">
            <input
              type="checkbox"
              checked={settings.stoplist || false}
              onChange={(e) => handleChange('stoplist', e.target.checked)}
              className="rounded border-gray-300"
            />
            <span>Exclude common words (stoplist)</span>
          </label>
        </div>
      </div>
    </div>
  );
};

export default RarePairsSettings;
