#!/usr/bin/env bash
# The existing installer installs the session helper only in user mode.
set -euo pipefail
if [[ -f /usr/local/libexec/khptz-gui-session ]]; then
    # A still-running system controller takes precedence during mode changes.
    if /usr/bin/systemctl is-active --quiet khptz-control.service; then
        exit 0
    fi
    exec /usr/local/libexec/khptz-gui-session
fi
# Starting a supervised unit is idempotent. Never launch main.py directly.
exec /usr/bin/systemctl --no-ask-password --no-block start khptz-control.service
