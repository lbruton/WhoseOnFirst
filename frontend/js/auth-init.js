/**
 * Auth Init — shared authentication and sidebar wiring for all pages.
 *
 * Listens for the 'sidebarLoaded' event, then:
 *   - Calls /api/v1/auth/me to verify the session
 *   - Redirects to /login.html if unauthenticated
 *   - Populates sidebar user display (#usernameDisplay, #userRoleDisplay, #userRoleIcon)
 *   - Hides .admin-only elements for viewer-role users
 *   - Wires the #logoutBtn click handler
 *   - Dispatches 'authReady' with { detail: { user } } for page scripts to start data loading
 *
 * Pages should listen for 'authReady' instead of duplicating this auth block.
 */
(function () {
    var API_BASE = '/api/v1';

    window.addEventListener('sidebarLoaded', async function () {
        try {
            var response = await fetch(API_BASE + '/auth/me', { credentials: 'include' });

            if (!response.ok) {
                window.location.href = '/login.html';
                return;
            }

            var user = await response.json();

            // Expose for pages that need the user object before authReady fires
            window.__wofUser = user;

            // Populate sidebar user display
            var usernameEl = document.getElementById('usernameDisplay');
            var roleEl = document.getElementById('userRoleDisplay');
            var roleIconEl = document.getElementById('userRoleIcon');

            if (usernameEl) usernameEl.textContent = user.username;
            if (roleEl) roleEl.textContent = user.role === 'admin' ? 'Administrator' : 'Viewer';
            if (roleIconEl) {
                var icon = roleIconEl.querySelector('i');
                if (icon) icon.className = user.role === 'admin' ? 'ti ti-shield-check' : 'ti ti-eye';
            }

            // Hide admin-only elements for viewers
            if (user.role !== 'admin') {
                document.querySelectorAll('.admin-only').forEach(function (el) {
                    el.style.display = 'none';
                });
            }

            // Wire logout button
            var logoutBtn = document.getElementById('logoutBtn');
            if (logoutBtn) {
                logoutBtn.addEventListener('click', async function (e) {
                    e.preventDefault();
                    try {
                        await fetch(API_BASE + '/auth/logout', {
                            method: 'POST',
                            credentials: 'include'
                        });
                    } catch (err) {
                        console.error('Logout error:', err);
                    }
                    window.location.href = '/login.html';
                });
            }

            // Signal pages to begin data loading
            window.dispatchEvent(new CustomEvent('authReady', { detail: { user: user } }));

        } catch (error) {
            console.error('Auth check failed:', error);
            window.location.href = '/login.html';
        }
    });
})();
