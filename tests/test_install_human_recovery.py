"""Execute only presentation branches. No installation or device I/O."""
from pathlib import Path
import subprocess

import pytest

SOURCE = (Path(__file__).resolve().parents[1] / "install_khptz_rpi.sh").read_text()


def fatal_section():
    return SOURCE[SOURCE.index("INSTALL_STARTED=false"):SOURCE.index("# ── Arguments")]


@pytest.mark.parametrize("started,expected", [("false", "no ha iniciado"),
                                             ("true", "puede haber cambios parciales")])
def test_failure_reports_phase_and_never_claims_automatic_rollback(started, expected):
    script = fatal_section() + f'\nINSTALL_STARTED={started}\nfatal "fixture ERROR"'
    result = subprocess.run(["bash", "-c", script], capture_output=True, text=True)
    assert result.returncode == 30
    assert expected in result.stderr
    assert "fixture ERROR" in result.stderr
    assert result.stderr.count("Siguiente paso:") == 1
    assert "Nothing further was changed" not in result.stderr
    if started == "true":
        assert "no repitas" in result.stderr
        assert "--check" not in result.stderr


@pytest.mark.parametrize("code,expected,rc", [(0, "INSTALADO:", 0), (10, "recomendaciones", 0),
                                           (20, "PENDIENTE", 20), (30, "DETENIDO", 30),
                                           (99, "DETENIDO", 30)])
def test_final_recovery_is_one_safe_step_without_forced_reconfiguration(code, expected, rc):
    start = SOURCE.index('echo\necho "======================================================================"',
                         SOURCE.index('# ── One clear next action'))
    script = f'DOCTOR_RC={code}; VERSION=fixture; COMMIT=test; WIZARD_USER=desktop\n' + SOURCE[start:]
    result = subprocess.run(["bash", "-c", script], capture_output=True, text=True)
    assert result.returncode == rc
    assert expected in result.stdout
    assert result.stdout.count("Siguiente paso:") == 1
    assert "khptz setup --force" not in result.stdout
    assert "sudo bash" not in result.stdout
    if code in (0, 10):
        assert "no certifica" in result.stdout
    if code == 20:
        assert "ya estaba configurado" in result.stdout


def test_partial_boundary_precedes_child_install_but_follows_check_only_exit():
    started = SOURCE.index('INSTALL_STARTED=true')
    check_exit = SOURCE.index('if [[ "${CHECK_ONLY}" == "true" ]]; then')
    child = SOURCE.index('if ! bash "${INSTALLER}" --wizard-user')
    assert check_exit < started < child


def test_human_guide_warns_before_probes_and_recovery_not_auto_install():
    doc = (Path(__file__).resolve().parents[1] / "docs/INSTALL_HUMANO.md").read_text()
    assert "copia de seguridad comprobada" in doc
    assert "no ejecutes `sudo khptz doctor`" in doc
    assert "El diagnostico normal puede contactar" in doc
    assert "rollback total" in doc
    assert "no eludas" in doc.lower()
    assert "Pi 5" in doc and "validacion" in doc


@pytest.mark.parametrize("mode", [[], ["--check"], ["--dev"], ["--gui-mode", "user"]])
def test_permission_recipe_always_checks_never_installs(tmp_path, mode):
    """Run the real wrapper up to a forced non-root gate; no child is run."""
    import os
    import shlex

    checkout = tmp_path / "approved source with spaces"
    checkout.mkdir()
    wrapper = checkout / "install_khptz_rpi.sh"
    # Force only the guard, so this also exercises the recipe if CI runs as root.
    text = SOURCE.replace('if [[ "${EUID}" -ne 0 ]]; then', 'if true; then')
    wrapper.write_text(text)
    result = subprocess.run(['bash', str(wrapper), '--wizard-user', 'desktop user', *mode],
                            env=dict(os.environ, USER='wrong-default'),
                            capture_output=True, text=True, timeout=10)
    assert result.returncode == 30
    recipes = [line.strip() for line in result.stderr.splitlines()
               if line.strip().startswith('sudo bash ')]
    assert len(recipes) == 1
    assert shlex.split(recipes[0]) == ['sudo', 'bash', str(wrapper), '--wizard-user',
                                      'desktop user', '--check']
    assert 'SIN instalar' in result.stderr
    assert 'no ha iniciado la instalacion' in result.stderr
    assert result.stderr.count('Siguiente paso:') == 1
    assert 'Carpeta del programa:' not in result.stdout
