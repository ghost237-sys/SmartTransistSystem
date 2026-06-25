const variants = {
  green:  'bg-green-100 text-green-800',
  amber:  'bg-amber/20 text-amber-dark',
  red:    'bg-red-100 text-red-700',
  gray:   'bg-gray-100 text-gray-600',
  blue:   'bg-blue-100 text-blue-700',
}

export default function Badge({ children, variant = 'gray' }) {
  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold ${variants[variant]}`}>
      {children}
    </span>
  )
}