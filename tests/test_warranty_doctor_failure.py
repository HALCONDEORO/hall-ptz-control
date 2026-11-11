"""An unavailable diagnostic report is not proof of a validated installation."""
from unittest.mock import Mock

import pytest

from application.known_good_state_service import StateDiff
from application.warranty_state_service import SupportHintEngine, WarrantyStateService
from domain.supportability import WarrantyState


@pytest.mark.parametrize("has_known_good", [True, False])
def test_doctor_failure_is_reported_as_unknown(has_known_good):
    known_good = Mock()
    known_good.diff.return_value = StateDiff(has_known_good=has_known_good)
    diagnostics = Mock()
    diagnostics.run.side_effect = RuntimeError("diagnostic source unavailable")

    result = WarrantyStateService(known_good, diagnostics).assess()

    assert result.state is WarrantyState.UNKNOWN
    assert "diagnostic" in result.reason.lower()
    assert result.customer_message
    assert "validated and in a known-good state" not in result.customer_message


def test_unavailable_doctor_hint_does_not_claim_baseline_missing():
    known_good = Mock()
    known_good.diff.return_value = StateDiff(has_known_good=True)
    diagnostics = Mock()
    diagnostics.run.side_effect = RuntimeError("diagnostic source unavailable")
    result = WarrantyStateService(known_good, diagnostics).assess()

    hints = SupportHintEngine().hints_for(result, [])

    assert len(hints) == 1
    assert "diagnostic" in hints[0].hint.lower()
    assert "baseline" not in hints[0].hint.lower()
    assert hints[0].action == "Run 'khptz doctor' and retry the support assessment."
    assert "known-good mark" not in hints[0].action
