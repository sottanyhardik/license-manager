import logging
from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status

logger = logging.getLogger(__name__)


def custom_exception_handler(exc, context):
    """
    Global DRF exception handler.

    Wraps all error responses in the standard envelope:
      {"success": false, "data": null, "errors": [...], "message": "..."}
    """
    response = exception_handler(exc, context)

    if response is not None:
        errors = []
        data = response.data

        if isinstance(data, dict):
            for field, messages in data.items():
                if isinstance(messages, list):
                    for msg in messages:
                        errors.append({"field": field, "message": str(msg)})
                else:
                    errors.append({"field": field, "message": str(messages)})
        elif isinstance(data, list):
            errors = [{"field": "non_field_errors", "message": str(m)} for m in data]
        else:
            errors = [{"field": "detail", "message": str(data)}]

        message = "Validation failed" if response.status_code == status.HTTP_400_BAD_REQUEST else str(exc)

        response.data = {
            "success": False,
            "data": None,
            "errors": errors,
            "message": message,
        }

    else:
        logger.exception("Unhandled exception in view", exc_info=exc)
        response = Response(
            {
                "success": False,
                "data": None,
                "errors": [{"field": "detail", "message": "Internal server error"}],
                "message": "Internal server error",
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    return response
