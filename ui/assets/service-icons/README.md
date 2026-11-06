# 민원톡톡 서비스 아이콘

‘자주 찾는 서비스’의 12개 분야에 맞춰 직접 제작한 SVG 도안이다. 이모지·외부 아이콘 라이브러리·원격 이미지가 아니다. 파란 외곽선, 밝은 파랑 바탕과 민트 보조색, 64×64 좌표계를 공통으로 사용한다.

| 파일 | 서비스 |
| --- | --- |
| `parking.svg` | 불법주정차 |
| `documents.svg` | 서류 안내 |
| `roads.svg` | 도로·시설 |
| `environment.svg` | 소음·환경 |
| `recycling.svg` | 폐기물 |
| `water.svg` | 상수도 |
| `parks.svg` | 공원·녹지 |
| `pets.svg` | 반려동물 |
| `housing.svg` | 주택·건축 |
| `taxes.svg` | 지방세 |
| `welfare.svg` | 생활·복지 |
| `transit.svg` | 대중교통 |

원본은 [`src/service-icons.js`](../../src/service-icons.js)다. UI는 같은 원본을 인라인 SVG로 렌더링하고, 이 폴더에는 개별 재사용 파일을 제공한다. 원본 수정 후 저장소 루트에서 `npm --prefix ui run icons:export`를 실행해 내보낸 파일을 갱신한다. 버튼의 텍스트가 접근성 이름을 제공하므로 화면의 SVG는 장식으로 처리하고, 단독 SVG 파일은 해당 서비스 이름을 포함한다.
