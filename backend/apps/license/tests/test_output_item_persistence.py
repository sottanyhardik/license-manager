"""Test that output_item is persisted when updating a planning rule via the API."""
import pytest
from decimal import Decimal
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model
from apps.core.models import ItemNameModel, SionNormClassModel, HeadSIONNormsModel
from apps.license.models import SionPlanningRule

User = get_user_model()


@pytest.mark.django_db
class TestOutputItemPersistence:
    """Verify that output_item is properly persisted during updates."""

    @pytest.fixture
    def authenticated_client(self):
        """Create an authenticated API client."""
        # Clean up any existing test user
        User.objects.filter(username='testuser').delete()
        user = User.objects.create_user(
            username='testuser',
            password='testpass123',
            is_staff=True,
            is_superuser=True
        )
        client = APIClient()
        client.force_authenticate(user=user)
        return client, user

    @pytest.fixture
    def sion_norm(self):
        """Create a SION norm for testing."""
        head_norm, _ = HeadSIONNormsModel.objects.get_or_create(
            name='E Norms'
        )
        sion, _ = SionNormClassModel.objects.get_or_create(
            norm_class='TEST_E1',
            defaults={
                'description': 'Test SION',
                'head_norm': head_norm
            }
        )
        return sion

    @pytest.fixture
    def planning_rule_with_item(self, sion_norm, authenticated_client):
        """Create a planning rule with output_item."""
        _, user = authenticated_client
        item = ItemNameModel.objects.create(
            name='Item A Test',
            sion_norm_class=sion_norm,
            is_active=True
        )
        # Get max priority and add 1
        max_priority = SionPlanningRule.objects.filter(sion=sion_norm, is_active=True).aggregate(
            max_p=__import__('django.db.models', fromlist=['Max']).Max('priority'))['max_p'] or 0
        next_priority = max_priority + 100  # Use high priority to avoid conflicts

        rule = SionPlanningRule.objects.create(
            sion=sion_norm,
            name='Test Rule Item Persist',
            expression={'operator': 'AND', 'conditions': []},
            max_unit_price=Decimal('100.00'),
            unit='KG',
            priority=next_priority,
            is_active=True,
            output_item=item,
            created_by=user,
            modified_by=user
        )
        return rule, item

    def test_output_item_persisted_on_update(self, authenticated_client, sion_norm, planning_rule_with_item):
        """Test that output_item is persisted when updating a rule."""
        client, user = authenticated_client
        rule, item1 = planning_rule_with_item

        # Create a second item to update to
        item2 = ItemNameModel.objects.create(
            name='Item B Test',
            sion_norm_class=sion_norm,
            is_active=True
        )

        # Verify initial state
        rule_before = SionPlanningRule.objects.get(id=rule.id)
        assert rule_before.output_item_id == item1.id

        # Update the rule via API to use item2
        response = client.patch(
            f'/api/sion-planning-rules/{rule.id}/',
            {
                'name': 'Updated Rule',
                'output_item': item2.id,
                'max_unit_price': '100.00',
                'unit': 'KG',
                'is_active': True,
                'expression': {'operator': 'AND', 'conditions': []}
            },
            format='json'
        )

        # Check response
        assert response.status_code == 200, f"Response: {response.data if hasattr(response, 'data') else response.content}"
        data = response.data if hasattr(response, 'data') else response.json()
        assert data['output_item'] == item2.id

        # Verify persisted value - get the NEW version created by the update
        all_rules = SionPlanningRule.objects.filter(stable_key=rule.stable_key).order_by('-version')
        new_rule = all_rules.first()
        assert new_rule is not None
        assert new_rule.output_item_id == item2.id

    def test_output_item_can_be_cleared(self, authenticated_client, sion_norm, planning_rule_with_item):
        """Test that output_item can be cleared (set to null) when updating a rule."""
        client, user = authenticated_client
        rule, item1 = planning_rule_with_item

        # Verify initial state
        rule_before = SionPlanningRule.objects.get(id=rule.id)
        assert rule_before.output_item_id == item1.id

        # Update the rule via API to clear the output_item
        response = client.patch(
            f'/api/sion-planning-rules/{rule.id}/',
            {
                'name': 'Cleared Item Rule',
                'output_item': None,
                'max_unit_price': '100.00',
                'unit': 'KG',
                'is_active': True,
                'expression': {'operator': 'AND', 'conditions': []}
            },
            format='json'
        )

        # Check response
        assert response.status_code == 200
        data = response.data if hasattr(response, 'data') else response.json()
        assert data['output_item'] is None

        # Verify persisted value
        all_rules = SionPlanningRule.objects.filter(stable_key=rule.stable_key).order_by('-version')
        new_rule = all_rules.first()
        assert new_rule.output_item_id is None
