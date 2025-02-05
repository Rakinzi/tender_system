from rest_framework import serializers
from ..models import Tender, TenderTimeline, Document, Approval, TenderCategory, User

class TenderTimelineSerializer(serializers.ModelSerializer):
    class Meta:
        model = TenderTimeline
        fields = '__all__'
        read_only_fields = ['tender']

class TenderDocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Document
        fields = ['document_id', 'document_type', 'file', 'description', 'created_at']
        read_only_fields = ['uploader']

class TenderApprovalSerializer(serializers.ModelSerializer):
    class Meta:
        model = Approval
        fields = ['approval_id', 'status', 'comments', 'created_at', 'approver']
        read_only_fields = ['approver']
        
class TenderSerializer(serializers.ModelSerializer):
    timeline = TenderTimelineSerializer(required=False)
    documents = TenderDocumentSerializer(many=True, read_only=True)
    approvals = TenderApprovalSerializer(many=True, read_only=True)
    
    class Meta:
        model = Tender
        fields = [
            'tender_id', 'tender_name', 'description', 'reference_number',
            'budget', 'deadline', 'status', 'company', 'category',
            'required_department', 'timeline', 'documents', 'approvals',
            'created_by', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_by', 'reference_number', 'status', 'created_at', 'updated_at']

    def create(self, validated_data):
        timeline_data = validated_data.pop('timeline', None)
        tender = super().create(validated_data)
        
        if timeline_data:
            TenderTimeline.objects.create(tender=tender, **timeline_data)
        else:
            # Create default timeline
            tender.get_timeline()
            
        return tender