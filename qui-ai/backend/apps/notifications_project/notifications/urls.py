from django.urls import path
from .views import NotificationListCreateView, NotificationDetailView, MarkAllNotificationsReadView

urlpatterns = [
    path('notifications/', NotificationListCreateView.as_view(), name='notification-list'),
    path('notifications/<int:pk>/', NotificationDetailView.as_view(), name='notification-detail'),
    path('notifications/mark-all-read/', MarkAllNotificationsReadView.as_view(), name='mark-all-read'),

]
