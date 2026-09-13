from datetime import datetime, timedelta, timezone

import pytest

from otimizer_api.licensing import Entitlements, InMemoryLicenseRepository, License


def make_license(price_cents: int = 2990) -> License:
    starts = datetime.now(timezone.utc)
    return License(
        license_id="lic-1",
        account_id="account-1",
        starts_at=starts,
        expires_at=starts + timedelta(days=30),
        entitlements=Entitlements(),
        price_cents=price_cents,
    )


def test_license_keeps_configured_price() -> None:
    license_record = make_license(2990)
    stored = InMemoryLicenseRepository([license_record]).get_active_license(
        "account-1", license_record.starts_at + timedelta(minutes=1)
    )
    assert stored is not None
    assert stored.price_cents == 2990


def test_license_price_can_be_changed_without_mutating_original() -> None:
    original = make_license(2990)
    changed = original.change_price(4990)

    assert original.price_cents == 2990
    assert changed.price_cents == 4990
    assert changed.license_id == original.license_id
    assert changed.account_id == original.account_id


def test_license_rejects_negative_price() -> None:
    with pytest.raises(ValueError):
        make_license().change_price(-1)

    with pytest.raises(ValueError):
        make_license(-1)
