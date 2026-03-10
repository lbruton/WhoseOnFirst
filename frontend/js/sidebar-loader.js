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

    } catch (error) {
        console.error('Error loading sidebar:', error);
    }
})();
