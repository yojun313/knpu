/* 분석 방법별 "현출(presentation)" 레지스트리 — 백엔드 MethodPlugin 의 프런트 짝.
 *
 * 실시간 콘솔 섹션 그리드(console.js)와 응답자 결과 공개 패널(respond.js)이
 * 쌍대비교 전제를 하드코딩하지 않도록, kind 별 뷰 객체를 여기 한곳에 모은다.
 * 새 방법(TOPSIS·엔트로피·직접평정 …)을 추가할 때 = 여기 객체 하나 등록.
 *
 * 계약 — 각 뷰 객체:
 *   consoleColumns(group, nameOf)          -> [{ key, label(HTML,이스케이프됨) }]
 *   consoleCells(group, answers, nameOf, ctx) -> [{ html:'<td>…</td>' }]   (columns 와 정렬)
 *       ctx = { respondentId, outlierSet }   outlierSet[itemKey+'|'+rid] === true
 *   consoleSave(group, selectEl)           -> PUT /api/entry/{cid}/answers 의 body 조각
 *                                            ({group_id, kind, …}) 또는 null(저장 안 함)
 *   worstHtml(items, nameOf)               -> #sectionWorstPairs 내부 HTML
 *   revealRows(weights, nameOf)            -> [{ name, pct }]  (가중치 내림차순)
 *
 * 레지스트리는 fetch/DOM 조회를 하지 않는다. 호스트가 nameOf(uuid)->표시명 을 준다.
 */
(function () {
  'use strict';

  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }
  function pid(a, b) { return [a, b].sort().join(':'); }

  function weightRows(weights, nameOf) {
    return Object.keys(weights || {})
      .sort(function (a, b) { return weights[b] - weights[a]; })
      .map(function (u) {
        return { name: nameOf(u), pct: (weights[u] * 100).toFixed(1) };
      });
  }

  // ── 쌍대비교 (AHP) ────────────────────────────────────────────────────
  function pairsOf(group) {
    const k = group.child_uuids || [];
    const out = [];
    for (let i = 0; i < k.length; i++) {
      for (let j = i + 1; j < k.length; j++) out.push([k[i], k[j]]);
    }
    return out;
  }
  function pairwiseScaleOptions(nameA, nameB, cur) {
    const opts = [];
    for (let n = 9; n >= 2; n--) opts.push({ v: n, label: nameA + '가(이) ' + n + '배 더 중요' });
    opts.push({ v: 1, label: '동일하게 중요' });
    for (let n = 2; n <= 9; n++) opts.push({ v: 1 / n, label: nameB + '가(이) ' + n + '배 더 중요' });
    return opts.map(function (o) {
      const on = cur != null && Math.abs(o.v - cur) < 1e-6 ? ' selected' : '';
      return '<option value="' + o.v + '"' + on + '>' + esc(o.label) + '</option>';
    }).join('');
  }
  function pairwiseCurrent(a, b, answers) {
    const s = [a, b].slice().sort();
    const k = s.join(':');
    if (!answers || !(k in answers)) return null;
    const v = answers[k];
    return a === s[0] ? v : 1 / v;
  }

  const pairwise = {
    kind: 'pairwise',
    consoleColumns: function (group, nameOf) {
      return pairsOf(group).map(function (p) {
        return { key: pid(p[0], p[1]), label: esc(nameOf(p[0])) + ' vs ' + esc(nameOf(p[1])) };
      });
    },
    consoleCells: function (group, answers, nameOf, ctx) {
      const rid = ctx.respondentId;
      const outlierSet = ctx.outlierSet || {};
      return pairsOf(group).map(function (p) {
        const key = pid(p[0], p[1]);
        const cur = pairwiseCurrent(p[0], p[1], answers);
        const cls = outlierSet[key + '|' + rid] ? 'section-outlier' : '';
        return {
          html: '<td class="' + cls + '"><select data-rid="' + rid +
            '" data-mv-kind="pairwise" data-a="' + p[0] + '" data-b="' + p[1] + '">' +
            '<option value="">(미응답)</option>' +
            pairwiseScaleOptions(nameOf(p[0]), nameOf(p[1]), cur) + '</select></td>',
        };
      });
    },
    consoleSave: function (group, el) {
      if (el.value === '') return null;
      return {
        group_id: group.group_id, kind: 'pairwise',
        uuid_a: el.dataset.a, uuid_b: el.dataset.b, value: Number(el.value),
      };
    },
    worstHtml: function (items, nameOf) {
      return (items || []).map(function (w) {
        const given = w.given_label || (w.given_value != null ? w.given_value.toFixed(2) : '');
        const sug = w.suggested_label || (w.suggested_value != null ? w.suggested_value.toFixed(2) : '');
        return '<div class="warn-item">⚠ ' + esc(nameOf(w.uuid_a)) + ' vs ' + esc(nameOf(w.uuid_b)) +
          ' — 응답값 ' + esc(given) + ', 그룹 관점 권장값 ' + esc(sug) + '</div>';
      }).join('');
    },
    revealRows: weightRows,
  };

  // ── BWM ──────────────────────────────────────────────────────────────
  function bwmScaleOptions(cur) {
    let h = '<option value="">–</option>';
    for (let n = 1; n <= 9; n++) {
      h += '<option value="' + n + '"' + (Number(cur) === n ? ' selected' : '') + '>' + n + '</option>';
    }
    return h;
  }
  function bwmChildOptions(kids, nameOf, selected, exclude) {
    return '<option value="">–</option>' + kids.filter(function (u) { return u !== exclude; })
      .map(function (u) {
        return '<option value="' + u + '"' + (selected === u ? ' selected' : '') + '>' +
          esc(nameOf(u)) + '</option>';
      }).join('');
  }

  const bwm = {
    kind: 'bwm',
    consoleColumns: function (group, nameOf) {
      const kids = group.child_uuids || [];
      const cols = [{ key: 'best', label: 'Best' }, { key: 'worst', label: 'Worst' }];
      kids.forEach(function (u) { cols.push({ key: 'BO:' + u, label: 'B↔' + esc(nameOf(u)) }); });
      kids.forEach(function (u) { cols.push({ key: 'OW:' + u, label: esc(nameOf(u)) + '↔W' }); });
      return cols;
    },
    consoleCells: function (group, answers, nameOf, ctx) {
      const rid = ctx.respondentId;
      const kids = group.child_uuids || [];
      const a = answers || {};
      const best = a.best || '', worst = a.worst || '';
      const cells = [];
      cells.push({
        html: '<td><select data-rid="' + rid + '" data-mv-kind="bwm" data-mv-role="pick_best">' +
          bwmChildOptions(kids, nameOf, best, worst) + '</select></td>',
      });
      cells.push({
        html: '<td><select data-rid="' + rid + '" data-mv-kind="bwm" data-mv-role="pick_worst">' +
          bwmChildOptions(kids, nameOf, worst, best) + '</select></td>',
      });
      kids.forEach(function (u) {
        const na = u === best ? ' disabled' : '';
        cells.push({
          html: '<td><select data-rid="' + rid + '" data-mv-kind="bwm" data-mv-role="vector" ' +
            'data-item="BO:' + u + '"' + na + '>' + bwmScaleOptions(a['BO:' + u]) + '</select></td>',
        });
      });
      kids.forEach(function (u) {
        const na = u === worst ? ' disabled' : '';
        cells.push({
          html: '<td><select data-rid="' + rid + '" data-mv-kind="bwm" data-mv-role="vector" ' +
            'data-item="OW:' + u + '"' + na + '>' + bwmScaleOptions(a['OW:' + u]) + '</select></td>',
        });
      });
      return cells;
    },
    consoleSave: function (group, el) {
      if (el.value === '') return null;
      const role = el.dataset.mvRole;
      if (role === 'pick_best') return { group_id: group.group_id, kind: 'pick_best', value: el.value };
      if (role === 'pick_worst') return { group_id: group.group_id, kind: 'pick_worst', value: el.value };
      return { group_id: group.group_id, kind: 'vector', item_id: el.dataset.item, value: Number(el.value) };
    },
    // BWM 의 재고 지점은 결과 화면(CR^I·OR 분포)에서 본다 — 콘솔 하단엔 안 띄운다.
    worstHtml: function () { return ''; },
    revealRows: weightRows,
  };

  const REG = { pairwise: pairwise, bwm: bwm };
  window.MCDMViews = {
    pairwise: pairwise,
    bwm: bwm,
    esc: esc,
    for: function (kind) { return REG[kind] || pairwise; },
  };
})();
