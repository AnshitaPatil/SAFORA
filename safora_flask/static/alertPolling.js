// Shared alert polling script - include this in all pages to detect alerts

(function() {
    'use strict';
    
    let alertPollingInterval = null;
    let isOnAlertPage = false;

    function checkAlertStatus() {
        // Don't poll if we're already on the alert page
        if (window.location.pathname === '/alert') {
            isOnAlertPage = true;
            return;
        }

        // If we were on alert page but navigated away, reset flag
        if (isOnAlertPage && window.location.pathname !== '/alert') {
            isOnAlertPage = false;
        }

        fetch('/alert_status')
            .then(response => response.json())
            .then(data => {
                if (data.show_alert && data.alert_active && !isOnAlertPage) {
                    // Alert is active and we're not on alert page - navigate to it
                    console.log('Alert detected! Navigating to alert page...');
                    window.location.href = '/alert';
                    isOnAlertPage = true;
                }
            })
            .catch(error => {
                // Silently handle errors - don't spam console
                console.debug('Alert status check error:', error);
            });
    }

    // Start polling for alerts every 1 second
    // Only poll if not already on alert page
    function startAlertPolling() {
        if (window.location.pathname !== '/alert') {
            if (!alertPollingInterval) {
                alertPollingInterval = setInterval(checkAlertStatus, 1000);
                console.log('Alert polling started');
            }
        }
    }

    // Stop polling when on alert page
    function stopAlertPolling() {
        if (alertPollingInterval) {
            clearInterval(alertPollingInterval);
            alertPollingInterval = null;
            console.log('Alert polling stopped');
        }
    }

    // Initialize polling when page loads
    document.addEventListener('DOMContentLoaded', function() {
        if (window.location.pathname === '/alert') {
            isOnAlertPage = true;
            stopAlertPolling();
        } else {
            startAlertPolling();
        }
    });

    // Listen for navigation changes (for SPA-like behavior)
    window.addEventListener('popstate', function() {
        if (window.location.pathname === '/alert') {
            isOnAlertPage = true;
            stopAlertPolling();
        } else {
            isOnAlertPage = false;
            startAlertPolling();
        }
    });

    // Also check immediately (in case DOMContentLoaded already fired)
    if (document.readyState === 'loading') {
        // DOM hasn't finished loading yet, wait for DOMContentLoaded
    } else {
        // DOM already loaded
        if (window.location.pathname === '/alert') {
            isOnAlertPage = true;
            stopAlertPolling();
        } else {
            startAlertPolling();
        }
    }
})();

