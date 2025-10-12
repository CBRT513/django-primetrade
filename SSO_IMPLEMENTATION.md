# SSO OAuth Integration - Implementation Summary

## Overview
SSO OAuth integration has been successfully implemented for the PrimeTrade application using the Barge2Rail SSO service.

## Configuration

### Environment Variables (.env)
```bash
# SSO Configuration
SSO_BASE_URL=https://sso.barge2rail.com
SSO_CLIENT_ID=app_0b97b7b94d192797
SSO_CLIENT_SECRET=Kyq6_cHugJLcWyYuP1K1JSf-eF59y0OHT6IJ7tMet4U
SSO_REDIRECT_URI=http://127.0.0.1:8001/auth/callback/
SSO_SCOPES=openid email profile
```

### Production Configuration
For production deployment, update the redirect URI:
```bash
SSO_REDIRECT_URI=https://prt.barge2rail.com/auth/callback/
```

## Implementation Details

### 1. OAuth Flow Architecture

The implementation follows the standard OAuth 2.0 Authorization Code flow:

1. **User clicks "Login with SSO"** → Redirects to `/auth/login/`
2. **SSO Login Initiation** → Generates state token and redirects to SSO authorization endpoint
3. **User authenticates** → SSO server validates credentials
4. **Callback** → SSO redirects to `/auth/callback/` with authorization code
5. **Token Exchange** → Application exchanges code for access/refresh tokens
6. **Session Creation** → Creates Django user session with JWT data
7. **Home Redirect** → User is logged in and redirected to dashboard

### 2. Key Files

#### `/primetrade_project/auth_views.py` (primetrade_project/auth_views.py:1-117)
Contains three main view functions:

- **`login_page(request)`** - Renders the login page with SSO button
- **`sso_login(request)`** - Initiates OAuth flow, generates state token
- **`sso_callback(request)`** - Handles OAuth callback, exchanges code for tokens
- **`sso_logout(request)`** - Logs out user and redirects to SSO logout

#### `/templates/login.html` (templates/login.html:1-67)
- Primary "Login with SSO" button prominently displayed
- Legacy username/password login available in collapsed section
- Branded with Cincinnati Barge & Rail Terminal styling

#### `/primetrade_project/urls.py` (primetrade_project/urls.py:23-27)
OAuth routes configured:
- `/login/` - Login page
- `/auth/login/` - SSO login initiation
- `/auth/callback/` - OAuth callback handler
- `/auth/logout/` - SSO logout

### 3. Security Features

✅ **CSRF Protection**: State parameter generated and validated
✅ **Secure Sessions**: Tokens stored in Django session
✅ **Role-Based Access**: Validates primetrade role from JWT
✅ **HTTPS Ready**: Secure cookies enabled for production
✅ **Token Storage**: Access and refresh tokens stored in session

### 4. SSO API Endpoints Used

- **Authorization URL**: `https://sso.barge2rail.com/auth/authorize/`
- **Token URL**: `https://sso.barge2rail.com/auth/token/`
- **Logout URL**: `https://sso.barge2rail.com/auth/logout/`

### 5. User Data Handling

The JWT token contains:
- `email` - User's email address
- `display_name` - User's full name
- `roles.primetrade.role` - User's role in PrimeTrade application

The callback handler:
1. Decodes the JWT access token
2. Extracts user email and role
3. Creates or retrieves Django User by email
4. Stores SSO role and tokens in session
5. Logs user into Django session

## Testing

### Local Testing (Port 8001)
```bash
# Start the Django development server
source venv/bin/activate
python manage.py runserver 127.0.0.1:8001
```

Navigate to: `http://127.0.0.1:8001/login/`

### Test Flow
1. Click "Login with SSO" button
2. You'll be redirected to `https://sso.barge2rail.com/auth/authorize/`
3. Enter your SSO credentials
4. After successful authentication, you'll be redirected back to the application
5. You should be logged in and see the dashboard

## Required Python Libraries

All required libraries are already installed:
- `PyJWT==2.10.1` - For JWT token decoding
- `requests==2.32.5` - For HTTP requests to SSO server
- `requests-oauthlib==2.0.0` - OAuth helper library
- `djangorestframework_simplejwt==5.5.1` - JWT support

## Session Data Stored

After successful SSO login, the following data is stored in the Django session:
- `oauth_state` - CSRF protection state (cleared after use)
- `sso_role` - User's PrimeTrade role (admin/user/viewer)
- `sso_access_token` - JWT access token
- `sso_refresh_token` - Refresh token for token renewal

## Role Validation

The callback handler validates that the user has a `primetrade` role:
```python
primetrade_role = user_roles.get('primetrade', {}).get('role')
if not primetrade_role:
    return HttpResponseForbidden("You don't have access to PrimeTrade. Contact admin.")
```

## Logout Flow

The logout handler:
1. Calls Django's `logout(request)` to clear local session
2. Redirects to SSO logout URL to clear SSO session
3. User is fully logged out of both systems

## Next Steps

### For Production Deployment:
1. Update `.env` with production redirect URI:
   ```bash
   SSO_REDIRECT_URI=https://prt.barge2rail.com/auth/callback/
   ```

2. Ensure the redirect URI is registered in the SSO admin panel

3. Set `DEBUG=False` in `.env`

4. Configure `ALLOWED_HOSTS` with production domain:
   ```bash
   ALLOWED_HOSTS=prt.barge2rail.com,www.prt.barge2rail.com
   ```

5. Add production domain to `CSRF_TRUSTED_ORIGINS` in `settings.py`:
   ```python
   CSRF_TRUSTED_ORIGINS = [
       'https://prt.barge2rail.com',
       'https://www.prt.barge2rail.com',
   ]
   ```

### Future Enhancements:
- Implement token refresh logic for long-lived sessions
- Add JWT signature verification with SSO public key
- Implement role-based permissions in Django
- Add SSO session timeout handling
- Create user profile page showing SSO data

## Troubleshooting

### Issue: "Invalid state parameter"
**Cause**: CSRF validation failed
**Solution**: Clear cookies and try again. State tokens expire.

### Issue: "No authorization code received"
**Cause**: SSO server didn't return an authorization code
**Solution**: Check SSO server logs, verify client credentials

### Issue: "Token exchange failed"
**Cause**: Invalid client credentials or redirect URI mismatch
**Solution**: Verify credentials in `.env` match SSO admin panel

### Issue: "You don't have access to PrimeTrade"
**Cause**: User doesn't have primetrade role assigned
**Solution**: Contact SSO admin to assign role

## Support

For SSO-related issues:
1. Check SSO admin panel at `https://sso.barge2rail.com/admin/`
2. Verify client credentials and redirect URIs
3. Check SSO server logs for authentication errors
4. Contact Barge2Rail SSO administrator

For application issues:
1. Check Django logs at `logs/primetrade.log`
2. Verify `.env` configuration
3. Test with DEBUG=True for detailed error messages
