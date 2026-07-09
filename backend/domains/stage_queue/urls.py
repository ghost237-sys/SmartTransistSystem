from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    ArrivedAtLoadingBayView, CallUpView, CheckInView, ConfirmView, DepartView, MarkFullView, MyQueueStatusView,
    QueueEntryViewSet, QueueStatusView, ReorderQueueView, StageViewSet
)

router = DefaultRouter()
router.register(r'stages', StageViewSet, basename='stage')
router.register(r'queue-entries', QueueEntryViewSet, basename='queueentry')

urlpatterns = [
    path('check-in/', CheckInView.as_view(), name='check-in'),
    path('confirm/', ConfirmView.as_view(), name='confirm'),
    path('call-up/', CallUpView.as_view(), name='call-up'),
    path('arrived-at-loading-bay/', ArrivedAtLoadingBayView.as_view(), name='arrived-at-loading-bay'),
    path('depart/', DepartView.as_view(), name='depart'),
    path('status/', QueueStatusView.as_view(), name='queue-status'),
    path('my-status/', MyQueueStatusView.as_view(), name='my-queue-status'),
    path('reorder/', ReorderQueueView.as_view(), name='reorder-queue'),
    path('mark-full/', MarkFullView.as_view(), name='mark-full'),
]

urlpatterns += router.urls
