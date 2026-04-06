import logging
from django.contrib.auth import authenticate, login, logout
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

logger = logging.getLogger(__name__)


def _user_data(user):
    return {
        'id':       user.id,
        'username': user.username,
        'email':    user.email,
        'is_staff': user.is_staff,
        'first_name': user.first_name,
        'last_name':  user.last_name,
    }


@api_view(['POST'])
@permission_classes([AllowAny])
def login_view(request):
    username = request.data.get('username') or request.data.get('email', '')
    password = request.data.get('password', '')

    user = authenticate(request, username=username, password=password)
    if user is None:
        return Response({'detail': 'Invalid credentials'}, status=status.HTTP_401_UNAUTHORIZED)

    login(request, user)
    logger.info(f"[portal.auth] User '{user.username}' logged in")
    return Response(_user_data(user))


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def logout_view(request):
    logger.info(f"[portal.auth] User '{request.user.username}' logged out")
    logout(request)
    return Response({'detail': 'Logged out'})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def me_view(request):
    return Response(_user_data(request.user))
