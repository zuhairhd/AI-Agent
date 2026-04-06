import logging
from rest_framework.decorators import api_view
from rest_framework.response import Response
from apps.portal.models import NotificationPreference
from apps.portal.serializers import NotificationPreferenceSerializer

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
