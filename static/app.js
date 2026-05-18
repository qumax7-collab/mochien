/**
 * 모찌엔 웹 UI — 공통 유틸리티
 * 페이지별 로직은 각 HTML <script> 태그에 인라인으로 작성됨.
 * 이 파일에는 여러 페이지에서 공유되는 헬퍼만 포함.
 */

/** HTML 특수문자 이스케이프 */
function escHtml(s) {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

/** 퍼센트 문자열 파싱 (0~100 범위 보정) */
function clampPct(v) {
  return Math.max(0, Math.min(100, parseInt(v, 10) || 0));
}

/** 초 → MM:SS 형식 */
function fmtDuration(sec) {
  const m = Math.floor(sec / 60);
  const s = sec % 60;
  return `${m}:${String(s).padStart(2, "0")}`;
}

/** 단일 따옴표 이스케이프 (HTML 속성 인라인 onclick 등에서 사용) */
function escQ(s) {
  return String(s).replace(/'/g, "\\'");
}

/**
 * SSE 스트림 수신 공용 핸들러 팩토리.
 * @param {string}   url      SSE 엔드포인트
 * @param {Function} onEvent  {step, pct, msg, url?} 수신 콜백
 * @param {Function} onError  문자열 오류 콜백
 * @returns EventSource 인스턴스 (필요 시 .close() 가능)
 */
function createSSE(url, onEvent, onError) {
  const es = new EventSource(url);

  es.onmessage = (e) => {
    let d;
    try { d = JSON.parse(e.data); } catch { return; }

    if (d.step === "Error") {
      es.close();
      onError(d.msg || "알 수 없는 오류");
      return;
    }
    onEvent(d);
    if (d.step === "Done") {
      es.close();
    }
  };

  es.onerror = () => {
    es.close();
    onError("서버 연결이 끊겼습니다. 페이지를 새로고침하세요.");
  };

  return es;
}

/**
 * 진행 바 + 퍼센트 레이블 업데이트 헬퍼.
 * @param {string} barId     progress-bar-fg 요소 ID
 * @param {string} labelId   progress-pct 요소 ID
 * @param {number} pct       0~100
 */
function updateProgressBar(barId, labelId, pct) {
  const bar   = document.getElementById(barId);
  const label = document.getElementById(labelId);
  if (bar)   bar.style.width       = clampPct(pct) + "%";
  if (label) label.textContent     = clampPct(pct) + "%";
}

/**
 * 단계 리스트 항목 상태 업데이트 헬퍼.
 * @param {Array}  steps     [{key, label, icon}, ...]
 * @param {string} prefix    요소 ID 접두사 (예: "" 또는 "lf-")
 * @param {string} curStep   현재 step 키
 */
function updateStepStatuses(steps, prefix, curStep) {
  const curIdx = steps.findIndex(s => s.key === curStep);
  steps.forEach((s, i) => {
    const statusEl = document.getElementById(`${prefix}ss-${s.key}`);
    const itemEl   = document.getElementById(`${prefix}si-${s.key}`);
    if (!statusEl) return;

    if (i < curIdx) {
      statusEl.textContent = "완료 ✓";
      statusEl.className   = "step-status done";
    } else if (i === curIdx) {
      statusEl.textContent = "진행 중 ⏳";
      statusEl.className   = "step-status running";
      itemEl?.classList.add("active");
    } else {
      statusEl.textContent = "대기";
      statusEl.className   = "step-status";
    }
  });
}

/** 전역 에러 경계: 미처리 Promise rejection 알림 */
window.addEventListener("unhandledrejection", (e) => {
  console.error("[웹 UI] 처리되지 않은 오류:", e.reason);
});
