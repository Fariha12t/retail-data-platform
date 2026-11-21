import pytest

from retail_pipeline.contracts import CONTRACTS


@pytest.mark.parametrize("contract", CONTRACTS.values(), ids=CONTRACTS.keys())
def test_contract_is_consistent(contract):
    names = contract.column_names
    assert len(names) == len(set(names)), "duplicate column names"
    assert set(contract.primary_key) <= set(names)
    if contract.version_column:
        assert contract.version_column in names
    if contract.incremental_column:
        assert contract.incremental_column in names
    assert contract.source in {"postgres", "csv", "api"}
