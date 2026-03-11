(function() {
  var tbody = document.getElementById('users-tbody');
  var form = document.getElementById('user-form');
  var formTitle = document.getElementById('user-form-title');
  var idInput = document.getElementById('user-id');
  var nameInput = document.getElementById('user-name');
  var branchSelect = document.getElementById('user-branch');
  var roleSelect = document.getElementById('user-role');
  var pinInput = document.getElementById('user-pin');
  var cancelBtn = document.getElementById('user-cancel');
  var messageEl = document.getElementById('user-message');

  function showMessage(text, isError) {
    if (!messageEl) return;
    messageEl.textContent = text;
    messageEl.className = 'message' + (isError ? ' error' : ' success');
  }

  function loadUsers() {
    if (!tbody) return;
    fetch('/api/admin/users')
      .then(function(r) { return r.json(); })
      .then(function(list) {
        if (!list || list.length === 0) {
          tbody.innerHTML = '<tr><td colspan="4">Žádní uživatelé.</td></tr>';
          return;
        }
        tbody.innerHTML = list.map(function(u) {
          var roleLabel = u.role === 'admin' ? 'Admin' : 'Uživatel';
          return '<tr>' +
            '<td>' + (u.name || '') + '</td>' +
            '<td>' + (u.branch_name || '—') + '</td>' +
            '<td>' + roleLabel + '</td>' +
            '<td>' +
            '<button type="button" class="btn btn-small btn-edit-user" data-id="' + u.id + '">Upravit</button> ' +
            '<button type="button" class="btn btn-small btn-delete-user" data-id="' + u.id + '" data-name="' + (u.name || '').replace(/"/g, '&quot;') + '">Smazat</button>' +
            '</td></tr>';
        }).join('');
      })
      .catch(function() {
        tbody.innerHTML = '<tr><td colspan="4">Chyba načtení.</td></tr>';
      });
  }

  function setFormBlank() {
    idInput.value = '';
    nameInput.value = '';
    if (branchSelect) branchSelect.value = '';
    if (roleSelect) roleSelect.value = 'user';
    pinInput.value = '';
    pinInput.placeholder = 'Povinný u nového';
    if (formTitle) formTitle.textContent = 'Přidat uživatele';
    if (cancelBtn) cancelBtn.style.display = 'none';
  }

  if (form) {
    form.addEventListener('submit', function(e) {
      e.preventDefault();
      var id = idInput.value.trim();
      var name = nameInput.value.trim();
      var branchId = branchSelect ? branchSelect.value : '';
      var role = roleSelect ? roleSelect.value : 'user';
      var pin = pinInput.value;
      if (!name) {
        showMessage('Jméno je povinné.', true);
        return;
      }
      if (!id && !pin) {
        showMessage('PIN je povinný u nového uživatele (4–6 číslic).', true);
        return;
      }
      var url = id ? '/api/admin/users/' + id : '/api/admin/users';
      var method = id ? 'PUT' : 'POST';
      var payload = { name: name, branch_id: branchId || null, role: role };
      if (pin) payload.pin = pin;
      fetch(url, {
        method: method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      })
      .then(function(r) { return r.json().then(function(data) { return { ok: r.ok, data: data }; }); })
      .then(function(result) {
        if (result.ok && result.data.ok) {
          showMessage('Uloženo.');
          setFormBlank();
          loadUsers();
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
      var editBtn = ev.target.closest('.btn-edit-user');
      var delBtn = ev.target.closest('.btn-delete-user');
      if (editBtn && editBtn.dataset.id) {
        fetch('/api/admin/users/' + editBtn.dataset.id)
          .then(function(r) { return r.json(); })
          .then(function(res) {
            if (res.ok && res.user) {
              var u = res.user;
              idInput.value = u.id;
              nameInput.value = u.name || '';
              if (branchSelect) branchSelect.value = u.branch_id || '';
              if (roleSelect) roleSelect.value = u.role || 'user';
              pinInput.value = '';
              pinInput.placeholder = 'Nechte prázdné, aby zůstal beze změny';
              formTitle.textContent = 'Upravit uživatele';
              cancelBtn.style.display = 'inline-flex';
            }
          });
      } else if (delBtn && delBtn.dataset.id) {
        if (!confirm('Opravdu smazat uživatele „' + (delBtn.dataset.name || '') + '“?')) return;
        fetch('/api/admin/users/' + delBtn.dataset.id, { method: 'DELETE' })
          .then(function(r) { return r.json(); })
          .then(function(data) {
            if (data.ok) {
              showMessage('Uživatel smazán.');
              setFormBlank();
              loadUsers();
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

  loadUsers();
})();
