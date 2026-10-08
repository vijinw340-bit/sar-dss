/** Small reference set of major Indian airports used for the "nearby airports" layer. */
export interface Airport {
  code: string;
  name: string;
  lat: number;
  lon: number;
}

export const AIRPORTS: Airport[] = [
  { code: "VIDP", name: "Indira Gandhi Intl, Delhi", lat: 28.5562, lon: 77.1 },
  { code: "VABB", name: "Chhatrapati Shivaji Intl, Mumbai", lat: 19.0887, lon: 72.8679 },
  { code: "VECC", name: "Netaji Subhas Chandra Bose, Kolkata", lat: 22.6547, lon: 88.4467 },
  { code: "VOMM", name: "Chennai Intl", lat: 12.9941, lon: 80.1709 },
  { code: "VOBL", name: "Kempegowda Intl, Bengaluru", lat: 13.1986, lon: 77.7066 },
  { code: "VOHY", name: "Rajiv Gandhi Intl, Hyderabad", lat: 17.2403, lon: 78.4294 },
  { code: "VIAA", name: "Sri Guru Ram Dass Jee Intl, Amritsar", lat: 31.7096, lon: 74.7973 },
  { code: "VIAR", name: "Sri Sathya Sai, Puttaparthi", lat: 14.1493, lon: 77.7911 },
  { code: "VAAH", name: "Sardar Vallabhbhai Patel Intl, Ahmedabad", lat: 23.0703, lon: 72.6286 },
  { code: "VABP", name: "Raja Bhoj, Bhopal", lat: 23.2875, lon: 77.3375 },
  { code: "VAGO", name: "Dabolim, Goa", lat: 15.3808, lon: 73.8314 },
  { code: "VGBR", name: "Barisal", lat: 22.8014, lon: 90.3012 },
  { code: "VEGT", name: "Lokpriya Gopinath Bordoloi Intl, Guwahati", lat: 26.1061, lon: 91.5859 },
  { code: "VIAL", name: "Prayagraj", lat: 25.4401, lon: 81.7339 },
  { code: "VIBN", name: "Varanasi Intl", lat: 25.4524, lon: 82.8593 },
  { code: "VIDN", name: "Dehradun (Jolly Grant)", lat: 30.1897, lon: 78.1803 },
  { code: "VIGR", name: "Gwalior", lat: 26.2936, lon: 78.2278 },
  { code: "VIJP", name: "Jaipur Intl", lat: 26.8242, lon: 75.8122 },
  { code: "VIKO", name: "Kota", lat: 25.1602, lon: 75.845 },
  { code: "VIKR", name: "Birsa Munda, Ranchi", lat: 23.3142, lon: 85.3217 },
  { code: "VILK", name: "Chaudhary Charan Singh Intl, Lucknow", lat: 26.7606, lon: 80.8893 },
  { code: "VIJO", name: "Jodhpur", lat: 26.2511, lon: 73.0481 },
  { code: "VOCL", name: "Calicut Intl", lat: 11.1368, lon: 75.955 },
  { code: "VOCI", name: "Coimbatore Intl", lat: 11.0301, lon: 77.0434 },
  { code: "VOCB", name: "Coimbatore (Peelamedu)", lat: 11.0299, lon: 77.0434 },
  { code: "VOPB", name: "Veer Savarkar Intl, Port Blair", lat: 11.6412, lon: 92.7297 },
  { code: "VOTV", name: "Thiruvananthapuram Intl", lat: 8.4821, lon: 76.9197 },
  { code: "VQPR", name: "Paro Intl, Bhutan", lat: 27.4032, lon: 89.4246 },
  { code: "VTCI", name: "Chiang Mai", lat: 18.7669, lon: 98.9626 },
  { code: "VNKT", name: "Tribhuvan Intl, Kathmandu", lat: 27.6966, lon: 85.3591 },
  { code: "VGBG", name: "Shah Amanat Intl, Chittagong", lat: 22.2496, lon: 91.8133 },
];

/** Convert GeoJSON [lon, lat] pairs to Leaflet [lat, lon] positions. */
export function geoToLatLng(coords: number[][]): [number, number][] {
  return coords.map(([lon, lat]) => [lat, lon] as [number, number]);
}

/** Approximate great-circle distance in nautical miles. */
export function haversineNm(lat1: number, lon1: number, lat2: number, lon2: number): number {
  const R = 3440.065;
  const toRad = (d: number) => (d * Math.PI) / 180;
  const dLat = toRad(lat2 - lat1);
  const dLon = toRad(lon2 - lon1);
  const a =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dLon / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(a));
}
