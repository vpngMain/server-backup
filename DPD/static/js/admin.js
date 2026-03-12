(function() {
  var tbody = document.getElementById('entries-tbody');
  var filterBranch = document.getElementById('filter-branch');
  var filterTyden = document.getElementById('filter-tyden');
  var btnRefresh = document.getElementById('btn-refresh');
  var exportLink = document.getElementById('export-link');
  var viewWeekly = document.getElementById('view-weekly');
  var viewMonthly = document.getElementById('view-monthly');
  var filterMesic = document.getElementById('filter-mesic');
  var btnLoadMonth = document.getElementById('btn-load-month');
  var monthlyContent = document.getElementById('monthly-content');

  var now = new Date();
  if (filterMesic) {
    filterMesic.value = now.getFullYear() + '-' + String(now.getMonth() + 1).padStart(2, '0');
  }

  document.querySelectorAll('.view-tab').forEach(function(tab) {
    tab.addEventListener('click', function() {
      var view = tab.getAttribute('data-view');
      document.querySelectorAll('.view-tab').forEach(function(t) { t.classList.remove('active'); });
      tab.classList.add('active');
      if (view === 'monthly') {
        viewWeekly.style.display = 'none';
        viewMonthly.style.display = 'block';
      } else {
        viewWeekly.style.display = 'block';
        viewMonthly.style.display = 'none';
      }
    });
  });

  function csDate(isoStr) {
    if (!isoStr) return '';
    var parts = String(isoStr).split('-');
    if (parts.length !== 3) return isoStr;
    return parts[2] + '/' + parts[1] + '/' + parts[0].slice(-2);
  }

  function buildParams() {
    var params = [];
    if (filterBranch && filterBranch.value) params.push('branch_id=' + encodeURIComponent(filterBranch.value));
    if (filterTyden && filterTyden.value) params.push('tyden=' + encodeURIComponent(filterTyden.value));
    return params.length ? '?' + params.join('&') : '';
  }

  function updateExportLink() {
    if (exportLink) exportLink.href = '/api/admin/export' + buildParams();
  }

  if (filterBranch) {
    filterBranch.addEventListener('change', function() { updateExportLink(); loadEntries(); });
  }
  if (filterTyden) {
    filterTyden.addEventListener('change', function() { updateExportLink(); loadEntries(); });
  }

  function loadEntries() {
    if (!tbody) return;
    tbody.innerHTML = '<tr><td colspan="7">Načítám…</td></tr>';
    var url = '/api/admin/entries' + buildParams();
    fetch(url)
      .then(function(r) { return r.json(); })
      .then(function(rows) {
        if (!rows || rows.length === 0) {
          tbody.innerHTML = '<tr><td colspan="7">Žádné záznamy.</td></tr>';
          return;
        }
        tbody.innerHTML = rows.map(function(row) {
          var tyden = row.tyden_zacatek && row.tyden_konec
            ? csDate(row.tyden_zacatek) + ' – ' + csDate(row.tyden_konec)
            : '';
          var kzp = row.k_zaplaceni != null ? Number(row.k_zaplaceni) : '—';
          if (typeof kzp === 'number' && kzp % 1 !== 0) kzp = kzp.toFixed(2);
          return '<tr>' +
            '<td>' + csDate(row.datum) + '</td>' +
            '<td>' + tyden + '</td>' +
            '<td>' + (row.pobocka || '') + '</td>' +
            '<td>' + kzp + '</td>' +
            '<td>' + row.obalka_celkem + ' Kč</td>' +
            '<td>' + row.kasa_celkem + ' Kč</td>' +
            '<td><button type="button" class="btn btn-small btn-detail" data-entry-id="' + row.id + '">Detail</button> ' +
            '<button type="button" class="btn btn-small btn-danger btn-delete-entry" data-entry-id="' + row.id + '">Smazat</button></td>' +
            '</tr>';
        }).join('');
      })
      .catch(function() {
        tbody.innerHTML = '<tr><td colspan="7">Chyba načtení.</td></tr>';
      });
    updateExportLink();
  }

  var detailModal = document.getElementById('detail-modal');
  var detailModalBody = document.getElementById('detail-modal-body');
  function showDetail(id) {
    fetch('/api/admin/entries/' + id)
      .then(function(r) { return r.json(); })
      .then(function(data) {
        if (!data.ok || !data.entry) {
          detailModalBody.innerHTML = '<p>Záznam nenalezen.</p>';
        } else {
          var e = data.entry;
          var kzp = e.k_zaplaceni != null ? Number(e.k_zaplaceni) : '—';
          if (typeof kzp === 'number' && kzp % 1 !== 0) kzp = kzp.toFixed(2);
          var obalkaRows = Object.keys(e.obalka || {}).sort(function(a,b){ return parseInt(b,10) - parseInt(a,10); }).map(function(d) {
            return '<tr><td>' + d + ' Kč</td><td>' + (e.obalka[d] || 0) + '</td></tr>';
          }).join('');
          var kasaRows = Object.keys(e.kasa || {}).sort(function(a,b){ return parseInt(b,10) - parseInt(a,10); }).map(function(d) {
            return '<tr><td>' + d + ' Kč</td><td>' + (e.kasa[d] || 0) + '</td></tr>';
          }).join('');
          detailModalBody.innerHTML =
            '<p><strong>Datum:</strong> ' + csDate(e.datum) + '</p>' +
            '<p><strong>Týden:</strong> ' + csDate(e.tyden_zacatek) + ' – ' + csDate(e.tyden_konec) + '</p>' +
            '<p><strong>Datum splatnosti:</strong> ' + csDate(e.datum_splatnosti) + '</p>' +
            '<p><strong>Pobočka:</strong> ' + (e.pobocka || '') + '</p>' +
            '<p><strong>Uživatel:</strong> ' + (e.uzivatel || '') + '</p>' +
            '<p><strong>K zaplacení:</strong> ' + kzp + '</p>' +
            '<h3>Obálka</h3><table class="data-table"><thead><tr><th>Nominál</th><th>Počet</th></tr></thead><tbody>' + obalkaRows + '</tbody></table><p><strong>Celkem obálka:</strong> ' + (e.obalka_celkem || 0) + ' Kč</p>' +
            '<h3>Kasička</h3><table class="data-table"><thead><tr><th>Nominál</th><th>Počet</th></tr></thead><tbody>' + kasaRows + '</tbody></table><p><strong>Celkem kasička:</strong> ' + (e.kasa_celkem || 0) + ' Kč</p>' +
            '<p style="margin-top: 1rem;"><button type="button" class="btn btn-danger btn-delete-entry" data-entry-id="' + e.id + '">Smazat záznam</button></p>';
        }
        if (detailModal) {
          detailModal.classList.add('modal-open');
          detailModal.setAttribute('aria-hidden', 'false');
        }
      })
      .catch(function() {
        detailModalBody.innerHTML = '<p>Chyba načtení.</p>';
        if (detailModal) {
          detailModal.classList.add('modal-open');
          detailModal.setAttribute('aria-hidden', 'false');
        }
      });
  }
  function hideDetail() {
    if (detailModal) {
      detailModal.classList.remove('modal-open');
      detailModal.setAttribute('aria-hidden', 'true');
    }
  }
  if (detailModal) {
    detailModal.querySelector('.modal-backdrop').addEventListener('click', hideDetail);
    detailModal.querySelector('.modal-close').addEventListener('click', hideDetail);
  }

  if (btnRefresh) btnRefresh.addEventListener('click', loadEntries);
  loadEntries();

  function rowHtml(row) {
    var tyden = row.tyden_zacatek && row.tyden_konec
      ? csDate(row.tyden_zacatek) + ' – ' + csDate(row.tyden_konec)
      : '';
    var kzp = row.k_zaplaceni != null ? Number(row.k_zaplaceni) : '—';
    if (typeof kzp === 'number' && kzp % 1 !== 0) kzp = kzp.toFixed(2);
    return '<tr>' +
      '<td>' + csDate(row.datum) + '</td>' +
      '<td>' + tyden + '</td>' +
      '<td>' + kzp + '</td>' +
      '<td>' + row.obalka_celkem + ' Kč</td>' +
      '<td>' + row.kasa_celkem + ' Kč</td>' +
      '<td><button type="button" class="btn btn-small btn-detail" data-entry-id="' + row.id + '">Detail</button> ' +
      '<button type="button" class="btn btn-small btn-danger btn-delete-entry" data-entry-id="' + row.id + '">Smazat</button></td>' +
      '</tr>';
  }

  function deleteEntry(entryId, afterDelete) {
    if (!confirm('Opravdu smazat tento záznam? Tuto akci nelze vrátit zpět.')) return;
    fetch('/api/admin/entries/' + entryId, { method: 'DELETE' })
      .then(function(r) { return r.json().then(function(data) { return { ok: r.ok, data: data }; }); })
      .then(function(result) {
        if (result.ok && result.data.ok) {
          hideDetail();
          if (typeof afterDelete === 'function') afterDelete();
        } else {
          alert(result.data.error || 'Záznam se nepodařilo smazat.');
        }
      })
      .catch(function() { alert('Chyba připojení.'); });
  }

  function loadMonthly() {
    if (!monthlyContent || !filterMesic || !filterMesic.value) return;
    monthlyContent.innerHTML = '<p>Načítám…</p>';
    var url = '/api/admin/entries?mesic=' + encodeURIComponent(filterMesic.value);
    fetch(url)
      .then(function(r) { return r.json(); })
      .then(function(rows) {
        if (!rows || rows.length === 0) {
          monthlyContent.innerHTML = '<p>Žádné záznamy pro zvolený měsíc.</p>';
          return;
        }
        var byBranch = {};
        rows.forEach(function(row) {
          var bid = row.branch_id != null ? row.branch_id : 0;
          var name = row.pobocka || 'Bez pobočky';
          if (!byBranch[bid]) byBranch[bid] = { name: name, rows: [] };
          byBranch[bid].rows.push(row);
        });
        var html = '';
        Object.keys(byBranch).sort(function(a, b) { return (byBranch[a].name || '').localeCompare(byBranch[b].name || ''); }).forEach(function(bid) {
          var block = byBranch[bid];
          html += '<div class="monthly-branch" style="margin-bottom: 2rem;">';
          html += '<h3 style="margin-bottom: 0.5rem;">' + (block.name || '') + '</h3>';
          html += '<table class="data-table"><thead><tr><th>Datum</th><th>Týden</th><th>K zaplacení</th><th>Obálka</th><th>Kasička</th><th></th></tr></thead><tbody>';
          block.rows.forEach(function(row) { html += rowHtml(row); });
          html += '</tbody></table></div>';
        });
        monthlyContent.innerHTML = html;
      })
      .catch(function() {
        monthlyContent.innerHTML = '<p class="message error">Chyba načtení.</p>';
      });
  }

  if (btnLoadMonth) btnLoadMonth.addEventListener('click', loadMonthly);

  document.addEventListener('click', function(ev) {
    var btn = ev.target.closest('.btn-detail');
    if (btn && btn.dataset.entryId) showDetail(btn.dataset.entryId);
    var delBtn = ev.target.closest('.btn-delete-entry');
    if (delBtn && delBtn.dataset.entryId) {
      deleteEntry(delBtn.dataset.entryId, loadEntries);
      if (monthlyContent && monthlyContent.innerHTML && !monthlyContent.innerHTML.includes('Žádné')) {
        loadMonthly();
      }
    }
  });
})();
