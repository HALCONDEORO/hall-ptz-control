#!/usr/bin/env python3
# Copyright (c) 2026 MACD Adaptive Limited.
# Licensed under the MIT License. See LICENSE in the repository root.
"""application/authentication.py — the single place that verifies passwords.

The product has two independent logins (set separately by the setup wizard):
  - the entry (operator) password  → secret_manager.SECRET_ENTRY (password.enc)
  - the administrator password      → secret_manager.SECRET_ADMIN (admin.enc)

Entry unlocks the operator UI; admin is required to elevate into Technician mode.
Centralising the comparison here keeps the rule in one tested place and lets the
UI (login screen, role-elevation overlay) call a service instead of reaching
into the crypto layer or comparing plaintext itself.

Comparisons are constant-time (hmac.compare_digest) so a wrong password cannot be
narrowed by timing.

Migration: installs created before the entry/admin split have only password.enc.
When no admin secret is configured yet, verify_admin() falls back to the entry
password so Technician mode stays reachable until an admin password is set (via
the wizard or a future change-password flow). Once admin.enc exists the entry
password no longer elevates — the two logins are then fully independent.
"""

from __future__ import annotations

import hmac

from runtime import secret_manager

def _matches(candidate: str, actual: str) -> bool:
    """Constant-time equality on the UTF-8 bytes of two passwords."""
    return hmac.compare_digest(candidate.encode("utf-8"), actual.encode("utf-8"))


def verify_entry(candidate: str) -> bool:
    """Return True iff *candidate* is the configured entry (operator) password.

    Uses decrypt_password so the legacy password.enc location is migrated on the
    first check, matching the existing login path. A missing/corrupt secret
    yields False (never a hardcoded fallback)."""
    try:
        actual = secret_manager.decrypt_password()
    except secret_manager.PasswordNotConfiguredError:
        return False
    return _matches(candidate, actual)


def admin_secret_configured() -> bool:
    """True once a dedicated administrator password (admin.enc) exists."""
    return secret_manager.secret_is_configured(secret_manager.SECRET_ADMIN)


def verify_admin(candidate: str) -> bool:
    """Return True iff *candidate* may elevate to Technician (administrator).

    If a dedicated admin password is configured, only that password is accepted.
    Otherwise (pre-split installs) the entry password is accepted as a migration
    fallback so existing single-password sites are not locked out of Technician
    mode."""
    # Gate on the file EXISTING, not on it decrypting.
    #
    # decrypt_secret() turns any failure — including an unreadable file — into
    # PasswordNotConfiguredError, so admin_secret_configured() answers False for
    # a secret that is merely inaccessible. Using that here meant an admin.enc
    # the process could not read silently re-enabled the pre-split migration
    # fallback, and the OPERATOR password then passed an administrator gate:
    # Repair provisioning, the password-change dialog, admin login and role
    # elevation all route through this function. An unreadable secret must deny
    # access; only a genuinely absent one may fall back.
    if secret_manager.secret_file_exists(secret_manager.SECRET_ADMIN):
        try:
            actual = secret_manager.decrypt_secret(secret_manager.SECRET_ADMIN)
        except secret_manager.PasswordNotConfiguredError:
            return False
        return _matches(candidate, actual)
    return verify_entry(candidate)
