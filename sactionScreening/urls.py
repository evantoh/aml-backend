from django.contrib import admin
from django.urls import path, include
from sanctions.views import dashboard
from django.urls import path, include
from django.contrib.auth import views as auth_views
from sanctions.views import dashboard

urlpatterns = [
    
    path("admin/", admin.site.urls),

    # LOGIN
    path("login/", auth_views.LoginView.as_view(template_name="login.html"), name="login"),
    path("logout/", auth_views.LogoutView.as_view(next_page="login"), name="logout"),

    path("", dashboard, name="dashboard"),  # ROOT DASHBOARD
    path("sanctions/", include("sanctions.urls")),
]
