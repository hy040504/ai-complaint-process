/**
 * 민원톡톡의 12개 서비스에 맞춰 직접 그린 SVG 아이콘입니다.
 */
const artwork = {
  parking: `<rect x="11" y="13" width="21" height="25" rx="5" fill="#2f6fed" stroke="none"/>
    <path d="M19 31V20h5a4 4 0 0 1 0 8h-5" stroke="#fff" stroke-width="2.6" fill="none"/>
    <path d="M22 40l3-8a5 5 0 0 1 5-3h11a5 5 0 0 1 5 3l4 8" fill="#dbe8ff"/>
    <rect x="20" y="38" width="33" height="12" rx="5" fill="#fff"/>
    <path d="M27 38h19M26 44h2m17 0h2"/>
    <path d="M25 50v3m23-3v3" stroke="#29466e" stroke-width="4"/>
    <path d="M12 48h4" stroke="#85b5ef"/>`,
  documents: `<path d="M19 11h20l10 10v30a3 3 0 0 1-3 3H19a3 3 0 0 1-3-3V14a3 3 0 0 1 3-3Z" fill="#fff"/>
    <path d="M37 11v12h12" fill="#dbe8ff"/>
    <path d="M23 30h17m-17 7h11m-11 7h8" stroke="#8baee6"/>
    <circle cx="45" cy="46" r="10" fill="#d9f1e9" stroke="#42a88e"/>
    <path d="m40 46 3 3 6-6" stroke="#278d75"/>`,
  roads: `<path d="M25 13h14l13 40H12Z" fill="#dbe8ff"/>
    <path d="m25 13-9 40m23-40 9 40" stroke="#2f6fed"/>
    <path d="M32 18v6m0 6v7m0 7v5" stroke="#537aaf"/>
    <path d="M45 15h8m-4-4v17" stroke="#42a88e"/>
    <path d="M46 15a3 3 0 0 1 6 0" fill="#a8dfd0" stroke="#42a88e"/>`,
  environment: `<path d="M13 27h11l14-11v34L24 39H13a2 2 0 0 1-2-2v-8a2 2 0 0 1 2-2Z" fill="#dbe8ff"/>
    <path d="M24 27v12"/>
    <path d="M45 24a13 13 0 0 1 0 18m6-24a22 22 0 0 1 0 30" fill="none"/>
    <path d="m18 40 3 11h7l-3-11" fill="#fff" stroke="#537aaf"/>
    <path d="M15 32h4" stroke="#8eafe2"/>`,
  recycling: `<path d="m24 20 5-8a4 4 0 0 1 7 0l8 13" fill="none" stroke="#2f6fed" stroke-width="5"/>
    <path d="m36 24 9 2 2-9" fill="none"/>
    <path d="m47 32 7 12a4 4 0 0 1-4 6H34" fill="none" stroke="#42a88e" stroke-width="5"/>
    <path d="m39 44-7 6 7 6" fill="none" stroke="#42a88e"/>
    <path d="M24 50H13a4 4 0 0 1-4-6l8-14" fill="none" stroke="#6b96e7" stroke-width="5"/>
    <path d="m9 33 9-4 4 9" fill="none" stroke="#6b96e7"/>
    <circle cx="31" cy="35" r="5" fill="#d9f1e9" stroke="none"/>`,
  water: `<path d="M32 10c-4 7-17 20-17 31a17 17 0 0 0 34 0c0-11-13-24-17-31Z" fill="#dbeeff"/>
    <path d="M22 40a11 11 0 0 0 10 12" fill="none" stroke="#7eb3ed" stroke-width="3"/>
    <path d="M26 29c2-3 4-5 6-8" fill="none" stroke="#fff" stroke-width="4"/>
    <path d="M48 16v7m-3-3h6" stroke="#57b49e" stroke-width="2"/>`,
  parks: `<path d="m32 10-12 17h5L14 42h13v11h10V42h13L39 27h5Z" fill="#d9f1e9"/>
    <path d="M32 22v30m0-16-6-6m6 12 7-7" stroke="#42a88e"/>
    <path d="M16 54h32" stroke="#89bba8"/>
    <path d="M14 19v5m-2-2h4" stroke="#87abe6" stroke-width="1.8"/>`,
  pets: `<path d="M21 20c-5-7-12-6-12 1v16c0 5 5 5 10-1m24-16c5-7 12-6 12 1v16c0 5-5 5-10-1" fill="#a9c5f6"/>
    <path d="M32 16c-12 0-17 8-17 19v6c0 10 8 15 17 15s17-5 17-15v-6c0-11-5-19-17-19Z" fill="#fff"/>
    <path d="M25 34v2m14-2v2" stroke="#29466e" stroke-width="3.5"/>
    <path d="M28 42q4-4 8 0l-4 4Z" fill="#29466e" stroke="#29466e" stroke-width="1.6"/>
    <path d="M32 46v3m-5 0q5 5 10 0" stroke="#537aaf"/>
    <path d="M24 54h16" stroke="#42a88e" stroke-width="3.5"/>`,
  housing: `<path d="M17 29v23h30V29" fill="#fff"/>
    <path d="m10 30 22-19 22 19" stroke-width="4" fill="none"/>
    <path d="M37 15v-4h7v10" fill="#dbe8ff"/>
    <path d="M26 52V37h12v15" fill="#dbe8ff"/>
    <path d="M20 32h4m18 0h3" stroke="#83a9e8"/>
    <path d="M11 54h43" stroke="#88a7d5"/>
    <circle cx="34" cy="44" r="1" fill="#2f6fed" stroke="none"/>`,
  taxes: `<rect x="12" y="11" width="29" height="41" rx="5" fill="#fff"/>
    <path d="M20 20h13m-13 7h13m-13 7h7" stroke="#8baee6"/>
    <circle cx="43" cy="43" r="13" fill="#dbe8ff"/>
    <path d="m35 38 4 12 4-11 4 11 4-12m-18 4h20m-19 4h18" stroke="#2f6fed" stroke-width="1.8"/>
    <path d="M18 43h4" stroke="#42a88e"/>`,
  welfare: `<path d="M32 33s-14-8-14-16a7 7 0 0 1 14-2 7 7 0 0 1 14 2c0 8-14 16-14 16Z" fill="#d9f1e9" stroke="#42a88e"/>
    <path d="M11 36v10l15 10 6-8-11-9c-3-3-6 1-3 4l6 5" fill="#dbe8ff"/>
    <path d="M53 36v10L38 56l-6-8 11-9c3-3 6 1 3 4l-6 5" fill="#dbe8ff"/>
    <path d="m10 47 11 8m33-8-11 8" stroke="#537aaf"/>`,
  transit: `<rect x="15" y="10" width="34" height="43" rx="8" fill="#fff"/>
    <rect x="20" y="20" width="24" height="16" rx="3" fill="#dbe8ff"/>
    <path d="M32 20v16" stroke="#9bb9eb" stroke-width="1.8"/>
    <path d="M26 15h12" stroke="#42a88e"/>
    <path d="M24 45h16" stroke="#97b7e8"/>
    <circle cx="22" cy="42" r="2" fill="#2f6fed" stroke="none"/>
    <circle cx="42" cy="42" r="2" fill="#2f6fed" stroke="none"/>
    <path d="M21 53v3m22-3v3" stroke="#29466e" stroke-width="4"/>`,
};

/**
 * 서비스 이름에 해당하는 독립적인 벡터 도안을 반환합니다.
 *
 * @param {string} name 표시할 아이콘의 등록 이름입니다.
 * @returns {string} 화면에 사용할 HTML 또는 변환 결과입니다.
 */
export function serviceIcon(name) {
  if (!Object.hasOwn(artwork, name))
    throw new Error(`서비스 아이콘을 찾을 수 없습니다: ${name}`);
  return `<svg class="service-artwork" width="40" height="40" viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg" stroke="#2f6fed" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false" data-service-icon="${name}"><rect x="3" y="3" width="58" height="58" rx="18" fill="#f0f5ff" stroke="none"/>${artwork[name]}</svg>`;
}
