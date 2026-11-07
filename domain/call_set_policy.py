#!/usr/bin/env python3
# Copyright (c) 2026 MACD Adaptive Limited.
# Licensed under the MIT License. See LICENSE in the repository root.
# domain/call_set_policy.py — Tipos del contrato CALL/SET (#535)

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class OperatingMode(str, Enum):
    """Two access roles plus non-persistent safety/work contexts.

    USER may CALL and SET with confirmation. ADMIN also configures the room
    and switches ATEM live. Historical member names are aliases, not roles.
    Contexts remain distinct so migration cannot enable real hardware.
    """
    USER = "user"
    ADMIN = "admin"

    # Source compatibility only. All new writes use user/admin.
    BASIC_OPERATOR = "user"
    CAMERA_OPERATOR = "user"
    OPERATOR = "user"
    TECHNICIAN = "admin"
    SYSTEM_ADMIN = "admin"
    ADMIN_INSTALLER = "admin"

    SUPPORT = "support"
    DEMO = "demo"
    NAME_EDIT = "name_edit"
    LAYOUT_EDIT = "layout_edit"
    PRESET_TEST = "preset_test"
    NAMES = "names"

    @classmethod
    def _missing_(cls, value):
        legacy = {
            "basic_operator": cls.USER, "camera_operator": cls.USER,
            "operator": cls.USER, "technician": cls.ADMIN,
            "system_admin": cls.ADMIN, "admin_installer": cls.ADMIN,
        }
        return legacy.get(value) if isinstance(value, str) else None


class InputType(str, Enum):
    """Tipo de entrada del operador sobre un asiento o preset."""
    TAP         = "tap"
    LEFT_CLICK  = "left_click"
    SHORT_PRESS = "short_press"
    RIGHT_CLICK = "right_click"
    LONG_PRESS  = "long_press"
    DRAG        = "drag"


class CallSetAction(str, Enum):
    """Acción de cámara resultante de la decisión de política."""
    CALL = "call"
    SET  = "set"
    NONE = "none"


@dataclass(frozen=True)
class PolicyDecision:
    """
    Resultado de la decisión CALL/SET para una combinación de modo + entrada.

    allowed=True  → la acción puede ejecutarse.
    allowed=False → la acción está bloqueada; reason_code explica por qué.
    requires_confirmation=True → el llamador debe pedir confirmación al usuario
                                 antes de enviar el comando (solo SET admin).
    reason_code="" cuando allowed=True.
    """
    action:                CallSetAction
    allowed:               bool
    requires_confirmation: bool
    reason_code:           str
