#!/usr/bin/env python3
# Copyright (c) 2026 MACD Adaptive Limited.
# Licensed under the MIT License. See LICENSE in the repository root.
# ptz/visca/parser.py — Parsers puros de respuestas VISCA
#
# Todas las funciones son puras: reciben bytes, devuelven el valor extraído o None.
# Sin efectos secundarios, sin red, sin Qt.

from __future__ import annotations

from typing import Iterator, Optional

from .types import ZOOM_MAX


def _valid_nibble_bytes(frame: bytes, indexes: list[int]) -> bool:
    """Return True if every indexed byte has a zero high nibble (VISCA 0p encoding)."""
    return all((frame[i] & 0xF0) == 0 for i in indexes)


def zoom(data: bytes) -> Optional[int]:
    """
    Extrae el valor 0–0x4000 de una respuesta VISCA zoom inquiry.
    Escanea el buffer para manejar ACK + Completion en el mismo paquete TCP.
    Formato Completion: 9x 50 0p 0q 0r 0s FF
    Devuelve None si los nibbles de payload son inválidos.
    """
    frame = inquiry_frame(data, payload_len=4)
    if frame is None:
        return None
    if not _valid_nibble_bytes(frame, [2, 3, 4, 5]):
        return None
    return (
        (frame[2] & 0xF) << 12
        | (frame[3] & 0xF) << 8
        | (frame[4] & 0xF) << 4
        | (frame[5] & 0xF)
    )


def zoom_to_pct(raw: int) -> int:
    """Convierte valor VISCA 0–0x4000 a porcentaje 0–100."""
    return round(raw * 100 / ZOOM_MAX)


def _to_signed_16(value: int) -> int:
    """Interpret a 16-bit unsigned VISCA value as a signed two's-complement integer."""
    return value - 0x10000 if value & 0x8000 else value


def ptz_position(data: bytes) -> Optional[tuple[int, int]]:
    """
    Extrae (pan, tilt) de una respuesta VISCA PTZ Position Inquiry.
    Escanea el buffer para manejar ACK + Completion en el mismo paquete TCP.
    Formato Completion: 9x 58 0p 0q 0r 0s 0t 0u 0v 0w FF

    Pan and tilt values are returned as signed 16-bit integers so that
    negative camera positions (e.g. 0xFFFF = -1) are correctly represented.
    Devuelve None si los nibbles de payload son inválidos.
    """
    # El estándar VISCA responde y0 50 ...; algunas cámaras usan la variante
    # y0 58 ... — se aceptan ambas (antes solo 0x58 y la posición siempre
    # devolvía None con cámaras estándar).
    frame = _find_completion_frame(data, response_byte=0x50, payload_len=8)
    if frame is None:
        frame = _find_completion_frame(data, response_byte=0x58, payload_len=8)
    if frame is None:
        return None
    if not _valid_nibble_bytes(frame, [2, 3, 4, 5, 6, 7, 8, 9]):
        return None
    pan_raw  = (frame[2] & 0xF) << 12 | (frame[3] & 0xF) << 8 | (frame[4] & 0xF) << 4 | (frame[5] & 0xF)
    tilt_raw = (frame[6] & 0xF) << 12 | (frame[7] & 0xF) << 8 | (frame[8] & 0xF) << 4 | (frame[9] & 0xF)
    return _to_signed_16(pan_raw), _to_signed_16(tilt_raw)


def _find_completion_frame(data: bytes, response_byte: int, payload_len: int) -> Optional[bytes]:
    """
    Busca una trama VISCA Completion-with-data en el buffer recibido.

    Escanea en lugar de asumir offset fijo porque algunas cámaras
    (PTZOptics, Datavideo…) envían ACK + Completion en el mismo paquete TCP.
    Formato: 9x <response_byte> [payload_len bytes] FF
    """
    frame_len = payload_len + 3  # 9x + response_byte + [payload] + FF
    for i in range(len(data) - frame_len + 1):
        if (
            (data[i] & 0xF0) == 0x90
            and data[i + 1] == response_byte
            and data[i + frame_len - 1] == 0xFF
        ):
            return data[i: i + frame_len]
    return None


def inquiry_frame(data: bytes, payload_len: int) -> Optional[bytes]:
    """
    Busca una trama VISCA Completion-with-data (9x 50 … FF) en el buffer.

    Wrapper de _find_completion_frame para mantener la interfaz existente.
    """
    return _find_completion_frame(data, response_byte=0x50, payload_len=payload_len)


def _is_exact_inquiry(frame: bytes, payload_len: int) -> bool:
    return (len(frame) == payload_len + 3 and (frame[0] & 0xF0) == 0x90
            and frame[1] == 0x50 and frame[-1] == 0xFF)


def ae_mode(frame: bytes) -> Optional[str]:
    """Return a supported AE mode, or None for malformed/unknown observations.

    Full auto, shutter priority and iris priority share the UI's auto controls.
    Unknown vendor modes must not silently overwrite a known manual/bright mode.
    """
    if not _is_exact_inquiry(frame, 1):
        return None
    return {0x00: "auto", 0x03: "manual", 0x0A: "auto",
            0x0B: "auto", 0x0D: "bright"}.get(frame[2])


def exp_comp_level(frame: bytes) -> Optional[int]:
    """
    Extrae el nivel de compensación de exposición de un frame CAM_ExpCompPosInq.
    El valor VISCA (0–14) se mapea a -7..+7.
    Devuelve None si los nibbles de payload son inválidos.
    """
    if not _is_exact_inquiry(frame, 4):
        return None
    if not _valid_nibble_bytes(frame, [2, 3, 4, 5]):
        return None
    val = (
        ((frame[2] & 0x0F) << 12)
        | ((frame[3] & 0x0F) <<  8)
        | ((frame[4] & 0x0F) <<  4)
        |  (frame[5] & 0x0F)
    )
    return max(-7, min(7, val - 7))


def _response_frames(buf: bytes) -> Iterator[bytes]:
    """Yield complete camera response frames, excluding the FF terminator.

    A partial TCP tail is not a frame. Error frames also require an error
    code; accepting only their type byte would stop the transport read early.
    """
    for frame in buf.split(b"\xff")[:-1]:
        if len(frame) < 2 or (frame[0] & 0xF0) != 0x90:
            continue
        kind = frame[1] & 0xF0
        if kind in (0x40, 0x50) or (kind == 0x60 and len(frame) >= 3):
            yield frame


def contains_final_response(buf: bytes) -> bool:
    """True si *buf* contiene una trama VISCA terminal: Completion (9x 5y FF)
    o Error (9x 6y FF).

    El ACK (9x 4y FF) NO es terminal: muchas cámaras lo envían antes del
    Completion en un segmento TCP separado.  Quien lee una respuesta confirmada
    debe seguir leyendo hasta ver una trama terminal para no:
      - reportar éxito al recibir solo el ACK, ni
      - perder un frame de Error que llega después del ACK.
    """
    return any((frame[1] & 0xF0) in (0x50, 0x60)
               for frame in _response_frames(buf))


def contains_completion(buf: bytes) -> bool:
    """True si *buf* contiene una trama VISCA Completion (9x 5y FF).

    Distinto de contains_final_response: ignora los frames de Error.
    Útil cuando el llamador ya sabe que hubo una trama terminal y necesita
    distinguir éxito (Completion) de fallo (Error).
    """
    return any((frame[1] & 0xF0) == 0x50 for frame in _response_frames(buf))


def validate_visca_response(response: bytes) -> tuple[bool, str]:
    """Validate a VISCA response buffer received after sending a command.

    VISCA frame structure (camera → controller):
      ACK:        [0x90, 0x4x, 0xFF]  — command accepted, still executing
      Completion: [0x90, 0x5x, 0xFF]  — command finished successfully
      Error:      [0x90, 0x6x, <error_code>, 0xFF]  — command rejected/failed

    A buffer may contain ACK + Completion concatenated (two separate TCP
    segments received via _recv_visca_response, which loops until a terminal
    frame).

    Returns (True, "") only when a Completion frame (9x 5y FF) is present.
    Returns (False, reason) for ACK-only, Error frames, empty buffers and
    malformed data.

    ACK-only is NOT success: a camera that sends only ACK has accepted the
    command but not confirmed it completed. Stopping at ACK risks reporting
    success for a command that never finished or was later rejected.
    """
    if not response:
        return False, "empty response — connection may have closed"

    found_completion = False
    found_ack = False
    for frame in _response_frames(response):
        resp_type = frame[1]
        high_nibble = resp_type >> 4
        if high_nibble == 0x6:
            return False, f"VISCA error frame (type={resp_type:#04x}, code={frame[2]:#04x})"
        if high_nibble == 0x5:
            found_completion = True
        elif high_nibble == 0x4:
            found_ack = True

    if found_completion:
        return True, ""
    if found_ack:
        return False, "ACK received but no Completion — camera accepted the command but did not confirm it completed"
    return False, "no valid ACK or Completion frame in response"
