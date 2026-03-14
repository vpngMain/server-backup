/** Vaping směnovač */
(function () {
  const API = "/api";
  let isAdmin = false;  // výchozí false – až /me potvrdí role

  window.toast = function (msg, type = "default") {
    const container = document.getElementById("toast-container");
    if (!container) return;
    const el = document.createElement("div");
    el.className = "toast " + (type === "success" ? "success" : type === "error" ? "error" : "");
    const icon = type === "success" ? "✓" : type === "error" ? "✕" : "•";
    el.innerHTML = `<span class="toast-icon">${icon}</span><span>${String(msg).replace(/</g, "&lt;")}</span>`;
    container.appendChild(el);
    const remove = () => {
      el.classList.add("leaving");
      setTimeout(() => el.remove(), 300);
    };
    setTimeout(remove, type === "error" ? 5000 : 3500);
  };

  function closeSidebar() {
    document.getElementById("sidebar")?.classList.remove("open");
    document.getElementById("sidebar-overlay")?.classList.remove("visible");
    document.body.classList.remove("sidebar-open");
  }
  function openSidebar() {
    document.getElementById("sidebar")?.classList.add("open");
    document.getElementById("sidebar-overlay")?.classList.add("visible");
    document.body.classList.add("sidebar-open");
  }
  document.getElementById("sidebar-toggle")?.addEventListener("click", () => {
    const sidebar = document.getElementById("sidebar");
    const isOpen = sidebar?.classList.toggle("open");
    document.getElementById("sidebar-overlay")?.classList.toggle("visible", isOpen);
    document.body.classList.toggle("sidebar-open", isOpen);
  });
  document.getElementById("sidebar-overlay")?.addEventListener("click", closeSidebar);

  let isFullAdmin = false;
  let isAccountant = false;  // účetní: isAdmin ale ne isFullAdmin
  function applyRole(me) {
    isAdmin = !!me?.isAdmin;
    isFullAdmin = !!me?.isFullAdmin;
    isAccountant = isAdmin && !isFullAdmin;
    document.body.classList.add("role-loaded");
    document.querySelectorAll("[data-admin-only]").forEach((el) => {
      el.style.display = isAdmin ? "" : "none";
    });
    document.querySelectorAll("[data-full-admin-only]").forEach((el) => {
      el.style.display = isFullAdmin ? "" : "none";
    });
    document.querySelectorAll("[data-employee-only]").forEach((el) => {
      el.style.display = isAdmin ? "none" : "";
    });
    document.querySelectorAll("[data-accountant-hide]").forEach((el) => {
      if (isAdmin) el.style.display = isAccountant ? "none" : "";
    });
    document.querySelectorAll("[data-accountant-only]").forEach((el) => {
      el.style.display = isAccountant ? "" : "none";
    });
  }

  function parseJsonResponse(r) {
    return r.text().then((text) => {
      try {
        return text ? JSON.parse(text) : {};
      } catch {
        return { error: "SERVER_ERROR", message: "Odpověď serveru nebyla ve formátu JSON. Zkuste to znovu nebo kontaktujte správce." };
      }
    });
  }
  function get(path, opts = {}) {
    return fetch(API + path, { credentials: "include", cache: "no-store", ...opts }).then((r) => {
      return parseJsonResponse(r).then((data) => {
        if (!r.ok) return Promise.reject({ ...data, _status: r.status });
        return data;
      });
    });
  }
  function post(path, data) {
    return fetch(API + path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify(data),
    }).then((r) => parseJsonResponse(r).then((body) => (r.ok ? body : Promise.reject({ ...body, _status: r.status }))));
  }
  function patch(path, data) {
    return fetch(API + path, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify(data),
    }).then((r) => parseJsonResponse(r).then((body) => (r.ok ? body : Promise.reject({ ...body, _status: r.status }))));
  }
  function del(path) {
    return fetch(API + path, { method: "DELETE", credentials: "include" });
  }

  function fmtDate(d) {
    return d.toISOString().slice(0, 10);
  }
  function fmtDateDisplay(dateStr) {
    if (!dateStr) return "";
    const [y, m, d] = String(dateStr).split("-");
    return `${d}. ${m}. ${y}`;
  }
  function startOfWeek(d) {
    const day = d.getDay();
    const diff = d.getDate() - day + (day === 0 ? -6 : 1);
    return new Date(d.setDate(diff));
  }
  function addDays(d, n) {
    const x = new Date(d);
    x.setDate(x.getDate() + n);
    return x;
  }
  function startOfMonth(d) {
    const x = new Date(d);
    x.setDate(1);
    return x;
  }
  function endOfMonth(d) {
    const x = new Date(d);
    x.setMonth(x.getMonth() + 1);
    x.setDate(0);
    return x;
  }

  function initTimePickers() {
    const hours = Array.from({ length: 24 }, (_, i) => `<option value="${String(i).padStart(2, "0")}">${String(i).padStart(2, "0")}</option>`).join("");
    const mins = ["00", "15", "30", "45"].map((m) => `<option value="${m}">${m}</option>`).join("");
    document.querySelectorAll("select.time-h").forEach((sel) => { sel.innerHTML = hours; });
    document.querySelectorAll("select.time-m").forEach((sel) => { sel.innerHTML = mins; });
  }
  function getTimeFromSelects(baseId) {
    const h = document.getElementById(baseId + "-h")?.value ?? "08";
    const m = document.getElementById(baseId + "-m")?.value ?? "00";
    return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}`;
  }
  function setTimeToSelects(baseId, timeStr) {
    if (!timeStr) return;
    const [h, m] = String(timeStr).split(":");
    const hSel = document.getElementById(baseId + "-h");
    const mSel = document.getElementById(baseId + "-m");
    if (hSel && h) hSel.value = String(parseInt(h, 10)).padStart(2, "0");
    if (mSel && m) {
      const mv = parseInt(m, 10);
      const rounded = [0, 15, 30, 45].reduce((a, b) => (Math.abs(mv - a) < Math.abs(mv - b) ? a : b));
      mSel.value = String(rounded).padStart(2, "0");
    }
  }
  function setShiftMobileTime(startTime, endTime) {
    const s = document.getElementById("shift-start-time");
    const e = document.getElementById("shift-end-time");
    if (s) s.value = (startTime || "08:00").substring(0, 5);
    if (e) e.value = (endTime || "14:00").substring(0, 5);
  }
  function getShiftTimeFromForm() {
    const isMobile = typeof window !== "undefined" && window.innerWidth <= 768;
    const startEl = document.getElementById("shift-start-time");
    const endEl = document.getElementById("shift-end-time");
    if (isMobile && startEl && endEl && startEl.value && endEl.value) {
      return { startTime: startEl.value.substring(0, 5), endTime: endEl.value.substring(0, 5) };
    }
    return { startTime: getTimeFromSelects("shift-start"), endTime: getTimeFromSelects("shift-end") };
  }

  // State
  let branches = [];
  let employees = [];
  let presets = [];

  // Navigation
  const main = document.querySelector(".main");
  function canAccessView(viewEl) {
    if (!viewEl) return false;
    if (viewEl.hasAttribute("data-admin-only") && !isAdmin) return false;
    if (viewEl.hasAttribute("data-full-admin-only") && !isFullAdmin) return false;
    return true;
  }

  document.querySelectorAll("[data-view]").forEach((el) => {
    el.addEventListener("click", (e) => {
      e.preventDefault();
      const view = el.dataset.view;
      const viewEl = document.getElementById("view-" + view.replace("-", "-"));
      if (!canAccessView(viewEl)) return;
      closeSidebar();
      main?.classList.add("view-transition");
      requestAnimationFrame(() => {
        setTimeout(() => {
          document.querySelectorAll(".view").forEach((v) => v.classList.remove("active"));
          document.querySelectorAll(".nav-item").forEach((n) => n.classList.remove("active"));
          if (viewEl) viewEl.classList.add("active");
          document.querySelector(`[data-view="${view}"]`)?.classList.add("active");
          if (view === "prehled") { isAdmin ? loadOverview() : loadPrehledEmployee(); }
      if (view === "kalendar") {
        const ce = document.getElementById("cal-branch");
        if (ce && isAdmin && branches.length > 0) { ce.style.display = ""; ce.value = ce.value || branches[0].id; }
        else if (ce && !isAdmin) ce.style.display = "none";
        renderCalendar();
      }
      if (view === "zadosti") { loadRequests(); }
      if (view === "pobocky") loadBranches();
      if (view === "ucetni") loadAccountantForm();
      if (view === "zamestnanci") {
        if (!branches.length) loadBranches().then(() => loadEmployees()); else loadEmployees();
      }
      if (view === "presety") loadPresets();
      if (view === "hodiny") loadHours();
      if (view === "kdo-s-kym") loadWho();
      if (view === "exporty") initExport();
          main?.classList.remove("view-transition");
          main?.classList.add("done");
          requestAnimationFrame(() => main?.classList.remove("done"));
        }, 50);
      });
    });
  });

  function loadLateOverview() {
    const from = document.getElementById("late-from")?.value;
    const to = document.getElementById("late-to")?.value;
    if (!from || !to) return;
    get(`/stats/late-overview?from=${from}&to=${to}`).then((data) => {
      const el = document.getElementById("overview-late");
      if (!el) return;
      const list = data.byEmployee || [];
      if (list.length === 0) {
        el.innerHTML = '<p class="empty">V období nejsou žádná zpoždění nad tolerancí.</p>';
        return;
      }
      el.innerHTML = '<table><thead><tr><th>Zaměstnanec</th><th style="text-align:right">Počet zpoždění</th><th>Poslední události</th></tr></thead><tbody>' +
        list.map((emp) => {
          const inc = (emp.incidents || []).slice(0, 5).map((i) => `${fmtDateDisplay(i.date)} +${i.minutesLate} min`).join(", ");
          return `<tr><td>${esc(emp.employee?.name || "")}</td><td style="text-align:right;font-weight:600;color:var(--rose)">${emp.lateCount}</td><td class="text-muted" style="font-size:0.8125rem">${esc(inc) || "—"}</td></tr>`;
        }).join("") + "</tbody></table>";
    });
  }
  document.getElementById("btn-load-late")?.addEventListener("click", loadLateOverview);

  function getCoverageMonth() {
    const el = document.getElementById("coverage-month");
    if (el?.value) return el.value;
    const n = new Date();
    return n.getFullYear() + "-" + String(n.getMonth() + 1).padStart(2, "0");
  }

  const MONTH_NAMES = ["leden", "únor", "březen", "duben", "květen", "červen", "červenec", "srpen", "září", "říjen", "listopad", "prosinec"];

  let coverageAbort = null;
  function loadCoverageGrid() {
    if (!isAdmin) return;
    const wrap = document.getElementById("coverage-grid-wrap");
    if (!wrap) return;
    const month = getCoverageMonth();
    if (!/^\d{4}-\d{2}$/.test(month)) return;
    const titleEl = document.getElementById("coverage-month-title");
    if (titleEl) {
      const [y, m] = month.split("-").map(Number);
      titleEl.textContent = (MONTH_NAMES[(m || 1) - 1] || "") + " " + (y || "");
    }
    wrap.innerHTML = '<p class="text-muted" style="padding:1.5rem;text-align:center">Načítám…</p>';
    if (coverageAbort) coverageAbort.abort();
    coverageAbort = new AbortController();
    const opts = { signal: coverageAbort.signal };
    fetch(API + "/coverage/auto?month=" + encodeURIComponent(month) + "&_=" + Date.now(), { credentials: "include", cache: "no-store", ...opts })
      .then((r) => {
        if (!r.ok) return r.json().catch(() => ({ error: "Chyba " + r.status })).then((e) => Promise.reject(e));
        return r.json();
      })
      .then((data) => {
        coverageAbort = null;
        const dates = data.dates || [];
        const grid = data.grid || [];
        if (grid.length === 0 && dates.length === 0) {
          wrap.innerHTML = '<p class="empty" style="padding:2rem">Žádné pobočky.</p>';
          return;
        }
        const dayHead = dates.map((d) => {
          const m = d.match(/^(\d{4})-(\d{2})-(\d{2})$/);
          const day = m ? m[3] : d.slice(-2);
          return `<th class="coverage-day" title="${esc(d)}">${esc(day)}</th>`;
        }).join("");
        const rows = grid.map((row) => {
          const cells = dates.map((date) => {
            const cov = row.days?.[date] || {};
            const ok = cov.covered;
            const shiftsStr = (cov.shifts || []).map((s) => `${s.employeeName} ${s.startTime}–${s.endTime}`).join("; ");
            const gaps = (cov.gaps || []).map((g) => g.from + "–" + g.to).join(", ");
            let title = cov.openTime && cov.closeTime ? `Otevírací doba ${cov.openTime}–${cov.closeTime}. ` : "";
            if (shiftsStr) title += `Směny: ${shiftsStr}. `;
            title += ok ? "Pokryto." : `Mezery: ${gaps || "celý den"}`;
            const cls = ok ? "coverage-ok" : "coverage-gap";
            return `<td class="coverage-cell ${cls}" title="${esc(title)}">${ok ? "✓" : "⚠"}</td>`;
          }).join("");
          return `<tr><th class="coverage-branch">${esc(row.branchName)}</th>${cells}</tr>`;
        }).join("");
        wrap.innerHTML = `
        <div class="coverage-legend mb-2" style="display:flex;gap:1rem;font-size:0.75rem;color:var(--gray-600)">
          <span><span class="coverage-legend-dot coverage-ok"></span> Pokryto</span>
          <span><span class="coverage-legend-dot coverage-gap"></span> Mezery</span>
        </div>
        <div class="coverage-table-scroll">
          <table class="coverage-table">
            <thead><tr><th>Pobočka</th>${dayHead}</tr></thead>
            <tbody>${rows}</tbody>
          </table>
        </div>
      `;
      })
      .catch((e) => {
        if (e?.name === "AbortError") return;
        coverageAbort = null;
        const errMsg = e?.error || e?.message || "Chyba načtení";
        wrap.innerHTML = '<p class="text-muted" style="padding:1.5rem;color:var(--rose)">' + esc(errMsg) + '</p><button type="button" class="btn btn-sm btn-secondary" id="coverage-retry-btn">Zkusit znovu</button>';
        wrap.querySelector("#coverage-retry-btn")?.addEventListener("click", loadCoverageGrid);
      });
  }

  document.getElementById("btn-load-coverage")?.addEventListener("click", loadCoverageGrid);
  document.getElementById("coverage-month")?.addEventListener("change", loadCoverageGrid);
  const coverageMonthEl = document.getElementById("coverage-month");
  if (coverageMonthEl && !coverageMonthEl.value) coverageMonthEl.value = getCoverageMonth();


  function getGreeting() {
    const h = new Date().getHours();
    if (h >= 5 && h < 11) return "Dobré ráno";
    if (h >= 11 && h < 12) return "Dobré dopoledne";
    if (h >= 12 && h < 18) return "Dobré odpoledne";
    return "Dobrý večer";
  }

  function loadPrehledEmployee() {
    if (isAdmin) return;
    const greetEl = document.getElementById("employee-greeting");
    const todayEl = document.getElementById("employee-today-content");
    const todayTitleEl = document.getElementById("employee-today-title");
    const reqsEl = document.getElementById("employee-requests-for-me");
    const weekEl = document.getElementById("employee-week-shifts");
    if (!greetEl || !todayEl) return;
    greetEl.textContent = "";
    todayEl.innerHTML = '<p class="text-muted">Načítám…</p>';
    if (reqsEl) reqsEl.innerHTML = '<p class="text-muted">Načítám…</p>';
    if (weekEl) weekEl.innerHTML = '<p class="text-muted">Načítám…</p>';
    get("/me/dashboard").then((data) => {
      const name = data.employeeName || "zaměstnanec";
      greetEl.textContent = `${getGreeting()}, ${name}!`;
      if (data.todayShift) {
        todayTitleEl.textContent = "Dnes";
        todayEl.innerHTML = `
          <p class="employee-shift-msg"><strong>Dnes máte směnu:</strong></p>
          <p class="employee-shift-detail">${data.todayShift.startTime} – ${data.todayShift.endTime}${data.todayShift.branchName ? ` · ${data.todayShift.branchName}` : ""}</p>
        `;
      } else if (data.nextShift) {
        todayTitleEl.textContent = "Dnes";
        todayEl.innerHTML = `
          <p class="employee-shift-msg"><strong>Dnes máte volno.</strong></p>
          <p class="employee-shift-msg">Další směna: <strong>${fmtDateDisplay(data.nextShift.date)}</strong> v ${data.nextShift.startTime} – ${data.nextShift.endTime}${data.nextShift.branchName ? ` · ${data.nextShift.branchName}` : ""}</p>
        `;
      } else {
        todayTitleEl.textContent = "Dnes";
        todayEl.innerHTML = '<p class="employee-shift-msg"><strong>Dnes máte volno.</strong></p><p class="text-muted">Nemáte v plánu žádnou další směnu v nejbližších 60 dnech.</p>';
      }
      if (reqsEl) {
        const reqs = data.requestsForMe || [];
        if (!reqs.length) {
          reqsEl.innerHTML = '<p class="empty">Žádné žádosti, které se vás týkají.</p>';
        } else {
          const reqTypeLabels = { leave: "Volno", late: "Zpoždění", swap: "Výměna směny", cover: "Volná směna – záskok" };
          reqsEl.innerHTML = '<table><thead><tr><th>Od</th><th>Typ</th><th>Detaily</th><th></th></tr></thead><tbody>' +
            reqs.map((r) => {
              let det = "";
              if (r.type === "swap" && r.shift && r.otherShift) det = `${r.employee?.name || ""} chce vyměnit svou směnu ${fmtDateDisplay(r.shift.date)} ${r.shift.startTime}–${r.shift.endTime} za vaši směnu ${fmtDateDisplay(r.otherShift.date)} ${r.otherShift.startTime}–${r.otherShift.endTime}`;
              else if (r.type === "cover" && r.shift) det = `${r.employee?.name || ""} nemůže na směnu ${fmtDateDisplay(r.shift.date)} ${r.shift.startTime}–${r.shift.endTime}`;
              else det = r.note || "—";
              const statusLabel = r.status === "pending" ? "Čeká" : r.status === "approved" ? "Schváleno" : "Odmítnuto";
              const applyBtn = r.type === "cover" && r.status === "pending" ? ` <button type="button" class="btn btn-sm btn-primary" onclick="window.applyForCover('${r.id}')">Přihlásit se na směnu</button>` : "";
              return `<tr><td>${esc(r.employee?.name || "")}</td><td><span class="badge badge-${r.type}">${reqTypeLabels[r.type] || r.type}</span></td><td>${esc(det)}</td><td>${statusLabel}${applyBtn}</td></tr>`;
            }).join("") + "</tbody></table>";
        }
      }
    }).catch((e) => {
      if (greetEl) greetEl.textContent = `${getGreeting()}!`;
      if (todayEl) todayEl.innerHTML = '<p class="text-muted" style="color:var(--rose)">Chyba načtení.</p>';
      if (reqsEl) reqsEl.innerHTML = '<p class="text-muted" style="color:var(--rose)">Chyba načtení.</p>';
      if (weekEl) weekEl.innerHTML = '<p class="text-muted" style="color:var(--rose)">Chyba načtení.</p>';
      toast(e?.error || "Chyba", "error");
    });
    // Týdenní rozvrh – tento týden (Po–Ne)
    if (weekEl) {
      const now = new Date();
      const weekStart = startOfWeek(now);
      const weekEnd = addDays(new Date(weekStart.getTime()), 6);
      const from = fmtDate(weekStart);
      const to = fmtDate(weekEnd);
      get("/my-shifts?from=" + from + "&to=" + to).then((shifts) => {
        const byDate = {};
        for (let i = 0; i < 7; i++) {
          const d = addDays(new Date(weekStart.getTime()), i);
          byDate[fmtDate(d)] = [];
        }
        (shifts || []).forEach((s) => {
          if (byDate[s.date]) byDate[s.date].push(s);
        });
        const dayNames = ["Po", "Út", "St", "Čt", "Pá", "So", "Ne"];
        const today = fmtDate(new Date());
        let html = '<div class="employee-week-cards">';
        for (let i = 0; i < 7; i++) {
          const d = addDays(new Date(weekStart.getTime()), i);
          const dateStr = fmtDate(d);
          const list = byDate[dateStr] || [];
          const isToday = dateStr === today;
          const dayLabel = d.toLocaleDateString("cs-CZ", { weekday: "short", day: "numeric", month: "numeric" });
          const shiftColor = (s) => (s?.employee?.color && /^#[0-9a-fA-F]{6}$/.test(s.employee.color) ? s.employee.color : "var(--blue)");
          const shiftsHtml = list.length
            ? list.map((s) => `<div class="employee-day-shift" style="border-left:3px solid ${shiftColor(s)}">${s.startTime}–${s.endTime}</div>`).join("")
            : '<p class="employee-day-empty">—</p>';
          html += `<div class="employee-day-card ${isToday ? "employee-day-today" : ""}">
            <div class="employee-day-header">${dayNames[i]} ${d.getDate()}.&nbsp;</div>
            <div class="employee-day-shifts">${shiftsHtml}</div>
          </div>`;
        }
        html += "</div>";
        weekEl.innerHTML = html;
      }).catch(() => {
        weekEl.innerHTML = '<p class="empty">Rozvrh na týden se nepodařilo načíst.</p>';
      });
    }
  }

  function loadOverview() {
    if (!isAdmin) return;
    loadCoverageGrid();
    const lateFrom = document.getElementById("late-from");
    const lateTo = document.getElementById("late-to");
    if (lateFrom && lateTo && !lateFrom.value) {
      lateFrom.value = fmtDate(addDays(startOfWeek(new Date()), -30));
      lateTo.value = fmtDate(new Date());
    }
    get("/overview").then((data) => {
      const pending = data.pendingRequests || 0;
      const cards = document.getElementById("overview-cards");
      cards.innerHTML = `
        <div class="overview-card overview-requests ${pending > 0 ? "urgent" : ""}">
          <div class="card-icon-wrap"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg></div>
          <span class="label">Čekající žádosti</span>
          <span class="value">${pending}</span>
        </div>
        <div class="overview-card overview-shifts">
          <div class="card-icon-wrap"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="4" width="18" height="18" rx="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg></div>
          <span class="label">Směny dnes</span>
          <span class="value">${data.todayShifts || 0}</span>
        </div>
        <div class="overview-card overview-employees">
          <div class="card-icon-wrap"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg></div>
          <span class="label">Zaměstnanci</span>
          <span class="value">${data.employeesCount || 0}</span>
        </div>
        <div class="overview-card overview-branches">
          <div class="card-icon-wrap"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/></svg></div>
          <span class="label">Pobočky</span>
          <span class="value">${data.branchesCount || 0}</span>
        </div>
      `;
    });
    loadLateOverview();
    get("/requests?status=pending").then((reqs) => {
      const el = document.getElementById("overview-requests");
      if (!el) return;
      if (!Array.isArray(reqs) || !reqs.length) {
        el.innerHTML = '<p class="empty">Žádné čekající žádosti.</p>';
        return;
      }
      const reqTypeLabels = { leave: "Volno", late: "Zpoždění", swap: "Výměna", cover: "Záskok" };
      el.innerHTML = '<table><thead><tr><th>Zaměstnanec</th><th>Typ</th><th>Detaily</th><th></th></tr></thead><tbody>' +
        reqs.map((r) => {
          if (r.type === "cover_apply") return "";
          let det = "";
          if (r.type === "leave") det = `${fmtDateDisplay(r.dateFrom)} – ${fmtDateDisplay(r.dateTo)}`;
          else if (r.type === "late") det = `${fmtDateDisplay(r.shiftDate)} (plán ${r.plannedTime} → ${r.actualTime || "?"})${r.minutesLate != null ? " +" + r.minutesLate + " min" : ""}`;
          else if (r.type === "swap" && r.shift && r.otherShift) det = `${r.shift.date} ${r.shift.startTime}–${r.shift.endTime} ↔ ${r.otherShift.employeeName} (${r.otherShift.date})`;
          else if (r.type === "cover" && r.shift) det = `${r.employee?.name || ""} nemůže na ${r.shift.date} ${r.shift.startTime}–${r.shift.endTime}` + ((r.applications || []).length ? ` · ${r.applications.length} přihláška/y` : "");
          const apps = r.applications || [];
          const actionCell = r.type === "cover" && apps.length > 0
            ? apps.map((a) => a.status === "pending" ? `<button class="btn btn-sm btn-primary" onclick="window.approveRequest('${a.id}')">Schválit ${esc(a.employee?.name || "")}</button>` : "").filter(Boolean).join(" ") || "—"
            : `<button class="btn btn-sm btn-primary" onclick="window.approveRequest('${r.id}')">Schválit</button>
                <button class="btn btn-sm btn-secondary" onclick="window.rejectRequest('${r.id}')">Zamítnout</button>`;
          return `<tr>
            <td>${esc(r.employee?.name || "")}</td>
            <td><span class="badge badge-${r.type}">${reqTypeLabels[r.type] || r.type}</span></td>
            <td>${esc(det)}</td>
            <td>${actionCell}</td>
          </tr>`;
        }).filter(Boolean).join("") + "</tbody></table>";
    }).catch((err) => {
      const el = document.getElementById("overview-requests");
      if (el) el.innerHTML = '<p class="empty">Chyba načtení žádostí. Obnovte stránku.</p>';
    });
  }

  window.approveRequest = (id) => {
    patch("/requests/" + id, { status: "approved" }).then(() => {
      toast("Žádost schválena ✓", "success");
      refreshAllViews();
      loadRequests();
    }).catch((err) => {
      toast(err?.error || "Nepodařilo se schválit", "error");
      loadRequests();
    });
  };
  window.rejectRequest = (id) => {
    patch("/requests/" + id, { status: "rejected" }).then(() => {
      toast("Žádost zamítnuta", "default");
      refreshAllViews();
      loadRequests();
    }).catch((err) => {
      toast(err?.error || "Nepodařilo se zamítnout", "error");
      loadRequests();
    });
  };
  window.applyForCover = (coverRequestId) => {
    post("/requests", { type: "cover_apply", appliesToRequestId: coverRequestId }).then(() => {
      toast("Přihláška na záskok odeslána ✓", "success");
      if (typeof loadPrehledEmployee === "function") loadPrehledEmployee();
      if (typeof loadRequests === "function") loadRequests();
      if (typeof refreshAllViews === "function") refreshAllViews();
    }).catch((err) => toast(err?.error || "Chyba přihlášení na záskok", "error"));
  };

  let requestsActiveTab = "registrace";
  function switchRequestsTab(tab) {
    requestsActiveTab = tab;
    document.querySelectorAll(".requests-tab").forEach((t) => t.classList.toggle("active", t.dataset.tab === tab));
    document.querySelectorAll(".requests-panel").forEach((p) => {
      const id = p.id;
      const show = (tab === "registrace" && id === "requests-registrace") || (tab === "reset-hesla" && id === "requests-reset-hesla") || (tab === "uzivatele" && id === "requests-uzivatele") || ((tab === "volno-zaskoky" || tab === "zamestnanci") && id === "requests-zamestnanci");
      p.classList.toggle("hidden", !show);
      p.style.display = show ? "" : "none";
    });
    if (tab === "registrace") loadRegistrationRequests();
    if (tab === "reset-hesla") loadPasswordResetRequests();
    if (tab === "uzivatele") loadUsers();
    if (tab === "volno-zaskoky" || tab === "zamestnanci") loadEmployeeRequests();
  }
  document.querySelectorAll(".requests-tab").forEach((b) => {
    b.addEventListener("click", () => switchRequestsTab(b.dataset.tab));
  });
  function loadRegistrationRequests() {
    if (!isFullAdmin) return;
    Promise.all([get("/registration-requests?status=pending"), get("/branches").then((d) => Array.isArray(d) ? d : []).catch(() => [])]).then(([reqs, branchList]) => {
      const list = document.getElementById("registration-requests-list");
      if (!list) return;
      if (!Array.isArray(reqs) || !reqs.length) {
        list.innerHTML = '<p class="empty">Žádné čekající žádosti o registraci.</p>';
        return;
      }
      const branchOpts = (branchList.length ? branchList : branches).map((b) => `<option value="${b.id}">${esc(b.name)}</option>`).join("");
      list.innerHTML = reqs.map((r) => `<div class="card list-item" data-reg-id="${r.id}">
        <div>
          <strong>${esc(r.email)}</strong>
          ${r.name ? `<span class="text-muted" style="margin-left:0.5rem">${esc(r.name)}</span>` : ""}
          <p class="text-muted" style="font-size:0.75rem;margin-top:0.25rem">${esc(r.createdAt || "")}</p>
          <label class="text-muted" style="font-size:0.8125rem;margin-top:0.5rem;display:block">Přiřadit do pobočky:</label>
          <select class="input input-sm reg-approve-branch" style="margin-top:0.25rem;max-width:100%">${branchOpts}</select>
        </div>
        <div class="flex gap-2">
          <button class="btn btn-sm btn-primary" onclick="window.approveRegistration('${r.id}', this.closest('.list-item').querySelector('select.reg-approve-branch')?.value)">Schválit a poslat odkaz</button>
          <button class="btn btn-sm btn-secondary" onclick="window.rejectRegistration('${r.id}')">Zamítnout</button>
        </div>
      </div>`).join("");
    }).catch(() => {
      const list = document.getElementById("registration-requests-list");
      if (list) list.innerHTML = '<p class="empty">Chyba načtení.</p>';
    });
  }
  window.approveRegistration = (id, branchId) => {
    const body = branchId ? { branchId: branchId } : {};
    post("/registration-requests/" + id + "/approve", body).then(() => {
      toast("Schváleno. Zaměstnanec je v seznamu a kalendáři. E-mail s odkazem odeslán ✓", "success");
      loadRegistrationRequests();
      refreshAllViews();
    }).catch((e) => toast(e?.error || "Chyba", "error"));
  };
  window.rejectRegistration = (id) => {
    post("/registration-requests/" + id + "/reject", {}).then(() => {
      toast("Žádost zamítnuta", "default");
      loadRegistrationRequests();
    }).catch((e) => toast(e?.error || "Chyba", "error"));
  };
  function loadPasswordResetRequests() {
    if (!isFullAdmin) return;
    get("/password-reset-requests?status=pending").then((reqs) => {
      const list = document.getElementById("password-reset-requests-list");
      if (!list) return;
      if (!Array.isArray(reqs) || !reqs.length) {
        list.innerHTML = '<p class="empty">Žádné čekající žádosti o reset hesla.</p>';
        return;
      }
      list.innerHTML = reqs.map((r) => `<div class="card list-item">
        <div>
          <strong>${esc(r.email)}</strong>
          ${r.userName ? `<span class="text-muted" style="margin-left:0.5rem">(${esc(r.userName)})</span>` : ""}
          <p class="text-muted" style="font-size:0.75rem;margin-top:0.25rem">${esc(r.createdAt || "")}</p>
        </div>
        <div class="flex gap-2">
          <button class="btn btn-sm btn-primary" onclick="window.approvePasswordReset('${r.id}')">Schválit a poslat odkaz</button>
          <button class="btn btn-sm btn-secondary" onclick="window.rejectPasswordReset('${r.id}')">Zamítnout</button>
        </div>
      </div>`).join("");
    }).catch(() => {
      const list = document.getElementById("password-reset-requests-list");
      if (list) list.innerHTML = '<p class="empty">Chyba načtení.</p>';
    });
  }
  window.approvePasswordReset = (id) => {
    post("/password-reset-requests/" + id + "/approve", {}).then(() => {
      toast("Schváleno. E-mail s odkazem odeslán ✓", "success");
      loadPasswordResetRequests();
    }).catch((e) => toast(e?.error || "Chyba", "error"));
  };
  window.rejectPasswordReset = (id) => {
    post("/password-reset-requests/" + id + "/reject", {}).then(() => {
      toast("Žádost zamítnuta", "default");
      loadPasswordResetRequests();
    }).catch((e) => toast(e?.error || "Chyba", "error"));
  };
  function loadUsers() {
    if (!isFullAdmin) return;
    Promise.all([get("/users"), get("/me")]).then(([users, me]) => {
      usersListCache = users || [];
      const list = document.getElementById("users-list");
      if (!list) return;
      if (!Array.isArray(users) || !users.length) {
        list.innerHTML = '<p class="empty">Žádní uživatelé.</p>';
        return;
      }
      const myId = me?.id;
      list.innerHTML = users.map((u) => {
        const roleLabels = { admin: "Admin", employee: "Zaměstnanec", ucetni: "Účetní" };
        const isMe = String(u.id) === String(myId);
        const selectHtml = isMe
          ? `<span class="text-muted">(vy)</span>`
          : `<select class="input input-sm" style="width:auto" onchange="window.updateUserRole('${u.id}', this.value)">
              <option value="admin" ${u.role === "admin" ? "selected" : ""}>Admin</option>
              <option value="employee" ${u.role === "employee" ? "selected" : ""}>Zaměstnanec</option>
              <option value="ucetni" ${u.role === "ucetni" ? "selected" : ""}>Účetní</option>
            </select>`;
        const sendResetBtn = !isMe ? `<button class="btn btn-sm btn-secondary" onclick="window.sendUserResetLink('${u.id}')" title="Odeslat odkaz na reset hesla">Odeslat odkaz</button>` : "";
        const editBtn = !isMe ? `<button class="btn btn-sm btn-secondary" onclick="window.editUser('${u.id}')">Upravit</button>` : "";
        const delBtn = !isMe ? `<button class="btn btn-sm btn-danger" onclick="window.deleteUser('${u.id}')">Smazat</button>` : "";
        return `<div class="card list-item users-list-item">
          <div>
            <strong>${esc(u.email)}</strong>
            ${u.name ? `<span class="text-muted"> – ${esc(u.name)}</span>` : ""}
            <p class="text-muted" style="font-size:0.75rem;margin-top:0.25rem">Role: ${roleLabels[u.role] || u.role}</p>
          </div>
          <div class="flex gap-2 align-center" style="flex-wrap:wrap">${selectHtml}${editBtn}${sendResetBtn}${delBtn}</div>
        </div>`;
      }).join("");
    }).catch(() => {
      const list = document.getElementById("users-list");
      if (list) list.innerHTML = '<p class="empty">Chyba načtení.</p>';
    });
  }
  window.updateUserRole = (id, role) => {
    patch("/users/" + id, { role }).then(() => {
      toast("Role aktualizována ✓", "success");
      loadUsers();
    }).catch((e) => toast(e?.error || "Chyba", "error"));
  };
  window.sendUserResetLink = (userId) => {
    post("/users/" + userId + "/send-reset-link", {}).then((data) => {
      toast(data.message || "Odkaz odeslán ✓", "success");
    }).catch((e) => toast(e?.error || "Chyba", "error"));
  };
  window.editUser = (id) => {
    const u = usersListCache?.find((x) => String(x.id) === String(id));
    if (!u) return;
    document.getElementById("user-edit-id").value = id;
    document.getElementById("user-edit-email").value = u.email || "";
    document.getElementById("user-edit-name").value = u.name || "";
    openModal("modal-user-edit");
  };
  window.deleteUser = (id) => {
    const u = usersListCache?.find((x) => String(x.id) === String(id));
    const label = u ? (u.email || "uživatele") : "uživatele";
    if (!confirm(`Opravdu smazat ${label}? Smaže se účet včetně všech jeho poboček a zaměstnanců.`)) return;
    del("/users/" + id).then(() => {
      toast("Uživatel smazán", "default");
      loadUsers();
    }).catch((e) => toast(e?.error || "Chyba", "error"));
  };
  let usersListCache = [];
  document.getElementById("form-user-edit")?.addEventListener("submit", (e) => {
    e.preventDefault();
    const id = document.getElementById("user-edit-id").value;
    patch("/users/" + id, {
      email: document.getElementById("user-edit-email").value.trim(),
      name: document.getElementById("user-edit-name").value.trim(),
    }).then(() => {
      toast("Uživatel upraven ✓", "success");
      closeModal("modal-user-edit");
      loadUsers();
    }).catch((e) => toast(e?.error || "Chyba", "error"));
  });

  function loadAvailableCovers() {
    if (isAdmin) return;
    const wrap = document.getElementById("requests-available-covers");
    const titleEl = document.getElementById("requests-available-title");
    const descEl = document.getElementById("requests-available-desc");
    if (!wrap) return;
    get("/me/dashboard").then((data) => {
      const covers = (data.requestsForMe || []).filter((r) => r.type === "cover" && r.status === "pending");
      if (titleEl) titleEl.style.display = "";
      if (descEl) descEl.style.display = "";
      wrap.style.display = "";
      if (!covers.length) {
        wrap.innerHTML = '<p class="empty">Momentálně žádné volné směny ve vaší pobočce.</p>';
        return;
      }
      wrap.innerHTML = covers.map((r) => {
        const det = r.shift ? `${r.employee?.name || ""} nemůže na ${fmtDateDisplay(r.shift.date)} ${r.shift.startTime}–${r.shift.endTime}` : "";
        return `<div class="card list-item">
          <div><strong>${esc(r.employee?.name || "?")}</strong><span class="badge badge-cover" style="margin-left:0.5rem">Volná směna</span>
            <p class="text-muted" style="font-size:0.8rem;margin-top:0.25rem">${esc(det)}</p></div>
          <button type="button" class="btn btn-sm btn-primary" onclick="window.applyForCover('${r.id}')">Přihlásit se na směnu</button>
        </div>`;
      }).join("");
    }).catch(() => {
      if (wrap) wrap.innerHTML = '<p class="empty">Chyba načtení volných směn.</p>';
    });
  }

  function renderRequestCard(r, typeLabels) {
    const typeLabel = typeLabels[r.type] || r.type;
    let det = "";
    if (r.type === "leave") det = `${fmtDateDisplay(r.dateFrom)} – ${fmtDateDisplay(r.dateTo)}`;
    else if (r.type === "late") det = `Směna ${fmtDateDisplay(r.shiftDate)}, plán ${r.plannedTime} → ${r.actualTime || "?"}${r.minutesLate != null ? ` (+${r.minutesLate} min)` : ""}`;
    else if (r.type === "swap" && r.shift && r.otherShift) det = `${r.shift.date} ${r.shift.startTime}–${r.shift.endTime} ↔ ${r.otherShift.employeeName} (${r.otherShift.date} ${r.otherShift.startTime}–${r.otherShift.endTime})`;
    else if (r.type === "cover" && r.shift) det = `Nemůžu na ${fmtDateDisplay(r.shift.date)} ${r.shift.startTime}–${r.shift.endTime}`;
    else if (r.type === "cover_apply" && r.shift) det = `Chci zaskočit na ${fmtDateDisplay(r.shift.date)} ${r.shift.startTime}–${r.shift.endTime}`;
    const statusCl = r.status === "approved" ? "emerald" : r.status === "rejected" ? "rose" : "amber";
    const apps = r.applications || [];
    const appsHtml = apps.length ? `<div class="cover-applications mt-2" style="margin-top:0.5rem;padding-top:0.5rem;border-top:1px solid var(--gray-200)">
      <strong style="font-size:0.8125rem">Přihlášky na záskok:</strong>
      ${apps.map((a) => `<div class="flex align-center gap-2" style="margin-top:0.35rem">
        <span>${esc(a.employee?.name || "?")}</span>
        ${a.status === "pending" && isAdmin ? `<button class="btn btn-sm btn-primary" onclick="window.approveRequest('${a.id}')">Schválit</button><button class="btn btn-sm btn-secondary" onclick="window.rejectRequest('${a.id}')">Zamítnout</button>` : `<span class="badge badge-${a.status === "approved" ? "emerald" : a.status === "rejected" ? "rose" : "amber"}">${a.status === "approved" ? "Schváleno" : a.status === "rejected" ? "Zamítnuto" : "Čeká"}</span>`}
      </div>`).join("")}
    </div>` : "";
    const directApprove = r.type !== "cover" || apps.length === 0;
    return `<div class="card list-item">
      <div>
        <strong>${esc(r.employee?.name || "?")}</strong>
        <span class="badge badge-${r.type}" style="margin-left:0.5rem">${typeLabel}</span>
        <span class="badge badge-${statusCl}" style="margin-left:0.25rem">${r.status === "approved" ? "Schváleno" : r.status === "rejected" ? "Zamítnuto" : "Čeká"}</span>
        <p class="text-muted" style="font-size:0.8rem;margin-top:0.25rem">${esc(det)}${r.note ? " · " + esc(r.note) : ""}</p>
        ${appsHtml}
      </div>
      ${isAdmin && r.status === "pending" && directApprove ? `
      <div class="flex gap-2">
        <button class="btn btn-sm btn-primary" onclick="window.approveRequest('${r.id}')">Schválit</button>
        <button class="btn btn-sm btn-secondary" onclick="window.rejectRequest('${r.id}')">Zamítnout</button>
      </div>` : ""}
    </div>`;
  }

  function loadEmployeeRequests() {
    if (!isAdmin) loadAvailableCovers();
    get("/requests").then((reqs) => {
      const list = document.getElementById("requests-list");
      if (!list) return;
      if (!Array.isArray(reqs) || !reqs.length) {
        list.innerHTML = '<p class="empty">Žádné žádosti.</p>';
        return;
      }
      const typeLabels = { leave: "Volno", late: "Zpoždění", swap: "Výměna směny", cover: "Záskok – hledám náhradu", cover_apply: "Přihláška na záskok" };
      list.innerHTML = reqs.map((r) => renderRequestCard(r, typeLabels)).join("");
    }).catch((err) => {
      const list = document.getElementById("requests-list");
      if (list) list.innerHTML = '<p class="empty">Chyba načtení žádostí. Zkuste obnovit stránku.</p>';
    });
  }

  function loadRequests() {
    if (isFullAdmin) {
      document.getElementById("requests-zadosti-tabs")?.style?.setProperty("display", "");
      document.querySelectorAll(".requests-panel").forEach((p) => {
        p.style.display = ""; p.classList.remove("hidden");
      });
      switchRequestsTab(requestsActiveTab);
    } else {
      document.getElementById("requests-zadosti-tabs")?.style?.setProperty("display", "none");
      document.querySelectorAll(".requests-panel").forEach((p) => {
        p.classList.toggle("hidden", p.id !== "requests-zamestnanci");
        p.style.display = p.id === "requests-zamestnanci" ? "" : "none";
      });
      loadEmployeeRequests();
    }
  }

  function loadAccountantForm() {
    document.getElementById("form-invite-accountant")?.reset();
    loadAccountants();
  }
  function loadAccountants() {
    if (!isFullAdmin) return;
    const list = document.getElementById("accountant-list");
    if (!list) return;
    get("/accountants").then((accountants) => {
      if (!accountants || accountants.length === 0) {
        list.innerHTML = '<p class="empty" style="padding:1rem">Zatím žádní účetní.</p>';
        return;
      }
      list.innerHTML = accountants.map((a) => `
        <div class="card list-item" style="max-width:420px">
          <div>
            <strong>${esc(a.name || a.email)}</strong>
            <p class="text-muted" style="font-size:0.875rem;margin-top:0.25rem">${esc(a.email)}</p>
          </div>
          <div class="flex gap-2">
            <button type="button" class="btn btn-secondary btn-sm" onclick="window.sendAccountantReset('${a.id}')">Poslat odkaz na reset hesla</button>
          </div>
        </div>
      `).join("");
    }).catch(() => {
      list.innerHTML = '<p class="empty" style="padding:1rem">Chyba načtení.</p>';
    });
  }
  window.sendAccountantReset = (uid) => {
    post("/users/" + uid + "/send-reset-link", {}).then((data) => {
      toast(data.message || "Odkaz odeslán ✓", "success");
    }).catch((e) => toast(e?.error || "Chyba", "error"));
  };
  document.getElementById("form-invite-accountant")?.addEventListener("submit", (e) => {
    e.preventDefault();
    const email = document.getElementById("accountant-email")?.value?.trim();
    const name = document.getElementById("accountant-name")?.value?.trim();
    const password = document.getElementById("accountant-password")?.value;
    if (!email || !password || password.length < 6) {
      toast("E-mail a heslo (min. 6 znaků) jsou povinné.", "error");
      return;
    }
    post("/invite-accountant", { email, name, password })
      .then((data) => {
        toast(data.message || "Účetní vytvořen ✓", "success");
        document.getElementById("form-invite-accountant")?.reset();
        loadAccountants();
      })
      .catch((err) => toast(err.error || "Chyba", "error"));
  });

  /** Po změně jakýchkoliv dat – obnoví všechny view, aby byly okamžitě live. */
  function refreshAllViews() {
    calMonthCache = null;
    renderCalendar();
    if (isAdmin) {
      if (typeof loadOverview === "function") loadOverview();
      if (typeof loadCoverageGrid === "function") loadCoverageGrid();
    } else if (typeof loadPrehledEmployee === "function") {
      loadPrehledEmployee();
    }
    loadEmployees();
    loadPresets();
    if (typeof loadRequests === "function") loadRequests();
  }

  function loadBranches() {
    return get("/branches")
      .then((data) => {
        branches = Array.isArray(data) ? data : [];
        fillBranchSelects();
        const list = document.getElementById("branches-list");
        if (!list) return;
        if (branches.length === 0) {
          list.innerHTML = '<p class="empty">Zatím žádné pobočky. Přidejte první.</p>';
          return;
        }
        list.innerHTML = branches
          .map(
          (b) =>
            `<div class="card list-item">
          <div>
            <strong>${esc(b.name)}</strong>
            ${b.address ? `<p class="text-muted">${esc(b.address)}</p>` : ""}
            <p class="text-muted" style="font-size:0.75rem">${b.openTime || "08:00"}–${b.closeTime || "20:00"}${b.openTimeWeekend && b.closeTimeWeekend ? ` · víkend ${b.openTimeWeekend}–${b.closeTimeWeekend}` : ""} · ${b._count?.employees || 0} zaměstnanců, ${b._count?.presets || 0} presetů</p>
          </div>
          <div class="flex gap-2">${isFullAdmin ? `<button class="btn btn-secondary btn-sm" onclick="window.editBranch('${b.id}')">Upravit</button><button class="btn btn-danger btn-sm" onclick="window.delBranch('${b.id}')">Smazat</button>` : ""}</div>
        </div>`
          )
          .join("");
      })
      .catch((err) => {
        branches = [];
        fillBranchSelects();
        const list = document.getElementById("branches-list");
        if (list) list.innerHTML = '<p class="empty">' + (err?.error ? esc(err.error) : "Chyba načtení.") + '</p>';
        if (err?._status === 403) refreshRoleOn403();
      });
  }

  function refreshRoleOn403() {
    get("/me").then((me) => {
      applyRole(me);
      toast("Oprávnění obnovena. Obnovte stránku, pokud se nic nezměnilo.", "default");
    }).catch(() => {});
  }

  function fillBranchSelects() {
    const list = Array.isArray(branches) ? branches : [];
    const validIds = new Set(list.map((b) => String(b.id)));
    const opts = list.map((b) => `<option value="${b.id}">${esc(b.name)}</option>`).join("");
    ["branch-filter", "preset-branch", "hours-branch", "who-branch", "shift-branch", "employee-branch", "preset-form-branch", "export-branch", "cal-branch"].forEach((id) => {
      const el = document.getElementById(id);
      if (!el) return;
      const prevVal = el.value;
      el.innerHTML = '<option value="">— vyberte —</option>' + opts;
      if (prevVal && !validIds.has(prevVal) && list.length > 0) el.value = list[0].id;
      else if (list.length === 1) el.value = list[0].id;
    });
  }

  function loadEmployees() {
    const branchId = document.getElementById("branch-filter")?.value;
    const path = branchId ? "/employees?branchId=" + branchId : "/employees";
    get(path)
      .then((data) => {
        employees = Array.isArray(data) ? data : [];
        const list = document.getElementById("employees-list");
        if (!list) return;
        if (employees.length === 0) {
          list.innerHTML = '<p class="empty">Zatím žádní zaměstnanci. Přidejte prvního.</p>';
          return;
        }
        const empColor = (c) => (c && /^#[0-9a-fA-F]{6}$/.test(c) ? c : null);
        list.innerHTML = employees
          .map(
          (e) => {
            const col = empColor(e.color);
            const leftBorder = col ? `border-left:4px solid ${col}` : "";
            return `<div class="card list-item" style="${leftBorder}">
          <div>
            <strong>${esc(e.name)}</strong>
            ${e.email ? `<p class="text-muted">${esc(e.email)}</p>` : ""}
                  <p class="text-muted" style="font-size:0.75rem">${e.branch?.name || ""}${(e.hourlyRate ?? e.branch?.defaultHourlyRate) ? ` · ${(e.hourlyRate ?? e.branch?.defaultHourlyRate)} Kč/h` : ""}</p>
          </div>
          <div class="flex gap-2">${isFullAdmin ? `<button class="btn btn-secondary btn-sm" onclick="window.editEmployee('${e.id}')">Upravit</button>${e.hasAccess ? '<span class="text-muted" style="font-size:0.75rem">Přístup existuje</span>' : '<button class="btn btn-accent btn-sm" data-create-access data-emp-id="' + e.id + '" data-emp-email="' + esc(String(e.email || "")) + '">Vytvořit přístup</button>'}<button class="btn btn-danger btn-sm" onclick="window.delEmployee('${e.id}')">Smazat</button>` : ""}</div>
        </div>`;
          }
          )
          .join("");
      })
      .catch((err) => {
        employees = [];
        const list = document.getElementById("employees-list");
        if (list) list.innerHTML = '<p class="empty">' + (err?.error ? esc(err.error) : "Chyba načtení.") + '</p>';
        if (err?._status === 403) refreshRoleOn403();
      });
  }

  function loadPresets() {
    const branchId = document.getElementById("preset-branch")?.value;
    const path = branchId ? "/presets?branchId=" + branchId : "/presets";
    get(path)
      .then((data) => {
        presets = Array.isArray(data) ? data : [];
        const list = document.getElementById("presets-list");
        if (!list) return;
        if (presets.length === 0) {
          list.innerHTML = '<p class="empty">Zatím žádné presety. Přidejte první.</p>';
          return;
        }
        list.innerHTML = presets
          .map(
          (p) =>
            `<div class="card list-item">
          <span><strong>${esc(p.name)}</strong> ${p.startTime}–${p.endTime}</span>
          <div class="flex gap-2">
            <button class="btn btn-secondary btn-sm" onclick="window.editPreset('${p.id}')">Upravit</button>
            <button class="btn btn-danger btn-sm" onclick="window.delPreset('${p.id}')">Smazat</button>
          </div>
        </div>`
          )
          .join("");
      })
      .catch((err) => {
        presets = [];
        const list = document.getElementById("presets-list");
        if (list) list.innerHTML = '<p class="empty">' + (err?.error ? esc(err.error) : "Chyba načtení.") + '</p>';
        if (err?._status === 403) refreshRoleOn403();
      });
  }

  function loadTodayWeek() {
    if (!document.getElementById("today-shifts") || !document.getElementById("week-shifts")) return;
    const today = fmtDate(new Date());
    const start = startOfWeek(new Date());
    const end = fmtDate(addDays(new Date(start.getTime()), 6));
    get("/my-shifts?from=" + today + "&to=" + today).then((todayData) => {
      const el = document.getElementById("today-shifts");
      const titleEl = document.getElementById("today-title");
      if (titleEl) titleEl.textContent = "Dnes · " + new Date().toLocaleDateString("cs-CZ", { weekday: "long", day: "numeric", month: "long" });
      if (todayData.length === 0) {
        el.innerHTML = '<div class="card empty">Žádné směny na dnešek.</div>';
      } else {
        const shiftColor = (s) => (s?.employee?.color && /^#[0-9a-fA-F]{6}$/.test(s.employee.color) ? s.employee.color : "var(--blue)");
        const editBtn = (s) => isAdmin ? ` <button class="btn btn-sm btn-secondary" onclick="window.editShift('${s.id}','${s.date}','${s.startTime}','${s.endTime}','${s.employee?.id || ""}','${s.branchId || s.employee?.branch?.id || ""}')" title="Upravit směnu">✎</button>` : "";
        el.innerHTML = todayData
          .map(
            (s) =>
              `<div class="card list-item" style="border-left:4px solid ${shiftColor(s)}">
            <span><strong>${esc(s.employee?.name || s.title || "Směna")}</strong></span>
            <span style="color:var(--blue);font-weight:500">${s.startTime} – ${s.endTime}</span>${editBtn(s)}
          </div>`
          )
          .join("");
      }
    });
    get("/my-shifts?from=" + start.toISOString().slice(0, 10) + "&to=" + end).then((weekData) => {
      const el = document.getElementById("week-shifts");
      if (weekData.length === 0) {
        el.innerHTML = '<div class="card empty">Žádné směny v tomto týdnu.</div>';
      } else {
        const byDate = {};
        weekData.forEach((s) => {
          if (!byDate[s.date]) byDate[s.date] = [];
          byDate[s.date].push(s);
        });
        const weekStart = fmtDate(start);
        let html = "";
        for (let i = 0; i < 7; i++) {
          const d = addDays(new Date(weekStart), i);
          const dateStr = fmtDate(d);
          const list = byDate[dateStr] || [];
          const shiftStyle = (s) => (s?.employee?.color && /^#[0-9a-fA-F]{6}$/.test(s.employee.color) ? `border-left:3px solid ${s.employee.color}` : "");
          const weekEditBtn = (s) => isAdmin ? ` <button class="btn btn-sm btn-secondary" style="padding:0.15rem 0.35rem;font-size:0.7rem" onclick="window.editShift('${s.id}','${s.date}','${s.startTime}','${s.endTime}','${s.employee?.id || ""}','${s.branchId || s.employee?.branch?.id || ""}')" title="Upravit">✎</button>` : "";
          html += `<div class="card">
            <strong style="font-size:0.875rem">${d.toLocaleDateString("cs-CZ", { weekday: "short", day: "numeric" })}</strong>
            ${list.map((s) => `<div class="cal-shift" style="${shiftStyle(s)}">${esc(s.employee?.name || "Směna")} <span>${s.startTime}–${s.endTime}</span>${weekEditBtn(s)}</div>`).join("") || '<p class="text-muted" style="font-size:0.75rem">—</p>'}
          </div>`;
        }
        el.innerHTML = '<div class="week-grid">' + html + "</div>";
      }
    });
  }

  function loadQuickPresets() {
    if (!isAdmin || !document.getElementById("quick-presets")) return;
    get("/presets").then((data) => {
      const pinned = (data || []).filter((p) => p.pinned).slice(0, 6);
      if (pinned.length === 0) {
        document.getElementById("quick-presets").innerHTML = "";
        return;
      }
      document.getElementById("quick-presets").innerHTML =
        '<p class="section h2" style="margin-bottom:0.5rem">Rychlé presety</p>' +
        pinned
          .map(
            (p) =>
              `<button class="quick-preset-btn" data-preset='${JSON.stringify(p).replace(/'/g, "&#39;")}'>${esc(p.name)} ${p.startTime}–${p.endTime}</button>`
          )
          .join("");
      document.querySelectorAll(".quick-preset-btn").forEach((btn) => {
        btn.addEventListener("click", () => {
          const p = JSON.parse(btn.dataset.preset.replace(/&#39;/g, "'"));
          document.getElementById("shift-date").value = fmtDate(new Date());
          setTimeToSelects("shift-start", p.startTime || "08:00");
          setTimeToSelects("shift-end", p.endTime || "14:00");
          const branchId = p.branchId;
          if (branchId) {
            document.getElementById("shift-branch").value = branchId;
            loadEmployeesForBranch(branchId).then(() => {
              document.getElementById("shift-employee").value = employees[0]?.id || "";
            });
          }
          openModal("modal-shift");
        });
      });
    });
  }

  function loadEmployeesForBranch(branchId) {
    return get("/employees?branchId=" + branchId).then((data) => {
      employees = data;
      const sel = document.getElementById("shift-employee");
      if (!sel) return;
      sel.innerHTML = data.map((e) => `<option value="${e.id}">${esc(e.name)}</option>`).join("");
      return data;
    });
  }

  // Calendar – 1 request per month via /api/calendar/month
  let calView = "month";
  let calStart = (() => { const d = new Date(); d.setDate(1); return d; })();
  let calMonthCache = null; // { month, months, branchId, data }

  function getCalMonth(d) {
    return d.getFullYear() + "-" + String(d.getMonth() + 1).padStart(2, "0");
  }
  function getCalBranchId() {
    const sel = document.getElementById("cal-branch");
    const val = sel?.value?.trim();
    if (isAdmin && (!val || val === "") && branches.length > 0) return String(branches[0].id);
    return (val && isAdmin) ? String(val) : null;
  }
  function loadCalendarMonth(monthStr, branchId) {
    const url = "/calendar/month?month=" + encodeURIComponent(monthStr) + (branchId ? "&branchId=" + encodeURIComponent(String(branchId)) : "") + "&_=" + Date.now();
    return get(url, { cache: "no-store" });
  }

  function renderCalendar() {
    const rangeEl = document.getElementById("cal-range");
    const headerEl = document.getElementById("cal-week-header");
    const gridEl = document.getElementById("calendar-grid");
    if (!gridEl) return;
    const today = fmtDate(new Date());
    let branchId = getCalBranchId();
    if (isAdmin && branches.length > 0 && (!branchId || branchId === "")) {
      branchId = String(branches[0].id);
      const sel = document.getElementById("cal-branch");
      if (sel) { sel.value = branchId; sel.style.display = ""; }
    }

    const monthStr = getCalMonth(calStart);
    let needMonths = [monthStr];
    if (calView === "week") {
      const endDate = addDays(new Date(calStart.getTime()), 6);
      const endMonth = getCalMonth(endDate);
      if (endMonth !== monthStr) needMonths = [monthStr, endMonth].sort();
    } else if (calView === "day") {
      needMonths = [monthStr];
    }

    const cacheOk = calMonthCache && (calMonthCache.month === monthStr || (calMonthCache.months && needMonths.every((m) => calMonthCache.months?.includes(m)))) && (calMonthCache.branchId || "") === (branchId || "");

    const doRender = (data) => {
      const shifts = data.shifts || [];
      const coverage = data.coverage || {};
      const openTime = data.openTime || "08:00";
      const closeTime = data.closeTime || "20:00";
      const byDate = {};
      shifts.forEach((s) => {
        if (!byDate[s.date]) byDate[s.date] = [];
        byDate[s.date].push(s);
      });
      const firstDate = data.firstDate || monthStr + "-01";
      const lastDate = data.lastDate;

      if (calView === "month") {
        if (rangeEl) rangeEl.textContent = (MONTH_NAMES[(parseInt(monthStr.slice(5), 10) || 1) - 1] || "") + " " + monthStr.slice(0, 4);
        const first = new Date(firstDate);
        const last = new Date(lastDate);
        const startPad = (first.getDay() + 6) % 7;
        const totalDays = Math.round((last - first) / 86400000) + 1;
        const cells = startPad + totalDays;
        const rows = Math.ceil(cells / 7);
        const legendEl = document.getElementById("cal-legend");
        if (legendEl) legendEl.innerHTML = `<span class="cal-legend-dot cal-covered"></span> Pokryto <span class="cal-legend-dot cal-gap"></span> Nepokryto${openTime && closeTime ? `<span class="cal-hours"> · Otevírací doba ${openTime}–${closeTime}</span>` : ""}`;
        if (headerEl) {
          headerEl.style.display = "grid";
          headerEl.style.gridTemplateColumns = "repeat(7, 1fr)";
          headerEl.innerHTML = ["Po", "Út", "St", "Čt", "Pá", "So", "Ne"].map((d) => {
            const hoursSpan = (openTime && closeTime) ? `<span class="cal-day-hours">${openTime}–${closeTime}</span>` : "";
            return `<div class="cal-day-head"><span class="cal-day-name">${d}</span>${hoursSpan}</div>`;
          }).join("");
        }
        gridEl.style.gridTemplateColumns = "repeat(7, 1fr)";
        let html = "";
        for (let i = 0; i < rows * 7; i++) {
          const dayNum = i - startPad + 1;
          const dateStr = dayNum >= 1 && dayNum <= totalDays ? (monthStr + "-" + String(dayNum).padStart(2, "0")) : "";
          const list = dateStr ? (byDate[dateStr] || []) : [];
          const isToday = dateStr === today;
          const dayLabel = dateStr ? new Date(dateStr).getDate() : "";
          const covered = dateStr ? !!coverage[dateStr] : null;
          const shiftBorder = (s) => (s?.employeeColor && /^#[0-9a-fA-F]{6}$/.test(s.employeeColor) ? `border-left:3px solid ${s.employeeColor}` : "");
          const calEditBtn = (s) => isAdmin ? ` <button class="btn btn-sm btn-secondary" style="padding:0.1rem 0.25rem;font-size:0.65rem" onclick="window.editShift('${s.id}','${s.date}','${s.startTime}','${s.endTime}','${s.employeeId || ""}','${s.branchId || ""}')" title="Upravit">✎</button>` : "";
          let cls = dateStr ? "cal-day" : "cal-day cal-day-other";
          if (dateStr && covered !== null) cls += covered ? " cal-covered" : " cal-gap";
          if (isToday) cls += " today";
          const dropAttr = (dateStr && isAdmin && branchId) ? ` data-cal-date="${dateStr}" data-drop-zone` : "";
          html += `<div class="${cls}"${dropAttr}>
            <div class="cal-day-num">${dayLabel}</div>
            <div class="cal-shifts">${list.map((s) => `<div class="cal-shift" style="${shiftBorder(s)}"><span class="cal-shift-time">${s.startTime}–${s.endTime}</span><span class="cal-shift-name">${esc(s.employeeName || "Směna")}</span>${calEditBtn(s)}</div>`).join("") || (dateStr ? '<p class="cal-empty">—</p>' : "")}</div>
          </div>`;
        }
        gridEl.innerHTML = html;
      } else {
        const legendEl = document.getElementById("cal-legend");
        if (legendEl) legendEl.innerHTML = `<span class="cal-legend-dot cal-covered"></span> Pokryto <span class="cal-legend-dot cal-gap"></span> Nepokryto${openTime && closeTime ? `<span class="cal-hours"> · ${openTime}–${closeTime}</span>` : ""}`;
        const days = calView === "week" ? 7 : 1;
        const from = fmtDate(calStart);
        const to = calView === "week" ? fmtDate(addDays(new Date(calStart.getTime()), 6)) : from;
        if (rangeEl) rangeEl.textContent = calView === "week" ? fmtDateDisplay(from) + " – " + fmtDateDisplay(to) : fmtDateDisplay(from);
        if (headerEl) {
          headerEl.style.display = calView === "week" ? "grid" : "none";
          headerEl.style.gridTemplateColumns = calView === "week" ? "repeat(7, 1fr)" : "";
          headerEl.innerHTML = calView === "week" ? Array.from({ length: 7 }, (_, i) => {
            const d = addDays(new Date(calStart.getTime()), i);
            const ds = fmtDate(d);
            const hoursSpan = (openTime && closeTime) ? `<span class="cal-day-hours">${openTime}–${closeTime}</span>` : "";
            return `<div class="cal-day-head ${ds === today ? "today" : ""}"><span class="cal-day-name">${d.toLocaleDateString("cs-CZ", { weekday: "narrow" })}</span><span class="cal-day-num">${d.getDate()}</span>${hoursSpan}</div>`;
          }).join("") : "";
        }
        gridEl.style.gridTemplateColumns = calView === "week" ? "repeat(7, 1fr)" : "1fr";
        let html = "";
        for (let i = 0; i < days; i++) {
          const d = addDays(new Date(calStart.getTime()), i);
          const dateStr = fmtDate(d);
          const list = byDate[dateStr] || [];
          const isToday = dateStr === today;
          const covered = !!coverage[dateStr];
          const shiftBorder = (s) => (s?.employeeColor && /^#[0-9a-fA-F]{6}$/.test(s.employeeColor) ? `border-left:3px solid ${s.employeeColor}` : "");
          const calEditBtn = (s) => isAdmin ? ` <button class="btn btn-sm btn-secondary" style="padding:0.1rem 0.25rem;font-size:0.65rem" onclick="window.editShift('${s.id}','${s.date}','${s.startTime}','${s.endTime}','${s.employeeId || ""}','${s.branchId || ""}')" title="Upravit">✎</button>` : "";
          const dropAttr = (isAdmin && branchId) ? ` data-cal-date="${dateStr}" data-drop-zone` : "";
          let cls = "cal-day";
          if (covered) cls += " cal-covered";
          else cls += " cal-gap";
          if (isToday) cls += " today";
          html += `<div class="${cls}"${dropAttr}>
            <div class="cal-day-label">${d.toLocaleDateString("cs-CZ", { weekday: "short", day: "numeric" })}</div>
            <div class="cal-shifts">${list.map((s) => `<div class="cal-shift" style="${shiftBorder(s)}"><span class="cal-shift-time">${s.startTime}–${s.endTime}</span><span class="cal-shift-name">${esc(s.employeeName || "Směna")}</span>${calEditBtn(s)}</div>`).join("") || '<p class="cal-empty">—</p>'}</div>
          </div>`;
        }
        gridEl.innerHTML = html;
      }
      // Zaměstnanci pro drag & drop (pouze admin + vybraná pobočka)
      const empWrap = document.getElementById("cal-employees");
      const empList = document.getElementById("cal-employees-list");
      if (empWrap && empList) {
        const emps = data.employees || [];
        if (isAdmin && branchId && emps.length) {
          empWrap.style.display = "flex";
          empList.innerHTML = emps.map((e) => {
            const c = (e.color && /^#[0-9a-fA-F]{6}$/.test(e.color)) ? e.color : "#2563eb";
            return `<span class="cal-employee-chip" draggable="true" data-employee-id="${e.id}" data-employee-name="${esc(e.name)}" data-employee-color="${c}" style="border-left:3px solid ${c}">${esc(e.name)}</span>`;
          }).join("");
          initCalDragDrop(branchId, data.presets || [], data.employees || []);
        } else {
          empWrap.style.display = "none";
        }
      }
    };

    if (cacheOk && calMonthCache.data) {
      doRender(calMonthCache.data);
      return;
    }
    gridEl.innerHTML = '<p class="empty">Načítám kalendář…</p>';
    Promise.all(needMonths.map((m) => loadCalendarMonth(m, branchId))).then((results) => {
      const mergedCoverage = Object.assign({}, ...(results.map((r) => r.coverage || {})));
      const merged = {
        month: needMonths[0],
        months: needMonths,
        firstDate: results[0]?.firstDate,
        lastDate: results[results.length - 1]?.lastDate || results[0]?.lastDate,
        shifts: results.flatMap((r) => r.shifts || []),
        employees: results[0]?.employees || [],
        presets: results[0]?.presets || [],
        coverage: mergedCoverage,
        openTime: results[0]?.openTime,
        closeTime: results[0]?.closeTime,
      };
      calMonthCache = { month: monthStr, months: needMonths, branchId: branchId || "", data: merged };
      doRender(merged);
    }).catch((err) => {
      gridEl.innerHTML = '<p class="empty">' + (err?.error ? esc(err.error) : "Chyba načtení kalendáře.") + '</p>';
    });
  }
  document.querySelectorAll("[data-cal-view]").forEach((btn) => {
    btn.addEventListener("click", () => {
      calView = btn.dataset.calView;
      document.querySelectorAll(".cal-tab").forEach((b) => b.classList.toggle("active", b.dataset.calView === calView));
      if (calView === "month") {
        calStart = new Date(calStart.getFullYear(), calStart.getMonth(), 1);
      } else if (calView === "week") {
        calStart = startOfWeek(new Date(calStart.getTime()));
      } else {
        calStart = new Date(calStart.getFullYear(), calStart.getMonth(), Math.min(15, new Date(calStart.getFullYear(), calStart.getMonth() + 1, 0).getDate()));
      }
      renderCalendar();
    });
  });
  document.getElementById("cal-prev")?.addEventListener("click", () => {
    if (calView === "month") {
      calStart = new Date(calStart.getFullYear(), calStart.getMonth() - 1, 1);
    } else {
      calStart = addDays(calStart, calView === "week" ? -7 : -1);
      if (calView === "week") calStart = startOfWeek(calStart);
    }
    renderCalendar();
  });
  document.getElementById("cal-next")?.addEventListener("click", () => {
    if (calView === "month") {
      calStart = new Date(calStart.getFullYear(), calStart.getMonth() + 1, 1);
    } else {
      calStart = addDays(calStart, calView === "week" ? 7 : 1);
      if (calView === "week") calStart = startOfWeek(calStart);
    }
    renderCalendar();
  });
  document.getElementById("cal-today")?.addEventListener("click", () => {
    const now = new Date();
    if (calView === "month") calStart = new Date(now.getFullYear(), now.getMonth(), 1);
    else if (calView === "week") calStart = startOfWeek(now);
    else calStart = now;
    renderCalendar();
  });
  function initCalDragDrop(branchId, presets, employees) {
    const chips = document.querySelectorAll(".cal-employee-chip");
    const zones = document.querySelectorAll("[data-drop-zone]");
    chips.forEach((chip) => {
      chip.removeEventListener("dragstart", chip._calDragStart);
      chip.removeEventListener("click", chip._calChipClick);
      chip._calDragStart = (e) => {
        e.dataTransfer.setData("text/plain", JSON.stringify({
          employeeId: chip.dataset.employeeId,
          employeeName: chip.dataset.employeeName
        }));
        e.dataTransfer.effectAllowed = "copy";
        chip.classList.add("dragging");
      };
      chip._calChipClick = () => {
        if (chip.dataset._justDragged === "1") return;
        const empId = chip.dataset.employeeId;
        if (!empId || !branchId) return;
        const today = fmtDate(new Date());
        openShiftModalForDrop(today, empId, branchId, presets, employees);
      };
      chip.addEventListener("dragstart", chip._calDragStart);
      chip.addEventListener("dragend", () => {
        chip.classList.remove("dragging");
        chip.dataset._justDragged = "1";
        setTimeout(() => delete chip.dataset._justDragged, 100);
      });
      chip.addEventListener("click", chip._calChipClick);
    });
    zones.forEach((zone) => {
      zone.removeEventListener("dragover", zone._calDragOver);
      zone.removeEventListener("drop", zone._calDrop);
      zone._calDragOver = (e) => {
        e.preventDefault();
        e.dataTransfer.dropEffect = "copy";
        zone.classList.add("droppable");
      };
      zone._calDrop = (e) => {
        e.preventDefault();
        zone.classList.remove("droppable");
        let payload;
        try { payload = JSON.parse(e.dataTransfer.getData("text/plain")); } catch (_) { return; }
        const employeeId = payload?.employeeId;
        const dateStr = zone.dataset.calDate;
        if (!employeeId || !dateStr) return;
        openShiftModalForDrop(dateStr, employeeId, branchId, presets, employees);
      };
      zone.addEventListener("dragover", zone._calDragOver);
      zone.addEventListener("drop", zone._calDrop);
      zone.addEventListener("dragleave", () => zone.classList.remove("droppable"));
    });
  }
  function openShiftModalForDrop(dateStr, employeeId, branchId, presets, employees) {
    document.getElementById("modal-shift-title").textContent = "Přidat směnu";
    document.getElementById("shift-id").value = "";
    const delBtn = document.getElementById("btn-delete-shift");
    if (delBtn) delBtn.style.display = "none";
    document.getElementById("shift-employee-id").value = employeeId;
    document.getElementById("shift-date").value = dateStr;
    document.getElementById("shift-branch").value = branchId;
    const empSel = document.getElementById("shift-employee");
    if (empSel && employees?.length) {
      empSel.innerHTML = employees.map((e) => `<option value="${e.id}">${esc(e.name)}</option>`).join("");
      empSel.value = employeeId;
    }
    const p = (presets && presets.length) ? presets[0] : null;
    setTimeToSelects("shift-start", p?.startTime || "08:00");
    setTimeToSelects("shift-end", p?.endTime || "14:00");
    openModal("modal-shift");
  }

  document.getElementById("cal-branch")?.addEventListener("change", () => {
    calMonthCache = null;
    renderCalendar();
  });
  document.querySelectorAll(".cal-tab").forEach((b) => b.classList.toggle("active", b.dataset.calView === calView));

  // Hours
  function loadHours() {
    const from = document.getElementById("hours-from")?.value;
    const to = document.getElementById("hours-to")?.value;
    const bid = document.getElementById("hours-branch")?.value;
    if (!from || !to) {
      document.getElementById("hours-table").innerHTML = '<p class="empty">Vyberte rozsah datumů.</p>';
      document.getElementById("btn-export-hours")?.style.setProperty("display", "none");
      return;
    }
    if (isFullAdmin && !bid) {
      document.getElementById("hours-table").innerHTML = '<p class="empty">Vyberte pobočku a rozsah datumů.</p>';
      document.getElementById("btn-export-hours")?.style.setProperty("display", "none");
      return;
    }
    document.getElementById("hours-table").innerHTML = '<div class="skeleton-wrapper"><div class="skeleton skeleton-text" style="width:60%"></div><div class="skeleton skeleton-card"></div><div class="skeleton skeleton-card"></div><div class="skeleton skeleton-card"></div><div class="skeleton skeleton-card"></div></div>';
    const useOverview = isAccountant;
    const path = useOverview ? `/stats/hours-overview?from=${from}&to=${to}` : (isAdmin ? `/stats/hours?branchId=${bid}&from=${from}&to=${to}` : `/stats/hours?from=${from}&to=${to}`);
    get(path)
      .then((data) => {
        const rows = useOverview ? (data.rows || []) : (Array.isArray(data) ? data : []);
        if (!rows.length) {
          document.getElementById("hours-table").innerHTML = '<p class="empty">V zadaném období nejsou žádné směny.</p>';
          document.getElementById("btn-export-hours")?.style.setProperty("display", "none");
          return;
        }
        const exportBtn = document.getElementById("btn-export-hours");
        if (exportBtn) {
          if (useOverview) {
            exportBtn.style.display = "inline-flex";
            exportBtn.textContent = "Export CSV";
            exportBtn.onclick = () => triggerDownload(`/api/export/hours-overview?from=${from}&to=${to}`);
          } else if (isFullAdmin) {
            exportBtn.style.display = "inline-flex";
            exportBtn.textContent = "Export CSV";
            exportBtn.onclick = () => triggerDownload(`/api/export/hours?branchId=${bid}&from=${from}&to=${to}`);
          } else {
            exportBtn.style.display = "none";
          }
        }
        if (useOverview) {
          const totalPay = rows.reduce((sum, r) => sum + (r.estimatedPay || 0), 0);
          const totalHours = rows.reduce((sum, r) => sum + (r.minutes || 0), 0);
          const th = Math.floor(totalHours / 60);
          const tm = totalHours % 60;
          const totalHoursStr = tm ? `${th}:${String(tm).padStart(2, "0")}` : String(th);
          const byBranch = {};
          rows.forEach((r) => {
            const b = r.branchName || "—";
            if (!byBranch[b]) byBranch[b] = [];
            byBranch[b].push(r);
          });
          const branchCards = Object.entries(byBranch).sort((a, b) => a[0].localeCompare(b[0])).map(([branchName, branchRows]) => {
            const branchHours = branchRows.reduce((s, r) => s + (r.minutes || 0), 0);
            const bh = Math.floor(branchHours / 60);
            const bm = branchHours % 60;
            const branchHoursStr = bm ? `${bh}:${String(bm).padStart(2, "0")}` : String(bh);
            const branchPay = branchRows.reduce((s, r) => s + (r.estimatedPay || 0), 0);
            const rowsHtml = branchRows.map((r) => {
              const rate = r.hourlyRate != null ? r.hourlyRate + " Kč" : "—";
              const pay = r.estimatedPay != null ? r.estimatedPay.toLocaleString("cs-CZ") + " Kč" : "—";
              return `<tr><td>${esc(r.name)}</td><td style="text-align:right;color:var(--blue);font-weight:500">${r.hoursFormatted || 0}</td><td style="text-align:right">${rate}</td><td style="text-align:right;font-weight:600;color:var(--emerald)">${pay}</td></tr>`;
            }).join("");
            return `<div class="hours-branch-card card mb-4">
              <div class="hours-branch-header">
                <span class="badge badge-branch">${esc(branchName)}</span>
                <span class="hours-branch-totals">${branchHoursStr} h · ${branchPay.toLocaleString("cs-CZ")} Kč</span>
              </div>
              <table class="hours-overview-table"><thead><tr><th>Zaměstnanec</th><th style="text-align:right">Hodiny</th><th style="text-align:right">Sazba (Kč/h)</th><th style="text-align:right">Orientační plat (Kč)</th></tr></thead><tbody>${rowsHtml}</tbody></table>
            </div>`;
          }).join("");
          document.getElementById("hours-table").innerHTML =
            `<div class="hours-overview-summary mb-4">
              <div class="summary-row"><span>Celkem poboček:</span><strong>${Object.keys(byBranch).length}</strong></div>
              <div class="summary-row"><span>Celkové hodiny:</span><strong style="color:var(--blue)">${totalHoursStr} h</strong></div>
              <div class="summary-row"><span>Celkový orientační plat:</span><strong style="color:var(--emerald)">${totalPay.toLocaleString("cs-CZ")} Kč</strong></div>
            </div>` + branchCards;
        } else {
          document.getElementById("hours-table").innerHTML =
            "<table><thead><tr><th>Zaměstnanec</th><th style='text-align:right'>Hodiny</th><th style='text-align:right'>Sazba (Kč/h)</th><th style='text-align:right'>Orientační plat (Kč)</th></tr></thead><tbody>" +
            rows.map((r) => {
              const rate = r.hourlyRate != null ? r.hourlyRate + " Kč" : "—";
              const pay = r.estimatedPay != null ? r.estimatedPay.toLocaleString("cs-CZ") + " Kč" : "—";
              return `<tr><td>${esc(r.name)}</td><td style="text-align:right;color:var(--blue)">${r.hoursFormatted || 0}</td><td style="text-align:right">${rate}</td><td style="text-align:right;font-weight:600;color:var(--emerald)">${pay}</td></tr>`;
            }).join("") +
            "</tbody></table>";
        }
      })
      .catch(() => {
        document.getElementById("hours-table").innerHTML = '<p class="empty">Chyba načtení.</p>';
      });
  }

  // Who with whom
  function loadWho() {
    const bid = document.getElementById("who-branch")?.value;
    const from = document.getElementById("who-from")?.value;
    const to = document.getElementById("who-to")?.value;
    if (!bid || !from || !to) {
      document.getElementById("who-content").innerHTML = '<p class="empty">Vyberte pobočku a rozsah datumů.</p>';
      return;
    }
    document.getElementById("who-content").innerHTML = '<div class="skeleton-wrapper"><div class="skeleton skeleton-text" style="width:50%"></div><div class="skeleton skeleton-card"></div><div class="skeleton skeleton-card"></div></div>';
    fetch(`/api/stats/who-with-whom?branchId=${bid}&from=${from}&to=${to}`, { credentials: "include" })
      .then((r) => r.json())
      .then((data) => {
        const byDate = data.byDate || {};
        const dates = Object.keys(byDate).sort();
        if (dates.length === 0) {
          document.getElementById("who-content").innerHTML = '<p class="empty">V zadaném období nejsou žádné směny.</p>';
          return;
        }
        document.getElementById("who-content").innerHTML = dates
          .map(
            (date) =>
              `<div class="card mb-4">
            <h3 style="margin:0 0 0.75rem;font-size:1rem">${new Date(date).toLocaleDateString("cs-CZ", { weekday: "long", day: "numeric", month: "numeric", year: "numeric" })}</h3>
            <table>
              <thead><tr><th>Zaměstnanec</th><th>Čas</th><th>S kým</th></tr></thead>
              <tbody>
                ${(byDate[date] || [])
                  .map(
                    (s) =>
                      `<tr><td>${esc(s.employeeName)}</td><td>${s.startTime}–${s.endTime}</td><td>${s.overlapsWith?.length ? esc(s.overlapsWith.join(", ")) : "—"}</td></tr>`
                  )
                  .join("")}
              </tbody>
            </table>
          </div>`
          )
          .join("");
      })
      .catch(() => {
        document.getElementById("who-content").innerHTML = '<p class="empty">Chyba načtení.</p>';
      });
  }

  // Init date inputs
  const now = new Date();
  const start = startOfWeek(now);
  const monthStart = fmtDate(startOfMonth(now));
  const monthEnd = fmtDate(endOfMonth(now));
  const hoursFromEl = document.getElementById("hours-from");
  const hoursToEl = document.getElementById("hours-to");
  if (hoursFromEl) { hoursFromEl.value = monthStart; hoursFromEl.setAttribute("value", monthStart); }
  if (hoursToEl) { hoursToEl.value = monthEnd; hoursToEl.setAttribute("value", monthEnd); }
  document.getElementById("who-from")?.setAttribute("value", fmtDate(addDays(start, -7)));
  document.getElementById("who-to")?.setAttribute("value", fmtDate(now));

  // Modals
  function openModal(id) {
    document.getElementById(id)?.classList.remove("hidden");
  }
  function closeModal(id) {
    document.getElementById(id)?.classList.add("hidden");
  }
  document.querySelectorAll("[data-close]").forEach((btn) => {
    btn.addEventListener("click", () => btn.closest(".modal")?.classList.add("hidden"));
  });
  document.querySelectorAll(".modal").forEach((m) => {
    m.addEventListener("click", (e) => {
      if (e.target === m) m.classList.add("hidden");
    });
  });

  document.getElementById("btn-add-request")?.addEventListener("click", () => {
    document.getElementById("form-request").reset();
    document.getElementById("request-type").value = "leave";
    document.getElementById("request-leave-fields").style.display = "block";
    document.getElementById("request-late-fields").style.display = "none";
    document.getElementById("request-swap-fields").style.display = "none";
    document.getElementById("request-cover-fields").style.display = "none";
    initTimePickers();
    document.getElementById("request-date-from").value = fmtDate(new Date());
    document.getElementById("request-date-to").value = fmtDate(new Date());
    document.getElementById("request-shift-date").value = fmtDate(new Date());
    openModal("modal-request");
  });
  let todayShiftsForLate = [];
  document.getElementById("btn-quick-late")?.addEventListener("click", () => {
    document.getElementById("form-quick-late").reset();
    initTimePickers();
    document.getElementById("quick-late-mode").value = "arrived";
    document.getElementById("quick-late-arrived-fields").style.display = "block";
    document.getElementById("quick-late-willbe-fields").style.display = "none";
    document.querySelectorAll("[data-late-mode]").forEach((b) => { b.classList.remove("active"); if (b.dataset.lateMode === "arrived") b.classList.add("active"); });
    const today = fmtDate(new Date());
    document.getElementById("quick-late-shift").innerHTML = '<option value="">— načítám —</option>';
    openModal("modal-quick-late");
    get(`/my-shifts?from=${today}&to=${today}`).then((shifts) => {
      todayShiftsForLate = shifts || [];
      const sel = document.getElementById("quick-late-shift");
      if (todayShiftsForLate.length === 0) {
        sel.innerHTML = '<option value="">Dnes nemáte směnu</option>';
        return;
      }
      sel.innerHTML = todayShiftsForLate.map((s) => `<option value="${s.id}" data-date="${s.date}" data-start="${s.startTime}">${fmtDateDisplay(s.date)} ${s.startTime}–${s.endTime}</option>`).join("");
      const first = todayShiftsForLate[0];
      sel.value = first.id;
      document.getElementById("quick-late-planned-display").textContent = first.startTime;
      const now = new Date();
      setTimeToSelects("quick-late-actual", `${String(now.getHours()).padStart(2, "0")}:${String(Math.floor(now.getMinutes() / 15) * 15).padStart(2, "0")}`);
      updateLateMinutes();
    });
  });
  document.querySelectorAll("[data-late-mode]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const mode = btn.dataset.lateMode;
      document.getElementById("quick-late-mode").value = mode;
      document.querySelectorAll("[data-late-mode]").forEach((b) => b.classList.toggle("active", b.dataset.lateMode === mode));
      document.getElementById("quick-late-arrived-fields").style.display = mode === "arrived" ? "block" : "none";
      document.getElementById("quick-late-willbe-fields").style.display = mode === "willbe" ? "block" : "none";
    });
  });
  document.getElementById("quick-late-shift")?.addEventListener("change", function () {
    const opt = this.options[this.selectedIndex];
    if (opt?.dataset?.start) document.getElementById("quick-late-planned-display").textContent = opt.dataset.start;
    updateLateMinutes();
  });
  document.getElementById("btn-late-now")?.addEventListener("click", () => {
    const now = new Date();
    setTimeToSelects("quick-late-actual", `${String(now.getHours()).padStart(2, "0")}:${String(Math.floor(now.getMinutes() / 15) * 15).padStart(2, "0")}`);
    updateLateMinutes();
  });
  ["quick-late-actual-h", "quick-late-actual-m"].forEach((id) => {
    document.getElementById(id)?.addEventListener("change", updateLateMinutes);
  });
  function updateLateMinutes() {
    const opt = document.getElementById("quick-late-shift")?.selectedOptions?.[0];
    if (!opt?.dataset?.start) return;
    const planned = opt.dataset.start;
    const actual = getTimeFromSelects("quick-late-actual");
    const [ph, pm] = planned.split(":").map(Number);
    const [ah, am] = actual.split(":").map(Number);
    const plannedM = ph * 60 + pm;
    const actualM = ah * 60 + am;
    const mins = Math.max(0, actualM - plannedM);
    document.getElementById("quick-late-result").style.display = "block";
    document.getElementById("quick-late-mins").textContent = mins;
  }
  document.getElementById("btn-quick-absent")?.addEventListener("click", () => {
    if (!confirm("Odeslat žádost o volno na dnešek? Nemůžete přijít na směnu.")) return;
    const today = fmtDate(new Date());
    post("/requests", { type: "leave", dateFrom: today, dateTo: today })
      .then(() => {
        toast("Žádost odeslána ✓", "success");
        loadRequests();
      })
      .catch((err) => toast(err.error || "Chyba", "error"));
  });
  document.getElementById("form-quick-late")?.addEventListener("submit", (e) => {
    e.preventDefault();
    const opt = document.getElementById("quick-late-shift")?.selectedOptions?.[0];
    const mode = document.getElementById("quick-late-mode")?.value;
    if (!opt?.value) {
      toast("Vyberte směnu.", "error");
      return;
    }
    const shiftId = opt.value;
    const shiftDate = opt.dataset.date;
    const plannedTime = opt.dataset.start;
    const data = { type: "late", shiftDate, shiftId, note: document.getElementById("quick-late-note").value };
    if (mode === "arrived") {
      data.plannedTime = plannedTime;
      data.actualTime = getTimeFromSelects("quick-late-actual");
    }
    post("/requests", data)
      .then(() => {
        toast("Zpoždění nahlášeno ✓", "success");
        closeModal("modal-quick-late");
        refreshAllViews();
        loadRequests();
      })
      .catch((err) => toast(err.error || "Chyba", "error"));
  });
  document.getElementById("request-type")?.addEventListener("change", function () {
    const v = this.value;
    document.getElementById("request-leave-fields").style.display = v === "leave" ? "block" : "none";
    document.getElementById("request-late-fields").style.display = v === "late" ? "block" : "none";
    document.getElementById("request-swap-fields").style.display = v === "swap" ? "block" : "none";
    document.getElementById("request-cover-fields").style.display = v === "cover" ? "block" : "none";
    if (v === "swap" || v === "cover") loadRequestShiftSelects();
  });
  function loadRequestShiftSelects() {
    const now = new Date();
    const from = fmtDate(now);
    const to = fmtDate(addDays(now, 60));
    const opts = '<option value="">— vyberte —</option>';
    get(`/my-branch-shifts?from=${from}&to=${to}`).then((shifts) => {
      if (!Array.isArray(shifts)) return;
      const myOpts = shifts.filter((s) => s.isMine).map((s) => `<option value="${s.id}">${s.date} ${s.startTime}–${s.endTime}</option>`).join("");
      const otherOpts = shifts.filter((s) => !s.isMine).map((s) => `<option value="${s.id}">${s.employeeName} – ${s.date} ${s.startTime}–${s.endTime}</option>`).join("");
      const swapMy = document.getElementById("request-swap-my-shift");
      const swapOther = document.getElementById("request-swap-other-shift");
      const cover = document.getElementById("request-cover-shift");
      if (swapMy) swapMy.innerHTML = opts + myOpts;
      if (swapOther) swapOther.innerHTML = opts + otherOpts;
      if (cover) cover.innerHTML = opts + myOpts;
    }).catch(() => {
      const errOpt = '<option value="">— chyba načtení —</option>';
      const swapMy = document.getElementById("request-swap-my-shift");
      const swapOther = document.getElementById("request-swap-other-shift");
      const cover = document.getElementById("request-cover-shift");
      if (swapMy) swapMy.innerHTML = errOpt;
      if (swapOther) swapOther.innerHTML = errOpt;
      if (cover) cover.innerHTML = errOpt;
    });
  }
  document.getElementById("form-request")?.addEventListener("submit", (e) => {
    e.preventDefault();
    const type = document.getElementById("request-type").value;
    const data = { type, note: document.getElementById("request-note").value };
    if (type === "leave") {
      data.dateFrom = document.getElementById("request-date-from").value;
      data.dateTo = document.getElementById("request-date-to").value;
      if (!data.dateFrom) { toast("Vyberte datum od.", "error"); return; }
    } else if (type === "swap") {
      data.shiftId = document.getElementById("request-swap-my-shift").value;
      data.otherShiftId = document.getElementById("request-swap-other-shift").value;
      if (!data.shiftId || !data.otherShiftId) { toast("Vyberte obě směny.", "error"); return; }
    } else if (type === "cover") {
      data.shiftId = document.getElementById("request-cover-shift").value;
      if (!data.shiftId) { toast("Vyberte směnu.", "error"); return; }
    } else {
      data.shiftDate = document.getElementById("request-shift-date").value;
      data.plannedTime = getTimeFromSelects("request-planned");
      data.actualTime = getTimeFromSelects("request-actual");
      if (!data.shiftDate) { toast("Vyberte datum směny.", "error"); return; }
    }
    post("/requests", data)
      .then(() => {
        toast("Žádost odeslána ✓", "success");
        closeModal("modal-request");
        loadRequests();
        if (typeof refreshAllViews === "function") refreshAllViews();
      })
      .catch((err) => toast(err?.error || "Chyba odeslání žádosti", "error"));
  });

  document.body.addEventListener("click", (e) => {
    const btn = e.target.closest("[data-create-access]");
    if (!btn || !isAdmin) return;
    const eid = btn.dataset.empId;
    const defaultEmail = btn.dataset.empEmail || "";
    const email = prompt("E-mail pro přihlášení:", defaultEmail);
    if (!email) return;
    const password = prompt("Heslo (min. 6 znaků):", "");
    if (!password || password.length < 6) {
      toast("Heslo musí mít alespoň 6 znaků.", "error");
      return;
    }
    post("/employees/" + eid + "/create-access", { email: email.trim(), password })
      .then(() => toast("Přístup vytvořen – zaměstnanec se může přihlásit ✓", "success"))
      .catch((err) => toast(err.error || "Chyba", "error"));
  });

  // Add / Edit / Delete Shift
  window.delShift = (id) => {
    if (!confirm("Opravdu smazat tuto směnu?")) return;
    del("/shifts/" + id).then(() => {
      toast("Směna smazána", "default");
      refreshAllViews();
    }).catch((err) => toast(err?.error || "Chyba", "error"));
  };
  window.editShift = (id, date, startTime, endTime, empId, branchId) => {
    document.getElementById("modal-shift-title").textContent = "Upravit směnu";
    document.getElementById("shift-id").value = id;
    const delBtn = document.getElementById("btn-delete-shift");
    if (delBtn) { delBtn.style.display = isAdmin ? "inline-flex" : "none"; }
    document.getElementById("shift-date").value = date;
    setTimeToSelects("shift-start", startTime || "08:00");
    setTimeToSelects("shift-end", endTime || "14:00");
    setShiftMobileTime(startTime || "08:00", endTime || "14:00");
    const brId = branchId || branches[0]?.id;
    document.getElementById("shift-branch").value = brId;
    loadEmployeesForBranch(brId).then(() => {
      document.getElementById("shift-employee").value = empId || employees[0]?.id || "";
    });
    openModal("modal-shift");
  };
  document.getElementById("btn-delete-shift")?.addEventListener("click", () => {
    const id = document.getElementById("shift-id").value;
    if (id) window.delShift(id);
    closeModal("modal-shift");
  });
  document.getElementById("btn-send-schedule-email")?.addEventListener("click", () => {
    const now = new Date();
    const fromEl = document.getElementById("schedule-email-from");
    const toEl = document.getElementById("schedule-email-to");
    if (fromEl) fromEl.value = fmtDate(startOfMonth(now));
    if (toEl) toEl.value = fmtDate(endOfMonth(now));
    openModal("modal-send-schedule");
  });
  document.getElementById("form-send-schedule")?.addEventListener("submit", (e) => {
    e.preventDefault();
    const fromVal = document.getElementById("schedule-email-from")?.value;
    const toVal = document.getElementById("schedule-email-to")?.value;
    if (!fromVal || !toVal) {
      toast("Vyberte rozsah datumů.", "error");
      return;
    }
    const btn = e.target.querySelector('button[type="submit"]');
    if (btn) btn.disabled = true;
    post("/send-schedule-emails", { from: fromVal, to: toVal })
      .then((data) => {
        toast(data.message || "E-maily odeslány ✓", "success");
        closeModal("modal-send-schedule");
      })
      .catch((err) => toast(err?.error || "Chyba", "error"))
      .finally(() => { if (btn) btn.disabled = false; });
  });

  // Kopírování rozpisu – vyplnění datumů a souhrnů v kartách
  function updateCopySummaries() {
    const srcFrom = document.getElementById("copy-source-from")?.value;
    const srcTo = document.getElementById("copy-source-to")?.value;
    const tgtFrom = document.getElementById("copy-target-from")?.value;
    const tgtTo = document.getElementById("copy-target-to")?.value;
    const srcEl = document.getElementById("copy-source-summary");
    const tgtEl = document.getElementById("copy-target-summary");
    if (srcEl) srcEl.textContent = srcFrom && srcTo ? fmtDateDisplay(srcFrom) + " – " + fmtDateDisplay(srcTo) : "";
    if (tgtEl) tgtEl.textContent = tgtFrom && tgtTo ? fmtDateDisplay(tgtFrom) + " – " + fmtDateDisplay(tgtTo) : "";
  }
  function fillCopyDates(sourceStart, sourceEnd, targetStart, targetEnd) {
    document.getElementById("copy-source-from").value = fmtDate(sourceStart);
    document.getElementById("copy-source-to").value = fmtDate(sourceEnd);
    document.getElementById("copy-target-from").value = fmtDate(targetStart);
    document.getElementById("copy-target-to").value = fmtDate(targetEnd);
    document.getElementById("copy-preview").style.display = "none";
    document.getElementById("copy-conflicts").style.display = "none";
    updateCopySummaries();
    toast("Období vyplněno – zvolte pobočku a klikněte Náhled nebo Kopírovat.", "default");
  }
  document.getElementById("btn-copy-shifts")?.addEventListener("click", () => {
    const sel = document.getElementById("copy-branch");
    sel.innerHTML = branches.map((b) => `<option value="${b.id}">${esc(b.name)}</option>`).join("");
    if (branches.length === 1) sel.value = branches[0].id;
    const now = new Date();
    const weekStart = startOfWeek(now);
    const weekEnd = addDays(new Date(weekStart.getTime()), 6);
    const nextWeekStart = addDays(new Date(weekStart.getTime()), 7);
    const nextWeekEnd = addDays(new Date(weekStart.getTime()), 13);
    fillCopyDates(weekStart, weekEnd, nextWeekStart, nextWeekEnd);
    document.getElementById("copy-preserve-assignment").checked = true;
    document.getElementById("copy-default-emp-row").style.display = "none";
    document.getElementById("copy-skip-conflicts").checked = false;
    const bid = sel.value;
    if (bid) get("/employees?branchId=" + bid).then((emps) => {
      const empSel = document.getElementById("copy-default-employee");
      empSel.innerHTML = '<option value="">— vyberte —</option>' + (emps || []).map((e) => `<option value="${e.id}">${esc(e.name)}</option>`).join("");
    });
    openModal("modal-copy-shifts");
  });
  document.getElementById("copy-preset-this-to-next")?.addEventListener("click", () => {
    const now = new Date();
    const weekStart = startOfWeek(now);
    const weekEnd = addDays(new Date(weekStart.getTime()), 6);
    const nextWeekStart = addDays(new Date(weekStart.getTime()), 7);
    const nextWeekEnd = addDays(new Date(weekStart.getTime()), 13);
    fillCopyDates(weekStart, weekEnd, nextWeekStart, nextWeekEnd);
  });
  document.getElementById("copy-preset-last-to-this")?.addEventListener("click", () => {
    const now = new Date();
    const weekStart = startOfWeek(now);
    const lastWeekStart = addDays(new Date(weekStart.getTime()), -7);
    const lastWeekEnd = addDays(new Date(weekStart.getTime()), -1);
    fillCopyDates(lastWeekStart, lastWeekEnd, weekStart, addDays(new Date(weekStart.getTime()), 6));
  });
  document.getElementById("copy-preset-next-week")?.addEventListener("click", () => {
    const now = new Date();
    const weekStart = startOfWeek(now);
    const nextWeekStart = addDays(new Date(weekStart.getTime()), 7);
    const nextWeekEnd = addDays(new Date(weekStart.getTime()), 13);
    const weekAfterStart = addDays(new Date(weekStart.getTime()), 14);
    const weekAfterEnd = addDays(new Date(weekStart.getTime()), 20);
    fillCopyDates(nextWeekStart, nextWeekEnd, weekAfterStart, weekAfterEnd);
  });
  document.getElementById("copy-preset-month")?.addEventListener("click", () => {
    const now = new Date();
    const y = now.getFullYear(), m = now.getMonth();
    const firstThis = new Date(y, m, 1);
    const lastThis = new Date(y, m + 1, 0);
    const firstNext = new Date(y, m + 1, 1);
    const lastNext = new Date(y, m + 2, 0);
    const daysThis = (lastThis.getTime() - firstThis.getTime()) / (24 * 60 * 60 * 1000) + 1;
    const daysNext = (lastNext.getTime() - firstNext.getTime()) / (24 * 60 * 60 * 1000) + 1;
    const days = Math.min(daysThis, daysNext);
    const targetEnd = addDays(new Date(firstNext.getTime()), days - 1);
    fillCopyDates(firstThis, addDays(new Date(firstThis.getTime()), days - 1), firstNext, targetEnd);
  });
  ["copy-source-from", "copy-source-to", "copy-target-from", "copy-target-to"].forEach((id) => {
    document.getElementById(id)?.addEventListener("change", updateCopySummaries);
  });
  document.getElementById("copy-preserve-assignment")?.addEventListener("change", function() {
    const row = document.getElementById("copy-default-emp-row");
    row.style.display = this.checked ? "none" : "block";
  });
  function loadCopyPreview() {
    const branchId = document.getElementById("copy-branch")?.value;
    const preserve = document.getElementById("copy-preserve-assignment")?.checked;
    const defaultEmpId = document.getElementById("copy-default-employee")?.value;
    const skipConflicts = document.getElementById("copy-skip-conflicts")?.checked;
    if (!branchId) return Promise.resolve();
    const data = {
      sourceRange: { from: document.getElementById("copy-source-from").value, to: document.getElementById("copy-source-to").value },
      targetRange: { from: document.getElementById("copy-target-from").value, to: document.getElementById("copy-target-to").value },
      branchId: parseInt(branchId),
      preserveAssignment: preserve,
      defaultEmployeeId: preserve ? null : (defaultEmpId ? parseInt(defaultEmpId) : null),
      onConflict: skipConflicts ? "skip" : "abort",
      preview: true,
    };
    return post("/shifts/copy", data);
  }
  document.getElementById("btn-copy-preview")?.addEventListener("click", () => {
    const branchId = document.getElementById("copy-branch")?.value;
    const preserve = document.getElementById("copy-preserve-assignment")?.checked;
    if (!preserve && !document.getElementById("copy-default-employee")?.value) {
      toast("Vyberte výchozího zaměstnance.", "error");
      return;
    }
    loadCopyPreview()
      .then((r) => {
        const prev = document.getElementById("copy-preview");
        const conf = document.getElementById("copy-conflicts");
        prev.style.display = "";
        prev.classList.toggle("has-conflicts", !!(r.conflicts && r.conflicts.length > 0));
        conf.style.display = "none";
        const total = r.sourceShiftCount ?? (r.count + (r.conflicts?.length || 0));
        let msg = "";
        if (r.conflicts && r.conflicts.length > 0) {
          if (r.count > 0) {
            msg = `Z ${total} zdrojových směn vytvoříme ${r.count} směn. ${r.skippedCount} konfliktů (${r.conflicts.length} přeskočeno).`;
          } else {
            msg = `Všechny směny kolidují – ${r.conflicts.length} konfliktů. Zapněte „Při konfliktu přeskočit“ pro částečnou kopii.`;
          }
          conf.style.display = "";
          conf.innerHTML = "<strong>Konflikty:</strong><ul class=\"copy-conflicts-list\">" +
            r.conflicts.map((c) => `<li>${esc(c.employeeName)} · ${fmtDateDisplay(c.date)} ${c.startTime}–${c.endTime}${c.existingShift ? ` (kříží s ${c.existingShift.startTime}–${c.existingShift.endTime})` : ""}${c.reason ? " – " + esc(c.reason) : ""}</li>`).join("") + "</ul>";
        } else {
          msg = total > 0 ? `Z ${total} zdrojových směn vytvoříme ${r.count} směn.` : "Žádné směny ve zdrojovém období.";
        }
        prev.innerHTML = "<span class=\"copy-preview-count\">" + esc(msg) + "</span>";
      })
      .catch((err) => {
        const msg = err?.error?.message || err?.error || err?.message || "Chyba";
        toast(msg, "error");
      });
  });
  document.getElementById("copy-branch")?.addEventListener("change", function() {
    const branchId = this.value;
    if (!branchId) return;
    get("/employees?branchId=" + branchId).then((emps) => {
      const sel = document.getElementById("copy-default-employee");
      sel.innerHTML = '<option value="">— vyberte —</option>' + (emps || []).map((e) => `<option value="${e.id}">${esc(e.name)}</option>`).join("");
    });
  });
  document.getElementById("form-copy-shifts")?.addEventListener("submit", (e) => {
    e.preventDefault();
    const branchId = document.getElementById("copy-branch")?.value;
    const preserve = document.getElementById("copy-preserve-assignment")?.checked;
    const defaultEmpId = document.getElementById("copy-default-employee")?.value;
    const skipConflicts = document.getElementById("copy-skip-conflicts")?.checked;
    if (!preserve && !defaultEmpId) {
      toast("Vyberte výchozího zaměstnance.", "error");
      return;
    }
    const data = {
      sourceRange: { from: document.getElementById("copy-source-from").value, to: document.getElementById("copy-source-to").value },
      targetRange: { from: document.getElementById("copy-target-from").value, to: document.getElementById("copy-target-to").value },
      branchId: parseInt(branchId),
      preserveAssignment: preserve,
      defaultEmployeeId: preserve ? null : (defaultEmpId ? parseInt(defaultEmpId) : null),
      onConflict: skipConflicts ? "skip" : "abort",
    };
    const btn = document.getElementById("btn-copy-submit");
    if (btn) btn.disabled = true;
    post("/shifts/copy", data)
      .then((r) => {
        toast(r.message || "Rozpis zkopírován ✓", "success");
        closeModal("modal-copy-shifts");
        refreshAllViews();
      })
      .catch((err) => {
        const e = err?.error;
        const details = e?.details?.conflicts;
        if (details && Array.isArray(details)) {
          toast(e?.message || "Konflikty – zapněte „Při konfliktu přeskočit“ pro částečnou kopii.", "error");
          const conf = document.getElementById("copy-conflicts");
          conf.style.display = "";
          conf.innerHTML = "<strong>Konflikty:</strong><ul class=\"copy-conflicts-list\">" +
            details.map((c) => `<li>${esc(c.employeeName)} · ${fmtDateDisplay(c.date)} ${c.startTime}–${c.endTime}${c.existingShift ? ` (kříží s ${c.existingShift.startTime}–${c.existingShift.endTime})` : ""}</li>`).join("") + "</ul>";
        } else {
          toast(e?.message || err?.message || "Chyba", "error");
        }
      })
      .finally(() => { if (btn) btn.disabled = false; });
  });

  document.getElementById("btn-add-shift")?.addEventListener("click", () => {
    document.getElementById("modal-shift-title").textContent = "Přidat směnu";
    document.getElementById("form-shift").reset();
    document.getElementById("shift-id").value = "";
    const delBtn = document.getElementById("btn-delete-shift");
    if (delBtn) delBtn.style.display = "none";
    document.getElementById("shift-employee-id").value = "";
    document.getElementById("shift-date").value = fmtDate(new Date());
    setTimeToSelects("shift-start", "08:00");
    setTimeToSelects("shift-end", "14:00");
    setShiftMobileTime("08:00", "14:00");
    if (branches.length === 1) document.getElementById("shift-branch").value = branches[0].id;
    loadEmployeesForBranch(document.getElementById("shift-branch").value || branches[0]?.id).then(() => {
      if (employees.length > 0) document.getElementById("shift-employee").value = employees[0].id;
    });
    openModal("modal-shift");
  });
  document.getElementById("shift-branch")?.addEventListener("change", function () {
    loadEmployeesForBranch(this.value);
  });
  document.getElementById("form-shift")?.addEventListener("submit", (e) => {
    e.preventDefault();
    const shiftId = document.getElementById("shift-id").value;
    const branchId = document.getElementById("shift-branch").value;
    const empId = document.getElementById("shift-employee").value;
    if (!empId || !branchId) {
      toast("Vyberte pobočku a zaměstnance.", "error");
      return;
    }
    const times = getShiftTimeFromForm();
    const data = {
      employeeId: parseInt(empId),
      branchId: parseInt(branchId),
      date: document.getElementById("shift-date").value,
      startTime: times.startTime,
      endTime: times.endTime,
    };
    (shiftId ? patch("/shifts/" + shiftId, data) : post("/shifts", data))
      .then(() => {
        toast(shiftId ? "Směna upravena ✓" : "Směna přidána ✓", "success");
        closeModal("modal-shift");
        refreshAllViews();
      })
      .catch((err) => {
        const msg = (err?.error && typeof err.error === "object" && err.error?.message) ? err.error.message : (err?.error || err?.message || "Chyba");
        toast(msg, "error");
      });
  });

  // Branch weekend checkbox
  document.getElementById("branch-use-weekend")?.addEventListener("change", (e) => {
    const row = document.getElementById("branch-weekend-row");
    if (row) row.style.display = e.target.checked ? "flex" : "none";
  });

  // Branch CRUD
  document.getElementById("btn-add-branch")?.addEventListener("click", () => {
    document.getElementById("modal-branch-title").textContent = "Nová pobočka";
    document.getElementById("form-branch").reset();
    document.getElementById("branch-id").value = "";
    setTimeToSelects("branch-open", "08:00");
    setTimeToSelects("branch-close", "20:00");
    setTimeToSelects("branch-open-weekend", "09:00");
    setTimeToSelects("branch-close-weekend", "17:00");
    document.getElementById("branch-use-weekend").checked = false;
    document.getElementById("branch-weekend-row").style.display = "none";
    openModal("modal-branch");
  });
  document.getElementById("form-branch")?.addEventListener("submit", (e) => {
    e.preventDefault();
    const id = document.getElementById("branch-id").value;
    const rate = document.getElementById("branch-hourly-rate").value;
    const useWeekend = document.getElementById("branch-use-weekend")?.checked;
    const data = {
      name: document.getElementById("branch-name").value,
      address: document.getElementById("branch-address").value,
      defaultHourlyRate: rate ? parseFloat(rate) : null,
      openTime: getTimeFromSelects("branch-open") || "08:00",
      closeTime: getTimeFromSelects("branch-close") || "20:00",
    };
    if (useWeekend) {
      data.openTimeWeekend = getTimeFromSelects("branch-open-weekend") || "09:00";
      data.closeTimeWeekend = getTimeFromSelects("branch-close-weekend") || "17:00";
    } else {
      data.openTimeWeekend = null;
      data.closeTimeWeekend = null;
    }
    (id ? patch("/branches/" + id, data) : post("/branches", data))
      .then(() => {
        closeModal("modal-branch");
        loadBranches().then(refreshAllViews);
      })
      .catch((err) => toast(err.error || "Chyba", "error"));
  });
  window.editBranch = (id) => {
    const b = branches.find((x) => x.id === id);
    if (!b) return;
    document.getElementById("modal-branch-title").textContent = "Upravit pobočku";
    document.getElementById("branch-id").value = id;
    document.getElementById("branch-name").value = b.name;
    document.getElementById("branch-address").value = b.address || "";
    document.getElementById("branch-hourly-rate").value = b.defaultHourlyRate ?? "";
    setTimeToSelects("branch-open", b.openTime || "08:00");
    setTimeToSelects("branch-close", b.closeTime || "20:00");
    const useWeekend = !!(b.openTimeWeekend && b.closeTimeWeekend);
    document.getElementById("branch-use-weekend").checked = useWeekend;
    document.getElementById("branch-weekend-row").style.display = useWeekend ? "flex" : "none";
    if (useWeekend) {
      setTimeToSelects("branch-open-weekend", b.openTimeWeekend || "09:00");
      setTimeToSelects("branch-close-weekend", b.closeTimeWeekend || "17:00");
    }
    openModal("modal-branch");
  };
  window.delBranch = (id) => {
    if (!confirm("Opravdu smazat?")) return;
    del("/branches/" + id).then(() => loadBranches().then(refreshAllViews));
  };

  // Employee CRUD
  function syncEmployeeColorInputs() {
    const picker = document.getElementById("employee-color");
    const text = document.getElementById("employee-color-text");
    if (!picker || !text) return;
    picker.addEventListener("input", () => { text.value = picker.value; });
    text.addEventListener("input", () => {
      const v = text.value.trim();
      if (/^#[0-9a-fA-F]{6}$/.test(v)) picker.value = v;
    });
  }
  syncEmployeeColorInputs();

  document.getElementById("btn-add-employee")?.addEventListener("click", () => {
    document.getElementById("modal-employee-title").textContent = "Nový zaměstnanec";
    document.getElementById("form-employee").reset();
    document.getElementById("employee-id").value = "";
    document.getElementById("employee-color").value = "#2563eb";
    document.getElementById("employee-color-text").value = "";
    document.getElementById("employee-branch").innerHTML =
      '<option value="">— vyberte —</option>' + branches.map((b) => `<option value="${b.id}">${esc(b.name)}</option>`).join("");
    if (branches.length === 1) document.getElementById("employee-branch").value = branches[0].id;
    openModal("modal-employee");
  });
  document.getElementById("form-employee")?.addEventListener("submit", (e) => {
    e.preventDefault();
    const id = document.getElementById("employee-id").value;
    const rate = document.getElementById("employee-hourly-rate").value;
    const colorVal = document.getElementById("employee-color-text")?.value?.trim() || document.getElementById("employee-color")?.value || null;
    const data = {
      name: document.getElementById("employee-name").value,
      email: document.getElementById("employee-email").value,
      branchId: document.getElementById("employee-branch").value,
      hourlyRate: rate ? parseFloat(rate) : null,
      color: colorVal || null,
    };
    (id ? patch("/employees/" + id, data) : post("/employees", data))
      .then(() => {
        closeModal("modal-employee");
        refreshAllViews();
      })
      .catch((err) => toast(err.error || "Chyba", "error"));
  });
  window.editEmployee = (id) => {
    const e = employees.find((x) => x.id === id);
    if (!e) return;
    document.getElementById("modal-employee-title").textContent = "Upravit zaměstnance";
    document.getElementById("employee-id").value = id;
    document.getElementById("employee-name").value = e.name;
    document.getElementById("employee-email").value = e.email || "";
    document.getElementById("employee-hourly-rate").value = e.hourlyRate ?? "";
    const col = (e.color && /^#[0-9a-fA-F]{6}$/.test(e.color)) ? e.color : "#2563eb";
    document.getElementById("employee-color").value = col;
    document.getElementById("employee-color-text").value = e.color || "";
    document.getElementById("employee-branch").innerHTML = branches.map((b) => `<option value="${b.id}" ${b.id == e.branch?.id ? "selected" : ""}>${esc(b.name)}</option>`).join("");
    openModal("modal-employee");
  };
  window.delEmployee = (id) => {
    if (!confirm("Opravdu smazat?")) return;
    del("/employees/" + id).then(refreshAllViews);
  };

  // Preset CRUD
  document.getElementById("btn-add-preset")?.addEventListener("click", () => {
    document.getElementById("modal-preset-title").textContent = "Nový preset";
    document.getElementById("form-preset").reset();
    initTimePickers();
    document.getElementById("preset-id").value = "";
    setTimeToSelects("preset-start", "08:00");
    setTimeToSelects("preset-end", "14:00");
    document.getElementById("preset-pinned").checked = false;
    const sel = document.getElementById("preset-form-branch");
    sel.innerHTML = branches.map((b) => `<option value="${b.id}">${esc(b.name)}</option>`).join("");
    if (branches.length === 1) sel.value = branches[0].id;
    openModal("modal-preset");
  });
  document.getElementById("form-preset")?.addEventListener("submit", (e) => {
    e.preventDefault();
    const branchId = document.getElementById("preset-form-branch")?.value || document.getElementById("preset-branch")?.value || branches[0]?.id;
    if (!branchId) {
      toast("Vyberte pobočku.", "error");
      return;
    }
    const id = document.getElementById("preset-id").value;
    const data = {
      branchId: parseInt(branchId),
      name: document.getElementById("preset-name").value,
      startTime: getTimeFromSelects("preset-start"),
      endTime: getTimeFromSelects("preset-end"),
      pinned: document.getElementById("preset-pinned").checked,
    };
    (id ? patch("/presets/" + id, data) : post("/presets", data))
      .then(() => {
        closeModal("modal-preset");
        refreshAllViews();
      })
      .catch((err) => toast(err.error || "Chyba", "error"));
  });
  window.editPreset = (id) => {
    const p = presets.find((x) => x.id == id);
    if (!p) return;
    document.getElementById("modal-preset-title").textContent = "Upravit preset";
    document.getElementById("preset-id").value = id;
    document.getElementById("preset-name").value = p.name;
    setTimeToSelects("preset-start", p.startTime || "08:00");
    setTimeToSelects("preset-end", p.endTime || "14:00");
    document.getElementById("preset-pinned").checked = p.pinned;
    setTimeToSelects("preset-start", p.startTime || "08:00");
    setTimeToSelects("preset-end", p.endTime || "14:00");
    const sel = document.getElementById("preset-form-branch");
    sel.innerHTML = branches.map((b) => `<option value="${b.id}" ${b.id == p.branchId ? "selected" : ""}>${esc(b.name)}</option>`).join("");
    openModal("modal-preset");
  };
  window.delPreset = (id) => {
    if (!confirm("Opravdu smazat?")) return;
    del("/presets/" + id).then(refreshAllViews);
  };

  document.getElementById("branch-filter")?.addEventListener("change", loadEmployees);
  document.getElementById("preset-branch")?.addEventListener("change", loadPresets);
  document.getElementById("btn-load-hours")?.addEventListener("click", loadHours);
  document.getElementById("btn-load-who")?.addEventListener("click", loadWho);

  function initExport() {
    const sel = document.getElementById("export-branch");
    if (sel && isAdmin && sel.options.length <= 1) {
      sel.innerHTML = '<option value="">— vyberte —</option>' + branches.map((b) => `<option value="${b.id}">${esc(b.name)}</option>`).join("");
      if (branches.length === 1) sel.value = branches[0].id;
    }
    const now = new Date();
    const monthStart = fmtDate(startOfMonth(now));
    const monthEnd = fmtDate(endOfMonth(now));
    const from = document.getElementById("export-from");
    const to = document.getElementById("export-to");
    if (from) from.value = monthStart;
    if (to) to.value = monthEnd;
    get("/me").then((me) => {
      const box = document.getElementById("ical-subscribe-box");
      if (!box) return;
      if (me.icalSubscribeUrl) {
        box.style.display = "block";
        document.getElementById("ical-subscribe-url").value = me.icalSubscribeUrl;
      } else {
        box.innerHTML = "<p class=\"text-muted\">Pro odběr v Apple kalendáři vygenerujte odkaz:</p><button type=\"button\" class=\"btn btn-sm btn-secondary\" id=\"btn-generate-ical\">Vygenerovat odkaz</button>";
        box.style.display = "block";
        document.getElementById("btn-generate-ical")?.addEventListener("click", () => {
          post("/users/me/generate-ical-token", {}).then((d) => {
            box.innerHTML = '<h3 class="section-title" style="font-size:1rem">Odběr kalendáře pro Apple / iOS</h3><p class="text-muted" style="font-size:0.875rem">Na iPhone/iPad: Nastavení → Kalendáře → Přidat účet → Další → Přidejte odběr kalendáře → zadejte URL:</p><div class="flex gap-2 align-center" style="flex-wrap:wrap;margin-top:0.5rem"><input type="text" id="ical-subscribe-url" class="input" readonly style="flex:1;min-width:200px;font-size:0.8rem" value="' + esc(d.icalSubscribeUrl) + '"><button type="button" class="btn btn-sm btn-secondary" id="btn-copy-ical">Kopírovat</button></div>';
            document.getElementById("ical-subscribe-url").value = d.icalSubscribeUrl;
          }).catch((e) => toast(e?.error || "Chyba", "error"));
        });
      }
    });
  }
  document.getElementById("ical-subscribe-box")?.addEventListener("click", (e) => {
    if (e.target.id === "btn-copy-ical") {
      const url = document.getElementById("ical-subscribe-url")?.value;
      if (url && navigator.clipboard) { navigator.clipboard.writeText(url); toast("Zkopírováno ✓", "success"); }
    }
  });
  function triggerDownload(url, filename) {
    const a = document.createElement("a");
    a.href = url;
    a.target = "_blank";
    if (filename) a.download = filename;
    a.rel = "noopener noreferrer";
    a.style.display = "none";
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
  }

  document.getElementById("btn-export-shifts")?.addEventListener("click", function(e) {
    e.preventDefault();
    const bid = document.getElementById("export-branch")?.value;
    const fromVal = document.getElementById("export-from")?.value;
    const toVal = document.getElementById("export-to")?.value;
    if (!bid || !fromVal || !toVal) {
      toast("Vyberte pobočku a datumy.", "error");
      return;
    }
    triggerDownload(`/api/export/shifts?branchId=${bid}&from=${fromVal}&to=${toVal}`);
  });
  document.getElementById("btn-export-hours-csv")?.addEventListener("click", function(e) {
    e.preventDefault();
    const bid = document.getElementById("export-branch")?.value;
    const fromVal = document.getElementById("export-from")?.value;
    const toVal = document.getElementById("export-to")?.value;
    if (!bid || !fromVal || !toVal) {
      toast("Vyberte pobočku a datumy.", "error");
      return;
    }
    triggerDownload(`/api/export/hours?branchId=${bid}&from=${fromVal}&to=${toVal}`);
  });
  document.getElementById("btn-export-pdf")?.addEventListener("click", function(e) {
    e.preventDefault();
    const now = new Date();
    const fromVal = document.getElementById("export-from")?.value || fmtDate(startOfMonth(now));
    const toVal = document.getElementById("export-to")?.value || fmtDate(endOfMonth(now));
    triggerDownload(`/export/pdf?from=${fromVal}&to=${toVal}`);
  });
  document.getElementById("btn-export-ical")?.addEventListener("click", function(e) {
    e.preventDefault();
    const now = new Date();
    const fromVal = document.getElementById("export-from")?.value || fmtDate(startOfMonth(now));
    const toVal = document.getElementById("export-to")?.value || fmtDate(endOfMonth(now));
    triggerDownload(`/api/export/ical?from=${fromVal}&to=${toVal}`);
  });

  function esc(s) {
    if (s == null) return "";
    const d = document.createElement("div");
    d.textContent = String(s);
    return d.innerHTML;
  }

  initTimePickers();

  (function () {
    const stored = localStorage.getItem("theme");
    const prefers = window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
    const theme = stored || prefers;
    document.documentElement.setAttribute("data-theme", theme);
    const btn = document.getElementById("theme-toggle");
    if (btn) {
      btn.textContent = theme === "dark" ? "☀️" : "🌙";
      btn.addEventListener("click", () => {
        const next = document.documentElement.getAttribute("data-theme") === "dark" ? "light" : "dark";
        document.documentElement.setAttribute("data-theme", next);
        localStorage.setItem("theme", next);
        btn.textContent = next === "dark" ? "☀️" : "🌙";
      });
    }
  })();

  // Initial load
  get("/me")
    .then((me) => {
      applyRole(me);
      if (isAdmin) {
        document.querySelectorAll(".view").forEach((v) => v.classList.remove("active"));
        document.querySelectorAll(".nav-item").forEach((n) => n.classList.remove("active"));
        const viewParam = (new URLSearchParams(window.location.search)).get("v");
        const allowedViews = ["prehled", "kalendar", "zadosti", "pobocky", "ucetni", "zamestnanci", "presety", "hodiny", "kdo-s-kym", "exporty"];
        const defaultView = (viewParam && allowedViews.includes(viewParam)) ? viewParam : (isAccountant ? "hodiny" : "prehled");
        const defaultViewEl = document.getElementById("view-" + defaultView);
        const defaultNav = document.querySelector('[data-view="' + defaultView + '"]');
        if (defaultViewEl && defaultNav) {
          defaultViewEl.classList.add("active");
          defaultNav.classList.add("active");
          if (defaultView === "prehled") loadOverview();
          if (defaultView === "hodiny") loadHours();
          if (defaultView === "kalendar") renderCalendar();
          if (defaultView === "zadosti") loadRequests();
        }
        if (isAdmin) loadCoverageGrid();
        if (isAdmin) setInterval(loadCoverageGrid, 5 * 60 * 1000);
      }
      if (document.getElementById("view-kalendar")?.classList.contains("active")) renderCalendar();
      if (isAdmin) {
        return get("/branches")
          .then((data) => {
            branches = Array.isArray(data) ? data : [];
            fillBranchSelects();
            if (branches.length > 0) {
              const ids = ["branch-filter", "preset-branch", "hours-branch", "who-branch", "shift-branch", "cal-branch"];
              ids.forEach((id) => {
                const el = document.getElementById(id);
                if (el) el.value = branches[0].id;
              });
            }
            loadEmployees();
            loadPresets();
            if (isAccountant) loadHours();
          })
          .catch((err) => {
            branches = [];
            fillBranchSelects();
            if (isAccountant) loadHours();
            toast(err?.error || "Chyba načtení poboček", "error");
            if (err?._status === 403) refreshRoleOn403();
          });
      } else {
        document.querySelectorAll(".view").forEach((v) => v.classList.remove("active"));
        document.querySelectorAll(".nav-item").forEach((n) => n.classList.remove("active"));
        const viewParam = (new URLSearchParams(window.location.search)).get("v");
        const employeeViews = ["prehled", "kalendar", "zadosti", "hodiny"];
        const startView = (viewParam && employeeViews.includes(viewParam)) ? viewParam : "prehled";
        const viewEl = document.getElementById("view-" + startView);
        const viewNav = document.querySelector('[data-view="' + startView + '"]');
        if (viewEl && viewNav) {
          viewEl.classList.add("active");
          viewNav.classList.add("active");
          if (startView === "prehled") loadPrehledEmployee();
          if (startView === "kalendar") renderCalendar();
          if (startView === "zadosti") loadRequests();
          if (startView === "hodiny") loadHours();
        }
        loadHours();
        loadRequests();
        if (isAccountant) get("/branches").then((d) => { branches = Array.isArray(d) ? d : []; fillBranchSelects(); }).catch(() => {});
      }
    })
    .catch(() => {});
})();
