// Simple service-worker registration helper for CampusHub web build
(function registerServiceWorker() {
  if (!('serviceWorker' in navigator)) return;

  const swPath = '/static/pwa/sw.js';

  navigator.serviceWorker
    .register(swPath)
    .then((registration) => {
      console.info('[SW] Registered:', registration.scope);

      // Listen for updates
      registration.onupdatefound = () => {
        const installing = registration.installing;
        if (!installing) return;
        installing.onstatechange = () => {
          if (installing.state === 'installed') {
            if (navigator.serviceWorker.controller) {
              // New content available
              registration.waiting?.postMessage({ type: 'SKIP_WAITING' });
              window.dispatchEvent(new Event('campushub:sw-update'));
            } else {
              console.info('[SW] Content cached for offline use.');
            }
          }
        };
      };
    })
    .catch((error) => console.error('[SW] Registration failed', error));
})();
