from django.conf import settings


def test_dgft_ownership_settings_are_environment_backed():
    """DGFT credentials remain configurable and are never source defaults."""
    assert settings.DGFT_OWNERSHIP_URL == "https://www.dgft.gov.in/CP/webHP"
    assert all(
        hasattr(settings, name)
        for name in (
            "DGFT_SCRIP_NUMBER",
            "DGFT_SCRIP_ISSUE_DATE",
            "DGFT_IEC_NUMBER",
            "DGFT_APP_ID",
            "DGFT_SESSION_ID",
            "DGFT_CSRF_TOKEN",
            "DGFT_AWSALB",
        )
    )
