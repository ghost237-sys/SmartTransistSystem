export const SUPER_METRO_ROUTES = {
  "Route 105: Nairobi CBD - Kikuyu": [
    "Odeon", "Museum Hill", "Chiromo", "Westlands Stage", "Church Road", "ABC Place",
    "Kangemi", "Mountain View", "Uthiru", "Kinoo", "Regen", "Kikuyu Town"
  ],
  "Route 237: Nairobi CBD - Thika / Makongeni": [
    "Commercial", "Pangani", "Muthaiga", "KCA University", "Garden City", "Allsops",
    "Roysambu", "Githurai", "Kahawa Barracks", "Kahawa Sukari", "Kenyatta University",
    "Ruiru Flyover", "Clay Works", "Eastern Bypass Junction", "Juja", "Witeithie",
    "Mang'u High School", "Thika Town"
  ],
  "Route 236: Nairobi CBD - Juja": [
    "Commercial", "Pangani", "Muthaiga", "Roysambu", "Githurai", "Kahawa Sukari",
    "Ruiru", "Juja"
  ],
  "Route 111: Nairobi CBD - Ngong": [
    "Railways", "KNH", "Coptic Hospital", "Prestige Plaza", "Adams Arcade",
    "Jamhuri / Posta", "Junction Mall", "Lenana", "Karen", "Kephis",
    "Shade Hotel", "Bulbul", "Ngong"
  ],
  "Nairobi CBD - Kahawa West": [
    "Commercial", "Survey", "Roasters", "TRM", "Zimmerman", "Githurai 44",
    "Kahawa West Roundabout"
  ],
  "Route 102: Kencom - Kabiria": [
    "Kencom", "Community", "Upperhill", "KNH", "Ngong Road", "Wanyee Road",
    "Satellite", "Kabiria"
  ],
  "Nairobi CBD - Ongata Rongai": [
    "Railways", "T-Mall", "Lang'ata Road", "Brookhouse", "Multimedia University",
    "Rongai Town"
  ],
  "Nairobi CBD - Malaa": [
    "Mfangano", "Landhies Road", "Jogoo Road", "Outering Road Junction", "Taj Mall",
    "Ruai", "Kamulu", "Joska", "Malaa"
  ]
}

/**
 * Returns all other stops on a route excluding the boarding stage.
 * This lets the commuter pick any destination (either direction) from a mid-route stop.
 */
export function getAllOtherStops(routeName, boardingStage) {
  const stages = SUPER_METRO_ROUTES[routeName]
  if (!stages) return []
  return stages.filter(s => s !== boardingStage)
}

/**
 * Automatically infers travel direction from the ordered route sequence.
 * @returns {'outbound'|'inbound'|null}
 */
export function inferDirection(routeName, boardingStage, destinationStage) {
  const stages = SUPER_METRO_ROUTES[routeName]
  if (!stages) return null
  const boardIdx = stages.indexOf(boardingStage)
  const destIdx = stages.indexOf(destinationStage)
  if (boardIdx === -1 || destIdx === -1) return null
  return destIdx > boardIdx ? 'outbound' : 'inbound'
}

/**
 * Get the intermediate stops between boarding and destination (inclusive of destination).
 * Respects travel direction automatically.
 */
export function getIntermediateStops(routeName, boardingStage, destinationStage) {
  const stages = SUPER_METRO_ROUTES[routeName]
  if (!stages) return []
  const boardIdx = stages.indexOf(boardingStage)
  const destIdx = stages.indexOf(destinationStage)
  if (boardIdx === -1 || destIdx === -1) return []
  if (destIdx > boardIdx) {
    // Outbound: slice forward from boarding+1 to destination (inclusive)
    return stages.slice(boardIdx + 1, destIdx + 1)
  } else {
    // Inbound: slice backward from boarding-1 to destination (inclusive), reversed
    return stages.slice(destIdx, boardIdx).reverse()
  }
}

export function getFilteredDestinations(routeName, boardingStage, direction = 'Outbound') {
  const stages = SUPER_METRO_ROUTES[routeName]
  if (!stages) return []
  const sequence = direction === 'Inbound' ? [...stages].reverse() : stages
  const boardingIndex = sequence.indexOf(boardingStage)
  if (boardingIndex === -1) return sequence
  return sequence.slice(boardingIndex + 1)
}

export function getRoutesForStop(stopName) {
  return Object.entries(SUPER_METRO_ROUTES)
    .filter(([_, stages]) => stages.includes(stopName))
    .map(([routeName]) => routeName)
}

export function matchRouteKey(backendRouteName) {
  if (!backendRouteName) return null
  const lower = backendRouteName.toLowerCase()
  return Object.keys(SUPER_METRO_ROUTES).find(key => {
    const keyLower = key.toLowerCase()
    return keyLower.includes(lower) || lower.includes(keyLower) ||
      keyLower.split(/[-/]/).some(part => part.trim() && lower.includes(part.trim())) ||
      lower.split(/[-/]/).some(part => part.trim() && keyLower.includes(part.trim()))
  }) || null
}
