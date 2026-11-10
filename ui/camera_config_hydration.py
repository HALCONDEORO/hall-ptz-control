# Copyright (c) 2026 MACD Adaptive Limited.
# Licensed under the MIT License. See LICENSE in the repository root.
"""Map persisted roles to shared runtime objects without rebinding them."""


def hydrate_camera_roles(cameras, platform, comments):
    # Splash, Admin and services hold references to these same objects.
    by_role = {saved.role: saved for saved in cameras}
    for role, current in (('platform', platform), ('comments', comments)):
        saved = by_role.get(role)
        current.ip = saved.ip if saved is not None else ''
        current.cam_id = saved.visca_id if saved is not None else ''


def hydrate_atem(atem_settings, atem_config):
    """Point the shared ATEM config object at the persisted IP.

    Without this the ATEM global kept its empty default on every boot — the
    only writer was the Settings dialog — so the monitor started with no IP
    and reported NOT_CONFIGURED until the operator re-entered the address,
    even though config.yaml already held it.
    """
    saved_ip = getattr(atem_settings, 'ip', '') if atem_settings is not None else ''
    atem_config.ip = (saved_ip or '').strip()
