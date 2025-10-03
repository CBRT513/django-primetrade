/**
 * Firebase Configuration for PrimeTrade
 * Connects to barge2rail-auth-e4c16 for centralized SSO
 */

// Firebase configuration for barge2rail-auth-e4c16
const FIREBASE_CONFIG = {
  apiKey: "AIzaSyDV7F15c4lWfYrDhKXLPxMVFWPGKCtBMws",
  authDomain: "barge2rail-auth-e4c16.firebaseapp.com",
  projectId: "barge2rail-auth-e4c16",
  storageBucket: "barge2rail-auth-e4c16.firebasestorage.app",
  messagingSenderId: "576191086033",
  appId: "1:576191086033:web:e5b5fc5302bc5e5302f97c"
};

// Firebase modules - dynamically loaded
let firebaseApp = null;
let firebaseAuth = null;

const FirebaseAuth = {
  // Initialize Firebase (lazy loading)
  async initialize() {
    if (firebaseApp) return firebaseAuth;
    
    try {
      // Import Firebase modules dynamically
      const { initializeApp } = await import('https://www.gstatic.com/firebasejs/10.7.0/firebase-app.js');
      const { getAuth, signInWithEmailAndPassword, onAuthStateChanged, signOut } = 
        await import('https://www.gstatic.com/firebasejs/10.7.0/firebase-auth.js');
      
      // Initialize Firebase app
      firebaseApp = initializeApp(FIREBASE_CONFIG);
      firebaseAuth = getAuth(firebaseApp);
      
      // Store methods for later use
      this.signInWithEmailAndPassword = signInWithEmailAndPassword;
      this.onAuthStateChanged = onAuthStateChanged;
      this.signOut = signOut;
      
      console.log('[Firebase] Initialized successfully');
      return firebaseAuth;
    } catch (error) {
      console.error('[Firebase] Initialization failed:', error);
      throw new Error('Authentication system unavailable. Please try again later.');
    }
  },

  // Sign in with email/password
  async signIn(email, password) {
    if (!firebaseAuth) await this.initialize();
    
    try {
      const userCredential = await this.signInWithEmailAndPassword(firebaseAuth, email, password);
      console.log('[Firebase] Sign in successful for:', email);
      return userCredential;
    } catch (error) {
      console.error('[Firebase] Sign in failed:', error);
      
      // Return user-friendly error messages
      switch (error.code) {
        case 'auth/user-not-found':
        case 'auth/wrong-password':
        case 'auth/invalid-credential':
          throw new Error('Invalid email or password');
        case 'auth/user-disabled':
          throw new Error('This account has been disabled. Please contact your administrator.');
        case 'auth/too-many-requests':
          throw new Error('Too many failed attempts. Please try again later.');
        case 'auth/network-request-failed':
          throw new Error('Network error. Please check your connection and try again.');
        default:
          throw new Error('Login failed. Please try again.');
      }
    }
  },

  // Sign out
  async signOutUser() {
    if (!firebaseAuth) await this.initialize();
    
    try {
      await this.signOut(firebaseAuth);
      console.log('[Firebase] Sign out successful');
    } catch (error) {
      console.error('[Firebase] Sign out failed:', error);
      throw new Error('Sign out failed');
    }
  },

  // Get current user
  async getCurrentUser() {
    if (!firebaseAuth) await this.initialize();
    
    return new Promise((resolve) => {
      const unsubscribe = this.onAuthStateChanged(firebaseAuth, (user) => {
        unsubscribe();
        resolve(user);
      });
    });
  },

  // Listen to auth state changes
  onAuthStateChanged(callback) {
    if (!firebaseAuth) {
      this.initialize().then(() => {
        this.onAuthStateChanged(firebaseAuth, callback);
      });
      return;
    }
    
    return this.onAuthStateChanged(firebaseAuth, callback);
  }
};

// Make it globally available for backward compatibility
window.FirebaseAuth = FirebaseAuth;

export default FirebaseAuth;
