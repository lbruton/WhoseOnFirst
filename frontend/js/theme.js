// Part A: Synchronous IIFE — runs before body renders to prevent FOUC
(function () {
  try {
    var saved = localStorage.getItem('wof_theme');
    var prefersDark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
    var theme = saved || (prefersDark ? 'dark' : 'light');
    document.documentElement.setAttribute('data-bs-theme', theme);
  } catch (e) {
    // localStorage unavailable (private mode) — default to light
    document.documentElement.setAttribute('data-bs-theme', 'light');
  }
})();

// Part B: Theme management API
window.__wofTheme = (function () {
  var STORAGE_KEY = 'wof_theme';

  function _getTheme() {
    try {
      return localStorage.getItem(STORAGE_KEY) || 'light';
    } catch (e) {
      return document.documentElement.getAttribute('data-bs-theme') || 'light';
    }
  }

  function _saveTheme(theme) {
    try {
      localStorage.setItem(STORAGE_KEY, theme);
    } catch (e) {
      // private mode — skip
    }
  }

  function _updateButton(theme) {
    var icon = document.getElementById('themeIcon');
    var label = document.getElementById('themeLabel');
    if (icon) {
      icon.className = theme === 'dark' ? 'ti ti-moon' : 'ti ti-sun';
    }
    if (label) {
      label.textContent = theme === 'dark' ? 'Dark mode' : 'Light mode';
    }
  }

  function apply() {
    var theme = _getTheme();
    document.documentElement.setAttribute('data-bs-theme', theme);
    _updateButton(theme);

    var btn = document.getElementById('themeToggle');
    if (btn) {
      btn.removeEventListener('click', toggle); // prevent duplicate listeners
      btn.addEventListener('click', toggle);
    }
  }

  function toggle() {
    var current = document.documentElement.getAttribute('data-bs-theme') || 'light';
    var next = current === 'dark' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-bs-theme', next);
    _saveTheme(next);
    _updateButton(next);
  }

  function current() {
    return document.documentElement.getAttribute('data-bs-theme') || 'light';
  }

  return { apply: apply, toggle: toggle, current: current };
})();
