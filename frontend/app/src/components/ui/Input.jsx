export default function Input({
  label,
  error,
  className = '',
  ...props
}) {
  return (
    <div className="flex flex-col gap-1">
      {label && (
        <label className="text-sm font-medium text-ink">
          {label}
        </label>
      )}
      <input
        className={`
          w-full px-4 py-3 rounded-xl border bg-white text-ink
          placeholder-ink-light outline-none transition-all
          border-gray-200 focus:border-green-mid focus:ring-2 focus:ring-green-pale
          ${error ? 'border-red-400 focus:border-red-400 focus:ring-red-100' : ''}
          ${className}
        `}
        {...props}
      />
      {error && <span className="text-xs text-red-500">{error}</span>}
    </div>
  )
}