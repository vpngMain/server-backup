(function () {
  const APPLE_HINT_KEY = "blooms_ios_install_hint_hidden";

  function isIos() {
    const ua = window.navigator.userAgent || "";
    return /iPhone|iPad|iPod/i.test(ua);
  }

  function isStandalone() {
    return window.matchMedia("(display-mode: standalone)").matches || window.navigator.standalone === true;
  }

  function registerServiceWorker() {
    if (!("serviceWorker" in navigator)) return;
    window.addEventListener("load", function () {
      navigator.serviceWorker.register("/sw.js").catch(function () {
        // no-op: app musí běžet i bez SW
      });
    });
  }

  function ensureIosInstallHint() {
    if (!isIos() || isStandalone()) return;
    if (window.localStorage.getItem(APPLE_HINT_KEY) === "1") return;

    const box = document.createElement("div");
    box.className = "ios-install-hint";
    box.innerHTML =
      '<div class="ios-install-hint__text"><strong>Pro nejlepší zážitek na iPhonu:</strong> otevřete Sdílet a dejte <em>Přidat na plochu</em>.</div>' +
      '<button type="button" class="ios-install-hint__close" aria-label="Zavřít">×</button>';
    document.body.appendChild(box);

    const btn = box.querySelector(".ios-install-hint__close");
    if (btn) {
      btn.addEventListener("click", function () {
        window.localStorage.setItem(APPLE_HINT_KEY, "1");
        box.remove();
      });
    }
  }

  function wireSkeletonForHtmx() {
    if (!window.htmx) return;
    document.body.addEventListener("htmx:beforeRequest", function (evt) {
      const target = evt.detail && evt.detail.target;
      if (!target) return;
      target.classList.add("is-loading");
    });
    document.body.addEventListener("htmx:afterSwap", function (evt) {
      const target = evt.detail && evt.detail.target;
      if (!target) return;
      target.classList.remove("is-loading");
    });
  }

  function showSkeleton(id) {
    const el = document.getElementById(id);
    if (el) el.classList.remove("d-none");
  }

  function hideSkeleton(id) {
    const el = document.getElementById(id);
    if (el) el.classList.add("d-none");
  }

  function deviceBucket() {
    return window.matchMedia("(max-width: 767.98px)").matches ? "mobile" : "desktop";
  }

  function prefKey(pageKey) {
    const uid = (document.body && document.body.getAttribute("data-user-id")) || "anon";
    return "ux_prefs_" + uid + "_" + pageKey + "_" + deviceBucket();
  }

  function loadPrefs(pageKey) {
    try {
      const raw = localStorage.getItem(prefKey(pageKey));
      return raw ? JSON.parse(raw) : {};
    } catch (_e) {
      return {};
    }
  }

  function savePrefs(pageKey, prefs) {
    try {
      localStorage.setItem(prefKey(pageKey), JSON.stringify(prefs || {}));
    } catch (_e) {
      // ignore quota failures
    }
  }

  function applyVisualPrefs(prefs) {
    const root = document.documentElement;
    const density = (prefs && prefs.density) || "normal";
    const font = (prefs && prefs.font) || "normal";
    root.classList.toggle("ux-density-compact", density === "compact");
    root.classList.toggle("ux-font-large", font === "large");
  }

  window.BloomsUX = {
    showSkeleton: showSkeleton,
    hideSkeleton: hideSkeleton,
    deviceBucket: deviceBucket,
    loadPrefs: loadPrefs,
    savePrefs: savePrefs,
    applyVisualPrefs: applyVisualPrefs,
  };

  registerServiceWorker();
  ensureIosInstallHint();
  wireSkeletonForHtmx();
})();
