window.BloomsTabulator = (function () {
  function _csrf() {
    const meta = document.querySelector('meta[name="csrf-token"]');
    return meta ? meta.getAttribute("content") : "";
  }

  function _stateUrl(pageKey) {
    return "/ui/tabulator-state/" + encodeURIComponent(pageKey);
  }

  async function loadState(pageKey) {
    try {
      const res = await fetch(_stateUrl(pageKey), { credentials: "same-origin" });
      if (!res.ok) return null;
      const data = await res.json();
      return data && data.state ? data.state : null;
    } catch (_e) {
      return null;
    }
  }

  async function saveState(pageKey, state) {
    try {
      await fetch(_stateUrl(pageKey), {
        method: "POST",
        credentials: "same-origin",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": _csrf(),
        },
        body: JSON.stringify({ state: state }),
      });
    } catch (_e) {
      // no-op
    }
  }

  function debounce(fn, wait) {
    let t = null;
    return function () {
      const args = arguments;
      clearTimeout(t);
      t = setTimeout(function () {
        fn.apply(null, args);
      }, wait);
    };
  }

  function badge(text, cssClass) {
    return '<span class="badge ' + (cssClass || "text-bg-secondary") + '">' + text + "</span>";
  }

  function statusFormatter(map, fallbackClass) {
    return function (cell) {
      const val = String(cell.getValue() || "");
      const conf = map[val];
      if (!conf) return badge(val || "-", fallbackClass || "text-bg-secondary");
      return badge(conf.label, conf.className);
    };
  }

  function yesNoFormatter(cell) {
    const v = String(cell.getValue() || "").toLowerCase();
    if (v === "ano" || v === "true" || v === "1") return badge("Ano", "text-bg-success");
    if (v === "ne" || v === "false" || v === "0") return badge("Ne", "text-bg-secondary");
    return badge(cell.getValue() || "-", "text-bg-secondary");
  }

  function _applyMobileVisibility(table, fieldsToHide) {
    if (!fieldsToHide || !fieldsToHide.length) return;
    const isMobile = window.innerWidth < 992;
    table.getColumns().forEach(function (col) {
      const field = col.getField ? col.getField() : "";
      if (!field || fieldsToHide.indexOf(field) === -1) return;
      if (isMobile) col.hide();
      else col.show();
    });
  }

  function buildState(table) {
    return {
      sorters: table.getSorters ? table.getSorters() : [],
      filters: table.getFilters ? table.getFilters() : [],
      columns: table.getColumnLayout ? table.getColumnLayout() : [],
    };
  }

  function applyState(table, state) {
    if (!state) return;
    try {
      if (state.columns && table.setColumnLayout) table.setColumnLayout(state.columns);
      if (state.sorters && table.setSort) table.setSort(state.sorters);
      if (state.filters && table.setFilter) table.setFilter(state.filters);
    } catch (_e) {
      // no-op
    }
  }

  async function wire(table, opts) {
    const pageKey = opts.pageKey;
    const state = await loadState(pageKey);
    applyState(table, state);

    const persist = debounce(function () {
      saveState(pageKey, buildState(table));
    }, 500);

    table.on("sortChanged", persist);
    table.on("dataFiltered", persist);
    table.on("columnMoved", function () {
      persist();
      _applyMobileVisibility(table, opts.mobileHideFields || []);
    });
    table.on("columnResized", persist);
    table.on("columnVisibilityChanged", persist);

    if (opts.searchInputId) {
      const input = document.getElementById(opts.searchInputId);
      if (input) {
        input.addEventListener("input", function () {
          const q = input.value || "";
          const fields = opts.quickSearchFields || [];
          if (!q) {
            table.clearFilter(true);
          } else {
            const filters = fields.map(function (f) {
              return { field: f, type: "like", value: q };
            });
            if (filters.length) table.setFilter(filters);
          }
        });
      }
    }

    if (opts.clearBtnId) {
      const clearBtn = document.getElementById(opts.clearBtnId);
      if (clearBtn) {
        clearBtn.addEventListener("click", function () {
          table.clearFilter(true);
          if (opts.searchInputId) {
            const input = document.getElementById(opts.searchInputId);
            if (input) input.value = "";
          }
          persist();
        });
      }
    }

    if (opts.resetBtnId) {
      const resetBtn = document.getElementById(opts.resetBtnId);
      if (resetBtn) {
        resetBtn.addEventListener("click", function () {
          table.clearFilter(true);
          table.clearSort();
          if (table.setColumnLayout && opts.defaultColumnLayout) {
            table.setColumnLayout(opts.defaultColumnLayout);
          }
          saveState(pageKey, null);
          if (opts.searchInputId) {
            const input = document.getElementById(opts.searchInputId);
            if (input) input.value = "";
          }
        });
      }
    }

    if (opts.exportCsvBtnId) {
      const b = document.getElementById(opts.exportCsvBtnId);
      if (b) b.addEventListener("click", function () { table.download("csv", (opts.exportPrefix || "grid") + ".csv"); });
    }
    if (opts.exportXlsxBtnId) {
      const b = document.getElementById(opts.exportXlsxBtnId);
      if (b) b.addEventListener("click", function () { table.download("xlsx", (opts.exportPrefix || "grid") + ".xlsx", { sheetName: "Data" }); });
    }

    _applyMobileVisibility(table, opts.mobileHideFields || []);
    window.addEventListener("resize", debounce(function () {
      _applyMobileVisibility(table, opts.mobileHideFields || []);
    }, 120));
  }

  return {
    wire: wire,
    badge: badge,
    statusFormatter: statusFormatter,
    yesNoFormatter: yesNoFormatter,
  };
})();
