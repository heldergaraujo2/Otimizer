import pytest

from otimizer_importer.models import ImportResult


def test_import_result_requires_every_data_row_to_be_accounted_for():
    with pytest.raises(ValueError, match="account for every data row"):
        ImportResult((), (2,), 2)


def test_import_result_reports_complete_accounting():
    result = ImportResult((), (2, 3), 2)

    assert result.eligible_delivery_count == 0
    assert result.unresolved_count == 2
    assert result.accounted_rows == 2


def test_import_result_rejects_duplicate_unresolved_rows():
    with pytest.raises(ValueError, match="unique"):
        ImportResult((), (2, 2), 2)
