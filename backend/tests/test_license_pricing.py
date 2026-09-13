from datetime import datetime, timedelta, timezone

import pytest

from otimizer_api.licensing import Entitlements, InMemoryLicenseRepository, License


def test_license_keeps_configured_price() -> None:
    starts = datetime.now(timezone.utc)
    license_record = License(
        license_id="lic-1",
        account_id="account-1",
        starts_at=starts,
        expires_at=starts + timedelta(days=30),
        entitlements=Entitlements(),
        price_cents=2990,
    )

    stored = InMemoryLicenseRepository([license_record]).get_active_license("account-1", starts + timedelta(minutes=1))
    assert stored is not None
    assert stored.price_cents == 2990


def test_license_rejects_negative_price() -> None:
    starts = datetime.now(timezone.utc)
    with pytest.raises(ValueError):
        License(
            license_id="lic-1",
            account_id="account-1",
            starts_at=starts,
            expires_at=starts + timedelta(days=30),
            price_cents=-1,
        )
