# bill_of_entry/views/ledger.py
from rest_framework import status
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import BillOfEntryPermission


class LedgerUploadView(APIView):
    permission_classes = [BillOfEntryPermission]
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

        # Dispatch async task (stub — task implementation deferred)
        task_id = f"ledger-upload-stub-{file_obj.name}"
        return Response(
            {"task_id": task_id, "status": "pending"},
            status=status.HTTP_202_ACCEPTED,
        )
