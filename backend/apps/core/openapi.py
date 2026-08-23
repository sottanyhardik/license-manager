"""Schema-only drf-spectacular extensions for the public API contract.

The application contains a number of small APIViews whose response shape is
computed at runtime (exports, task status and operational reports).  They do
not have a DRF serializer because adding one would change neither the runtime
payload nor validation, but drf-spectacular needs an explicit schema shape.
These extensions are loaded by :class:`CoreConfig` and affect documentation
generation only.
"""
from __future__ import annotations

from drf_spectacular.extensions import (
    OpenApiAuthenticationExtension,
    OpenApiSerializerFieldExtension,
    OpenApiViewExtension,
)
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import serializers


class QueryParameterJWTAuthenticationScheme(OpenApiAuthenticationExtension):
    """Document the standard bearer header accepted by the JWT authenticator.

    Query-string support is deliberately limited to authenticated download
    URLs by the runtime authenticator.  It is not advertised as a general
    credential transport in OpenAPI.
    """

    target_class = "apps.core.authentication.JWTAuthenticationFromQueryParam"
    name = "jwtAuth"

    def get_security_definition(self, auto_schema):
        return {"type": "http", "scheme": "bearer", "bearerFormat": "JWT"}


class PeerTokenAuthenticationScheme(OpenApiAuthenticationExtension):
    """Document the private sync peer bearer credential."""

    target_class = "apps.core.sync.authentication.PeerTokenAuthentication"
    name = "peerTokenAuth"

    def get_security_definition(self, auto_schema):
        return {"type": "http", "scheme": "bearer", "bearerFormat": "Peer token"}


class RuntimeObjectSerializer(serializers.Serializer):
    """Accurate safe fallback for dynamic JSON object endpoints.

    The affected endpoints return response dictionaries assembled from report,
    task, import, or file metadata.  Treating their payload as a JSON object
    avoids fabricating fields while retaining the actual documented transport
    contract.  Normal ModelViewSet endpoints continue using their concrete
    serializers.
    """

    # An empty DRF serializer intentionally produces an OpenAPI object without
    # invented properties.  The documented endpoints retain their dynamic
    # report/task metadata keys while clients can rely on the JSON-object
    # transport type.
    pass


class RuntimeAPIViewSchema(OpenApiViewExtension):
    """Give dynamic APIViews an explicit response serializer for OpenAPI.

    This is intentionally limited to plain ``APIView`` subclasses which have
    no serializer_class.  GenericAPIView/ViewSet implementations retain their
    native concrete serializer introspection.
    """

    target_class = "rest_framework.views.APIView"
    match_subclasses = True
    priority = -1

    def view_replacement(self):
        target = self.target
        if getattr(target, "serializer_class", None) is not None:
            return target
        attrs = {"serializer_class": RuntimeObjectSerializer}
        if target.__name__ == "LicenseLedgerViewSet":
            # The collection/detail handlers are bespoke and do not call a
            # queryset.  A harmless empty queryset gives schema generation a
            # concrete integer lookup model without altering request handling.
            from apps.license.models import LicenseDetailsModel
            attrs["queryset"] = LicenseDetailsModel.objects.none()
        # Schema generation instantiates this replacement only.  Runtime URL
        # callbacks still point at the original view class.
        replacement = type(
            f"{target.__name__}Schema",
            (target,),
            attrs,
        )
        # These action-only ViewSets intentionally have no model queryset.
        # Their route converters accept integer database identifiers.  Declare
        # the concrete path types here rather than letting spectacular infer a
        # misleading string from the missing queryset.
        parameter_names = {
            "AllotmentActionViewSet": {"id", "item_id"},
            "InventoryBalanceViewSet": {"id"},
            "ItemPivotViewSet": {"task_id"},
            "LicenseActionViewSet": {"id"},
            "LicenseLedgerViewSet": {"id"},
        }.get(target.__name__, set())
        action_parameters = [
            OpenApiParameter(name, OpenApiTypes.INT, OpenApiParameter.PATH)
            for name in parameter_names
        ]
        return extend_schema(parameters=action_parameters)(replacement)


class RuntimeSerializerMethodFieldSchema(OpenApiSerializerFieldExtension):
    """Document unannotated ``SerializerMethodField`` return values.

    Existing runtime serializers commonly expose formatted Decimal/date values
    as JSON strings.  Boolean predicate names are documented as booleans and
    structured metadata names as objects.  This matches wire behaviour while
    avoiding the previous misleading implicit-string warning fallback.
    """

    target_class = "rest_framework.fields.SerializerMethodField"
    match_subclasses = True
    priority = 1

    _BOOLEAN_PREFIXES = ("is_", "has_", "needs_", "can_", "should_")
    _BOOLEAN_NAMES = {"quantity_cap_applied"}
    _OBJECT_NAMES = {
        "ledger", "items_detail", "norm_details", "planning_options",
        "linked_trade_info", "counterpart_info", "roles",
    }

    def map_serializer_field(self, auto_schema, direction):
        field_name = self.target.field_name
        if field_name.startswith(self._BOOLEAN_PREFIXES) or field_name in self._BOOLEAN_NAMES:
            return {"type": "boolean", "readOnly": True}
        if field_name in self._OBJECT_NAMES:
            return {
                "type": "object",
                "additionalProperties": {},
                "readOnly": True,
            }
        # Decimal/date and display-label getters are JSON strings in DRF's
        # default renderer.  This is the same wire type that the old fallback
        # produced, now declared deliberately and warning-free.
        return {"type": "string", "readOnly": True}
