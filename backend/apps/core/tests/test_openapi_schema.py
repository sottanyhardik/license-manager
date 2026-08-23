"""Regression coverage for the generated public OpenAPI contract."""

from drf_spectacular.generators import SchemaGenerator


def test_openapi_schema_generates_dynamic_endpoints_with_documented_security():
    """Dynamic operational APIViews must remain present and schema-valid.

    This exercises the same generator used by ``manage.py spectacular``.  It
    guards against reintroducing APIView/serializer/authentication discovery
    warnings while leaving runtime response construction untouched.
    """

    schema = SchemaGenerator().get_schema(request=None, public=True)

    assert "/api/allotment-actions/{id}/available-licenses/" in schema["paths"]
    assert "/api/masters/throttle-status/" in schema["paths"]
    assert "/api/masters/throttle-status/{scope}/" in schema["paths"]
    assert schema["components"]["securitySchemes"]["jwtAuth"] == {
        "type": "http",
        "scheme": "bearer",
        "bearerFormat": "JWT",
    }
    assert (
        schema["paths"]["/api/masters/throttle-status/"]["get"]["operationId"]
        == "masters_throttle_status_list"
    )
    assert (
        schema["paths"]["/api/masters/throttle-status/{scope}/"]["get"]["operationId"]
        == "masters_throttle_scope_status_retrieve"
    )
