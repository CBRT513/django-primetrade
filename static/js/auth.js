/**
 * Enhanced Authentication Module
 * Handles Firebase Auth integration with backward compatibility
 * Supports centralized SSO via barge2rail-auth-e4c16
 */

const Auth = (function() {
  'use strict';
  
  // Check if user is authenticated
  function isAuthenticated() {
    return !!localStorage.getItem('firebase_token');
  }
  
  // Get current user email
  function getUserEmail() {
    return localStorage.getItem('user_email') || '';
  }
  
  // Get authentication token
  function getToken() {
    return localStorage.getItem('firebase_token');
  }
  
  // Set authentication data
  function setAuth(token, email) {
    if (token) {
      localStorage.setItem('firebase_token', token);
    }
    if (email) {
      localStorage.setItem('user_email', email);
    }
  }
  
  // Clear authentication data
  function clearAuth() {
    localStorage.removeItem('firebase_token');
    localStorage.removeItem('user_email');
  }
  
  // Logout user
  function logout() {
    clearAuth();
    localStorage.setItem('logout_requested', 'true');
    window.location.href = '/login.html';
  }
  
  // Check authentication and redirect if needed
  function requireAuth(redirectUrl = null) {
    if (!isAuthenticated()) {
      const redirect = redirectUrl || window.location.href;
      window.location.href = '/login.html?redirect=' + encodeURIComponent(redirect);
      return false;
    }
    return true;
  }
  
  // Initialize auth UI elements
  function initAuthUI() {
    const userEmailElement = document.getElementById('userEmail');
    if (userEmailElement) {
      userEmailElement.textContent = getUserEmail();
    }
    
    // Set up logout buttons
    const logoutButtons = document.querySelectorAll('[onclick*="logout()"]');
    logoutButtons.forEach(button => {
      button.onclick = logout;
    });
  }
  
  // Handle authentication error (401)
  function handleAuthError() {
    clearAuth();
    window.location.href = '/login.html?redirect=' + encodeURIComponent(window.location.href);
  }
  
  // Firebase Auth integration methods
  async function signInWithFirebase(email, password) {
    try {
      // Load Firebase config dynamically
      const FirebaseAuth = window.FirebaseAuth;
      if (!FirebaseAuth) {
        throw new Error('Firebase Auth not loaded. Please refresh the page.');
      }
      
      // Sign in with Firebase
      const userCredential = await FirebaseAuth.signIn(email, password);
      const user = userCredential.user;
      
      // Get Firebase ID token
      const token = await user.getIdToken();
      
      // Verify access with backend
      const profileResponse = await fetch('/api/user-profile', {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      
      if (!profileResponse.ok) {
        const error = await profileResponse.json();
        throw new Error(error.message || error.error || 'Access denied');
      }
      
      const profile = await profileResponse.json();
      
      // Store auth data
      setAuth(token, user.email);
      localStorage.setItem('user_profile', JSON.stringify(profile));
      
      return {
        user: user,
        token: token,
        profile: profile
      };
      
    } catch (error) {
      console.error('Firebase sign in error:', error);
      throw error;
    }
  }
  
  async function signOutFromFirebase() {
    try {
      const FirebaseAuth = window.FirebaseAuth;
      if (FirebaseAuth) {
        await FirebaseAuth.signOutUser();
      }
    } catch (error) {
      console.warn('Firebase sign out error:', error);
    }
    
    // Always clear local storage
    clearAuth();
    localStorage.removeItem('user_profile');
  }
  
  function getUserProfile() {
    try {
      const profile = localStorage.getItem('user_profile');
      return profile ? JSON.parse(profile) : null;
    } catch (error) {
      console.warn('Error parsing user profile:', error);
      return null;
    }
  }
  
  // Enhanced logout with Firebase support
  function logout() {
    signOutFromFirebase().then(() => {
      localStorage.setItem('logout_requested', 'true');
      window.location.href = '/login.html';
    });
  }
  
  // Auto-refresh token if needed
  async function refreshTokenIfNeeded() {
    if (!isAuthenticated()) return false;
    
    try {
      const FirebaseAuth = window.FirebaseAuth;
      if (!FirebaseAuth) return true; // Assume valid if Firebase not loaded
      
      const user = await FirebaseAuth.getCurrentUser();
      if (!user) {
        handleAuthError();
        return false;
      }
      
      // Get fresh token
      const token = await user.getIdToken(true); // Force refresh
      setAuth(token, user.email);
      
      return true;
    } catch (error) {
      console.error('Token refresh failed:', error);
      handleAuthError();
      return false;
    }
  }
  
  // Public API
  return {
    isAuthenticated,
    getUserEmail,
    getToken,
    setAuth,
    clearAuth,
    logout,
    requireAuth,
    initAuthUI,
    handleAuthError,
    // Firebase Auth methods
    signInWithFirebase,
    signOutFromFirebase,
    getUserProfile,
    refreshTokenIfNeeded
  };
})();

// Make logout globally available for onclick handlers
window.logout = Auth.logout;