# bill_of_entry/views/ledger.py
import os
import uuid

from rest_framework import status
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import LedgerUploadPermission

ALLOWED_EXTENSIONS = {".xlsx", ".xls", ".csv"}
MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB


class LedgerUploadView(APIView):
    permission_classes = [LedgerUploadPermission]
    parser_classes = [MultiPartParser]

    def post(self, request):
        """
        Async ledger upload. Dispatches Celery task and returns task_id.
        Celery tasks for BOE are deferred — returns a stub task_id.
        """
        file_obj = request.FILES.get("file")
        if not file_obj:
            return Response(
                {"detail": "No file provided."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        ext = os.path.splitext(file_obj.name)[1].lower()
        if ext not in ALLOWED_EXTENSIONS:
            return Response(
                {"detail": "Unsupported file type."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if file_obj.size > MAX_UPLOAD_BYTES:
            return Response(
                {"detail": "File too large (max 10 MB)."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Do NOT echo client filename in task_id
        task_id = f"ledger-upload-stub-{uuid.uuid4().hex}"
        return Response(
            {"task_id": task_id, "status": "pending"},
            status=status.HTTP_202_ACCEPTED,
        )
