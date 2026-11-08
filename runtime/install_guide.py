"""Read-only installation routing. No diagnostics, subprocesses or network probes."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import platform
import shlex
import sys


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8").replace("\x00", "").strip()
    except OSError:
        return "unknown"


def os_codename(text: str) -> str:
    for line in text.splitlines():
        key, sep, value = line.partition("=")
        if sep and key == "VERSION_CODENAME":
            return value.strip().strip("\"'")
    return "unknown"


def next_step(*, model: str, codename: str, architecture: str,
              python_version: tuple, session: str, installed: bool | None,
              provisioned: bool | None, installer: Path, user: str) -> tuple[str, int]:
    """Choose one step, failing closed on missing platform/install evidence."""
    baseline = (model.startswith("Raspberry Pi 4 Model B")
                and codename == "bullseye" and architecture == "aarch64"
                and python_version[:2] == (3, 9))
    if not baseline:
        return ("Detener la instalacion y solicitar validacion de esta plataforma; "
                "Pi 5 / Bookworm / Trixie siguen sin validacion fisica.", 20)
    if session != "x11":
        return ("Abrir una sesion de escritorio X11 y repetir la guia desde su terminal.", 20)
    if not user or user == "root" or user.startswith("-"):
        return ("Repetir la guia desde el escritorio como usuario normal, no como root.", 20)
    if installed is None or provisioned is None:
        return ("Solicitar revision de permisos: no se pudo leer el estado de instalacion.", 30)
    if not installed:
        return ("Ejecutar la comprobacion sin instalar: sudo bash "
                f"{shlex.quote(str(installer))} --wizard-user {shlex.quote(user)} --check", 20)
    if not provisioned:
        return ("Desde esta sesion de escritorio ejecutar: khptz setup", 20)
    return ("Ejecutar los diagnosticos (incluyen comprobaciones de red): "
            "khptz doctor --guide", 20)


def exists(path: Path) -> bool | None:
    try:
        path.stat()
        return True
    except FileNotFoundError:
        return False
    except OSError:
        return None


def doctor_next_step(exit_code: int) -> str:
    if exit_code in (0, 10):
        return "Completar la lista de aceptacion fisica antes de usar el equipo en una reunion."
    if exit_code == 20:
        return "Revisar el primer problema pendiente indicado arriba antes de repetir doctor --guide."
    return "Corregir el primer FAIL indicado arriba antes de repetir doctor --guide."


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wizard-user", default="")
    args = parser.parse_args(argv)
    model = read_text(Path("/proc/device-tree/model"))
    codename = os_codename(read_text(Path("/etc/os-release")))
    arch = platform.machine()
    session = os.environ.get("XDG_SESSION_TYPE", "unknown")
    user = args.wizard_user or os.environ.get("SUDO_USER") or os.environ.get("USER", "")
    print("KH PTZ - Guia de instalacion (solo lectura)")
    print(f"Pi: {model} | Sistema: {codename} | Arquitectura: {arch}")
    print(f"Python: {platform.python_version()} | Sesion: {session}")
    print("Base validada: Pi 4 / Bullseye 64-bit / Python 3.9 / X11.")
    print("No instala, no inicia doctor ni el asistente, no prueba camaras ni red.")
    action, code = next_step(
        model=model, codename=codename, architecture=arch,
        python_version=sys.version_info, session=session,
        installed=exists(Path("/usr/local/bin/khptz")),
        provisioned=exists(Path("/etc/khptz/.provisioned")),
        installer=Path(__file__).resolve().parents[1] / "install_khptz_rpi.sh", user=user,
    )
    print(f"Siguiente paso: {action}")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
