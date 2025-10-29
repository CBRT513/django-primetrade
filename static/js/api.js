/**
 * API Module (Session-based)
 * Uses Django sessions and CSRF tokens; no Bearer tokens.
 */

const API = (function() {
  'use strict';
  
  // Base API request function
  async function request(url, options = {}) {
    const defaultOptions = {
      credentials: 'same-origin',
      headers: {
        'Content-Type': 'application/json',
      }
    };

    // Add CSRF token for non-GET requests
    const method = (options.method || 'GET').toUpperCase();
    if (method !== 'GET') {
      const csrf = (window.Utils && Utils.getCSRFToken) ? Utils.getCSRFToken() : null;
      if (csrf) {
        defaultOptions.headers['X-CSRFToken'] = csrf;
      }
    }
    
    const finalOptions = {
      ...defaultOptions,
      ...options,
      headers: {
        ...defaultOptions.headers,
        ...(options.headers || {})
      }
    };
    
    const response = await fetch(url, finalOptions);
    
    // Handle authentication/permission errors
    if (response.status === 401 || response.status === 403) {
      if (typeof Auth !== 'undefined' && Auth.handleAuthError) Auth.handleAuthError();
      return;
    }
    
    if (!response.ok) {
      const error = await response.text();
      throw new Error(error || `Request failed: ${response.status}`);
    }
    
    try {
      return await response.json();
    } catch (e) {
      return response.text();
    }
  }
  
  // GET request
  async function get(url, options = {}) {
    return request(url, { ...options, method: 'GET' });
  }
  
  // POST request
  async function post(url, data, options = {}) {
    return request(url, {
      ...options,
      method: 'POST',
      body: JSON.stringify(data)
    });
  }
  
  // DELETE request
  async function del(url, options = {}) {
    return request(url, { ...options, method: 'DELETE' });
  }
  
  // Legacy convenience wrappers
  async function getJSON(url) { return get(url); }
  async function postJSON(url, body) { return post(url, body); }
  
  return { request, get, post, del, getJSON, postJSON };
})();
