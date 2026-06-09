/**
 * Sidebar Component Loader
 * Loads the shared sidebar component and handles initialization
 */

(async function() {
    try {
        // Fetch the sidebar component
        const response = await fetch('/components/sidebar.html');
        if (!response.ok) {
            throw new Error(`Failed to load sidebar: ${response.status}`);
        }

        // SECURITY: Validate response is from expected same-origin path
        // This ensures we only parse HTML from our own trusted server component
        const responseURL = new URL(response.url);
        const expectedPath = '/components/sidebar.html';
        if (responseURL.origin !== window.location.origin || !responseURL.pathname.endsWith(expectedPath)) {
            throw new Error('Security: Unexpected sidebar source');
        }

        const sidebarHTML = await response.text();

        // Find the sidebar container and replace it with the sidebar HTML
        const sidebarContainer = document.getElementById('sidebar-container');
        if (sidebarContainer) {
            // Parse trusted same-origin HTML component using DOMParser (doesn't execute scripts)
            const parser = new DOMParser();
            const doc = parser.parseFromString(sidebarHTML, 'text/html');

            // Replace the container with the actual sidebar element
            sidebarContainer.replaceWith(doc.body.firstElementChild);
        } else {
            console.error('Sidebar container (#sidebar-container) not found');
            return;
        }

        // Set active page based on data-page attribute
        const currentPage = document.body.getAttribute('data-page');
        if (currentPage) {
            const navItems = document.querySelectorAll('.navbar-nav .nav-item');
            navItems.forEach(item => {
                if (item.getAttribute('data-page') === currentPage) {
                    item.classList.add('active');
                }
            });
        }

        // Apply theme and wire toggle button
        if (window.__wofTheme) {
            window.__wofTheme.apply();
        }
        // Register service worker
        if (window.__wofPwa) {
            window.__wofPwa.register();
        }

        // Dispatch a custom event to signal sidebar is loaded
        // This allows page-specific scripts to initialize after sidebar is ready
        window.dispatchEvent(new CustomEvent('sidebarLoaded'));

        // === SMS status pill — admin-only, post-WHO-43 ===

        function _wofUpdateSmsStatusPill() {
            const pill = document.getElementById('sms-status-pill');
            const text = document.getElementById('sms-status-pill-text');
            if (!pill || !text) return;

            if (!window.__wofUser || window.__wofUser.role !== 'admin') {
                pill.hidden = true;
                return;
            }

            fetch('/api/v1/settings/sms-status')
                .then(function (r) {
                    if (!r.ok) {
                        // Non-2xx (e.g. 401/500) — hide pill rather than parse error body
                        pill.hidden = true;
                        return null;
                    }
                    return r.json();
                })
                .then(function (data) {
                    if (!data) return;
                    if (data.source === 'db' || data.source === 'env') {
                        pill.hidden = true;
                        return;
                    }
                    pill.hidden = false;
                    if (data.source === 'mock') {
                        text.textContent = 'SMS: mock mode';
                    } else {
                        text.textContent = 'SMS: not configured';
                    }
                })
                .catch(function () {
                    // Silent — leave pill in current state if status fetch fails
                });
        }

        // Initial fetch after auth resolves (auth-init.js dispatches authReady
        // post-/auth/me; window.__wofUser is set by then). Triggering on
        // sidebarLoaded would race the async auth fetch and leave the pill
        // permanently hidden for admins.
        //
        // Guard against pre-fired authReady: on a full-page reload the browser
        // may run auth-init.js before sidebar-loader.js finishes, so authReady
        // has already fired by the time we reach this listener registration.
        // auth-init.js sets window.__wofUser synchronously before dispatching
        // authReady, so its presence reliably indicates auth is already settled.
        window.addEventListener('authReady', _wofUpdateSmsStatusPill);
        if (window.__wofUser) {
            _wofUpdateSmsStatusPill();
        }

        // Re-fetch when admin.html dispatches smsStatusChanged after saving Twilio config
        window.addEventListener('smsStatusChanged', _wofUpdateSmsStatusPill);

        // Fetch and display app version
        fetch('/api/v1/version')
            .then(function(r) { return r.json(); })
            .then(function(data) {
                var el = document.getElementById('appVersion');
                if (el) el.textContent = 'v' + data.version;
            })
            .catch(function() {
                var el = document.getElementById('appVersion');
                if (el) el.textContent = 'v?';
            });

        // Easter egg: Shift-click logo opens the inspiration
        var logo = document.getElementById('appLogo');
        if (logo) {
            logo.addEventListener('click', function(e) {
                if (e.shiftKey) {
                    e.preventDefault();
                    window.open('https://www.youtube.com/watch?v=sYOUFGfK4bU', 'WhosOnFirst', 'width=800,height=600,menubar=no,toolbar=no,location=no,status=no');
                }
            });
        }

    } catch (error) {
        console.error('Error loading sidebar:', error);
    }
})();
