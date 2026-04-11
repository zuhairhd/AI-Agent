import logging
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from apps.portal.models import NotificationPreference, SiteConfig
from apps.portal.serializers import NotificationPreferenceSerializer, SiteConfigSerializer

logger = logging.getLogger(__name__)


@api_view(['GET', 'PUT'])
def notification_preferences_view(request):
    pref, _ = NotificationPreference.objects.get_or_create(user=request.user)

    if request.method == 'GET':
        return Response(NotificationPreferenceSerializer(pref).data)

    serializer = NotificationPreferenceSerializer(pref, data=request.data, partial=True)
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data)
    return Response(serializer.errors, status=400)


@api_view(['GET', 'PUT'])
def site_config_view(request):
    """
    GET  /api/portal/settings/site-config/ — read branding/config (all authenticated users)
    PUT  /api/portal/settings/site-config/ — update config (staff only)
    """
    cfg = SiteConfig.get_solo()

    if request.method == 'GET':
        return Response(SiteConfigSerializer(cfg).data)

    if not request.user.is_staff:
        return Response({'detail': 'Staff access required.'}, status=status.HTTP_403_FORBIDDEN)

    serializer = SiteConfigSerializer(cfg, data=request.data, partial=True)
    if serializer.is_valid():
        serializer.save()
        logger.info(f"[site_config] Updated by {request.user.username}")
        return Response(serializer.data)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
