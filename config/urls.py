import os
from pathlib import Path

from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.conf.urls.static import static
from django.http import HttpResponse, FileResponse
from django.views import View


class PortalSPAView(View):
    """
    Serve the built Vue SPA.
    Returns a 503 with setup instructions if the frontend dist/ directory
    has not been built yet.
    """
    def get(self, request, *args, **kwargs):
        dist_index = Path(settings.BASE_DIR) / 'frontend' / 'dist' / 'index.html'
        if not dist_index.exists():
            return HttpResponse(
                "<h2>Portal UI not built yet.</h2>"
                "<p>Run: <code>cd frontend && npm install && npm run build</code></p>",
                content_type='text/html',
                status=503,
            )
        return FileResponse(open(dist_index, 'rb'), content_type='text/html')


urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('apps.asterisk_bridge.urls')),
    path('api/admin/', include('apps.admin_panel.urls')),
    path('api/portal/', include('apps.portal.urls')),

    # Root landing page
    path('', PortalSPAView.as_view(), name='landing_spa'),
]

urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# SPA catch-all for portal routes
urlpatterns += [
    re_path(r'^portal(/.*)?$', PortalSPAView.as_view(), name='portal_spa'),
]
