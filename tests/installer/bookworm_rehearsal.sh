#!/usr/bin/env bash
# Synthetic data only. Must run in the disposable Bookworm container as root.
set -euo pipefail
cd /src
[[ "$(id -u)" == 0 ]] || { echo 'Container root required'; exit 1; }
/usr/bin/python3 -c 'import sys; assert sys.version_info[:2] == (3, 11), sys.version'
echo "REHEARSAL_ARCH=$(uname -m)"
echo 'No real systemd, display, network devices or camera movement are tested.'
bash tests/installer/container_install_test.sh

# Confirm user-GUI limitation without weakening the secret permissions.
# These are disposable fixture strings, never appliance credentials.
useradd --no-create-home --shell /usr/sbin/nologin --groups khptz khptz-test-desktop
secret_dir="$(mktemp -d)"
trap 'rm -rf -- "$secret_dir"' EXIT
chown khptz:khptz "$secret_dir"
chmod 2770 "$secret_dir"
runuser -u khptz -- env KHPTZ_DATA_DIR="$secret_dir" PYTHONPATH=/src /usr/bin/python3 - <<'PY'
from runtime import secret_manager as s
s.encrypt_secret(s.SECRET_ENTRY, 'fixture-entry')
s.encrypt_secret(s.SECRET_ADMIN, 'fixture-admin')
for name in (s.SECRET_ENTRY, s.SECRET_ADMIN):
    assert s._secret_file(name).stat().st_mode & 0o777 == 0o600
from application.authentication import verify_entry, verify_admin
assert verify_entry('fixture-entry')
assert verify_admin('fixture-admin')
assert not verify_admin('fixture-entry')
print('PASS service identity authenticates against private 0600 fixtures')
PY
runuser -u khptz-test-desktop -- env KHPTZ_DATA_DIR="$secret_dir" PYTHONPATH=/src /usr/bin/python3 - <<'PY'
from runtime import secret_manager as s
from application.authentication import verify_entry, verify_admin
assert s.secret_file_exists(s.SECRET_ADMIN)
assert not s.password_is_configured()
assert not verify_entry('fixture-entry')
assert not verify_admin('fixture-admin')
assert not verify_admin('fixture-entry')
print('PASS distinct desktop identity fails closed; user GUI is not approved for this rehearsal')
PY
echo 'PASS Bookworm system-mode install rehearsal; real Pi/X11/camera acceptance remains required.'
