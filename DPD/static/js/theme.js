(function() {
  var STORAGE_KEY = 'dpd-theme';
  var el = document.documentElement;

  function getTheme() {
    try {
      return localStorage.getItem(STORAGE_KEY) || 'light';
    } catch (e) {
      return 'light';
    }
  }

  function setTheme(theme) {
    theme = theme === 'dark' ? 'dark' : 'light';
    if (theme === 'dark') el.setAttribute('data-theme', 'dark');
    else el.removeAttribute('data-theme');
    try {
      localStorage.setItem(STORAGE_KEY, theme);
    } catch (e) {}
    var btn = document.getElementById('theme-toggle-btn');
    if (btn) btn.textContent = theme === 'dark' ? 'Světlý režim' : 'Tmavý režim';
  }

  function init() {
    var theme = getTheme();
    if (theme === 'dark') el.setAttribute('data-theme', 'dark');
    else el.removeAttribute('data-theme');
    var btn = document.getElementById('theme-toggle-btn');
    if (btn) {
      btn.textContent = theme === 'dark' ? 'Světlý režim' : 'Tmavý režim';
      btn.addEventListener('click', function() {
        setTheme(getTheme() === 'dark' ? 'light' : 'dark');
      });
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
