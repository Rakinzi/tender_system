from rest_framework import viewsets, status
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.response import Response
from ..models import Tender, User
from .serializers import TenderCreateSerializer


class TenderViewSet(viewsets.ModelViewSet):
    queryset = Tender.objects.all()
    serializer_class = TenderCreateSerializer
    parser_classes = (MultiPartParser, JSONParser, FormParser)

    def create(self, request, *args, **kwargs):
        tender_data = (
            request.data.dict() if hasattr(request.data, "dict") else request.data
        )

        documents_data = []
        for key in request.FILES:
            if key.startswith("documents"):
                doc_type = request.data.get(f"{key}_type", "other")
                desc = request.data.get(f"{key}_description", "")
                documents_data.append(
                    {
                        "file": request.FILES[key],
                        "document_type": doc_type,
                        "description": desc,
                    }
                )

        tender_data = {
            "tender_name": tender_data.get("tender_name"),
            "description": tender_data.get("description"),
            "reference_number": tender_data.get("reference_number"),
            "budget": tender_data.get("budget"),
            "deadline": tender_data.get("deadline"),
            "category": tender_data.get("category"),
            "required_department": tender_data.get("required_department"),
            "company": tender_data.get("company"),
            "documents": documents_data,
            "timeline": tender_data.get("timeline"),
        }

        serializer = self.get_serializer(data=tender_data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    def perform_create(self, serializer):
        user = User.objects.filter(role="manager").first()
        serializer.save(created_by=user)