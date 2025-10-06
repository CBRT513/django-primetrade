/**
 * Utilities Module
 * Common utility functions used across the application
 */

const Utils = (function() {
  'use strict';
  
  // Quick selector function
  function qs(id) {
    return document.getElementById(id);
  }
  
  // Show status message
  function showStatus(message, type = 'success', duration = 5000) {
    const status = document.getElementById('status');
    if (!status) return;
    
    status.textContent = message;
    status.className = 'status ' + type;
    
    if (duration > 0) {
      setTimeout(() => {
        status.className = 'status';
        status.textContent = '';
      }, duration);
    }
  }
  
  // Format date to YYYY-MM-DD
  function formatDate(date) {
    if (!date) return '';
    const d = new Date(date);
    const year = d.getFullYear();
    const month = String(d.getMonth() + 1).padStart(2, '0');
    const day = String(d.getDate()).padStart(2, '0');
    return `${year}-${month}-${day}`;
  }
  
  // Format number with commas
  function formatNumber(num) {
    return Number(num).toLocaleString();
  }
  
  // Format tonnage
  function formatTons(tons) {
    return Number(tons).toFixed(2);
  }
  
  // Parse query parameters
  function getQueryParams() {
    const params = {};
    const searchParams = new URLSearchParams(window.location.search);
    for (const [key, value] of searchParams) {
      params[key] = value;
    }
    return params;
  }
  
  // Escape HTML for safe display
  function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
  }
  
  // Reset form
  function resetForm(formId) {
    const form = typeof formId === 'string' ? document.getElementById(formId) : formId;
    if (form) {
      form.reset();
      // Clear any hidden fields
      const hiddenFields = form.querySelectorAll('input[type="hidden"]');
      hiddenFields.forEach(field => {
        if (field.id !== 'editId') { // Keep editId for edit forms
          field.value = '';
        }
      });
    }
  }
  
  // Debounce function for input handlers
  function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
      const later = () => {
        clearTimeout(timeout);
        func(...args);
      };
      clearTimeout(timeout);
      timeout = setTimeout(later, wait);
    };
  }
  
  // Initialize common UI elements
  function initCommonUI() {
    // Initialize auth UI
    if (typeof Auth !== 'undefined') {
      Auth.initAuthUI();
    }
    
    // Add loading state class removal
    const loadingStates = document.querySelectorAll('.loading, #loadingState');
    loadingStates.forEach(el => {
      if (el.id === 'loadingState') {
        el.style.display = 'none';
      }
    });
    
    // Show main content
    const mainContent = document.getElementById('mainContent');
    if (mainContent) {
      mainContent.style.display = mainContent.dataset.display || 'grid';
    }
  }
  
  // Handle form validation
  function validateForm(formId) {
    const form = document.getElementById(formId);
    if (!form) return false;

    const requiredFields = form.querySelectorAll('[required]');
    for (const field of requiredFields) {
      if (!field.value.trim()) {
        showStatus(`Please fill in ${field.previousElementSibling?.textContent || 'all required fields'}`, 'error');
        field.focus();
        return false;
      }
    }
    return true;
  }

  // Get cookie value by name
  function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
      const cookies = document.cookie.split(';');
      for (let i = 0; i < cookies.length; i++) {
        const cookie = cookies[i].trim();
        if (cookie.substring(0, name.length + 1) === (name + '=')) {
          cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
          break;
        }
      }
    }
    return cookieValue;
  }

  // Get CSRF token from cookie
  function getCSRFToken() {
    return getCookie('csrftoken');
  }

  // Public API
  return {
    qs,
    showStatus,
    formatDate,
    formatNumber,
    formatTons,
    getQueryParams,
    escapeHtml,
    resetForm,
    debounce,
    initCommonUI,
    validateForm,
    getCookie,
    getCSRFToken
  };
})();

// Make commonly used functions globally available
window.qs = Utils.qs;
window.showStatus = Utils.showStatus;