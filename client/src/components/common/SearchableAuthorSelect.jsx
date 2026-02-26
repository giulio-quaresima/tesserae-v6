import { useState, useEffect, useRef, useMemo } from 'react';

const isTouchDevice = () => {
  if (typeof window === 'undefined') return false;
  return window.matchMedia('(pointer: coarse)').matches;
};

const SearchableAuthorSelect = ({
  value,
  onChange,
  authors,
  filter: externalFilter,
  setFilter: externalSetFilter,
  showDropdown: externalShowDropdown,
  setShowDropdown: externalSetShowDropdown
}) => {
  const inputRef = useRef(null);
  const containerRef = useRef(null);
  const [internalFilter, setInternalFilter] = useState('');
  const [internalShowDropdown, setInternalShowDropdown] = useState(false);
  const [isEditing, setIsEditing] = useState(false);

  const filter = externalFilter !== undefined ? externalFilter : internalFilter;
  const setFilter = externalSetFilter || setInternalFilter;
  const showDropdown = externalShowDropdown !== undefined ? externalShowDropdown : internalShowDropdown;
  const setShowDropdown = externalSetShowDropdown || setInternalShowDropdown;

  const safeAuthors = Array.isArray(authors) ? authors : [];

  const filteredAuthors = useMemo(() =>
    safeAuthors.filter(a => a.author && a.author.toLowerCase().includes(filter.toLowerCase())),
    [safeAuthors, filter]
  );
  const selectedAuthor = safeAuthors.find(a => a.author_key === value);

  useEffect(() => {
    const handleClickOutside = (e) => {
      if (containerRef.current && !containerRef.current.contains(e.target)) {
        setShowDropdown(false);
        setIsEditing(false);
        setFilter('');
      }
    };
    document.addEventListener('pointerdown', handleClickOutside);
    return () => document.removeEventListener('pointerdown', handleClickOutside);
  }, [setShowDropdown, setFilter]);

  const displayValue = isEditing ? filter : (selectedAuthor ? selectedAuthor.author : '');

  const handleSelect = (authorKey) => {
    onChange(authorKey);
    setFilter('');
    setShowDropdown(false);
    setIsEditing(false);
  };

  // On touch devices, use native <select> for reliable mobile support
  if (isTouchDevice()) {
    return (
      <select
        value={value}
        onChange={e => onChange(e.target.value)}
        className="w-full border rounded px-2 py-2 text-sm"
      >
        <option value="">Select author...</option>
        {safeAuthors.map(a => (
          <option key={a.author_key} value={a.author_key}>{a.author}</option>
        ))}
      </select>
    );
  }

  return (
    <div ref={containerRef} className="relative">
      <input
        ref={inputRef}
        type="text"
        placeholder="Type to search..."
        value={displayValue}
        onChange={e => { setFilter(e.target.value); setShowDropdown(true); setIsEditing(true); }}
        onFocus={() => { setShowDropdown(true); setIsEditing(true); setFilter(''); }}
        onBlur={() => { if (!showDropdown) { setIsEditing(false); setFilter(''); } }}
        className="w-full border rounded px-2 py-2 text-sm"
      />
      {showDropdown && (
        <div className="absolute z-50 w-full mt-1 bg-white border rounded shadow-lg max-h-48 overflow-y-auto">
          {filteredAuthors.length > 0 ? filteredAuthors.map(a => (
            <button key={a.author_key} type="button"
              onPointerDown={(e) => { e.preventDefault(); handleSelect(a.author_key); }}
              className={`w-full text-left px-3 py-1.5 text-sm hover:bg-gray-100 cursor-pointer ${value === a.author_key ? 'bg-gray-50 font-medium' : ''}`}>
              {a.author}
            </button>
          )) : <div className="px-3 py-2 text-sm text-gray-500">No matches</div>}
        </div>
      )}
    </div>
  );
};

export default SearchableAuthorSelect;
