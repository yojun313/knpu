(function () {
  'use strict';

  // 9~1~1/9 전 구간(17칸) — entry.js의 scaleOptionsHtml과 같은 눈금으로 맞춘다.
  const SAATY_LEVELS = [9, 8, 7, 6, 5, 4, 3, 2, 1, 2, 3, 4, 5, 6, 7, 8, 9];
  function levelLabel(n, i) { return i <= SAATY_LEVELS.length / 2 ? String(n) : ('1/' + n); }

  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }

  function render(data) {
    const survey = data.survey;
    const nodes = data.nodes;
    const parts = [];

    parts.push('<div class="sv-title">' + esc(survey.title) + '</div>');
    if (survey.intro_text) parts.push('<div class="sv-intro">' + esc(survey.intro_text) + '</div>');
    if (survey.consent_text) parts.push('<div class="sv-consent">' + esc(survey.consent_text) + '</div>');
    parts.push('<div class="sv-meta">응답자: ______________________&nbsp;&nbsp;&nbsp; 소속/경력: ______________________&nbsp;&nbsp;&nbsp; 일자: ______________________</div>');

    survey.matrices.forEach(function (m) {
      const parentName = (nodes[m.parent_uuid] || {}).name || '';
      const parentDesc = survey.node_descriptions[m.parent_uuid] || '';
      let block = '<div class="matrix-block"><h2>\'' + esc(parentName) + '\' 측면 비교</h2>';
      if (parentDesc) block += '<div class="mb-desc">' + esc(parentDesc) + '</div>';
      block += '<div class="mb-q">' + esc(m.question_text) + '</div>';

      const children = m.child_uuids;
      for (let i = 0; i < children.length; i++) {
        for (let j = i + 1; j < children.length; j++) {
          const nameA = (nodes[children[i]] || {}).name || children[i];
          const nameB = (nodes[children[j]] || {}).name || children[j];
          block += '<table class="pair-table"><thead><tr><th>' + esc(nameA) + '</th>' +
            SAATY_LEVELS.map(function (n, i) { return '<th>' + levelLabel(n, i) + '</th>'; }).join('') +
            '<th>' + esc(nameB) + '</th></tr></thead><tbody><tr><td></td>' +
            SAATY_LEVELS.map(function () { return '<td class="mark-cell"></td>'; }).join('') +
            '<td></td></tr></tbody></table>';
        }
      }
      block += '</div>';
      parts.push(block);
    });

    document.getElementById('sheet').innerHTML = parts.join('');
  }

  async function init() {
    const surveyId = window.AHP_SURVEY_ID;
    try {
      const res = await fetch('/api/surveys/' + surveyId + '/print-data', { credentials: 'include' });
      if (!res.ok) throw new Error('load failed');
      const data = await res.json();
      render(data);
    } catch (e) {
      document.getElementById('sheet').innerHTML = '<p>설문지를 불러오지 못했습니다.</p>';
    }
    document.getElementById('printBtn').addEventListener('click', function () { window.print(); });
  }

  init();
})();
