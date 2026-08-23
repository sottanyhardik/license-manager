import pytest
from decimal import Decimal
from django.utils import timezone
from django.contrib.auth import get_user_model

from apps.allotment.models import AllotmentItems, AllotmentModel, AuditEvent, Shortfall, AllocationVersion
from apps.core.models import CompanyModel
from apps.license.models import LicenseDetailsModel, LicenseImportItemsModel

User = get_user_model()


@pytest.mark.django_db
class TestAllotmentItemsLifecycle:
    """Test AllotmentItems lifecycle fields and status management."""

    @pytest.fixture
    def company(self):
        return CompanyModel.objects.create(name='Test Company', iec='1234567890')

    @pytest.fixture
    def allotment(self, company):
        return AllotmentModel.objects.create(
            company=company,
            type='H',
            required_quantity=Decimal('1000.00'),
            unit_value_per_unit=Decimal('10.000'),
        )

    @pytest.fixture
    def license(self, company):
        return LicenseDetailsModel.objects.create(
            license_number='LIC-001',
            license_date=timezone.now().date(),
            exporter=company,
        )

    @pytest.fixture
    def item(self, license):
        # Use a sequential number for serial_number
        count = LicenseImportItemsModel.objects.filter(license=license).count()
        return LicenseImportItemsModel.objects.create(
            license=license,
            description='Test Item',
            serial_number=count + 1,
        )

    @pytest.fixture
    def allocation_item(self, allotment, item):
        return AllotmentItems.objects.create(
            allotment=allotment,
            item=item,
            qty=Decimal('100.000'),
            cif_fc=Decimal('1000.00'),
            cif_inr=Decimal('75000.00'),
        )

    def test_allocation_item_status_default_created(self, allocation_item):
        """Test that new AllotmentItems have status='CREATED' by default."""
        assert allocation_item.status == 'CREATED'

    def test_allocation_item_is_released_property(self, allocation_item):
        """Test is_released property."""
        assert allocation_item.is_released is False
        allocation_item.status = 'RELEASED'
        assert allocation_item.is_released is True
        allocation_item.status = 'COMPLETED'
        assert allocation_item.is_released is True
        allocation_item.status = 'REACTIVATED'
        assert allocation_item.is_released is False

    def test_allocation_item_is_reactivated_property(self, allocation_item):
        """Test is_reactivated property."""
        assert allocation_item.is_reactivated is False
        allocation_item.status = 'REACTIVATED'
        allocation_item.save()
        allocation_item.refresh_from_db()
        assert allocation_item.is_reactivated is True

    def test_allocation_item_release_fields(self, allocation_item):
        """Test release tracking fields."""
        assert allocation_item.released_date is None
        assert allocation_item.release_reason is None

        allocation_item.status = 'RELEASED'
        allocation_item.released_quantity = Decimal('50.000')
        allocation_item.released_date = timezone.now()
        allocation_item.release_reason = 'Customer request'
        allocation_item.save()
        allocation_item.refresh_from_db()

        assert allocation_item.released_quantity == Decimal('50.000')
        assert allocation_item.released_date is not None
        assert allocation_item.release_reason == 'Customer request'

    def test_allocation_item_reactivation_fields(self, allocation_item):
        """Test reactivation tracking fields."""
        assert allocation_item.reactivated_date is None
        assert allocation_item.reactivated_from_company is None

        allocation_item.status = 'REACTIVATED'
        allocation_item.reactivated_quantity = Decimal('30.000')
        allocation_item.reactivated_date = timezone.now()
        allocation_item.reactivated_from_company = 'PREV-COMPANY-001'
        allocation_item.save()
        allocation_item.refresh_from_db()

        assert allocation_item.reactivated_quantity == Decimal('30.000')
        assert allocation_item.reactivated_date is not None
        assert allocation_item.reactivated_from_company == 'PREV-COMPANY-001'

    def test_allocation_item_version_history(self, allocation_item, allotment, license):
        """Test version history chaining with previous_version."""
        assert allocation_item.previous_version is None

        # Create a new version with a different item
        item2 = LicenseImportItemsModel.objects.create(
            license=license,
            description='Test Item 2',
            serial_number='002',
        )
        version2 = AllotmentItems.objects.create(
            allotment=allotment,
            item=item2,
            qty=Decimal('150.000'),
            cif_fc=Decimal('1500.00'),
            cif_inr=Decimal('112500.00'),
            previous_version=allocation_item,
        )

        allocation_item.refresh_from_db()
        assert version2.previous_version == allocation_item
        assert allocation_item.next_version.exists()
        assert allocation_item.next_version.first() == version2

    def test_allocation_item_status_choices(self, allocation_item):
        """Test all valid status choices."""
        valid_statuses = ['CREATED', 'RELEASED', 'REACTIVATED', 'COMPLETED']

        for status in valid_statuses:
            allocation_item.status = status
            allocation_item.save()
            allocation_item.refresh_from_db()
            assert allocation_item.status == status


@pytest.mark.django_db
class TestAuditEvent:
    """Test AuditEvent model for audit trail recording."""

    @pytest.fixture
    def company(self):
        return CompanyModel.objects.create(name='Test Company', iec='1234567890')

    @pytest.fixture
    def allotment(self, company):
        return AllotmentModel.objects.create(
            company=company,
            type='H',
            required_quantity=Decimal('1000.00'),
            unit_value_per_unit=Decimal('10.000'),
        )

    @pytest.fixture
    def license(self, company):
        return LicenseDetailsModel.objects.create(
            license_number='LIC-001',
            license_date=timezone.now().date(),
            exporter=company,
        )

    @pytest.fixture
    def item(self, license):
        # Use a sequential number for serial_number
        count = LicenseImportItemsModel.objects.filter(license=license).count()
        return LicenseImportItemsModel.objects.create(
            license=license,
            description='Test Item',
            serial_number=count + 1,
        )

    @pytest.fixture
    def allocation_item(self, allotment, item):
        return AllotmentItems.objects.create(
            allotment=allotment,
            item=item,
            qty=Decimal('100.000'),
            cif_fc=Decimal('1000.00'),
            cif_inr=Decimal('75000.00'),
        )

    @pytest.fixture
    def user(self):
        return User.objects.create_user(username='testuser', password='testpass')

    def test_audit_event_creation(self, allocation_item, user):
        """Test creating an audit event."""
        audit = AuditEvent.objects.create(
            allocation_item=allocation_item,
            action=AuditEvent.ALLOCATION,
            actor=user,
            quantity_before=Decimal('0.000'),
            quantity_after=Decimal('100.000'),
            cif_before=Decimal('0.00'),
            cif_after=Decimal('1000.00'),
            reason='Initial allocation',
        )

        audit.refresh_from_db()
        assert audit.allocation_item == allocation_item
        assert audit.action == AuditEvent.ALLOCATION
        assert audit.actor == user
        assert audit.quantity_after == Decimal('100.000')

    def test_audit_event_action_choices(self, allocation_item, user):
        """Test all valid action types."""
        actions = [
            AuditEvent.ALLOCATION,
            AuditEvent.RELEASE,
            AuditEvent.REVERSAL,
            AuditEvent.REACTIVATION,
            AuditEvent.BOE_RECONCILIATION,
            AuditEvent.COMPANY_CHANGE,
            AuditEvent.SHORTFALL_FULFILLMENT,
        ]

        for action in actions:
            audit = AuditEvent.objects.create(
                allocation_item=allocation_item,
                action=action,
                actor=user,
            )
            audit.refresh_from_db()
            assert audit.action == action

    def test_audit_event_with_details(self, allocation_item, user):
        """Test audit event with JSON details."""
        details = {
            'reason_code': 'CUSTOMER_REQUEST',
            'reference_id': 'REF-12345',
        }

        audit = AuditEvent.objects.create(
            allocation_item=allocation_item,
            action=AuditEvent.RELEASE,
            actor=user,
            details=details,
        )

        audit.refresh_from_db()
        assert audit.details == details


@pytest.mark.django_db
class TestShortfall:
    """Test Shortfall model for FIFO auto-fulfillment."""

    @pytest.fixture
    def company(self):
        return CompanyModel.objects.create(name='Test Company', iec='1234567890')

    @pytest.fixture
    def license(self, company):
        return LicenseDetailsModel.objects.create(
            license_number='LIC-001',
            license_date=timezone.now().date(),
            exporter=company,
        )

    def test_shortfall_creation(self, license):
        """Test creating a shortfall record."""
        shortfall = Shortfall.objects.create(
            license=license,
            required_quantity=Decimal('100.000'),
            required_cif=Decimal('1000.00'),
        )

        shortfall.refresh_from_db()
        assert shortfall.license == license
        assert shortfall.required_quantity == Decimal('100.000')
        assert shortfall.required_cif == Decimal('1000.00')
        assert shortfall.allocated_quantity == Decimal('0.000')
        assert shortfall.status == Shortfall.PENDING

    def test_shortfall_quantities(self, license):
        """Test shortfall quantity calculations."""
        shortfall = Shortfall.objects.create(
            license=license,
            required_quantity=Decimal('100.000'),
            required_cif=Decimal('1000.00'),
            allocated_quantity=Decimal('30.000'),
            allocated_cif=Decimal('300.00'),
        )

        assert shortfall.shortfall_quantity() == Decimal('70.000')
        assert shortfall.shortfall_cif() == Decimal('700.00')
        assert shortfall.is_fulfilled() is False

    def test_shortfall_fulfilled_status(self, license):
        """Test shortfall fulfillment status."""
        shortfall = Shortfall.objects.create(
            license=license,
            required_quantity=Decimal('100.000'),
            required_cif=Decimal('1000.00'),
            allocated_quantity=Decimal('100.000'),
            allocated_cif=Decimal('1000.00'),
        )

        assert shortfall.is_fulfilled() is True

    def test_shortfall_fifo_ordering(self, license):
        """Test that shortfalls are ordered FIFO (by created_on)."""
        shortfall1 = Shortfall.objects.create(
            license=license,
            required_quantity=Decimal('100.000'),
            required_cif=Decimal('1000.00'),
        )
        shortfall2 = Shortfall.objects.create(
            license=license,
            required_quantity=Decimal('50.000'),
            required_cif=Decimal('500.00'),
        )

        ordered = list(Shortfall.objects.all())
        assert ordered[0] == shortfall1
        assert ordered[1] == shortfall2

    def test_shortfall_status_changes(self, license):
        """Test shortfall status transitions."""
        shortfall = Shortfall.objects.create(
            license=license,
            required_quantity=Decimal('100.000'),
            required_cif=Decimal('1000.00'),
        )

        assert shortfall.status == Shortfall.PENDING

        shortfall.status = Shortfall.PARTIALLY_FULFILLED
        shortfall.save()
        shortfall.refresh_from_db()
        assert shortfall.status == Shortfall.PARTIALLY_FULFILLED

        shortfall.status = Shortfall.FULFILLED
        shortfall.fulfilled_on = timezone.now()
        shortfall.save()
        shortfall.refresh_from_db()
        assert shortfall.status == Shortfall.FULFILLED
        assert shortfall.fulfilled_on is not None


@pytest.mark.django_db
class TestAllocationVersion:
    """Test AllocationVersion model for immutable history."""

    @pytest.fixture
    def company(self):
        return CompanyModel.objects.create(name='Test Company', iec='1234567890')

    @pytest.fixture
    def allotment(self, company):
        return AllotmentModel.objects.create(
            company=company,
            type='H',
            required_quantity=Decimal('1000.00'),
            unit_value_per_unit=Decimal('10.000'),
        )

    @pytest.fixture
    def license(self, company):
        return LicenseDetailsModel.objects.create(
            license_number='LIC-001',
            license_date=timezone.now().date(),
            exporter=company,
        )

    @pytest.fixture
    def item(self, license):
        # Use a sequential number for serial_number
        count = LicenseImportItemsModel.objects.filter(license=license).count()
        return LicenseImportItemsModel.objects.create(
            license=license,
            description='Test Item',
            serial_number=count + 1,
        )

    @pytest.fixture
    def allocation_item(self, allotment, item):
        return AllotmentItems.objects.create(
            allotment=allotment,
            item=item,
            qty=Decimal('100.000'),
            cif_fc=Decimal('1000.00'),
            cif_inr=Decimal('75000.00'),
        )

    def test_allocation_version_creation(self, allocation_item, company):
        """Test creating an allocation version snapshot."""
        version = AllocationVersion.objects.create(
            allocation_item=allocation_item,
            status=allocation_item.status,
            quantity=allocation_item.qty,
            cif_fc=allocation_item.cif_fc,
            company=company,
        )

        version.refresh_from_db()
        assert version.allocation_item == allocation_item
        assert version.status == 'CREATED'
        assert version.quantity == Decimal('100.000')
        assert version.cif_fc == Decimal('1000.00')

    def test_allocation_version_snapshot(self, allocation_item, company):
        """Test that versions preserve historical state."""
        # Create initial version
        version1 = AllocationVersion.objects.create(
            allocation_item=allocation_item,
            status='CREATED',
            quantity=Decimal('100.000'),
            cif_fc=Decimal('1000.00'),
            company=company,
        )

        # Modify allocation
        allocation_item.qty = Decimal('75.000')
        allocation_item.cif_fc = Decimal('750.00')
        allocation_item.status = 'RELEASED'
        allocation_item.save()

        # Create new version
        version2 = AllocationVersion.objects.create(
            allocation_item=allocation_item,
            status='RELEASED',
            quantity=Decimal('75.000'),
            cif_fc=Decimal('750.00'),
            company=company,
            change_reason='Partial release',
        )

        # Verify versions are independent
        assert version1.status == 'CREATED'
        assert version1.quantity == Decimal('100.000')
        assert version2.status == 'RELEASED'
        assert version2.quantity == Decimal('75.000')

    def test_allocation_version_ordering(self, allocation_item, company):
        """Test that versions are ordered reverse chronologically."""
        version1 = AllocationVersion.objects.create(
            allocation_item=allocation_item,
            status='CREATED',
            quantity=Decimal('100.000'),
            cif_fc=Decimal('1000.00'),
            company=company,
        )
        version2 = AllocationVersion.objects.create(
            allocation_item=allocation_item,
            status='RELEASED',
            quantity=Decimal('75.000'),
            cif_fc=Decimal('750.00'),
            company=company,
        )

        versions = list(AllocationVersion.objects.all())
        assert versions[0] == version2  # Most recent first
        assert versions[1] == version1
