from rest_framework import serializers


class SanctionsSearchSerializer(serializers.Serializer):
    query = serializers.CharField()
    include_report = serializers.BooleanField(required=False, default=False)
    min_score_threshold = serializers.IntegerField(required=False, default=90)
    client_id = serializers.CharField(required=False, allow_blank=True, default="")
    owner_type = serializers.CharField(required=False, default="CLIENT")
    recipient_id = serializers.IntegerField(required=False, allow_null=True, default=None)


class SanctionsReportSerializer(serializers.Serializer):
    """Payload for generating a PDF report for a specific match/result."""
    query = serializers.CharField()
    match = serializers.JSONField()
    client_id = serializers.CharField(required=False, allow_blank=True, default="")
    owner_type = serializers.CharField(required=False, default="CLIENT")

class SanctionsCombinedReportSerializer(serializers.Serializer):
    query = serializers.CharField()
    matches_found = serializers.IntegerField(required=False, allow_null=True)
    results = serializers.ListField(child=serializers.JSONField(), required=False, default=list)
    client_id = serializers.CharField(required=False, allow_blank=True, default="")
    owner_type = serializers.CharField(required=False, default="CLIENT")