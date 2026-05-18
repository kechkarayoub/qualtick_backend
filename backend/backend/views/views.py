# pylint: disable=broad-exception-caught,logging-fstring-interpolation
"""
Core views for the backend project.
"""

import logging

from django.conf import settings
from django.http import JsonResponse
from django.utils.translation import activate, gettext_lazy as _
from django.views.decorators.cache import cache_page
from django.views.decorators.http import require_http_methods
from django.views.decorators.vary import vary_on_headers
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from backend.exceptions import GeolocationException
from backend.repositories import ContactMessageRepository
from backend.serializers import ContactMessageSerializer, AuditLogSerializer
from backend.services.services import GeolocationService, ContactMessageService
from backend.services.audit_log_service import AuditLogService
from backend.utils import get_db_alias
from permissions.drf_permissions import require_permission


logger = logging.getLogger(__name__)


@require_http_methods(["GET"])
@cache_page(60 * 15)  # Cache for 15 minutes
@vary_on_headers('User-Agent', 'Accept-Language')
def get_geolocation(request):
    """
    Fetch geolocation data for a client's IP address.
    Query Parameters:
        - requested_info (str, optional): Comma-separated fields 
            (e.g., "country,countryCode")
        - selected_language (str, optional): Language code (e.g., "fr" for French)
    Returns:
        JsonResponse: Geolocation data or error message
        - Success: 200 + { "country": "France", "countryCode": "FR", ... }
        - Error: 400 + { "error": "message" }
    """
    client_ip = None
    try:
        # Get client IP address
        client_ip = GeolocationService.get_client_ip(request)
        # Parse query parameters
        requested_info = request.GET.get("requested_info", "country,countryCode")
        current_language = request.GET.get("selected_language", "fr")
        # Activate language
        activate(current_language)
        # Get geolocation data
        data = GeolocationService.get_geolocation_data(client_ip, requested_info)
        return JsonResponse(data, status=200)
    except GeolocationException as e:
        logger.warning(f"Geolocation error for IP {client_ip}: {str(e)}")
        return JsonResponse({
            "error": str(e)
        }, status=400)
    except Exception as e:
        logger.error(f"Unexpected error in geolocation view: {str(e)}", exc_info=True)
        return JsonResponse({
            "error": _("An unexpected error occurred")
        }, status=500)


@api_view(['GET'])
@permission_classes([AllowAny])
def health_check(request):
    """
    Health check endpoint for monitoring.
    Returns:
        Response: Health status
    """
    return Response({
        "status": "healthy",
        "message": "Service is running"
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([AllowAny])
def api_info(request):
    """
    API information endpoint.
    Returns:
        Response: API information
    """
    return Response({
        "application": settings.APPLICATION_NAME,
        "version": "1.0.0",
        "environment": settings.ENVIRONMENT,
        "languages": [lang[0] for lang in settings.LANGUAGES],
        "timezone": settings.TIME_ZONE,
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([AllowAny])
def contact_message_create(request):
    """
    Create a new contact message.
    POST /api/contact/
    Request Body:
        - name (str): Full name of the person
        - email (str): Email address for response
        - subject (str): Subject category (support, billing, feature, partnership, other)
        - message (str): The message content (min 10 characters)
    Returns:
        201: Message created successfully
        400: Validation errors
    """
    db_alias = get_db_alias(request=request)
    try:
        serializer = ContactMessageSerializer(data=request.data,
                                            context={'request': request})
        if serializer.is_valid():
            # Use service layer to create the contact message
            result = ContactMessageService.create_contact_message(
                serializer.validated_data,
                user=request.user if request.user.is_authenticated else None,
                db_alias=db_alias
            )
            
            if result['success']:
                return Response({
                    'success': True,
                    'message': _('Your message has been sent successfully. We will get '
                                 'back to you within 24 hours.'),
                    'id': result['id']
                }, status=status.HTTP_201_CREATED)
            else:
                return Response({
                    'success': False,
                    'message': result.get('error', _('Failed to create message'))
                }, status=status.HTTP_400_BAD_REQUEST)
        
        return Response({
            'success': False,
            'message': _('Please correct the errors below.'),
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.error(f"Error creating contact message: {str(e)}")
        return Response({
            'success': False,
            'message': _('An error occurred while sending your message. Please try again '
                         'later.')
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def contact_message_list(request):
    """
    List contact messages. Admin users see all, regular users see only their own.
    GET /api/contact/messages/
    
    Query Parameters:
        - status (str, optional): Filter by status (new, in_progress, resolved, closed)
        - search (str, optional): Search in name, email, or message
    
    Returns:
        200: List of contact messages
    """
    try:
        db_alias = get_db_alias(request=request)
        user = request.user
        status_filter = request.GET.get('status')
        search_query = request.GET.get('search')
        
        # Admin users can see all messages, regular users see only their own
        if user.is_staff or user.is_superuser:
            if search_query:
                messages = ContactMessageService.search_messages(search_query,
                                                                 db_alias=db_alias)
            elif status_filter:
                messages = ContactMessageService.get_messages_by_status(status_filter,
                                                                        db_alias=db_alias)
            else:
                messages = ContactMessageRepository.all(db_alias=db_alias)
        else:
            messages = ContactMessageService.get_user_messages(user.id, db_alias=db_alias)
            if status_filter:
                messages = messages.filter(status=status_filter)
            if search_query:
                from django.db.models import Q
                messages = messages.filter(
                    Q(subject__icontains=search_query) |
                    Q(message__icontains=search_query)
                )
        
        # Serialize the messages
        serializer = ContactMessageSerializer(messages, many=True)
        
        return Response({
            'success': True,
            'count': messages.count(),
            'messages': serializer.data
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Error listing contact messages: {str(e)}")
        return Response({
            'success': False,
            'message': _('An error occurred while fetching messages.')
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def contact_message_detail(request, message_id):
    """
    Get a specific contact message by ID.
    GET /api/contact/messages/<id>/
    
    Returns:
        200: Message details
        403: Forbidden (not admin and not owner)
        404: Message not found
    """
    db_alias = get_db_alias(request=request)
    try:
        message = ContactMessageService.get_message_by_id(message_id, db_alias=db_alias)
        
        if not message:
            return Response({
                'success': False,
                'message': _('Message not found')
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Check permissions: admin or message owner
        user = request.user
        if not (user.is_staff or user.is_superuser or message.user_id == user.id):
            return Response({
                'success': False,
                'message': _('You do not have permission to view this message')
            }, status=status.HTTP_403_FORBIDDEN)
        
        serializer = ContactMessageSerializer(message)
        
        return Response({
            'success': True,
            'message': serializer.data
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Error retrieving contact message {message_id}: {str(e)}")
        return Response({
            'success': False,
            'message': _('An error occurred while fetching the message.')
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['PATCH'])
@permission_classes([IsAuthenticated, require_permission('manage_contact_messages')])
def contact_message_update_status(request, message_id):
    """
    Update the status of a contact message.
    PATCH /api/contact/messages/<id>/status/
    
    Request Body:
        - status (str): New status (new, in_progress, resolved, closed)
        - admin_notes (str, optional): Admin notes
    
    Returns:
        200: Status updated successfully
        404: Message not found
        400: Invalid status
    """
    db_alias = get_db_alias(request=request)
    try:
        new_status = request.data.get('status')
        admin_notes = request.data.get('admin_notes')
        
        if not new_status:
            return Response({
                'success': False,
                'message': _('Status is required')
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Validate status
        valid_statuses = ['new', 'in_progress', 'resolved', 'closed']
        if new_status not in valid_statuses:
            return Response({
                'success': False,
                'message': _('Invalid status. Must be one of: new, in_progress, resolved, closed')
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Update through service
        updated_message = ContactMessageService.update_message_status(
            message_id, new_status, admin_notes, db_alias=db_alias
        )
        
        if not updated_message:
            return Response({
                'success': False,
                'message': _('Message not found')
            }, status=status.HTTP_404_NOT_FOUND)
        
        serializer = ContactMessageSerializer(updated_message)
        
        logger.info(f"Contact message {message_id} status updated to {new_status} by {request.user.username}")
        
        return Response({
            'success': True,
            'message': _('Status updated successfully'),
            'data': serializer.data
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Error updating contact message {message_id} status: {str(e)}")
        return Response({
            'success': False,
            'message': _('An error occurred while updating the message.')
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated, require_permission('manage_contact_messages')])
def contact_message_statistics(request):
    """
    Get contact message statistics.
    GET /api/contact/statistics/
    
    Returns:
        200: Statistics data
    """
    db_alias = get_db_alias(request=request)
    try:
        stats = ContactMessageService.get_statistics(db_alias=db_alias)
        
        return Response({
            'success': True,
            'statistics': stats
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Error retrieving contact message statistics: {str(e)}")
        return Response({
            'success': False,
            'message': _('An error occurred while fetching statistics.')
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated, require_permission('view_audit_logs')])
def audit_log_list(request):
    """
    List audit logs.
    GET /api/audit-logs/

    Query parameters:
        - user_id      (int)
        - action       (str)
        - outcome      (str)
        - resource_type (str)
        - resource_id  (str)
        - date_from    (ISO-8601)
        - date_to      (ISO-8601)
        - page         (int, default 1)
        - page_size    (int, default 50, max 200)
    """
    from django.utils.dateparse import parse_datetime
    db_alias = get_db_alias(request=request)
    try:
        filters = {}
        for key in ('user_id', 'action', 'outcome', 'resource_type', 'resource_id'):
            val = request.GET.get(key)
            if val:
                filters[key] = int(val) if key == 'user_id' else val
        date_from = parse_datetime(request.GET.get('date_from', '')) if request.GET.get('date_from') else None
        date_to   = parse_datetime(request.GET.get('date_to', ''))   if request.GET.get('date_to')   else None

        qs = AuditLogService.get_logs(
            **filters, date_from=date_from, date_to=date_to, db_alias=db_alias
        )

        try:
            page_size = min(int(request.GET.get('page_size', 50)), 200)
            page      = max(int(request.GET.get('page', 1)), 1)
        except (ValueError, TypeError):
            page_size, page = 50, 1

        total  = qs.count()
        offset = (page - 1) * page_size
        logs   = qs[offset: offset + page_size]

        serializer = AuditLogSerializer(logs, many=True)
        return Response({
            'success': True,
            'total': total,
            'page': page,
            'page_size': page_size,
            'logs': serializer.data,
        }, status=status.HTTP_200_OK)
    except Exception as e:
        logger.error(f"Error listing audit logs: {str(e)}")
        return Response({
            'success': False,
            'message': _('An error occurred while fetching audit logs.'),
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated, require_permission('view_audit_logs')])
def audit_log_detail(request, log_id):
    """
    Retrieve a single audit log entry.
    GET /api/audit-logs/<id>/
    """
    from backend.repositories import AuditLogRepository
    db_alias = get_db_alias(request=request)
    try:
        log = AuditLogRepository.get_by_id(log_id, db_alias=db_alias)
        if not log:
            return Response({'success': False, 'message': _('Log entry not found.')},
                            status=status.HTTP_404_NOT_FOUND)
        serializer = AuditLogSerializer(log)
        return Response({'success': True, 'log': serializer.data}, status=status.HTTP_200_OK)
    except Exception as e:
        logger.error(f"Error retrieving audit log {log_id}: {str(e)}")
        return Response({
            'success': False,
            'message': _('An error occurred while fetching the log entry.'),
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated, require_permission('view_audit_logs')])
def audit_log_statistics(request):
    """
    Return aggregate statistics for the audit log.
    GET /api/audit-logs/statistics/
    """
    db_alias = get_db_alias(request=request)
    try:
        stats = AuditLogService.get_statistics(db_alias=db_alias)
        return Response({'success': True, 'statistics': stats}, status=status.HTTP_200_OK)
    except Exception as e:
        logger.error(f"Error retrieving audit log statistics: {str(e)}")
        return Response({
            'success': False,
            'message': _('An error occurred while fetching statistics.'),
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
