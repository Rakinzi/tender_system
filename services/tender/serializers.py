from rest_framework import serializers
from ..models import Tender, Document

class TenderSerializer(serializers.ModelSerializer):
    documents = serializers.ListField(
        child=serializers.FileField(max_length=100000, allow_empty_file=False),
        write_only=True,
        required=False
    )

    class Meta:
        model = Tender
        fields = [
            'tender_id', 'tender_name', 'description', 'reference_number',
            'budget', 'deadline', 'category', 'required_department', 'documents',
            'created_by', 'company'  # Add these fields for manual input
        ]
        read_only_fields = ['tender_id', 'status', 'assigned_to']

    def create(self, validated_data):
        documents_data = validated_data.pop('documents', [])
        
        # Create tender without user authentication
        tender = Tender.objects.create(**validated_data)

        # Create documents with a default uploader (you might need to adjust this)
        for doc in documents_data:
            Document.objects.create(
                tender=tender,
                uploader=None,  # Or set a default user
                document_type='notice',
                file=doc
            )

        return tender
    documents = serializers.ListField(
        child=serializers.FileField(max_length=100000, allow_empty_file=False),
        write_only=True,
        required=False
    )

    class Meta:
        model = Tender
        fields = [
            'tender_id', 'tender_name', 'description', 'reference_number',
            'budget', 'deadline', 'category', 'required_department', 'documents'
        ]
        read_only_fields = ['tender_id', 'status', 'created_by', 'company', 'assigned_to']

    def create(self, validated_data):
        documents_data = validated_data.pop('documents', [])
        user = self.context['request'].user
        
        tender = Tender.objects.create(
            created_by=user,
            company=user.company,
            **validated_data
        )

        for doc in documents_data:
            Document.objects.create(
                tender=tender,
                uploader=user,
                document_type='notice',
                file=doc
            )

        return tender