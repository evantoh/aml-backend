# compliance/views.py
from multiprocessing import context
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from .services.unified_sanctions import UnifiedSanctionsBot  
import base64
import json
import requests
import os
from django.shortcuts import render, redirect
import configparser
from django.template.context_processors import csrf
from django.views.decorators.csrf import csrf_exempt
from datetime import datetime

from django.http import HttpResponse
from .serializers import SanctionsSearchSerializer, SanctionsReportSerializer,SanctionsCombinedReportSerializer

class SanctionsSearchView(APIView):
    """
    POST /api/sanctions/search
    {
      "query": "Name or term",
      "include_report": true,          # optional, default: true
      "min_score_threshold": 85,       # optional, default: 70
      "client_id": "8a8187b26a786927016a81b129d675a3",  # optional
    }
    """
    def post(self, request):
        ser = SanctionsSearchSerializer(data=request.data)
        if not ser.is_valid():
            return Response(ser.errors, status=status.HTTP_400_BAD_REQUEST)

        query = ser.validated_data["query"].strip()
        include_report = ser.validated_data["include_report"]
        min_score = ser.validated_data.get("min_score_threshold", 70)  # Default to 70
        client_id = ser.validated_data.get("client_id", "").strip()
        owner_type = ser.validated_data.get("owner_type")
        if owner_type  in ["LOAN_ACCOUNT"]:
            recipient_id = ser.validated_data.get("recipient_id")
        else:
            recipient_id = None
        # Default to CLIENT

        try:
            svc = UnifiedSanctionsBot()

            # Prepare request data for the API method
            request_data = {
                "query": query,
                "include_report": include_report,
                "min_score_threshold": min_score,
                "client_id": client_id if client_id else None,
                "owner_type": owner_type,
                "recipient_id": recipient_id
            }
            print("Request Data:", request_data)  # Debugging line

            # Use the screen_from_api method which handles all the logic
            result = svc.screen_from_api(request_data)

            return Response(result, status=status.HTTP_200_OK)

        except Exception as exc:
            return Response(
                {"detail": "Search failed", "error": str(exc)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class SanctionsReportView(APIView):
    """POST /sanctions/report
    {
      "query": "search term",
      "match": { ...single result object... },
      "client_id": "optional",
      "owner_type": "CLIENT"
    }
    Returns: application/pdf (attachment)
    """

    def post(self, request):
        ser = SanctionsReportSerializer(data=request.data)
        if not ser.is_valid():
            return Response(ser.errors, status=status.HTTP_400_BAD_REQUEST)

        query = ser.validated_data["query"].strip()
        match = ser.validated_data["match"]
        client_id = ser.validated_data.get("client_id", "").strip()
        owner_type = ser.validated_data.get("owner_type", "CLIENT")

        try:
            svc = UnifiedSanctionsBot()
            pdf_bytes = svc.generate_pdf_report_bytes(
                query=query,
                match=match,
                client_id=client_id,
                owner_type=owner_type,
            )

            safe_q = "_".join(query.split()) or "query"
            filename = f"sanctions_report_{safe_q}.pdf"

            resp = HttpResponse(pdf_bytes, content_type="application/pdf")
            resp["Content-Disposition"] = f'attachment; filename="{filename}"'
            return resp

        except Exception as exc:
            return Response(
                {"detail": "Report generation failed", "error": str(exc)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

class SanctionsCombinedReportView(APIView):
    def post(self, request):
        ser = SanctionsCombinedReportSerializer(data=request.data)
        if not ser.is_valid():
            return Response(ser.errors, status=status.HTTP_400_BAD_REQUEST)

        query = ser.validated_data["query"].strip()
        results = ser.validated_data.get("results", [])
        matches_found = ser.validated_data.get("matches_found", None)
        client_id = ser.validated_data.get("client_id", "").strip()
        owner_type = ser.validated_data.get("owner_type", "CLIENT")

        try:
            svc = UnifiedSanctionsBot()
            pdf_bytes = svc.generate_combined_pdf_report_bytes(
                query=query,
                results=results,
                matches_found=matches_found,
                client_id=client_id,
                owner_type=owner_type,
            )

            safe_q = "_".join(query.split()) or "query"
            filename = f"unified_sanctions_report_{safe_q}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"

            resp = HttpResponse(pdf_bytes, content_type="application/pdf")
            resp["Content-Disposition"] = f'attachment; filename=\"{filename}\"'
            return resp

        except Exception as exc:
            return Response(
                {"detail": "Combined report generation failed", "error": str(exc)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )