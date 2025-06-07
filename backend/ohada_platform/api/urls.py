from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    UserViewSet, CurrentUserView,
    DocumentCategoryViewSet, DocumentTemplateViewSet # Added new ViewSets
)

router = DefaultRouter()
router.register(r'users', UserViewSet, basename='user')
router.register(r'categories', DocumentCategoryViewSet, basename='documentcategory')
router.register(r'templates', DocumentTemplateViewSet, basename='documenttemplate')

urlpatterns = [
    path('', include(router.urls)),
    path('users/me/', CurrentUserView.as_view(), name='current-user'),
]
