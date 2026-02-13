from django.urls import path
from . import views

urlpatterns = [
    path("search", views.search_view),
    path("download", views.download_report),
]
