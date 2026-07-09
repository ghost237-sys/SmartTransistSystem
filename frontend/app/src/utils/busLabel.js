/** Display label: plate number primary, fleet/windshield code secondary. */
export function formatBusLabel(ride) {
  const plate = ride?.vehicle_plate?.trim()
  const code = ride?.fleet_code?.trim()
  if (plate && code && plate.toUpperCase() !== code.toUpperCase()) {
    return `${plate} · ${code}`
  }
  return plate || code || 'Bus'
}
