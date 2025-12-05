import os
from django.http import Http404, HttpResponseRedirect, FileResponse
from django.contrib.auth.decorators import login_required
from django.core.files.storage import default_storage
from django.views.static import serve
from django.views.decorators.csrf import ensure_csrf_cookie
from django.conf import settings
from primetrade_project.decorators import require_role
from bol_system.permissions import feature_permission_required


@login_required
@feature_permission_required('dashboard', 'view')
@ensure_csrf_cookie
def dashboard(request):
    """
    Main dashboard view with RBAC enforcement.

    Requires 'dashboard:view' permission from SSO RBAC.
    """
    file_path = os.path.join(settings.BASE_DIR, 'static', 'index.html')
    return serve(request, 'index.html', document_root=os.path.join(settings.BASE_DIR, 'static'))


@login_required
@require_role('Admin', 'Office', 'Client')
def secure_media_download(request, path):
    """
    Generate signed S3 URL for authenticated users.

    Phase 1: Any authenticated role can download (single-tenant)
    Phase 2: Add tenant filtering to restrict cross-tenant access
    """
    # TODO Phase 2: Add tenant filtering using request.tenant_id

    # Verify file exists in storage
    if not default_storage.exists(path):
        raise Http404("File not found")

    # If using local filesystem storage, stream the file directly to avoid redirect loops
    if not hasattr(default_storage, 'bucket'):
        local_path = default_storage.path(path)
        if not os.path.exists(local_path):
            raise Http404("File not found")
        return FileResponse(open(local_path, 'rb'))

    # Generate signed URL (24-hour expiry via AWS_QUERYSTRING_EXPIRE)
    signed_url = default_storage.url(path)
    return HttpResponseRedirect(signed_url)
