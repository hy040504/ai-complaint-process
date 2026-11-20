/*
 * ui04 목업 ↔ 서버 /api/v1 어댑터 (시연용)
 *
 * 목업(minwon-toktok-ui04.html)은 api(method, path, body, hdr) 한 함수로 데이터를 주고받습니다.
 * 이 파일은 그 함수를 window.ui04Bridge 로 가로채 실제 Flask 서버를 부르고,
 * 응답을 목업이 쓰는 모양({status, data})으로 바꿔 돌려줍니다.
 *
 * 한계 (서버에 없거나 모양이 다른 것):
 * - 시민 계정은 서버에서 하나(citizen-demo)로 합쳐집니다. 목업의 여러 시민 이름은 구분되지 않습니다.
 * - AI 결과(근거·추천 부서·채택)는 서버에 없습니다. AI 후보 문장은 작업 이벤트에만 보입니다.
 * - 철회 취소, 해결 확인(종료), 처리 상태 직접 변경, 공개 신청·승인, 초안 삭제는 서버에 없어 안내 메시지로 막습니다.
 * - 공개 신청(public_requested)은 서버에 없어 비공개로 저장합니다.
 * - 분류는 서버의 6개 값으로 줄어듭니다. 목업의 15개 분류는 가까운 값으로 바뀌어 저장됩니다.
 */
(function () {
  'use strict';

  var BASE = '/api/v1';
  var SESSION_KEY = 'mwtt.ui04.session1';
  var CAT_TO_SERVER = {
    '교통': '도로·교통', '도로': '도로·교통', '환경': '환경·청소',
    '복지교육': '생활·복지', '보건소': '생활·복지', '도시부동산': '주택·건축'
  };
  var CAT_FROM_SERVER = {
    '도로·교통': '교통', '환경·청소': '환경', '공원·녹지': '기타',
    '생활·복지': '복지교육', '주택·건축': '도시부동산', '기타': '기타'
  };
  var CITIZEN_ID = 'citizen-demo';
  var STAFF_ID = 'staff-demo';
  var serverRole = null;      // 서버 쿠키 세션의 현재 역할
  var cache = [];             // 마지막으로 받은 민원 목록 (헤더 집계용)

  /* ---------- 공통 ---------- */
  function me() {
    try { return JSON.parse(sessionStorage.getItem(SESSION_KEY) || 'null'); } catch (e) { return null; }
  }
  function fail(status, code, message, extra) {
    var d = { code: code, message: message };
    if (extra) Object.keys(extra).forEach(function (k) { d[k] = extra[k]; });
    return Promise.resolve({ status: status, data: d });
  }
  function unsupported(what) {
    return fail(409, 'unsupported', '서버 시연판에는 아직 "' + what + '" 기능이 없습니다.');
  }
  function srv(method, path, body, headers) {
    var opt = { method: method, headers: Object.assign({}, headers || {}), credentials: 'same-origin' };
    if (body !== undefined && body !== null) {
      opt.headers['Content-Type'] = 'application/json';
      opt.body = JSON.stringify(body);
    }
    return fetch(BASE + path, opt).then(function (r) {
      return r.text().then(function (t) {
        var d = null;
        try { d = t ? JSON.parse(t) : null; } catch (e) { d = null; }
        return { status: r.status, data: d };
      });
    });
  }
  function qs(o) {
    return Object.keys(o).filter(function (k) { return o[k] !== undefined && o[k] !== null && o[k] !== ''; })
      .map(function (k) { return encodeURIComponent(k) + '=' + encodeURIComponent(o[k]); }).join('&');
  }
  function parseQ(s) {
    var o = {};
    (s || '').split('&').forEach(function (kv) {
      if (!kv) return;
      var a = kv.split('=');
      o[decodeURIComponent(a[0])] = decodeURIComponent((a[1] || '').replace(/\+/g, ' '));
    });
    return o;
  }
  /* 서버 역할을 화면 역할과 맞춥니다. 탭 전환 등으로 어긋나면 다시 로그인합니다. */
  function ensureRole(role) {
    if (serverRole === role) return Promise.resolve();
    return srv('POST', '/session', { role: role }).then(function (r) {
      if (r.status === 200) serverRole = role;
    });
  }
  function fetchAll(path) {
    var sep = path.indexOf('?') >= 0 ? '&' : '?';
    var out = [];
    function step(page) {
      return srv('GET', path + sep + 'page=' + page + '&limit=100').then(function (r) {
        if (r.status !== 200) return Promise.reject(r);
        var items = r.data.complaints || [];
        out = out.concat(items);
        if (out.length >= (r.data.total || 0) || items.length === 0 || page >= 50) return out;
        return step(page + 1);
      });
    }
    return step(1).then(function (all) { cache = all; return all; });
  }
  function paged(list, q, mapFn) {
    var size = Math.min(50, parseInt(q.size, 10) || 10);
    var pages = Math.max(1, Math.ceil(list.length / size));
    var page = Math.min(pages, Math.max(1, parseInt(q.page, 10) || 1));
    return { status: 200, data: {
      items: list.slice((page - 1) * size, page * size).map(mapFn),
      total: list.length, page: page, pages: pages, size: size
    } };
  }

  /* ---------- 서버 모양 → 목업 모양 ---------- */
  function badgeOf(origin) {
    if (origin === 'ai') return 'rev';        // AI 초안을 담당자가 그대로 게시
    if (origin === 'ai_edited') return 'edit'; // AI 초안을 담당자가 고쳐 게시
    return 'staff';
  }
  function visOut(v) { return v === 'public' ? 'public_approved' : 'private'; }
  function visIn(v) { return v === 'public_approved' ? 'public' : 'private'; }
  function catOut(c) { return CAT_FROM_SERVER[c] || '기타'; }
  function catIn(c) { return CAT_TO_SERVER[c] || c || '기타'; }
  function jobsOf(c) {
    var j = c.job;
    if (!j || (j.status === 'queued' && (!j.events || j.events.length === 0))) return [];
    var events = (j.events || []).map(function (e) { return { at: e.date, text: e.stage }; });
    if (c.aiCandidate) events.push({ at: c.date, text: 'AI 후보 준비 (자동 적용 안 함): ' + c.aiCandidate });
    return [{
      id: c.id + '#job', attempt: j.attempt || 1, context_version: j.contextVersion || c.contextVersion,
      state: j.status, stage: j.stage || '', error: '', created_at: j.startedAt || c.date, events: events
    }];
  }
  function view(c, role) {
    var pub = c.published || null;
    var hasDraft = !!(c.draft && (!pub || c.draft !== pub.text));
    var jobs = role === 'staff' ? jobsOf(c) : [];
    var mine = role === 'citizen' && c.owner === CITIZEN_ID;
    var open = (c.status === 'submitted' || c.status === 'under_review') && !pub;
    return {
      id: c.id, public_code: c.id, title: c.title, body: c.body, category: catOut(c.category),
      district: c.district, visibility: visOut(c.visibility), status: c.status, version: c.version,
      context_version: c.contextVersion,
      author: { id: c.owner, name: c.owner === STAFF_ID ? '담당자' : '시민(시연)' },
      assignee: c.assigned ? { id: STAFF_ID, name: '담당자(시연)' } : null,
      is_synthetic: !!c.isSynthetic, created_at: c.date, updated_at: c.date,
      deleted_at: c.status === 'withdrawn' ? c.date : null,
      latest_answer: pub ? { badge: badgeOf(pub.origin), published_at: pub.date } : null,
      ai: { job: jobs[0] ? { id: jobs[0].id, state: jobs[0].state, stage: jobs[0].stage, error: '' } : null,
            outcome: null, department: '', has_draft: hasDraft },
      can_edit: mine && open, can_withdraw: mine && open, has_draft: hasDraft
    };
  }
  function answerOut(c) {
    var pub = c.published;
    return { id: c.id + '#pub', version_no: c.draftVersion || 1, body: pub.text, badge: badgeOf(pub.origin),
             published_at: pub.date, evidence: [] };
  }
  function versionState(v, c) {
    var pub = c.published;
    if (v.kind === '초안 저장') return (c.draft && v.text === c.draft && (!pub || c.draft !== pub.text)) ? 'draft' : 'retracted';
    if (v.kind === '게시') return (pub && v.text === pub.text) ? 'published' : 'retracted';
    return 'retracted';
  }
  function staffDetail(c) {
    var out = view(c, 'staff');
    var pub = c.published || null;
    var hasDraft = out.has_draft;
    out.published = pub ? { id: c.id + '#pub', version_no: c.draftVersion || 1, body: pub.text,
                            badge: badgeOf(pub.origin), published_at: pub.date, evidence: [] } : null;
    out.draft = hasDraft ? { id: c.id + '#draft', version_no: c.draftVersion || 1, body: c.draft, origin: 'staff',
                             edited_by: null, publish_state: 'draft', created_at: c.date, retract_reason: '',
                             context_version: c.contextVersion } : null;
    out.ai_original = c.aiOriginal ? { id: c.id + '#ai', body: c.aiOriginal, version_no: 0, evidence: [] } : null;
    out.versions = (c.versions || []).map(function (v, i) {
      return { id: c.id + '#v' + i, version_no: v.version, body: v.text, origin: 'staff', edited_by: null,
               badge_if_published: 'staff', publish_state: versionState(v, c), created_at: v.date,
               retract_reason: v.reason || '', context_version: c.contextVersion };
    });
    out.jobs = jobsOf(c);
    out.results = [];   // 서버에는 AI 결과 저장이 없습니다.
    out.inquiries = (c.messages || []).map(function (m, i) { return { id: c.id + '#m' + i, body: m.text, at: m.date }; });
    out.history = (c.history || []).map(function (h) { return { at: h.date, text: h.text }; });
    out.stale_draft = false;
    return out;
  }
  function citizenDetail(c) {
    var out = view(c, 'citizen');
    var mine = c.owner === CITIZEN_ID;
    out.answers = c.published ? [answerOut(c)] : [];
    out.inquiries = mine ? (c.messages || []).map(function (m, i) { return { id: c.id + '#m' + i, body: m.text, at: m.date }; }) : [];
    out.history = mine ? (c.history || []).map(function (h) { return { at: h.date, text: h.text }; }) : [];
    out.is_owner = mine;
    if (!mine) { out.can_edit = false; out.can_withdraw = false; out.ai = { job: null, outcome: null, department: '', has_draft: false }; }
    return out;
  }
  function todayCount(list, offset) {
    var d = new Date(); d.setDate(d.getDate() - offset);
    var key = d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0');
    return list.filter(function (c) {
      var t = new Date(c.date);
      return t.getFullYear() + '-' + String(t.getMonth() + 1).padStart(2, '0') + '-' + String(t.getDate()).padStart(2, '0') === key;
    }).length;
  }

  /* ---------- 라우트 ---------- */
  function getComplaint(cid) { return srv('GET', '/complaints/' + cid); }

  function listCitizen(ctx) {
    var q = ctx.q, scope = q.scope === 'public' ? 'public' : 'mine';
    var params = { limit: 100, q: q.q, district: q.district };
    if (scope === 'mine') { params.mine = 'true'; if (q.status) params.status = q.status; }
    return fetchAll('/complaints?' + qs(params)).then(function (all) {
      var list = all.filter(function (c) {
        if (scope === 'mine') return c.owner === CITIZEN_ID;
        return c.visibility === 'public' && c.owner !== CITIZEN_ID && !!c.published;
      });
      if (q.period) {
        var days = +q.period, now = Date.now();
        if (days) list = list.filter(function (c) { return now - Date.parse(c.date) <= days * 864e5; });
      }
      list.sort(function (a, b) { return q.sort === 'old' ? Date.parse(a.date) - Date.parse(b.date) : Date.parse(b.date) - Date.parse(a.date); });
      return paged(list, q, function (c) { return view(c, 'citizen'); });
    });
  }
  function createComplaint(ctx) {
    var b = ctx.b, key = ctx.h['Idempotency-Key'] || ('ui04-' + Date.now() + '-' + Math.random().toString(36).slice(2));
    var vis = b.visibility === 'public_requested' ? 'private' : (b.visibility === 'public_approved' ? 'public' : 'private');
    var body = { title: b.title, body: b.body, district: b.district || '모름', category: catIn(b.category), visibility: vis };
    return srv('POST', '/complaints', body, { 'Idempotency-Key': key }).then(function (r) {
      if (r.status === 201 || r.status === 200) {
        r.data = view(r.data, 'citizen');
        if (b.visibility === 'public_requested') r.data.notice = '공개 신청은 서버 시연판에 없어 비공개로 저장했습니다.';
      }
      return r;
    });
  }
  function getCitizenDetailRoute(ctx) {
    return getComplaint(ctx.m[1]).then(function (r) {
      if (r.status !== 200) return r;
      return { status: 200, data: citizenDetail(r.data) };
    });
  }
  function updateComplaint(ctx) {
    var b = ctx.b, cid = ctx.m[1];
    var body = { version: b.version, title: b.title, body: b.body, district: b.district || '모름',
                 category: catIn(b.category), visibility: b.visibility === 'public_approved' ? 'public' : 'private' };
    return srv('PUT', '/complaints/' + cid, body).then(function (r) {
      return r.status === 200 ? { status: 200, data: view(r.data, 'citizen') } : r;
    });
  }
  function withdraw(ctx) {
    var cid = ctx.m[1];
    return srv('DELETE', '/complaints/' + cid, { version: ctx.b.version, reason: '시민 철회' }).then(function (r) {
      return r.status === 200 ? { status: 200, data: view(r.data, 'citizen') } : r;
    });
  }
  function addMessage(ctx) {
    var cid = ctx.m[1];
    return srv('POST', '/complaints/' + cid + '/messages', { version: ctx.b.version, message: ctx.b.body || '' }).then(function (r) {
      return r.status === 200 ? { status: 201, data: view(r.data, 'citizen') } : r;
    });
  }
  function staffSummary() {
    return fetchAll('/complaints?limit=100').then(function (all) {
      var live = all.filter(function (c) { return c.status !== 'withdrawn'; });
      var n = { review: 0, running: 0, waiting: 0, failed: 0 };
      live.forEach(function (c) {
        var j = jobsOf(c)[0];
        if (c.status === 'submitted' || c.status === 'under_review') n.review++;
        if (j && (j.state === 'queued' || j.state === 'running')) n.running++;
        if (c.draft && (!c.published || c.draft !== c.published.text)) n.waiting++;
        if (j && j.state === 'failed') n.failed++;
      });
      return { status: 200, data: { review: n.review, running: n.running, waiting: n.waiting, failed: n.failed, total: live.length } };
    });
  }
  function staffList(ctx) {
    var q = ctx.q;
    var params = { limit: 100, q: q.q, status: q.status, district: q.district };
    return fetchAll('/complaints?' + qs(params)).then(function (all) {
      var list = all.filter(function (c) {
        if (q.assignee === 'me' && !c.assigned) return false;
        if (q.assignee === 'none' && c.assigned) return false;
        if (q.outcome === 'failed') return !!(c.job && c.job.status === 'failed');
        if (q.outcome) return false;   // 서버에는 AI 결과 분류가 없습니다.
        return true;
      });
      return paged(list, q, function (c) { return view(c, 'staff'); });
    });
  }
  function staffDetailRoute(ctx) {
    return getComplaint(ctx.m[1]).then(function (r) {
      return r.status === 200 ? { status: 200, data: staffDetail(r.data) } : r;
    });
  }
  function saveDraft(ctx) {
    var cid = ctx.m[1], b = ctx.b;
    return srv('PUT', '/complaints/' + cid + '/draft', { version: b.version, text: b.body || '', reason: '담당자 초안 저장' })
      .then(function (r) { return r.status === 200 ? { status: 201, data: { complaint_version: r.data.version } } : r; });
  }
  function publishVersion(ctx) {
    var vid = ctx.m[1], cid = vid.split('#')[0], kind = vid.split('#')[1];
    if (kind !== 'draft') return unsupported('이전 버전 다시 게시');
    return getComplaint(cid).then(function (g) {
      if (g.status !== 200) return g;
      return srv('POST', '/complaints/' + cid + '/publish', { version: ctx.b.version, text: g.data.draft, reason: '담당자 게시' })
        .then(function (r) { return r.status === 200 ? { status: 200, data: { badge: badgeOf(r.data.published.origin), complaint_version: r.data.version } } : r; });
    });
  }
  function retractVersion(ctx) {
    var vid = ctx.m[1], cid = vid.split('#')[0], kind = vid.split('#')[1];
    if (kind !== 'pub') return unsupported('이전 버전 철회');
    return srv('POST', '/complaints/' + cid + '/retract', { version: ctx.b.version, reason: ctx.b.reason || '' })
      .then(function (r) { return r.status === 200 ? { status: 200, data: { complaint_version: r.data.version } } : r; });
  }
  function assignee(ctx) {
    var cid = ctx.m[1];
    return srv('PUT', '/complaints/' + cid + '/assignment', { version: ctx.b.version, assigned: !!ctx.b.assignee_id })
      .then(function (r) { return r.status === 200 ? { status: 200, data: view(r.data, 'staff') } : r; });
  }
  function startJob(ctx) {
    var cid = ctx.m[1];
    return srv('POST', '/complaints/' + cid + '/jobs', { version: ctx.b.version })
      .then(function (r) { return r.status === 200 ? { status: 202, data: { job_id: cid + '#job', state: 'queued', complaint_version: r.data.version } } : r; });
  }
  function cancelJob(ctx) {
    var cid = ctx.m[1].split('#')[0];
    return getComplaint(cid).then(function (g) {
      if (g.status !== 200) return g;
      return srv('POST', '/complaints/' + cid + '/jobs/cancel', { version: g.data.version })
        .then(function (r) { return r.status === 200 ? { status: 200, data: { id: cid + '#job', state: 'cancelled' } } : r; });
    });
  }

  var ROUTES = [
    ['POST', /^\/session$/, function (ctx) {
      var role = ctx.b.role;
      return srv('POST', '/session', { role: role }).then(function (r) {
        if (r.status !== 200) return r;
        serverRole = role;
        var name = role === 'staff' ? '담당자(시연)' : ((ctx.b.name || '').trim() || '시민(시연)');
        return { status: 200, data: { role: role, uid: role === 'staff' ? STAFF_ID : CITIZEN_ID, name: name } };
      });
    }, 'any'],
    ['GET', /^\/me$/, function () {
      var s = me();
      return s ? { status: 200, data: { id: s.uid, role: s.role, name: s.name } } : fail(401, 'unauthorized', '로그인이 필요합니다.');
    }, 'any'],
    ['GET', /^\/complaints$/, listCitizen, 'citizen'],
    ['POST', /^\/complaints$/, createComplaint, 'citizen'],
    ['GET', /^\/complaints\/([^/]+)$/, getCitizenDetailRoute, 'citizen'],
    ['PATCH', /^\/complaints\/([^/]+)$/, updateComplaint, 'citizen'],
    ['DELETE', /^\/complaints\/([^/]+)$/, withdraw, 'citizen'],
    ['POST', /^\/complaints\/([^/]+)\/restore$/, function () { return unsupported('철회 취소'); }, 'citizen'],
    ['POST', /^\/complaints\/([^/]+)\/messages$/, addMessage, 'citizen'],
    ['POST', /^\/complaints\/([^/]+)\/confirm$/, function () { return unsupported('해결 확인(종료)'); }, 'citizen'],
    ['GET', /^\/staff\/summary$/, staffSummary, 'staff'],
    ['GET', /^\/staff\/complaints$/, staffList, 'staff'],
    ['GET', /^\/staff\/complaints\/([^/]+)$/, staffDetailRoute, 'staff'],
    ['POST', /^\/complaints\/([^/]+)\/drafts$/, saveDraft, 'staff'],
    ['DELETE', /^\/complaints\/([^/]+)\/drafts$/, function () { return unsupported('초안 삭제'); }, 'staff'],
    ['POST', /^\/ai-results\/([^/]+)\/adopt$/, function () { return unsupported('AI 후보 채택'); }, 'staff'],
    ['POST', /^\/versions\/([^/]+)\/publish$/, publishVersion, 'staff'],
    ['POST', /^\/versions\/([^/]+)\/retract$/, retractVersion, 'staff'],
    ['PATCH', /^\/complaints\/([^/]+)\/status$/, function () { return unsupported('처리 상태 직접 변경'); }, 'staff'],
    ['PATCH', /^\/complaints\/([^/]+)\/assignee$/, assignee, 'staff'],
    ['PATCH', /^\/complaints\/([^/]+)\/visibility$/, function () { return unsupported('공개 범위 승인'); }, 'staff'],
    ['POST', /^\/complaints\/([^/]+)\/ai-jobs$/, startJob, 'staff'],
    ['POST', /^\/ai-jobs\/([^/]+)\/cancel$/, cancelJob, 'staff']
  ];

  /* 목업의 api() 대신 호출됩니다. */
  window.ui04Bridge = function (method, path, body, hdr) {
    var parts = path.split('?');
    var p = parts[0], q = parseQ(parts[1] || '');
    var hit = null, m = null;
    for (var i = 0; i < ROUTES.length; i++) {
      if (ROUTES[i][0] !== method) continue;
      m = ROUTES[i][1].exec(p);
      if (m) { hit = ROUTES[i]; break; }
    }
    if (!hit) return fail(404, 'no_route', '없는 주소입니다: ' + method + ' ' + p);
    var session = me();
    var need = hit[3];
    if (need !== 'any' && need !== undefined) {
      if (!session) return fail(401, 'unauthorized', '로그인이 필요합니다.');
      if (session.role !== need) return fail(403, 'forbidden', '이 기능을 쓸 권한이 없습니다.');
    }
    var ctx = { m: m, q: q, b: body || {}, h: hdr || {} };
    var role = session ? session.role : null;
    var ready = (need === 'any' || !role) ? Promise.resolve() : ensureRole(role);
    return ready.then(function () { return hit[2](ctx); }).catch(function (e) {
      if (e && typeof e.status === 'number') return e;
      return { status: 500, data: { code: 'adapter_error', message: String((e && e.message) || e) } };
    });
  };

  /* 헤더 집계: 마지막으로 받은 목록 기준 (목업의 로컬 저장소 대신) */
  window.ui04Stats = function () {
    return { a: todayCount(cache, 0), b: todayCount(cache, 1) };
  };
})();
