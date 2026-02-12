from django.urls import path
from .import views
from .views import SanctionsSearchView, SanctionsReportView,SanctionsCombinedReportView

app_name = 'sanctionScereningV2'


urlpatterns = [

    # API endpoint for programmatic access
    path("search", SanctionsSearchView.as_view(), name="sanctions-search"),
    
    path("report",SanctionsReportView.as_view(), name="sanctions-report"),

    path("report/combined", SanctionsCombinedReportView.as_view(), name="sanctions-report-combined"),  # ✅ new

]