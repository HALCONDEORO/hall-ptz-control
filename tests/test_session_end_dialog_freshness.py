"""An End Session answer belongs only to the session shown in that dialog."""
import ast
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest


def controller_with_dialog_answer(change, answer=1):
    # Execute the real method without importing Qt or copying its logic.
    path = Path(__file__).resolve().parents[1] / 'ui/session_mixin.py'
    tree = ast.parse(path.read_text())
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef)
               and n.name == 'SessionController')
    method = next(n for n in cls.body if isinstance(n, ast.FunctionDef)
                  and n.name == 'ToggleSession')
    window = SimpleNamespace(session_active=True, _shutting_down=False)
    controller = SimpleNamespace(_w=window, _session_generation=4, shutdown=Mock())
    def question(*args):
        change(controller)
        return answer
    env = {'QMessageBox': SimpleNamespace(Yes=1, No=2, question=question)}
    exec(compile(ast.fix_missing_locations(ast.Module(body=[method], type_ignores=[])),
                 str(path), 'exec'), env)
    return controller, env['ToggleSession']


@pytest.mark.parametrize('change', [
    lambda c: setattr(c._w, 'session_active', False),
    lambda c: setattr(c, '_session_generation', 6),
    lambda c: setattr(c._w, '_shutting_down', True),
])
def test_stale_yes_does_not_end_a_different_or_already_closed_session(change):
    controller, toggle = controller_with_dialog_answer(change)
    toggle(controller)
    controller.shutdown.assert_not_called()


@pytest.mark.parametrize('answer,expected', [(1, 1), (2, 0)])
def test_current_session_keeps_explicit_yes_no_behavior(answer, expected):
    controller, toggle = controller_with_dialog_answer(lambda c: None, answer)
    toggle(controller)
    assert controller.shutdown.call_count == expected
    if expected:
        controller.shutdown.assert_called_once_with('manual')
