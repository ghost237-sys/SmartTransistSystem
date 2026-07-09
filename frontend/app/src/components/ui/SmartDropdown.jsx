import { useState, useRef, useEffect } from 'react'

export default function SmartDropdown({
  placeholder = 'Search...',
  value = '',
  onChange,
  items = [],
  renderItem,
  onSelect,
  loading = false,
  emptyMessage = 'No results found',
  className = '',
}) {
  const [isOpen, setIsOpen] = useState(false)
  const dropdownRef = useRef(null)

  useEffect(() => {
    function handleClickOutside(event) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target)) {
        setIsOpen(false)
      }
    }

    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  const handleInputChange = (e) => {
    onChange(e.target.value)
    setIsOpen(true)
  }

  const handleItemSelect = (item) => {
    onSelect(item)
    setIsOpen(false)
  }

  return (
    <div ref={dropdownRef} className={`relative ${className}`}>
      <div className={`relative ${isOpen ? 'rounded-t-xl rounded-b-none' : 'rounded-xl'}`}>
        <svg
          className="absolute left-4 top-1/2 -translate-y-1/2 text-ink-light w-4 h-4"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          viewBox="0 0 24 24"
        >
          <circle cx="11" cy="11" r="8" />
          <path d="m21 21-4.35-4.35" />
        </svg>
        <input
          type="text"
          placeholder={placeholder}
          value={value}
          onChange={handleInputChange}
          onFocus={() => setIsOpen(true)}
          className={`w-full pl-11 pr-4 py-3 border border-gray-200 bg-white text-ink placeholder-ink-light outline-none transition-all ${
            isOpen 
              ? 'border-b-0 rounded-t-xl focus:border-green-mid focus:ring-2 focus:ring-green-pale focus:rounded-t-xl' 
              : 'rounded-xl focus:border-green-mid focus:ring-2 focus:ring-green-pale'
          }`}
        />
      </div>

      {isOpen && (
        <div className="absolute z-50 w-full bg-white border border-gray-200 border-t-0 rounded-b-xl shadow-lg max-h-96 overflow-y-auto">
          {loading ? (
            <div className="flex justify-center py-8">
              <svg className="animate-spin h-6 w-6 text-green-deep" viewBox="0 0 24 24" fill="none">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
              </svg>
            </div>
          ) : items.length === 0 ? (
            <div className="py-4 px-4 text-center">
              <p className="text-sm text-ink-light">{emptyMessage}</p>
            </div>
          ) : (
            <div className="py-2">
              {items.map((item, index) => (
                <div
                  key={index}
                  onClick={() => handleItemSelect(item)}
                  className="px-4 py-3 hover:bg-gray-50 cursor-pointer transition-colors"
                >
                  {renderItem ? renderItem(item) : <span className="text-ink">{String(item)}</span>}
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
