from rest_framework import serializers
from ..models import Tender, Document, User, TenderTimeline


class DocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Document
        fields = ["document_type", "file", "description"]


class TenderCreateSerializer(serializers.ModelSerializer):
    documents = DocumentSerializer(many=True, required=False)
    timeline = serializers.JSONField(required=False)

    class Meta:
        model = Tender
        fields = [
            "tender_name",
            "description",
            "reference_number",
            "budget",
            "deadline",
            "category",
            "required_department",
            "company",
            "documents",
            "timeline",
        ]

    def create(self, validated_data):
        documents_data = validated_data.pop("documents", [])
        timeline_data = validated_data.pop("timeline", None)

        tender = Tender.objects.create(**validated_data)

        if timeline_data:
            TenderTimeline.objects.create(tender=tender, **timeline_data)
        else:
            tender.get_timeline()

        for doc_data in documents_data:
            Document.objects.create(
                tender=tender, uploader=validated_data["created_by"], **doc_data
            )

        managers = User.objects.filter(
            department=tender.required_department,
            role="manager",
            company=tender.company,
        )
        tender.assigned_to.add(*managers)
        return tender
