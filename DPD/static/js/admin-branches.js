(function() {
  var tbody = document.getElementById('branches-tbody');
  var form = document.getElementById('branch-form');
  var formTitle = document.getElementById('form-title');
  var idInput = document.getElementById('branch-id');
  var nameInput = document.getElementById('branch-name');
  var codeInput = document.getElementById('branch-code');
  var cancelBtn = document.getElementById('branch-cancel');
  var messageEl = document.getElementById('branch-message');

  function showMessage(text, isError) {
    if (!messageEl) return;
    messageEl.textContent = text;
    messageEl.className = 'message' + (isError ? ' error' : ' success');
  }

  function loadBranches() {
    if (!tbody) return;
    fetch('/api/admin/branches')
      .then(function(r) { return r.json(); })
      .then(function(list) {
        if (!list || list.length === 0) {
          tbody.innerHTML = '<tr><td colspan="3">Žádné pobočky.</td></tr>';
          return;
        }
        tbody.innerHTML = list.map(function(b) {
          return '<tr>' +
            '<td>' + (b.name || '') + '</td>' +
            '<td>' + (b.code || '') + '</td>' +
            '<td>' +
            '<button type="button" class="btn btn-small btn-edit-branch" data-id="' + b.id + '">Upravit</button> ' +
            '<button type="button" class="btn btn-small btn-delete-branch" data-id="' + b.id + '" data-name="' + (b.name || '').replace(/"/g, '&quot;') + '">Smazat</button>' +
            '</td></tr>';
        }).join('');
      })
      .catch(function() {
        tbody.innerHTML = '<tr><td colspan="3">Chyba načtení.</td></tr>';
      });
  }

  function setFormBlank() {
    idInput.value = '';
    nameInput.value = '';
    codeInput.value = '';
    formTitle.textContent = 'Přidat pobočku';
    if (cancelBtn) cancelBtn.style.display = 'none';
  }

  if (form) {
    form.addEventListener('submit', function(e) {
      e.preventDefault();
      var id = idInput.value.trim();
      var name = nameInput.value.trim();
      var code = codeInput.value.trim();
      if (!name) {
        showMessage('Název je povinný.', true);
        return;
      }
      var url = id ? '/api/admin/branches/' + id : '/api/admin/branches';
      var method = id ? 'PUT' : 'POST';
      fetch(url, {
        method: method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: name, code: code })
      })
      .then(function(r) { return r.json().then(function(data) { return { ok: r.ok, data: data }; }); })
      .then(function(result) {
        if (result.ok && result.data.ok) {
          showMessage('Uloženo.');
          setFormBlank();
          loadBranches();
        } else {
          showMessage(result.data.error || 'Chyba.', true);
        }
      })
      .catch(function() {
        showMessage('Chyba připojení.', true);
      });
    });
  }

  if (cancelBtn) cancelBtn.addEventListener('click', setFormBlank);

  if (tbody) {
    tbody.addEventListener('click', function(ev) {
      var editBtn = ev.target.closest('.btn-edit-branch');
      var delBtn = ev.target.closest('.btn-delete-branch');
      if (editBtn && editBtn.dataset.id) {
        fetch('/api/admin/branches/' + editBtn.dataset.id)
          .then(function(r) { return r.json(); })
          .then(function(res) {
            if (res.ok && res.branch) {
              var b = res.branch;
              idInput.value = b.id;
              nameInput.value = b.name || '';
              codeInput.value = b.code || '';
              formTitle.textContent = 'Upravit pobočku';
              cancelBtn.style.display = 'inline-flex';
            }
          });
      } else if (delBtn && delBtn.dataset.id) {
        if (!confirm('Opravdu smazat pobočku „' + (delBtn.dataset.name || '') + '“?')) return;
        fetch('/api/admin/branches/' + delBtn.dataset.id, { method: 'DELETE' })
          .then(function(r) { return r.json(); })
          .then(function(data) {
            if (data.ok) {
              showMessage('Pobočka smazána.');
              setFormBlank();
              loadBranches();
            } else {
              showMessage(data.error || 'Chyba.', true);
            }
          })
          .catch(function() {
            showMessage('Chyba připojení.', true);
          });
      }
    });
  }

  loadBranches();
})();
