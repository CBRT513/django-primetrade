/**
 * Staging Banner Component
 *
 * Automatically adds a staging/development banner to pages
 * based on the current environment (detected from hostname).
 *
 * Include this script at the top of any page to show the banner.
 */
(function() {
    'use strict';

    // Detect environment from hostname
    const hostname = window.location.hostname;

    let environment = 'production';
    let showBanner = false;

    if (hostname === 'localhost' || hostname === '127.0.0.1') {
        environment = 'development';
        showBanner = true;
    } else if (hostname.includes('staging') || hostname.includes('test') || hostname.includes('dev')) {
        environment = 'staging';
        showBanner = true;
    } else if (hostname.includes('onrender.com') && !hostname.includes('primetrade.')) {
        // Non-production Render deployments
        environment = 'staging';
        showBanner = true;
    }

    if (!showBanner) return;

    // Create banner element
    const banner = document.createElement('div');
    banner.id = 'staging-banner';
    banner.style.cssText = `
        background: ${environment === 'staging' ? '#f59e0b' : '#3b82f6'};
        color: white;
        text-align: center;
        padding: 8px 16px;
        font-size: 13px;
        font-weight: 600;
        letter-spacing: 0.5px;
        position: relative;
        z-index: 1000;
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    `;

    if (environment === 'staging') {
        banner.textContent = 'STAGING ENVIRONMENT - Data may be reset at any time';
    } else if (environment === 'development') {
        banner.textContent = 'DEVELOPMENT - Local testing environment';
    }

    // Insert at very top of body
    document.body.insertBefore(banner, document.body.firstChild);
})();
