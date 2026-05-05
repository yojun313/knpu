// ===============================
// 공통 폼 저장 / 복원
// ===============================

function initFormStorage(formKey) {
  if (!formKey) return;

  function saveForm() {
    const data = {};
    document.querySelectorAll("input, textarea, select").forEach((el) => {
      if (el.name) {
        data[el.name] = el.value;
      }
    });
    localStorage.setItem(formKey, JSON.stringify(data));
  }

  function loadForm() {
    const saved = localStorage.getItem(formKey);
    if (!saved) return;

    const data = JSON.parse(saved);
    document.querySelectorAll("input, textarea, select").forEach((el) => {
      if (el.name && data[el.name] !== undefined) {
        el.value = data[el.name];
      }
    });
  }

  window.addEventListener("load", loadForm);
  document.addEventListener("input", saveForm);
}

// ===============================
// 경찰서 선택 (경찰청 → 경찰서)
// ===============================

function initPoliceSelector({
  sidoSelectId = "police_sido",
  stationSelectId = "제출 경찰서",
  apiUrl = "https://complaint-api.knpu.re.kr/api/police/stations",
} = {}) {
  let policeData = {};

  fetch(apiUrl)
    .then((res) => res.json())
    .then((data) => {
      policeData = data;

      const sidoSelect = document.getElementById(sidoSelectId);
      if (!sidoSelect) return;

      Object.keys(data).forEach((sido) => {
        const option = document.createElement("option");
        option.value = sido;
        option.textContent = sido;
        sidoSelect.appendChild(option);
      });
    })
    .catch((err) => {
      console.error("경찰서 목록 로딩 실패:", err);
    });

  document
    .getElementById(sidoSelectId)
    ?.addEventListener("change", function () {
      const stationSelect = document.getElementById(stationSelectId);
      const selectedSido = this.value;

      if (!stationSelect) return;

      stationSelect.innerHTML = `<option value="" disabled selected>경찰서 선택</option>`;

      if (!policeData[selectedSido]) return;

      policeData[selectedSido].forEach((station) => {
        const option = document.createElement("option");
        option.value = station.name;
        option.textContent = station.name;
        stationSelect.appendChild(option);
      });
    });
}

function printTransferInfo() {
  const holder = document.getElementById('account_holder').value;
  const bank = document.getElementById('bank_name').value;
  const account = document.getElementById('account_number').value;

  if (holder && bank && account) {
      const result = `${holder}명의의 ${bank} 계좌번호 ${account}으로 이체하여 교부하였다.`;
      document.getElementById('result_display').innerText = result;
  } else {
      alert("모든 항목을 입력해주세요.");
  }
}
