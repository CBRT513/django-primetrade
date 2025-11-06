/**
 * Role-Based Access Control (RBAC) utilities for PrimeTrade frontend
 *
 * Fetches user role from backend and provides functions to:
 * - Hide/show elements based on role
 * - Display role badge
 * - Check permissions before actions
 */

class RBACManager {
    constructor() {
        this.userContext = null;
        this.loaded = false;
    }

    /**
     * Fetch user context (role and permissions) from backend
     */
    async loadUserContext() {
        try {
            const response = await fetch('/api/user/context/', {
                credentials: 'include'
            });

            if (!response.ok) {
                console.error('Failed to load user context:', response.statusText);
                return false;
            }

            this.userContext = await response.json();
            this.loaded = true;
            console.log('[RBAC] User context loaded:', this.userContext);
            return true;
        } catch (error) {
            console.error('[RBAC] Error loading user context:', error);
            return false;
        }
    }

    /**
     * Get user role
     */
    getRole() {
        return this.userContext?.user?.role || 'viewer';
    }

    /**
     * Check if user can perform write operations
     */
    canWrite() {
        return this.userContext?.can_write === true;
    }

    /**
     * Check if user is admin
     */
    isAdmin() {
        return this.userContext?.is_admin === true;
    }

    /**
     * Get user email
     */
    getUserEmail() {
        return this.userContext?.user?.email || 'Unknown';
    }

    /**
     * Hide write operations from read-only users
     *
     * Elements with these classes/IDs will be hidden for read-only users:
     * - .write-operation
     * - .admin-only (hidden for non-admin)
     * - Any button/form with create/edit/delete actions
     */
    applyRoleVisibility() {
        const canWrite = this.canWrite();
        const isAdmin = this.isAdmin();
        const role = this.getRole();

        console.log(`[RBAC] Applying role visibility - Role: ${role}, CanWrite: ${canWrite}, IsAdmin: ${isAdmin}`);

        // Hide write operations for read-only users
        if (!canWrite) {
            document.querySelectorAll('.write-operation, [data-role="write"]').forEach(el => {
                el.style.display = 'none';
                console.log('[RBAC] Hiding write operation:', el);
            });

            // Hide buttons with write keywords in text or ID
            document.querySelectorAll('button').forEach(button => {
                const text = button.textContent.toLowerCase();
                const id = button.id.toLowerCase();
                const writeKeywords = ['create', 'add', 'new', 'upload', 'save', 'edit', 'update', 'delete', 'approve'];

                if (writeKeywords.some(kw => text.includes(kw) || id.includes(kw))) {
                    button.style.display = 'none';
                    console.log('[RBAC] Hiding write button:', button.textContent || button.id);
                }
            });

            // Show read-only message
            this.showReadOnlyMessage();
        }

        // Hide admin-only elements for non-admin users
        if (!isAdmin) {
            document.querySelectorAll('.admin-only, [data-role="admin"]').forEach(el => {
                el.style.display = 'none';
                console.log('[RBAC] Hiding admin-only element:', el);
            });
        }
    }

    /**
     * Show read-only mode message
     */
    showReadOnlyMessage() {
        // Check if message already exists
        if (document.getElementById('rbac-readonly-message')) {
            return;
        }

        const message = document.createElement('div');
        message.id = 'rbac-readonly-message';
        message.style.cssText = `
            position: fixed;
            top: 60px;
            right: 20px;
            background: #fff3cd;
            border: 1px solid #ffc107;
            border-radius: 8px;
            padding: 12px 16px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            z-index: 1000;
            font-size: 14px;
            color: #856404;
        `;
        message.innerHTML = `
            <strong>📖 Read-Only Mode</strong><br>
            <small>You can view data but cannot make changes</small>
        `;

        document.body.appendChild(message);

        // Auto-hide after 5 seconds
        setTimeout(() => {
            message.style.transition = 'opacity 0.5s';
            message.style.opacity = '0';
            setTimeout(() => message.remove(), 500);
        }, 5000);
    }

    /**
     * Display role badge in UI
     *
     * @param {string} containerId - ID of element to append badge to (default: body)
     */
    displayRoleBadge(containerId = null) {
        const role = this.getRole();
        const email = this.getUserEmail();

        const badge = document.createElement('div');
        badge.id = 'rbac-role-badge';
        badge.style.cssText = `
            position: fixed;
            top: 10px;
            right: 10px;
            display: flex;
            align-items: center;
            gap: 8px;
            background: white;
            border-radius: 8px;
            padding: 8px 12px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            z-index: 1001;
            font-size: 13px;
        `;

        const roleColors = {
            'admin': { bg: '#dc3545', text: 'white' },
            'user': { bg: '#28a745', text: 'white' },
            'viewer': { bg: '#6c757d', text: 'white' },
            'read only': { bg: '#6c757d', text: 'white' },
            'read-only': { bg: '#6c757d', text: 'white' }
        };

        const colors = roleColors[role.toLowerCase()] || { bg: '#6c757d', text: 'white' };

        badge.innerHTML = `
            <span style="color: #666;">${email}</span>
            <span style="
                background: ${colors.bg};
                color: ${colors.text};
                padding: 4px 8px;
                border-radius: 4px;
                font-weight: 500;
                text-transform: uppercase;
                font-size: 11px;
            ">${role}</span>
        `;

        const container = containerId ? document.getElementById(containerId) : document.body;
        container.appendChild(badge);
    }

    /**
     * Initialize RBAC - fetch user context and apply visibility rules
     *
     * Call this on page load:
     * document.addEventListener('DOMContentLoaded', () => rbac.init());
     */
    async init() {
        console.log('[RBAC] Initializing...');

        const success = await this.loadUserContext();
        if (!success) {
            console.error('[RBAC] Failed to load user context');
            return false;
        }

        // Display role badge
        this.displayRoleBadge();

        // Apply role-based visibility
        this.applyRoleVisibility();

        console.log('[RBAC] Initialization complete');
        return true;
    }

    /**
     * Warn user before write operation (if read-only)
     */
    warnBeforeWrite(action = 'perform this action') {
        if (!this.canWrite()) {
            alert(`You have read-only access and cannot ${action}.\n\nContact your administrator if you need write access.`);
            return false;
        }
        return true;
    }
}

// Export global instance
window.rbac = new RBACManager();

// Auto-initialize on DOM ready
document.addEventListener('DOMContentLoaded', () => {
    window.rbac.init();
});
