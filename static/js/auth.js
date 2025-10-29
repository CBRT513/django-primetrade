/**
 * Session Authentication Module
 * Works with SSO + Django sessions (no client tokens).
 */

const Auth = (function() {
  'use strict';

  function getCsrfToken() {
    return (window.Utils && Utils.getCSRFToken) ? Utils.getCSRFToken() : null;
  }

  async function isAuthenticated() {
    try {
      const resp = await fetch('/api/auth/me/', { credentials: 'same-origin' });
      return resp.ok;
    } catch (_) { return false; }
  }

  async function getCurrentUser() {
    try {
      const resp = await fetch('/api/auth/me/', { credentials: 'same-origin' });
      if (!resp.ok) return null;
      return await resp.json();
    } catch (_) { return null; }
  }

  async function getUserEmail() {
    const user = await getCurrentUser();
    return user ? user.email : '';
  }

  function logout() {
    window.location.href = '/auth/logout/';
  }

  async function requireAuth(redirectUrl = null) {
    const ok = await isAuthenticated();
    if (!ok) {
      const redirect = redirectUrl || window.location.href;
      window.location.href = '/login/?next=' + encodeURIComponent(redirect);
      return false;
    }
    return true;
  }

  async function initAuthUI() {
    const userEmailElement = document.getElementById('userEmail');
    const usernameDisplay = document.getElementById('usernameDisplay');
    const user = await getCurrentUser();
    if (user) {
      if (userEmailElement) userEmailElement.textContent = user.email || '';
      if (usernameDisplay) usernameDisplay.textContent = `Welcome, ${user.username || ''}`;
    }
    // Attach logout buttons
    const logoutButtons = document.querySelectorAll('[data-logout], [onclick*="logout"]');
    logoutButtons.forEach(btn => btn.onclick = (e) => { e.preventDefault(); logout(); });
  }

  function handleAuthError() {
    window.location.href = '/login/?next=' + encodeURIComponent(window.location.href);
  }

  return {
    getCsrfToken,
    isAuthenticated,
    getCurrentUser,
    getUserEmail,
    logout,
    requireAuth,
    initAuthUI,
    handleAuthError
  };
})();

// Make logout globally available for onclick handlers
window.logout = Auth.logout;
