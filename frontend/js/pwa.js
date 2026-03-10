window.__wofPwa = (function () {
  function register() {
    if (!('serviceWorker' in navigator)) return;
    window.addEventListener('load', function () {
      navigator.serviceWorker.register('/sw.js')
        .then(function (reg) {
          console.log('WOF SW registered:', reg.scope);
        })
        .catch(function (e) {
          console.warn('WOF SW registration failed:', e);
        });
    });
  }

  return { register: register };
})();
