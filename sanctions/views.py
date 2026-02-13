from django.shortcuts import render
from django.http import JsonResponse, FileResponse, Http404
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
import os
import json
from .services.unified_sanctions import UnifiedSanctionsBot

from django.contrib.auth.decorators import login_required

@login_required(login_url="/login/")
def dashboard(request):
    return render(request, "dashboard.html")


@csrf_exempt
def search_view(request):
    bot = UnifiedSanctionsBot()
    data = json.loads(request.body)

    response = bot.screen_from_api(data)

    return JsonResponse(response)


def download_report(request):
    filename = request.GET.get("filename")

    if not filename:
        raise Http404("Filename missing")

    filepath = os.path.join(settings.MEDIA_ROOT, filename)

    # Security check (VERY IMPORTANT)
    if not filepath.startswith(str(settings.MEDIA_ROOT)):
        raise Http404("Invalid path")

    if not os.path.exists(filepath):
        raise Http404("File not found")

    return FileResponse(
        open(filepath, "rb"),
        as_attachment=True,
        filename=filename,
        content_type="text/plain"
    )
