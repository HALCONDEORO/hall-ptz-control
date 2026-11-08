"""Exercise the guide without touching devices, network or host installation."""
from argparse import Namespace
from pathlib import Path
import subprocess
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from runtime import install_guide as guide

ROOT = Path(__file__).resolve().parents[1]


def evidence(**changes):
    values = dict(model="Raspberry Pi 4 Model B Rev 1.4", codename="bullseye",
                  architecture="aarch64", python_version=(3, 9, 2), session="x11",
                  installed=False, provisioned=False, installer=Path("/approved dir/install.sh"),
                  user="desktop")
    values.update(changes)
    return values


@pytest.mark.parametrize("change", [
    {"model": "Raspberry Pi 5 Model B Rev 1.0"}, {"model": "unknown"},
    {"codename": "bookworm"}, {"codename": "trixie"}, {"codename": "unknown"},
    {"architecture": "armv7l"}, {"python_version": (3, 11, 2)},
])
def test_unvalidated_platform_stops_before_any_install_command(change):
    action, code = guide.next_step(**evidence(**change))
    assert code == 20
    assert action.startswith("Detener")
    assert "sudo bash" not in action


@pytest.mark.parametrize("session", ["wayland", "unknown", ""])
def test_display_must_be_known_x11(session):
    action, code = guide.next_step(**evidence(session=session))
    assert code == 20 and "X11" in action and "sudo" not in action


@pytest.mark.parametrize("user", ["", "root", "--help"])
def test_no_guessing_desktop_identity(user):
    action, code = guide.next_step(**evidence(user=user))
    assert code == 20 and "usuario normal" in action


def test_fresh_install_routes_to_check_not_install_and_quotes_paths():
    action, code = guide.next_step(**evidence())
    assert code == 20
    assert "'/approved dir/install.sh'" in action
    assert action.endswith("--wizard-user desktop --check")


@pytest.mark.parametrize("field", ["installed", "provisioned"])
def test_unknown_install_state_never_routes_to_overwriting_install(field):
    action, code = guide.next_step(**evidence(**{field: None}))
    assert code == 30 and "permisos" in action


def test_installed_without_marker_routes_to_wizard_in_desktop_not_sudo():
    action, code = guide.next_step(**evidence(installed=True))
    assert code == 20 and action.endswith("khptz setup")
    assert "sudo" not in action and "--force" not in action


def test_provisioned_routes_to_explicit_diagnostics_with_probe_warning():
    action, code = guide.next_step(**evidence(installed=True, provisioned=True))
    assert code == 20 and action.endswith("khptz doctor --guide")
    assert "red" in action


@pytest.mark.parametrize("code,expected", [(0, "aceptacion fisica"), (10, "aceptacion fisica"),
                                           (20, "pendiente"), (30, "FAIL"), (99, "FAIL")])
def test_doctor_next_action_never_claims_deployment_approval(code, expected):
    assert expected in guide.doctor_next_step(code)


def test_permission_error_is_not_missing(tmp_path):
    with patch.object(Path, "stat", side_effect=PermissionError):
        assert guide.exists(tmp_path) is None


def test_guide_main_is_read_only_and_emits_one_action(capsys):
    with patch.object(guide, "read_text", side_effect=["Raspberry Pi 4 Model B Rev 1.4",
                                                      'VERSION_CODENAME="bullseye"']), \
         patch.object(guide.platform, "machine", return_value="aarch64"), \
         patch.object(guide.sys, "version_info", (3, 9, 2)), \
         patch.dict(guide.os.environ, {"XDG_SESSION_TYPE": "x11"}), \
         patch.object(guide, "exists", return_value=False), \
         patch("socket.socket", side_effect=AssertionError("network forbidden")), \
         patch("subprocess.run", side_effect=AssertionError("process forbidden")), \
         patch.object(Path, "write_text", side_effect=AssertionError("write forbidden")):
        assert guide.main(["--wizard-user", "desktop"]) == 20
    output = capsys.readouterr().out
    assert output.count("Siguiente paso:") == 1
    assert output.rstrip().endswith("--check")


def test_actual_wrapper_guide_runs_without_installing_or_root():
    result = subprocess.run(["bash", str(ROOT / "install_khptz_rpi.sh"), "--guide"],
                            capture_output=True, text=True, timeout=10)
    assert result.returncode == 20
    assert result.stdout.count("Siguiente paso:") == 1
    assert "Checking how this script was started" not in result.stdout
    assert "Detener" in result.stdout  # test runner is not a validated Pi


def test_check_completion_preserves_selected_options_without_empty_argument():
    source = (ROOT / "install_khptz_rpi.sh").read_text()
    start = source.index('if [[ "${CHECK_ONLY}" == "true" ]]; then')
    end = source.index('# ── Install / repair', start)
    for passthrough in ('()', '(--gui-mode user --atem)', '(--dev)'):
        script = ('CHECK_ONLY=true; SELF="/approved dir/install.sh"; WIZARD_USER=desktop; '
                  f'ALLOW_DIRTY=false; PASSTHROUGH={passthrough}; info() {{ :; }};\n'
                  + source[start:end])
        result = subprocess.run(["bash", "-c", script], capture_output=True, text=True)
        assert result.returncode == 0
        assert result.stdout.count("Siguiente paso:") == 1
        assert "''" not in result.stdout
        assert "--check" not in result.stdout
        if passthrough != '()':
            assert passthrough.strip('()') in result.stdout


@pytest.mark.parametrize("code", [0, 10, 20, 30])
def test_doctor_guided_output_preserves_exit_and_all_findings(code, capsys):
    from runtime import cli
    report = SimpleNamespace(checks=[], exit_code=code,
                             outcome=SimpleNamespace(value="fixture"),
                             outcome_description="synthetic diagnosis")
    with patch.object(cli, "_prepare_runtime_mode", return_value=cli.RuntimeMode.PRODUCTION), \
         patch.object(cli, "_make_cli_recorder", return_value=None), \
         patch("application.diagnostics_service.DiagnosticsService") as svc:
        svc.return_value.run.return_value = report
        assert cli.cmd_doctor(Namespace(guide=True, json=False)) == code
    output = capsys.readouterr().out
    assert output.count("Siguiente paso:") == 1
    assert "synthetic diagnosis" in output


def test_doctor_json_remains_machine_readable(capsys):
    from runtime import cli
    with patch.object(cli, "_prepare_runtime_mode"), \
         patch.object(cli, "_make_cli_recorder", return_value=None), \
         patch("application.diagnostics_service.DiagnosticsService") as svc:
        svc.return_value.run.return_value.exit_code = 20
        svc.return_value.run.return_value.to_json_dict.return_value = {"outcome": "CONFIG_REQUIRED"}
        assert cli.cmd_doctor(Namespace(guide=True, json=True)) == 20
    assert 'Siguiente paso' not in capsys.readouterr().out


@pytest.mark.parametrize("extra", ["--check", "--dev", "--atem", "--allow-dirty"])
def test_guide_rejects_install_options_before_host_access(extra):
    result = subprocess.run(["bash", str(ROOT / "install_khptz_rpi.sh"), "--guide", extra],
                            capture_output=True, text=True, timeout=10)
    assert result.returncode == 30
    assert "--guide accepts only" in result.stderr
    assert "Checking how this script was started" not in result.stdout
