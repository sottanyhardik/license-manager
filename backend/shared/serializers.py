from rest_framework import serializers


class EnvelopeMixin:
    """
    Mixin that wraps serializer `data` in the standard response envelope.

    Use via EnvelopeSerializer or call `EnvelopeMixin.wrap(data, success, message)`.
    """

    @staticmethod
    def wrap(data=None, success: bool = True, message: str | None = None, errors=None) -> dict:
        if success:
            return {"success": True, "data": data, "message": message}
        return {"success": False, "data": None, "errors": errors or [], "message": message or "An error occurred"}


class EnvelopeSerializer(EnvelopeMixin, serializers.Serializer):
    """Base serializer that exposes the envelope helper."""
    pass
