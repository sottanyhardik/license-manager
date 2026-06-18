# Template — DRF ViewSet (extends MasterViewSet)

Rules: `.claude/rules/{backend,database,security}.md`. Base: `apps/core/views/master_view.py:69`.

**model** (`apps/<app>/models.py`) — inherit `AuditModel`:

```python
from apps.core.models import AuditModel

class WidgetModel(AuditModel):
    name = models.CharField(max_length=255)
    company = models.ForeignKey("core.CompanyModel", on_delete=models.PROTECT,
                                related_name="widgets")

    class Meta:
        indexes = [models.Index(fields=["company", "name"])]  # match real filter/order use
```

**serializer** (`apps/<app>/serializers.py`) — validation lives here:

```python
class WidgetSerializer(serializers.ModelSerializer):
    class Meta:
        model = WidgetModel
        fields = "__all__"

    def validate_name(self, value):
        if not value.strip():
            raise serializers.ValidationError("Name is required.")
        return value
```

**view** (`apps/<app>/views.py`) — extend `MasterViewSet`, declare permissions:

```python
from apps.core.views.master_view import MasterViewSet

class WidgetViewSet(MasterViewSet):
    queryset = WidgetModel.objects.select_related("company")  # avoid N+1
    serializer_class = WidgetSerializer
    permission_classes = [IsAuthenticated, <RolePermission>]   # never leave empty
    filterset_fields = ["company"]
    search_fields = ["name"]
    ordering_fields = ["name", "created_on"]
```

**url** (`apps/<app>/urls.py`): register on the router. You inherit filter/search/order,
inline PATCH, bulk export, and audit auto-population from `MasterViewSet`.

Then add tests per `.claude/templates/test.md`.
