/**
 * 이름에 해당하는 장식용 아이콘을 반환합니다.
 *
 * @param {string} name 표시할 아이콘의 등록 이름입니다.
 * @param {number} [size=20] 아이콘의 가로·세로 크기입니다.
 * @returns {string} 화면에 사용할 HTML 또는 변환 결과입니다.
 */
export function icon(name, size = 20) {
  const paths = {
    chat: '<path d="M21 11a8 8 0 0 1-8 8H7l-5 3V11a9 9 0 0 1 19 0Z"/><path d="M7 9h8M7 13h5"/>',
    arrow: '<path d="M5 12h14m-5-5 5 5-5 5"/>',
    chevron: '<path d="m9 5 7 7-7 7"/>',
    search: '<circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 5 5"/>',
    plus: '<path d="M12 5v14M5 12h14"/>',
    home: '<path d="m3 10 9-7 9 7v10H3Zm6 10v-7h6v7"/>',
    file: '<path d="M14 3H5v18h14V8Zm0 0v5h5M8 12h8M8 16h5"/>',
    grid: '<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/>',
    spark:
      '<path d="m12 3 2.5 6.5L21 12l-6.5 2.5L12 21l-2.5-6.5L3 12l6.5-2.5ZM20 2v4m-2-2h4"/>',
    user: '<circle cx="12" cy="8" r="4"/><path d="M4 21v-3a8 8 0 0 1 16 0v3"/>',
    bell: '<path d="M5 16h14l-2-4V8A5 5 0 0 0 7 8v4ZM10 20h4"/>',
    check: '<path d="m5 12 4 4L19 6"/>',
    clock: '<circle cx="12" cy="12" r="9"/><path d="M12 6v6l4 2"/>',
    pin: '<path d="M19 10c0 5-7 11-7 11S5 15 5 10a7 7 0 0 1 14 0Z"/><circle cx="12" cy="10" r="2"/>',
    leaf: '<path d="M20 3C7 2 2 8 6 15c6 7 15-1 14-12ZM3 21 16 8"/>',
    road: '<path d="M7 3 3 21M17 3l4 18M12 3v3m0 4v4m0 4v3"/>',
    bus: '<rect x="5" y="3" width="14" height="16" rx="3"/><path d="M5 11h14M8 19v2m8-2v2M9 15h.01M15 15h.01M9 6h6"/>',
    park: '<path d="m12 2-6 8h3l-5 7h16l-5-7h3ZM12 17v5"/>',
    building: '<path d="M3 21h18M5 21V8h14v13M3 8l9-5 9 5M9 11v6m6-6v6"/>',
    help: '<circle cx="12" cy="12" r="9"/><path d="M9 9a3 3 0 1 1 5 2c-2 1-2 2-2 3m0 3h.01"/>',
    monitor:
      '<rect x="2" y="3" width="20" height="14" rx="2"/><path d="M8 21h8m-4-4v4M6 11l4-4 4 5 4-4"/>',
    filter: '<path d="M4 5h16l-6 7v7l-4 2v-9Z"/>',
    exit: '<path d="M9 4H4v16h5M9 12h12m-4-4 4 4-4 4"/>',
    close: '<path d="m6 6 12 12M6 18 18 6"/>',
    refresh: '<path d="M20 8a8 8 0 1 0 0 8M20 3v5h-5"/>',
    shield: '<path d="m12 2 8 4v6c0 5-8 10-8 10S4 17 4 12V6Zm-4 9 3 3 5-6"/>',
    menu: '<path d="M4 6h16M4 12h16M4 18h16"/>',
    book: '<path d="M12 5C9 3 5 3 2 4v15c4-1 7-1 10 1 3-2 6-2 10-1V4c-3-1-7-1-10 1Zm0 0v15"/>',
    sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2m0 16v2M4.93 4.93l1.42 1.42m11.3 11.3 1.42 1.42M2 12h2m16 0h2M4.93 19.07l1.42-1.42m11.3-11.3 1.42-1.42"/>',
    moon: '<path d="M20.4 15.6A8.8 8.8 0 0 1 8.4 3.6 9 9 0 1 0 20.4 15.6Z"/>',
    sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2m0 16v2M4.93 4.93l1.42 1.42m11.3 11.3 1.42 1.42M2 12h2m16 0h2M4.93 19.07l1.42-1.42m11.3-11.3 1.42-1.42"/>',
    moon: '<path d="M20.4 15.6A8.8 8.8 0 0 1 8.4 3.6 9 9 0 1 0 20.4 15.6Z"/>',
  };
  return `<svg width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${paths[name] || paths.file}</svg>`;
}
