/**
 * API Module
 * Handles all API communications with authentication and error handling
 */

const API = (function() {
  'use strict';
  
  // Base API request function
  async function request(url, options = {}) {
    const token = Auth.getToken();
    
    if (!token && options.requireAuth !== false) {
      throw new Error('Not authenticated');
    }
    
    const defaultOptions = {
      headers: {
        'Content-Type': 'application/json',
        ...(token && { 'Authorization': 'Bearer ' + token })
      }
    };
    
    const finalOptions = {
      ...defaultOptions,
      ...options,
      headers: {
        ...defaultOptions.headers,
        ...(options.headers || {})
      }
    };
    
    const response = await fetch(url, finalOptions);
    
    // Handle authentication errors
    if (response.status === 401) {
      Auth.handleAuthError();
      return;
    }
    
    // Handle permission errors
    if (response.status === 403) {
      const error = await response.text();
      throw new Error('Access denied: ' + (error || 'You do not have permission.'));
    }
    
    // Handle other errors
    if (!response.ok) {
      const error = await response.text();
      throw new Error(error || `Request failed: ${response.status}`);
    }
    
    // Parse JSON response
    try {
      return await response.json();
    } catch (e) {
      // Return text if not JSON
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
  
  // Legacy functions for compatibility
  async function getJSON(url) {
    return get(url);
  }
  
  async function postJSON(url, body) {
    return post(url, body);
  }
  
  // API wrapper with authentication
  async function apiRequest(url, options = {}) {
    const token = Auth.getToken();
    
    if (!token) {
      throw new Error('Not authenticated');
    }
    
    const defaultOptions = {
      headers: {
        'Authorization': 'Bearer ' + token,
        'Content-Type': 'application/json'
      }
    };
    
    const response = await fetch(url, { ...defaultOptions, ...options });
    
    if (response.status === 401) {
      Auth.handleAuthError();
      return;
    }
    
    if (response.status === 403) {
      throw new Error('Access denied. Admin role required.');
    }
    
    if (!response.ok) {
      const error = await response.text();
      throw new Error(error || 'Request failed');
    }
    
    return response.json();
  }
  
  // Public API
  return {
    request,
    get,
    post,
    del,
    getJSON,
    postJSON,
    apiRequest
  };
})();