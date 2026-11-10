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
