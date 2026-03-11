(function() {
  var OBALKA = [5000, 2000, 1000, 500, 200, 100];
  var KASA = [5000, 2000, 1000, 500, 200, 100, 50, 20, 10, 5, 2, 1];

  function getValues(sectionId) {
    var grid = document.getElementById(sectionId);
    if (!grid) return {};
    var out = {};
    grid.querySelectorAll('.denom-input').forEach(function(input) {
    var d = input.getAttribute('data-denom');
    if (d) {
      var n = parseInt(input.value, 10);
      out[d] = isNaN(n) || n < 0 ? 0 : n;
    }
    });
    return out;
  }

  function setTotal(sectionId, denoms, totalElId) {
    var grid = document.getElementById(sectionId);
    var totalEl = document.getElementById(totalElId);
    if (!grid || !totalEl) return;
    var total = 0;
    grid.querySelectorAll('.denom-input').forEach(function(input) {
    var d = input.getAttribute('data-denom');
    var n = parseInt(input.value, 10);
    if (!isNaN(n) && n >= 0) total += n * parseInt(d, 10);
    });
    if (sectionId === 'obalka-grid') totalEl.textContent = 'CELKEM V OBÁLCE: ' + total + ' Kč';
    else totalEl.textContent = 'CELKEM V KASIČCE: ' + total + ' Kč';
  }

  function clampInput(input) {
    var n = parseInt(input.value, 10);
    if (isNaN(n) || n < 0) input.value = 0;
    else input.value = n;
  }

  function bindSection(sectionId, totalElId) {
    var grid = document.getElementById(sectionId);
    if (!grid) return;
    grid.querySelectorAll('.btn-minus').forEach(function(btn) {
    btn.addEventListener('click', function() {
      var d = btn.getAttribute('data-denom');
      var input = grid.querySelector('.denom-input[data-denom="' + d + '"]');
      if (input) {
        var n = parseInt(input.value, 10) || 0;
        input.value = Math.max(0, n - 1);
        setTotal(sectionId, null, totalElId);
      }
    });
    });
    grid.querySelectorAll('.btn-plus').forEach(function(btn) {
    btn.addEventListener('click', function() {
      var d = btn.getAttribute('data-denom');
      var input = grid.querySelector('.denom-input[data-denom="' + d + '"]');
      if (input) {
        var n = parseInt(input.value, 10) || 0;
        input.value = n + 1;
        setTotal(sectionId, null, totalElId);
      }
    });
    });
    grid.querySelectorAll('.denom-input').forEach(function(input) {
    input.addEventListener('focus', function() {
      if (input.value === '0') input.value = '';
    });
    input.addEventListener('blur', function() {
      clampInput(input);
      setTotal(sectionId, null, totalElId);
    });
    input.addEventListener('change', function() {
      clampInput(input);
      setTotal(sectionId, null, totalElId);
    });
    input.addEventListener('input', function() {
      setTotal(sectionId, null, totalElId);
    });
    });
  }

  bindSection('obalka-grid', 'obalka-celkem');
  bindSection('kasa-grid', 'kasa-celkem');

  function loadToday() {
    var url = '/api/entry/today';
    var branchEl = document.getElementById('entry-branch');
    if (branchEl && branchEl.value) {
      url += '?branch_id=' + encodeURIComponent(branchEl.value);
    }
    fetch(url)
      .then(function(r) { return r.json(); })
      .then(function(data) {
        if (!data.ok || !data.entry) return;
        var obalka = data.entry.obalka || {};
        var kasa = data.entry.kasa || {};
        var obalkaGrid = document.getElementById('obalka-grid');
        var kasaGrid = document.getElementById('kasa-grid');
        if (obalkaGrid) {
          obalkaGrid.querySelectorAll('.denom-input').forEach(function(input) {
            var d = input.getAttribute('data-denom');
            if (d && obalka[d] !== undefined) input.value = obalka[d];
          });
        }
        if (kasaGrid) {
          kasaGrid.querySelectorAll('.denom-input').forEach(function(input) {
            var d = input.getAttribute('data-denom');
            if (d && kasa[d] !== undefined) input.value = kasa[d];
          });
        }
        setTotal('obalka-grid', OBALKA, 'obalka-celkem');
        setTotal('kasa-grid', KASA, 'kasa-celkem');
        var kzEl = document.getElementById('k-zaplaceni');
        if (kzEl && data.entry.k_zaplaceni != null) kzEl.value = data.entry.k_zaplaceni;
      })
      .catch(function() {});
  }
  loadToday();
  var branchSelect = document.getElementById('entry-branch');
  if (branchSelect) branchSelect.addEventListener('change', loadToday);

  var btnUlozit = document.getElementById('btn-ulozit');
  var messageEl = document.getElementById('message');
  var btnPrintObalka = document.getElementById('btn-print-obalka');
  if (btnPrintObalka) {
    btnPrintObalka.addEventListener('click', function() {
      var obalka = getValues('obalka-grid');
      var today = new Date();
      var y = today.getFullYear();
      var m = String(today.getMonth() + 1).padStart(2, '0');
      var d = String(today.getDate()).padStart(2, '0');
      var datum = y + '-' + m + '-' + d;
      var printPayload = { obalka: obalka, datum: datum };
      var branchEl = document.getElementById('entry-branch');
      if (branchEl && branchEl.value) printPayload.branch_id = branchEl.value;
      var kzEl = document.getElementById('k-zaplaceni');
      if (kzEl && kzEl.value !== '') printPayload.k_zaplaceni = parseFloat(kzEl.value);
      fetch('/print/obalka', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(printPayload)
      })
      .then(function(r) { return r.text(); })
      .then(function(html) {
        var w = window.open('', '_blank');
        w.document.write(html);
        w.document.close();
        w.onload = function() { w.print(); };
      })
      .catch(function() {
        if (messageEl) {
          messageEl.textContent = 'Chyba při otevírání tisku.';
          messageEl.className = 'message error';
        }
      });
    });
  }

  if (btnUlozit) {
    btnUlozit.addEventListener('click', function() {
      var obalka = getValues('obalka-grid');
      var kasa = getValues('kasa-grid');
      var payload = { obalka: obalka, kasa: kasa };
      var branchEl = document.getElementById('entry-branch');
      if (branchEl && branchEl.value) payload.branch_id = branchEl.value;
      var kzEl = document.getElementById('k-zaplaceni');
      if (kzEl) {
        if (kzEl.value !== '') payload.k_zaplaceni = parseFloat(kzEl.value);
        else payload.k_zaplaceni = null;
      }
      var weekInput = document.getElementById('entry-week');
      if (weekInput && weekInput.value) {
        var match = weekInput.value.match(/^(\d{4})-W(\d{2})$/);
        if (match) {
          var year = parseInt(match[1], 10);
          var week = parseInt(match[2], 10);
          var jan4 = new Date(year, 0, 4);
          var daysToMon = (jan4.getDay() + 6) % 7;
          var mon = new Date(year, 0, 4 - daysToMon + (week - 1) * 7);
          var m = String(mon.getMonth() + 1).padStart(2, '0');
          var d = String(mon.getDate()).padStart(2, '0');
          payload.tyden_zacatek = mon.getFullYear() + '-' + m + '-' + d;
        }
      }
      btnUlozit.disabled = true;
      messageEl.textContent = '';
      messageEl.className = 'message';
      fetch('/api/entry', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      })
      .then(function(r) { return r.json().then(function(data) { return { ok: r.ok, data: data }; }); })
      .then(function(result) {
        btnUlozit.disabled = false;
        if (result.ok && result.data.ok) {
          messageEl.textContent = '\u2713 ' + (result.data.message || 'Data byla uložena.');
          messageEl.className = 'message success';
        } else {
          messageEl.textContent = result.data.error || 'Chyba při ukládání.';
          messageEl.className = 'message error';
        }
      })
      .catch(function() {
        btnUlozit.disabled = false;
        messageEl.textContent = 'Chyba připojení.';
        messageEl.className = 'message error';
      });
    });
  }

  setTotal('obalka-grid', OBALKA, 'obalka-celkem');
  setTotal('kasa-grid', KASA, 'kasa-celkem');
})();
