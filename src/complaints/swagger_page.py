"""청주톡톡 민원 업무 백엔드(:5000) 전용 한국어 Swagger UI 포털을 생성합니다."""

from __future__ import annotations


def render_swagger_html(*, embed: bool = False) -> str:
    """자체 정적 자산만 사용하는 한국어 Swagger UI HTML 문서를 반환합니다.

    외부 CDN 없이 `flask-openapi3`가 제공하는 `/openapi/swagger/*` 자산과
    `/openapi/openapi.json` 스펙을 재사용합니다. 라이트·다크 테마 동기화,
    경로·메서드·태그·설명 통합 검색, 시연 세션 원클릭 전환(담당자·시민)을 지원합니다.

    Args:
        embed: 담당자 콘솔(`#/staff/api`) 내부 iframe 임베드 모드 여부입니다.
            `True`이면 상단 포털 헤더와 안내 띠를 숨겨 본문만 표시합니다.

    Returns:
        UTF-8 HTML5 문서 문자열입니다.
    """
    body_class = "embed-mode" if embed else "standalone-mode"
    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>청주톡톡 민원 업무 백엔드 API · Swagger UI</title>
  <link rel="icon" type="image/svg+xml" href="/favicon.svg">
  <link rel="stylesheet" href="/openapi/swagger/css/swagger-ui.css">
  <style>
    :root {{
      --swg-bg: #f3f6fc;
      --swg-surface: #ffffff;
      --swg-elevated: #f8fafd;
      --swg-text: #0f172a;
      --swg-text-secondary: #334155;
      --swg-muted: #475569;
      --swg-border: #d5e0f0;
      --swg-accent: #1d4ed8;
      --swg-accent-soft: #e0ebff;
      --swg-accent-border: #bfdbfe;
      --swg-header-bg: #121c33;
      --swg-header-text: #f8fafc;
      --swg-header-border: #243456;
      --swg-warn-bg: #fff8eb;
      --swg-warn-text: #854d0e;
      --swg-warn-border: #f2cf88;
      --swg-code-bg: #0f172a;
      --swg-accept-text: #047857;
      --swg-shadow: 0 10px 28px rgba(15, 23, 42, 0.06);
    }}
    body[data-theme="dark"] {{
      --swg-bg: #0b1220;
      --swg-surface: #121d31;
      --swg-elevated: #182640;
      --swg-text: #eef4ff;
      --swg-text-secondary: #cbd5e1;
      --swg-muted: #a6b7d2;
      --swg-border: #2c3f60;
      --swg-accent: #93c5fd;
      --swg-accent-soft: #1d3257;
      --swg-accent-border: #3b63a8;
      --swg-header-bg: #0d1628;
      --swg-header-text: #f8fafc;
      --swg-header-border: #223250;
      --swg-warn-bg: #2a2112;
      --swg-warn-text: #fcd37a;
      --swg-warn-border: #664c1f;
      --swg-code-bg: #080e1a;
      --swg-accept-text: #6ee7b7;
      --swg-shadow: 0 12px 30px rgba(0, 0, 0, 0.4);
    }}
    *, *::before, *::after {{
      box-sizing: border-box;
    }}
    html, body {{
      margin: 0;
      padding: 0;
      background: var(--swg-bg);
      color: var(--swg-text);
      font-family: "Pretendard Variable", "Noto Sans KR", "Apple SD Gothic Neo", "Malgun Gothic", sans-serif;
      font-size: 15px;
      line-height: 1.55;
      -webkit-font-smoothing: antialiased;
    }}
    body.embed-mode .swg-portal-header,
    body.embed-mode .swg-notice-strip {{
      display: none;
    }}
    .swg-portal-header {{
      position: sticky;
      top: 0;
      z-index: 40;
      background: var(--swg-header-bg);
      color: var(--swg-header-text);
      border-bottom: 1px solid var(--swg-header-border);
      padding: 14px 24px;
    }}
    .swg-header-inner {{
      max-width: 1360px;
      margin: 0 auto;
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      justify-content: space-between;
      gap: 14px;
    }}
    .swg-brand {{
      display: flex;
      align-items: center;
      gap: 12px;
      min-width: 0;
    }}
    .swg-badge {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      padding: 4px 10px;
      border-radius: 999px;
      font-size: 11.5px;
      font-weight: 700;
      letter-spacing: 0.04em;
      background: rgba(96, 165, 250, 0.22);
      color: #bfdbfe;
      border: 1px solid rgba(147, 197, 253, 0.38);
      white-space: nowrap;
    }}
    .swg-brand h1 {{
      margin: 0;
      font-size: 18px;
      font-weight: 700;
      line-height: 1.3;
      color: #ffffff;
    }}
    .swg-brand p {{
      margin: 3px 0 0;
      font-size: 13px;
      color: #cbd5e1;
    }}
    .swg-nav-row {{
      max-width: 1360px;
      margin: 12px auto 0;
      padding-top: 10px;
      border-top: 1px solid rgba(148, 163, 184, 0.18);
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      justify-content: space-between;
      gap: 10px;
    }}
    .swg-links {{
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      gap: 8px;
    }}
    .swg-link {{
      display: inline-flex;
      align-items: center;
      gap: 5px;
      padding: 6px 12px;
      border-radius: 8px;
      font-size: 13px;
      font-weight: 600;
      text-decoration: none;
      color: #e0edff;
      background: rgba(255, 255, 255, 0.08);
      border: 1px solid rgba(148, 163, 184, 0.26);
      transition: background 0.15s ease, border-color 0.15s ease;
    }}
    .swg-link:hover {{
      background: rgba(255, 255, 255, 0.17);
      border-color: rgba(147, 197, 253, 0.6);
      color: #ffffff;
    }}
    .swg-link.primary {{
      background: #2563eb;
      border-color: #3b82f6;
      color: #ffffff;
    }}
    .swg-link.primary:hover {{
      background: #1d4ed8;
    }}
    .swg-tools {{
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      gap: 8px;
    }}
    .swg-pill {{
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 6px 11px;
      border-radius: 999px;
      font-size: 12.5px;
      font-weight: 600;
      background: rgba(255, 255, 255, 0.09);
      color: #f1f5f9;
      border: 1px solid rgba(148, 163, 184, 0.26);
    }}
    .swg-dot {{
      width: 8px;
      height: 8px;
      border-radius: 999px;
      background: #34d399;
      flex-shrink: 0;
    }}
    .swg-dot.warn {{
      background: #fbbf24;
    }}
    .swg-dot.off {{
      background: #f87171;
    }}
    .swg-btn {{
      display: inline-flex;
      align-items: center;
      gap: 4px;
      padding: 6px 11px;
      border-radius: 8px;
      font: inherit;
      font-size: 12.5px;
      font-weight: 600;
      cursor: pointer;
      color: #f8fafc;
      background: rgba(255, 255, 255, 0.11);
      border: 1px solid rgba(148, 163, 184, 0.32);
      transition: background 0.15s ease, border-color 0.15s ease;
    }}
    .swg-btn:hover {{
      background: rgba(255, 255, 255, 0.2);
      border-color: rgba(147, 197, 253, 0.65);
    }}
    .swg-btn.active {{
      background: #0f766e;
      border-color: #2dd4bf;
      color: #ffffff;
    }}
    .swg-notice-strip {{
      max-width: 1360px;
      margin: 16px auto 0;
      padding: 0 24px;
    }}
    .swg-notice-box {{
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      justify-content: space-between;
      gap: 10px;
      padding: 12px 16px;
      border-radius: 12px;
      background: var(--swg-warn-bg);
      color: var(--swg-warn-text);
      border: 1px solid var(--swg-warn-border);
      font-size: 13.5px;
      line-height: 1.55;
    }}
    .swg-notice-box code {{
      font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      font-size: 12.5px;
      padding: 1px 5px;
      border-radius: 5px;
      background: rgba(127, 90, 20, 0.12);
    }}
    body[data-theme="dark"] .swg-notice-box code {{
      background: rgba(252, 211, 122, 0.14);
      color: #fde68a;
    }}
    .swg-container {{
      max-width: 1360px;
      margin: 16px auto 36px;
      padding: 0 24px;
    }}
    body.embed-mode .swg-container {{
      max-width: 100%;
      margin: 0;
      padding: 10px 14px 28px;
    }}
    .swg-card {{
      background: var(--swg-surface);
      border: 1px solid var(--swg-border);
      border-radius: 16px;
      box-shadow: var(--swg-shadow);
      padding: 12px 20px 26px;
      overflow-x: auto;
    }}
    body.embed-mode .swg-card {{
      border-radius: 12px;
      box-shadow: none;
      padding: 8px 16px 22px;
    }}

    /* Swagger UI 본문 가독성·배지·폰트 통일 (라이트·다크 공용) */
    .swagger-ui {{
      color: var(--swg-text);
      font-family: inherit;
      font-size: 15px;
    }}
    .swagger-ui .wrapper {{
      max-width: none;
      padding: 0;
    }}
    .swagger-ui .topbar {{
      display: none;
    }}
    .swagger-ui .info {{
      margin: 18px 0 16px;
    }}
    .swagger-ui .info .title {{
      color: var(--swg-text);
      font-family: inherit;
      font-size: 28px;
      font-weight: 750;
      letter-spacing: -0.02em;
      line-height: 1.3;
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      gap: 8px;
    }}
    .swagger-ui .info .title small {{
      background: var(--swg-accent-soft);
      color: var(--swg-accent);
      border: 1px solid var(--swg-accent-border);
      border-radius: 999px;
      padding: 2px 10px;
      margin: 0;
      top: 0;
      display: inline-flex;
      align-items: center;
    }}
    .swagger-ui .info .title small pre {{
      color: var(--swg-accent) !important;
      font-family: inherit;
      font-size: 13px;
      font-weight: 700;
      margin: 0;
      padding: 0;
    }}
    .swagger-ui .info .title small.version-stamp {{
      background: #047857;
      border-color: #059669;
      color: #ffffff;
    }}
    .swagger-ui .info .title small.version-stamp pre {{
      color: #ffffff !important;
    }}
    .swagger-ui .info a,
    .swagger-ui .info .url {{
      color: var(--swg-accent);
      font-size: 13.5px;
    }}
    .swagger-ui .info p,
    .swagger-ui .info li,
    .swagger-ui .info table,
    .swagger-ui .renderedMarkdown p,
    .swagger-ui .markdown p {{
      color: var(--swg-text-secondary);
      font-family: inherit;
      font-size: 14.5px;
      line-height: 1.65;
    }}
    .swagger-ui .scheme-container {{
      display: none;
    }}
    .swagger-ui .filter-container {{
      margin: 0 0 14px;
      padding: 0;
      background: transparent;
    }}
    .swagger-ui .filter .operation-filter-input {{
      width: 100%;
      max-width: none;
      margin: 8px 0 4px;
      background: var(--swg-elevated);
      color: var(--swg-text);
      border: 1px solid var(--swg-border);
      border-radius: 10px;
      padding: 11px 14px;
      font-family: inherit;
      font-size: 14.5px;
    }}
    .swagger-ui .filter .operation-filter-input::placeholder {{
      color: var(--swg-muted);
      opacity: 1;
    }}
    .swagger-ui .opblock-tag-section {{
      margin-bottom: 12px;
    }}
    .swagger-ui .opblock-tag {{
      color: var(--swg-text);
      border-bottom: 1px solid var(--swg-border);
      font-family: inherit;
      font-size: 19px;
      font-weight: 700;
      padding: 14px 8px;
      margin: 8px 0;
    }}
    .swagger-ui .opblock-tag small,
    .swagger-ui .opblock-tag small p {{
      color: var(--swg-muted);
      font-family: inherit;
      font-size: 13.5px;
      font-weight: 500;
      margin: 0;
    }}
    .swagger-ui .opblock {{
      border-radius: 12px;
      box-shadow: none;
      margin-bottom: 10px;
    }}
    .swagger-ui .opblock .opblock-summary {{
      padding: 8px 12px;
    }}
    .swagger-ui .opblock .opblock-summary-method {{
      min-width: 78px;
      font-size: 13px;
      font-weight: 800;
      border-radius: 7px;
      padding: 6px 10px;
      text-shadow: none;
    }}
    .swagger-ui .opblock.opblock-get .opblock-summary-method {{
      background: #1d4ed8;
      color: #ffffff;
    }}
    .swagger-ui .opblock.opblock-post .opblock-summary-method {{
      background: #047857;
      color: #ffffff;
    }}
    .swagger-ui .opblock.opblock-put .opblock-summary-method {{
      background: #b45309;
      color: #ffffff;
    }}
    .swagger-ui .opblock.opblock-patch .opblock-summary-method {{
      background: #6d28d9;
      color: #ffffff;
    }}
    .swagger-ui .opblock.opblock-delete .opblock-summary-method {{
      background: #b91c1c;
      color: #ffffff;
    }}
    .swagger-ui .opblock .opblock-summary-path {{
      font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      font-size: 14px;
      font-weight: 650;
      color: var(--swg-text);
    }}
    .swagger-ui .opblock .opblock-summary-description {{
      font-family: inherit;
      font-size: 13.5px;
      color: var(--swg-text-secondary);
      line-height: 1.45;
    }}
    .swagger-ui .opblock-description-wrapper p,
    .swagger-ui .opblock-external-docs-wrapper p,
    .swagger-ui .parameter__name,
    .swagger-ui .parameter__type,
    .swagger-ui .response-col_status,
    .swagger-ui .response-col_description,
    .swagger-ui table thead tr th,
    .swagger-ui table thead tr td {{
      font-family: inherit;
      font-size: 13.5px;
    }}
    .swagger-ui .response-control-media-type__accept-message,
    .swagger-ui .response-control-media-type__accept-message code {{
      color: var(--swg-accept-text) !important;
      font-size: 12.5px;
      font-weight: 600;
    }}
    .swagger-ui .json-schema-2020-12-expand-deep-button {{
      background: #e2e8f0;
      color: #0f172a;
      border: 1px solid #cbd5e1;
      border-radius: 6px;
      padding: 2px 8px;
      font-size: 12px;
      font-weight: 650;
    }}
    .swagger-ui .json-schema-2020-12-expand-deep-button:hover {{
      background: #cbd5e1;
    }}
    .swagger-ui .btn {{
      border-radius: 8px;
      font-family: inherit;
      font-size: 13px;
      font-weight: 650;
    }}
    .swagger-ui select,
    .swagger-ui input[type=text],
    .swagger-ui input[type=search],
    .swagger-ui textarea {{
      border-radius: 8px;
      font-family: inherit;
      font-size: 13.5px;
    }}

    /* 다크 테마 Swagger UI 상세·스키마·응답 전면 보정 */
    body[data-theme="dark"] .swagger-ui,
    body[data-theme="dark"] .swagger-ui .opblock-tag,
    body[data-theme="dark"] .swagger-ui .opblock .opblock-summary-path,
    body[data-theme="dark"] .swagger-ui .opblock .opblock-summary-description,
    body[data-theme="dark"] .swagger-ui .opblock-section-header label,
    body[data-theme="dark"] .swagger-ui .opblock-title_normal,
    body[data-theme="dark"] .swagger-ui table thead tr td,
    body[data-theme="dark"] .swagger-ui table thead tr th,
    body[data-theme="dark"] .swagger-ui table.headers td,
    body[data-theme="dark"] .swagger-ui table.headers th,
    body[data-theme="dark"] .swagger-ui .parameter__name,
    body[data-theme="dark"] .swagger-ui .response-col_status,
    body[data-theme="dark"] .swagger-ui .response-col_description,
    body[data-theme="dark"] .swagger-ui .response-col_links,
    body[data-theme="dark"] .swagger-ui .tab li button.tablinks,
    body[data-theme="dark"] .swagger-ui section.models h4,
    body[data-theme="dark"] .swagger-ui section.models h4 button,
    body[data-theme="dark"] .swagger-ui .model-title,
    body[data-theme="dark"] .swagger-ui .model,
    body[data-theme="dark"] .swagger-ui .prop-name,
    body[data-theme="dark"] .swagger-ui .brace-open,
    body[data-theme="dark"] .swagger-ui .brace-close,
    body[data-theme="dark"] .swagger-ui .json-schema-2020-12,
    body[data-theme="dark"] .swagger-ui .json-schema-2020-12__title,
    body[data-theme="dark"] .swagger-ui .json-schema-2020-12-accordion__children {{
      color: var(--swg-text);
    }}
    body[data-theme="dark"] .swagger-ui .parameter__name.required span {{
      color: #fca5a5;
    }}
    body[data-theme="dark"] .swagger-ui .parameter__name.required::after {{
      color: #fca5a5;
    }}
    body[data-theme="dark"] .swagger-ui .parameter__type,
    body[data-theme="dark"] .swagger-ui .prop-type,
    body[data-theme="dark"] .swagger-ui .json-schema-2020-12__attribute--primary {{
      color: #93c5fd;
    }}
    body[data-theme="dark"] .swagger-ui .parameter__in,
    body[data-theme="dark"] .swagger-ui .parameter__extension,
    body[data-theme="dark"] .swagger-ui .parameter__deprecated,
    body[data-theme="dark"] .swagger-ui .response-col_links i,
    body[data-theme="dark"] .swagger-ui .opblock-description-wrapper p,
    body[data-theme="dark"] .swagger-ui .opblock-external-docs-wrapper p,
    body[data-theme="dark"] .swagger-ui .responses-inner h4,
    body[data-theme="dark"] .swagger-ui .responses-inner h5,
    body[data-theme="dark"] .swagger-ui .markdown code,
    body[data-theme="dark"] .swagger-ui .renderedMarkdown code,
    body[data-theme="dark"] .swagger-ui .prop-format,
    body[data-theme="dark"] .swagger-ui .json-schema-2020-12__attribute,
    body[data-theme="dark"] .swagger-ui .json-schema-2020-12-keyword,
    body[data-theme="dark"] .swagger-ui .json-schema-2020-12__constraint,
    body[data-theme="dark"] .swagger-ui .json-schema-2020-12-keyword__name {{
      color: var(--swg-text-secondary);
    }}
    body[data-theme="dark"] .swagger-ui .markdown code,
    body[data-theme="dark"] .swagger-ui .renderedMarkdown code {{
      background: #1d2d47;
      padding: 2px 6px;
      border-radius: 5px;
      color: #bfdbfe;
    }}
    body[data-theme="dark"] .swagger-ui .opblock .opblock-section-header {{
      background: #17243b;
      border-top: 1px solid var(--swg-border);
      border-bottom: 1px solid var(--swg-border);
    }}
    body[data-theme="dark"] .swagger-ui .opblock .opblock-section-header h4 {{
      color: var(--swg-text);
    }}
    body[data-theme="dark"] .swagger-ui .opblock.opblock-get {{
      background: rgba(37, 99, 235, 0.11);
      border-color: #2f5597;
    }}
    body[data-theme="dark"] .swagger-ui .opblock.opblock-post {{
      background: rgba(16, 185, 129, 0.11);
      border-color: #1f6f54;
    }}
    body[data-theme="dark"] .swagger-ui .opblock.opblock-put {{
      background: rgba(245, 158, 11, 0.11);
      border-color: #855a19;
    }}
    body[data-theme="dark"] .swagger-ui .opblock.opblock-patch {{
      background: rgba(139, 92, 246, 0.11);
      border-color: #5b3a99;
    }}
    body[data-theme="dark"] .swagger-ui .opblock.opblock-delete {{
      background: rgba(239, 68, 68, 0.11);
      border-color: #883232;
    }}
    body[data-theme="dark"] .swagger-ui section.models {{
      background: #152136;
      border-color: var(--swg-border);
      border-radius: 12px;
    }}
    body[data-theme="dark"] .swagger-ui section.models h4 {{
      border-bottom-color: var(--swg-border);
    }}
    body[data-theme="dark"] .swagger-ui section.models .model-container,
    body[data-theme="dark"] .swagger-ui .model-box,
    body[data-theme="dark"] .swagger-ui .json-schema-2020-12-accordion,
    body[data-theme="dark"] .swagger-ui .json-schema-2020-12-body {{
      background: #182640;
      border-color: var(--swg-border);
      color: var(--swg-text);
    }}
    body[data-theme="dark"] .swagger-ui .json-schema-2020-12-expand-deep-button {{
      background: #243554;
      color: #dbeafe;
      border: 1px solid #3f5885;
      border-radius: 6px;
      padding: 2px 8px;
    }}
    body[data-theme="dark"] .swagger-ui .responses-table,
    body[data-theme="dark"] .swagger-ui .parameters-col_description input,
    body[data-theme="dark"] .swagger-ui select,
    body[data-theme="dark"] .swagger-ui input[type=text],
    body[data-theme="dark"] .swagger-ui input[type=search],
    body[data-theme="dark"] .swagger-ui textarea {{
      background: var(--swg-elevated);
      color: var(--swg-text);
      border-color: var(--swg-border);
    }}
    body[data-theme="dark"] .swagger-ui .btn {{
      background: #1d2d4a;
      color: #eef4ff;
      border-color: #3d547d;
    }}
    body[data-theme="dark"] .swagger-ui .btn:hover {{
      background: #283d63;
      border-color: #6085c2;
    }}
    body[data-theme="dark"] .swagger-ui .btn.execute {{
      background: #2563eb;
      border-color: #3b82f6;
      color: #ffffff;
    }}
    body[data-theme="dark"] .swagger-ui .download-contents,
    body[data-theme="dark"] .swagger-ui .highlight-code .copy-to-clipboard {{
      background: #263653;
      color: #f8fafc;
      border: 1px solid #445d87;
    }}
    body[data-theme="dark"] .swagger-ui .highlight-code .copy-to-clipboard button {{
      background-color: transparent;
    }}
    body[data-theme="dark"] .swagger-ui .expand-operation svg,
    body[data-theme="dark"] .swagger-ui .opblock-summary-control svg,
    body[data-theme="dark"] .swagger-ui section.models svg,
    body[data-theme="dark"] .swagger-ui .json-schema-2020-12 svg,
    body[data-theme="dark"] .swagger-ui .model-toggle {{
      fill: #cbd5e1;
      color: #cbd5e1;
    }}
    body[data-theme="dark"] .swagger-ui .highlight-code,
    body[data-theme="dark"] .swagger-ui .curl-command .copy-paste,
    body[data-theme="dark"] .swagger-ui .request-url pre,
    body[data-theme="dark"] .swagger-ui pre.microlight {{
      background: var(--swg-code-bg) !important;
      color: #e2e8f0 !important;
      border: 1px solid #263653;
      border-radius: 10px;
    }}
    body[data-theme="dark"] .swagger-ui .responses-header,
    body[data-theme="dark"] .swagger-ui .response-controls,
    body[data-theme="dark"] .swagger-ui .loading-container .loading {{
      color: var(--swg-text);
    }}
    body[data-theme="dark"] .swagger-ui .dialog-ux .modal-ux {{
      background: #131e33;
      border: 1px solid var(--swg-border);
      color: var(--swg-text);
    }}
    body[data-theme="dark"] .swagger-ui .dialog-ux .modal-ux-header {{
      border-bottom-color: var(--swg-border);
    }}
    body[data-theme="dark"] .swagger-ui .dialog-ux .modal-ux-header h3,
    body[data-theme="dark"] .swagger-ui .dialog-ux .modal-ux-content h4,
    body[data-theme="dark"] .swagger-ui .dialog-ux .modal-ux-content p {{
      color: var(--swg-text);
    }}
    @media (max-width: 720px) {{
      .swg-portal-header {{
        padding: 12px 14px;
      }}
      .swg-notice-strip,
      .swg-container {{
        padding: 0 14px;
      }}
    }}
  </style>
</head>
<body class="{body_class}">
  <header class="swg-portal-header">
    <div class="swg-header-inner">
      <div class="swg-brand">
        <span class="swg-badge">OPENAPI 3.1</span>
        <div>
          <h1>청주톡톡 민원 업무 백엔드 API · Swagger UI</h1>
          <p>Flask 업무 서버(:5000) · PostgreSQL complaint_app · 응대 검사기 /api/v1/assist</p>
        </div>
      </div>
      <div class="swg-tools">
        <span class="swg-pill" id="swg-health-pill" title="GET /api/v1/health 상태">
          <span class="swg-dot warn" id="swg-health-dot"></span>
          <span id="swg-health-text">서버 상태 확인 중…</span>
        </span>
        <span class="swg-pill" id="swg-session-pill" title="현재 시연 HttpOnly 세션 역할">
          세션: 확인 중…
        </span>
        <button type="button" class="swg-btn" data-session-role="staff">담당자 세션 연결</button>
        <button type="button" class="swg-btn" data-session-role="citizen">시민 세션 연결</button>
        <button type="button" class="swg-btn" id="swg-session-clear">세션 해제</button>
        <button type="button" class="swg-btn" id="swg-theme-toggle" aria-label="테마 전환">다크 모드</button>
      </div>
    </div>
    <div class="swg-nav-row">
      <nav class="swg-links" aria-label="프로젝트 이동 링크">
        <a class="swg-link primary" href="/#/staff/api">담당자 API 콘솔</a>
        <a class="swg-link" href="/#/staff">담당자 업무 화면</a>
        <a class="swg-link" href="/#/citizen">시민 화면</a>
        <a class="swg-link" href="/#/lab">응대 검사기 (#/lab)</a>
        <a class="swg-link" href="/openapi/openapi.json" target="_blank" rel="noopener">OpenAPI JSON</a>
        <a class="swg-link" href="http://127.0.0.1:8007/docs" data-rag-docs-link="1" target="_blank" rel="noopener">RAG 검색 Swagger (:8007)</a>
      </nav>
    </div>
  </header>

  <section class="swg-notice-strip" aria-label="API 경계 안내">
    <div class="swg-notice-box">
      <span>
        <strong>세션 인증 안내:</strong> 이 서버는 별도 토큰이 아닌 <code>HttpOnly</code> 시연 쿠키(<code>POST /api/v1/session</code>)를 사용합니다. 상단 버튼으로 담당자·시민 세션을 연결한 뒤 <strong>Try it out</strong>을 실행하세요.
      </span>
      <span>미게시 초안 시민 비공개 · 공식 행정 이관 미연동(<code>automaticTransfer=false</code>)</span>
    </div>
  </section>

  <main class="swg-container">
    <div class="swg-card">
      <div id="swagger-ui"></div>
    </div>
  </main>

  <script src="/openapi/swagger/js/swagger-ui-bundle.js"></script>
  <script src="/openapi/swagger/js/swagger-ui-standalone-preset.js"></script>
  <script>
    (function () {{
      const THEME_KEY = "minwon-ui-theme";
      const params = new URLSearchParams(window.location.search);
      if (params.get("embed") === "1") {{
        document.body.classList.remove("standalone-mode");
        document.body.classList.add("embed-mode");
      }}

      /**
       * 브라우저 localStorage에서 저장된 UI 테마를 읽습니다.
       *
       * @returns {{"light"|"dark"}} 저장된 테마 또는 기본 `"light"`입니다.
       */
      function readSavedTheme() {{
        try {{
          return localStorage.getItem(THEME_KEY) === "dark" ? "dark" : "light";
        }} catch (_err) {{
          return "light";
        }}
      }}

      /**
       * Swagger 페이지와 테마 전환 단추 상태를 지정한 테마로 갱신합니다.
       *
       * @param {{"light"|"dark"|string}} theme 적용할 테마 이름입니다.
       * @param {{boolean}} persist localStorage 저장 여부입니다.
       * @returns {{void}}
       */
      function applyTheme(theme, persist) {{
        const next = theme === "dark" ? "dark" : "light";
        document.body.dataset.theme = next;
        document.documentElement.style.colorScheme = next;
        const btn = document.getElementById("swg-theme-toggle");
        if (btn) {{
          btn.textContent = next === "dark" ? "라이트 모드" : "다크 모드";
          btn.setAttribute("aria-pressed", String(next === "dark"));
        }}
        if (persist) {{
          try {{
            localStorage.setItem(THEME_KEY, next);
          }} catch (_err) {{}}
        }}
      }}

      /**
       * 임베드 부모 창 테마, 저장소, URL 쿼리 순으로 초기 테마를 결정합니다.
       *
       * @returns {{"light"|"dark"}} 초기 적용할 테마입니다.
       */
      function resolveInitialTheme() {{
        // 탭 전환·다크 토글 직후 iframe이 로드될 때 부모 창의 현재 테마와 어긋나지 않도록 우선 참조합니다.
        if (window.parent !== window) {{
          try {{
            const parentTheme = window.parent.document.body?.dataset?.theme;
            if (parentTheme === "dark" || parentTheme === "light") {{
              return parentTheme;
            }}
          }} catch (_err) {{}}
        }}
        const saved = readSavedTheme();
        const themeParam = params.get("theme");
        if (window.parent === window && (themeParam === "dark" || themeParam === "light")) {{
          return themeParam;
        }}
        return saved;
      }}

      applyTheme(resolveInitialTheme(), false);

      document.getElementById("swg-theme-toggle")?.addEventListener("click", function () {{
        const next = document.body.dataset.theme === "dark" ? "light" : "dark";
        applyTheme(next, true);
      }});

      window.addEventListener("storage", function (event) {{
        if (event.key === THEME_KEY) {{
          applyTheme(event.newValue === "dark" ? "dark" : "light", false);
        }}
      }});

      window.addEventListener("message", function (event) {{
        if (event.origin !== window.location.origin) return;
        if (event.data && event.data.type === "minwon-theme") {{
          applyTheme(event.data.theme, false);
        }}
      }});

      document.querySelectorAll("[data-rag-docs-link]").forEach(function (anchor) {{
        const host = window.location.hostname || "127.0.0.1";
        anchor.href = window.location.protocol + "//" + host + ":8007/docs";
      }});

      /**
       * `/api/v1/health`와 `/api/v1/session`을 조회해 상단 상태 배지를 갱신합니다.
       *
       * @returns {{Promise<void>}} 상태 조회·렌더링 완료 프로미스입니다.
       */
      async function refreshStatus() {{
        const healthDot = document.getElementById("swg-health-dot");
        const healthText = document.getElementById("swg-health-text");
        const sessionPill = document.getElementById("swg-session-pill");
        const roleButtons = document.querySelectorAll("[data-session-role]");
        try {{
          const res = await fetch("/api/v1/health", {{ credentials: "same-origin" }});
          const data = await res.json();
          if (healthDot && healthText) {{
            healthDot.className = "swg-dot" + (res.ok ? "" : " off");
            const storageLabel =
              data.storage === "postgresql" || data.storage === "postgres"
                ? "PostgreSQL"
                : (data.storage || "-");
            const searchLabel = (data.assistSearch ?? data.assist_search)
              ? "검색 :8007 연결"
              : "검색 미연결";
            const llmLabel = (data.assistLlm ?? data.assist_llm)
              ? "LLM 준비"
              : "LLM 시뮬/미설정";
            healthText.textContent = "DB: " + storageLabel + " · " + searchLabel + " · " + llmLabel;
          }}
        }} catch (_err) {{
          if (healthDot && healthText) {{
            healthDot.className = "swg-dot off";
            healthText.textContent = "헬스 체크 실패";
          }}
        }}

        try {{
          const res = await fetch("/api/v1/session", {{ credentials: "same-origin" }});
          const actor = await res.json();
          const role = actor && actor.role ? actor.role : "none";
          const roleName = role === "staff" ? "담당자(staff)" : role === "citizen" ? "시민(citizen)" : "미연결";
          if (sessionPill) {{
            sessionPill.textContent = "세션: " + roleName;
          }}
          roleButtons.forEach(function (btn) {{
            btn.classList.toggle("active", btn.dataset.sessionRole === role);
          }});
        }} catch (_err) {{
          if (sessionPill) sessionPill.textContent = "세션: 확인 실패";
        }}
      }}

      /**
       * 시연 세션 쿠키를 설정하거나 해제한 뒤 상단 세션 배지를 즉시 갱신합니다.
       *
       * @param {{"POST"|"DELETE"}} method HTTP 요청 메서드입니다.
       * @param {{string}} [role] `POST` 시 설정할 시연 역할(`staff` 또는 `citizen`)입니다.
       * @returns {{Promise<void>}} 세션 변경 후 상태 갱신 완료 프로미스입니다.
       */
      async function updateSession(method, role) {{
        try {{
          await fetch("/api/v1/session", {{
            method: method,
            credentials: "same-origin",
            ...(role
              ? {{
                  headers: {{ "Content-Type": "application/json" }},
                  body: JSON.stringify({{ role: role }}),
                }}
              : {{}}),
          }});
        }} finally {{
          refreshStatus();
        }}
      }}

      document.querySelectorAll("[data-session-role]").forEach(function (btn) {{
        btn.addEventListener("click", function () {{
          updateSession("POST", btn.dataset.sessionRole);
        }});
      }});

      document.getElementById("swg-session-clear")?.addEventListener("click", function () {{
        updateSession("DELETE");
      }});

      /**
       * 빈 securitySchemes로 생성되는 무기능 Authorize 버튼을 제거하고,
       * 태그뿐 아니라 경로·메서드·요약·설명까지 통합 필터링하는 플러그인입니다.
       *
       * @returns {{object}} Swagger UI 플러그인 정의 객체입니다.
       */
      function CheongjuSwaggerPlugin() {{
        return {{
          statePlugins: {{
            spec: {{
              wrapActions: {{
                updateJsonSpec: function (oriAction) {{
                  return function (jsonSpec) {{
                    if (
                      jsonSpec &&
                      jsonSpec.components &&
                      jsonSpec.components.securitySchemes &&
                      Object.keys(jsonSpec.components.securitySchemes).length === 0
                    ) {{
                      const nextComponents = Object.assign({{}}, jsonSpec.components);
                      delete nextComponents.securitySchemes;
                      return oriAction(
                        Object.assign({{}}, jsonSpec, {{ components: nextComponents }})
                      );
                    }}
                    return oriAction(jsonSpec);
                  }};
                }},
              }},
            }},
          }},
          fn: {{
            opsFilter: function (taggedOps, phrase) {{
              const needle = String(phrase || "").trim().toLowerCase();
              if (!needle) return taggedOps;
              return taggedOps
                .map(function (tagObj, tagName) {{
                  if (String(tagName || "").toLowerCase().includes(needle)) {{
                    return tagObj;
                  }}
                  const ops = tagObj.get("operations");
                  if (!ops) return null;
                  const filtered = ops.filter(function (op) {{
                    const path = String(op.get("path") || "").toLowerCase();
                    const method = String(op.get("method") || "").toLowerCase();
                    const opObj = op.get("operation");
                    const summary = String((opObj && opObj.get("summary")) || "").toLowerCase();
                    const desc = String((opObj && opObj.get("description")) || "").toLowerCase();
                    return (
                      path.includes(needle) ||
                      method.includes(needle) ||
                      summary.includes(needle) ||
                      desc.includes(needle)
                    );
                  }});
                  return filtered.size ? tagObj.set("operations", filtered) : null;
                }})
                .filter(Boolean);
            }},
          }},
        }};
      }}

      window.ui = SwaggerUIBundle({{
        url: "/openapi/openapi.json",
        dom_id: "#swagger-ui",
        deepLinking: true,
        displayRequestDuration: true,
        filter: true,
        docExpansion: "list",
        defaultModelsExpandDepth: 1,
        presets: [SwaggerUIBundle.presets.apis, SwaggerUIStandalonePreset],
        plugins: [CheongjuSwaggerPlugin],
        layout: "BaseLayout",
        requestInterceptor: function (req) {{
          req.credentials = "same-origin";
          return req;
        }},
        onComplete: function () {{
          const filterInput = document.querySelector(".operation-filter-input");
          if (filterInput) {{
            filterInput.placeholder = "경로(/complaints), 메서드(POST), 태그, 기능 설명 통합 검색";
            filterInput.setAttribute("aria-label", "API 경로·메서드·태그·설명 통합 검색");
          }}
        }},
      }});

      if (!document.body.classList.contains("embed-mode")) {{
        refreshStatus();
      }}
    }})();
  </script>
</body>
</html>
"""
