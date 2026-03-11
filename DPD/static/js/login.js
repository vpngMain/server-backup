(function() {
  var form = document.getElementById('login-form');
  if (!form) return;
  form.addEventListener('submit', function(e) {
    var pinEl = document.getElementById('pin');
    if (!pinEl) return;
    var pin = pinEl.value.trim();
    if (!/^\d{4,6}$/.test(pin)) {
      e.preventDefault();
      alert('Zadejte platný PIN (4–6 číslic).');
      pinEl.focus();
      return false;
    }
  });
})();
