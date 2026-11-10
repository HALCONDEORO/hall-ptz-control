"""Validated, non-secret runtime overrides without writable /etc configuration.

The base YAML remains root-owned. Only endpoint and PiP nudge fields may be
changed by the running service; credentials, roles and feature flags never are.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import asdict
import fcntl
import json
import logging
import os
import threading
from pathlib import Path

from config.loader import build_settings, load_config
from core.atomic_write import write_text_atomic, group_shared_mode
from runtime.path_resolver import RuntimePathResolver

OVERLAY_NAME = 'camera_overrides.json'
logger = logging.getLogger(__name__)
_path_locks: dict[Path, threading.Lock] = {}
_path_locks_guard = threading.Lock()


@contextmanager
def _overlay_transaction(path: Path):
    # Separate stable inode: the JSON itself is atomically replaced.
    key = path.resolve()
    with _path_locks_guard:
        lock = _path_locks.setdefault(key, threading.Lock())
    with lock:
        key.parent.mkdir(parents=True, exist_ok=True)
        lock_path = key.with_name(key.name + '.lock')
        shared_mode = group_shared_mode(key.parent)
        # The inode stays stable; read-only flock also lets another group
        # member lock an old 0644 file without needing to write its contents.
        fd = os.open(lock_path, os.O_CREAT | os.O_RDONLY, 0o600)
        with os.fdopen(fd, 'r') as handle:
            if shared_mode is not None and os.fstat(fd).st_uid == os.geteuid():
                parent_gid = key.parent.stat().st_gid
                if os.fstat(fd).st_gid != parent_gid:
                    os.fchown(fd, -1, parent_gid)
                os.fchmod(fd, shared_mode)
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)



def overlay_file() -> Path:
    return RuntimePathResolver().data_dir / OVERLAY_NAME


def _merge(base, raw):
    if not isinstance(raw, dict) or set(raw) - {'schema_version', 'cameras', 'atem'}:
        raise ValueError('Invalid runtime override fields')
    if type(raw.get('schema_version')) is not int or raw['schema_version'] != 1:
        raise ValueError('Unsupported runtime override version')
    merged = asdict(base)
    by_id = {cam['id']: cam for cam in merged['cameras']}
    cameras = raw.get('cameras', {})
    if not isinstance(cameras, dict):
        raise ValueError('Camera overrides must be a mapping')
    for cam_id, changes in cameras.items():
        if cam_id not in by_id or not isinstance(changes, dict) or set(changes) - {'ip', 'visca_id'}:
            raise ValueError('Unknown camera or override field')
        if not all(isinstance(v, str) and v for v in changes.values()):
            raise ValueError('Camera endpoints must be strings')
        by_id[cam_id].update(changes)
    atem = raw.get('atem', {})
    if not isinstance(atem, dict) or set(atem) - {'ip', 'pip_nudge'}:
        raise ValueError('Invalid ATEM override fields')
    if 'ip' in atem and not isinstance(atem['ip'], str):
        raise ValueError('ATEM IP must be a string')
    if 'pip_nudge' in atem:
        nudge = atem['pip_nudge']
        if not isinstance(nudge, dict) or set(nudge) - {'camera_role', 'pan_speed', 'direction', 'duration_ms'}:
            raise ValueError('Invalid PiP nudge override fields')
        merged['atem']['pip_nudge'].update(nudge)
    if 'ip' in atem:
        merged['atem']['ip'] = atem['ip']
    for cam in merged['cameras']:
        cam['visca_id'] = cam['visca_id'].upper()
    return build_settings(merged)


def _read(path: Path):
    return json.loads(path.read_text(encoding='utf-8'))


def load_effective_config(config_path: Path, overlay_path: Path | None = None):
    """Load base YAML and valid endpoint overrides, falling back on corruption."""
    base = load_config(config_path)
    path = overlay_path if overlay_path is not None else overlay_file()
    if not path.exists():
        return base
    try:
        return _merge(base, _read(path))
    except (OSError, ValueError, TypeError, KeyError):
        logger.warning('Runtime camera overrides invalid or unreadable; using base YAML')
        return base


def patch_runtime_config(config_path: Path, *, overlay_path: Path | None = None,
                         cam_index=None, cam_ip=None, cam_visca_id=None,
                         atem_ip=None, atem_pip_nudge=None):
    """Persist validated endpoint updates atomically; never widen /etc permissions.

    Non-product/source configurations retain their existing YAML write contract.
    Explicit overlay_path supports tests and controlled non-product deployments.
    """
    path = overlay_path if overlay_path is not None else overlay_file()
    source_yaml = (RuntimePathResolver().running_from_source
                   and config_path.parent.resolve() != Path('/etc/khptz').resolve())
    if overlay_path is None and source_yaml and not path.exists():
        from config.writer import patch_config_yaml
        return patch_config_yaml(config_path, cam_index=cam_index, cam_ip=cam_ip,
                                 cam_visca_id=cam_visca_id, atem_ip=atem_ip,
                                 atem_pip_nudge=atem_pip_nudge)
    with _overlay_transaction(path):
        base = load_config(config_path)
        def _discard_corrupt_overlay(exc: Exception) -> dict:
            # Loading already ignores an unusable overlay and falls back to
            # base YAML. Preserve the file for diagnosis using the json_io
            # .corrupt.<timestamp> convention, then start from an empty overlay.
            logger.warning(
                'Runtime camera overrides unusable (%s) - preserving and starting fresh',
                exc,
            )
            try:
                from datetime import datetime
                corrupt = path.with_name(
                    f"{path.stem}.corrupt.{datetime.now().strftime('%Y%m%d_%H%M%S')}{path.suffix}"
                )
                path.rename(corrupt)
            except OSError:
                pass
            return {'schema_version': 1}

        raw = {'schema_version': 1}
        if path.exists():
            try:
                raw = _read(path)
            except ValueError as exc:
                # ValueError covers JSONDecodeError and UnicodeDecodeError.
                # Propagate OSError: a transient read failure must not discard
                # otherwise valid overrides.
                raw = _discard_corrupt_overlay(exc)
        # Camera IDs belong to the current base configuration. A repaired or
        # renamed base may retire IDs; do not make every future save fail on
        # those orphaned entries, or carry their addresses onto another role.
        if isinstance(raw, dict) and isinstance(raw.get('cameras'), dict):
            known_ids = {camera.id for camera in base.cameras}
            orphaned = set(raw['cameras']) - known_ids
            if orphaned:
                logger.warning('Discarding %d retired camera override entries', len(orphaned))
                raw['cameras'] = {key: value for key, value in raw['cameras'].items()
                                  if key in known_ids}
        # Validate the existing overlay before applying new values. Loading
        # already ignores invalid overlays, so preserve one for diagnosis and
        # start fresh. The final merge still validates new values and may reject
        # conflicts without erasing them.
        if path.exists():
            try:
                _merge(base, raw)
            except ValueError as exc:
                raw = _discard_corrupt_overlay(exc)
        if cam_ip is not None or cam_visca_id is not None:
            if type(cam_index) is not int or not 0 <= cam_index < len(base.cameras):
                raise ValueError('Unknown camera index')
            entry = raw.setdefault('cameras', {}).setdefault(base.cameras[cam_index].id, {})
            if cam_ip is not None:
                entry['ip'] = cam_ip
            if cam_visca_id is not None:
                entry['visca_id'] = cam_visca_id
        if atem_ip is not None:
            raw.setdefault('atem', {})['ip'] = atem_ip
        if atem_pip_nudge is not None:
            raw.setdefault('atem', {}).setdefault('pip_nudge', {}).update(atem_pip_nudge)
        _merge(base, raw)
        write_text_atomic(path, json.dumps(raw, indent=2) + '\n')
