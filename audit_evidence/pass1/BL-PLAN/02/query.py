"""
BL-PLAN-02 evidence: `detect_norm()` / `PlannerFactory` provide zero
auto-planning coverage for the "PP" SION norm class, which real production
data shows is not a minor edge case -- it is the SINGLE LARGEST norm-class
group in the whole license book after E5.
"""
import os

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "lmanagement.settings")
django.setup()

from collections import Counter  # noqa: E402

from apps.core.models import SionNormClassModel  # noqa: E402
from apps.license.models import LicenseDetailsModel, LicenseExportItemModel  # noqa: E402
from apps.license.services.norm_plan import detect_norm  # noqa: E402
from apps.license.services.planner_factory import PlannerFactory  # noqa: E402


def main():
    pp = SionNormClassModel.objects.filter(norm_class="PP").first()
    print("SionNormClassModel row for code 'PP':", pp, "is_active=", getattr(pp, "is_active", None))

    export_norm_counts = Counter(
        (ei.norm_class.norm_class if ei.norm_class else None)
        for ei in LicenseExportItemModel.objects.select_related("norm_class")
    )
    print("\nExport-item norm_class distribution across all 228 real licenses:")
    for code, n in export_norm_counts.most_common():
        print(f"  {code!r}: {n}")

    detect_counts = Counter(detect_norm(lic) for lic in LicenseDetailsModel.objects.all())
    print("\ndetect_norm() distribution (blank = no norm recognised at all):", dict(detect_counts))

    print("\nPlannerFactory.supported_norms():", PlannerFactory.supported_norms())
    print("PlannerFactory.is_supported('PP'):", PlannerFactory.is_supported("PP"))


if __name__ == "__main__":
    main()
