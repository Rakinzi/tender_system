from rest_framework import viewsets, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.utils import timezone
from ..models import TenderCategory
from .serializers import TenderCategorySerializer
from .utils import create_audit_log, check_user_permission

class TenderCategoryViewSet(viewsets.ModelViewSet):
    serializer_class = TenderCategorySerializer
    permission_classes = [IsAuthenticated]
    queryset = TenderCategory.objects.all()

    def get_queryset(self):
        """
        Optionally restricts the returned categories,
        by filtering against a `name` query parameter in the URL.
        """
        queryset = TenderCategory.objects.all()
        name = self.request.query_params.get('name', None)
        if name is not None:
            queryset = queryset.filter(name__icontains=name)
        return queryset

    def create(self, request, *args, **kwargs):
        # Only managers and admins can create categories
        if not check_user_permission(request.user, 'manager') and not check_user_permission(request.user, 'admin'):
            return Response({
                'message': 'Not authorized to create tender categories',
                'timestamp': timezone.now().strftime('%Y-%m-%d %H:%M:%S'),
                'user': request.user.email
            }, status=status.HTTP_403_FORBIDDEN)

        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            category = serializer.save()
            create_audit_log(
                user=request.user,
                action='create',
                target_model='TenderCategory',
                target_id=category.category_id,
                details=f"Tender category '{category.name}' created"
            )
            return Response({
                'message': 'Tender category created successfully',
                'data': serializer.data,
                'timestamp': timezone.now().strftime('%Y-%m-%d %H:%M:%S'),
                'created_by': request.user.email
            }, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def update(self, request, *args, **kwargs):
        # Only managers and admins can update categories
        if not check_user_permission(request.user, 'manager') and not check_user_permission(request.user, 'admin'):
            return Response({
                'message': 'Not authorized to update tender categories',
                'timestamp': timezone.now().strftime('%Y-%m-%d %H:%M:%S'),
                'user': request.user.email
            }, status=status.HTTP_403_FORBIDDEN)

        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=kwargs.pop('partial', False))
        
        if serializer.is_valid():
            category = serializer.save()
            create_audit_log(
                user=request.user,
                action='update',
                target_model='TenderCategory',
                target_id=category.category_id,
                details=f"Tender category '{category.name}' updated"
            )
            return Response({
                'message': 'Tender category updated successfully',
                'data': serializer.data,
                'timestamp': timezone.now().strftime('%Y-%m-%d %H:%M:%S'),
                'updated_by': request.user.email
            })
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def destroy(self, request, *args, **kwargs):
        # Only admins can delete categories
        if not check_user_permission(request.user, 'admin'):
            return Response({
                'message': 'Not authorized to delete tender categories',
                'timestamp': timezone.now().strftime('%Y-%m-%d %H:%M:%S'),
                'user': request.user.email
            }, status=status.HTTP_403_FORBIDDEN)

        instance = self.get_object()
        category_name = instance.name
        
        create_audit_log(
            user=request.user,
            action='delete',
            target_model='TenderCategory',
            target_id=instance.category_id,
            details=f"Tender category '{category_name}' deleted"
        )
        
        self.perform_destroy(instance)
        return Response({
            'message': f'Tender category "{category_name}" deleted successfully',
            'timestamp': timezone.now().strftime('%Y-%m-%d %H:%M:%S'),
            'deleted_by': request.user.email
        }, status=status.HTTP_200_OK)