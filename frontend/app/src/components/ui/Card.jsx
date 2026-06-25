export default function Card({ children, className = '', ...props }) {
  return (
    <div
      className={`bg-white rounded-2xl border border-gray-100 shadow-sm p-6 ${className}`}
      {...props}
    >
      {children}
    </div>
  )
}