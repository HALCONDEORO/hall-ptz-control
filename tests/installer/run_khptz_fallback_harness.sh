#!/usr/bin/env bash
# run_khptz_fallback_harness.sh — exercise _ensure_run_khptz from install.sh
# without root. The function is extracted verbatim from the installer; install
# and stat are stubbed so owner/group can be simulated on a single-user host.
#
# Usage: run_khptz_fallback_harness.sh CASE WORKDIR
# Cases: absent | correct | mode700 | other-owner | symlink | create-fails
# Prints the function's [INFO]/[WARN] lines; exit code is the function's.
set -uo pipefail

CASE="$1"
WORK="$2"
REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
INSTALL_SH="${REPO_ROOT}/runtime/installer/install.sh"
TARGET="${WORK}/run-khptz"

mkdir -p "${WORK}/bin"

# stat stub: %a from the real file (lstat via python3), %U/%G from env so a
# single-user host can simulate foreign owners and the root group.
cat > "${WORK}/bin/stat" <<'STUB'
#!/usr/bin/env bash
fmt="$2"; path="$3"
case "${fmt}" in
    %a) python3 -c 'import os,sys; print(oct(os.lstat(sys.argv[1]).st_mode & 0o7777)[2:])' "${path}" ;;
    %U) echo "${STAT_FAKE_OWNER:-$(id -un)}" ;;
    %G) echo "${STAT_FAKE_GROUP:-root}" ;;
esac
STUB

# install stub: records the call, honours INSTALL_RC, and performs only
# mkdir+chmod (no chown — the harness runs unprivileged, owner is faked).
cat > "${WORK}/bin/install" <<'STUB'
#!/usr/bin/env bash
echo "$@" >> "${INSTALL_CALLS}"
[[ "${INSTALL_RC:-0}" == "0" ]] || exit 1
mkdir -p -- "$8" && chmod "$3" -- "$8"
STUB

chmod +x "${WORK}/bin/"*

# Set up the case.
case "${CASE}" in
    absent)        ;;
    correct)       mkdir -p "${TARGET}"; chmod 750 "${TARGET}"
                   STAT_FAKE_OWNER="$(id -un)"; STAT_FAKE_GROUP=root ;;
    mode700)       mkdir -p "${TARGET}"; chmod 700 "${TARGET}"
                   STAT_FAKE_OWNER="$(id -un)"; STAT_FAKE_GROUP=root ;;
    other-owner)   mkdir -p "${TARGET}"; chmod 750 "${TARGET}"
                   STAT_FAKE_OWNER="somebodyelse"; STAT_FAKE_GROUP=root ;;
    symlink)       mkdir -p "${WORK}/real-target"; ln -s "${WORK}/real-target" "${TARGET}" ;;
    create-fails)  INSTALL_RC=1 ;;
    *) echo "unknown case: ${CASE}" >&2; exit 2 ;;
esac

# Extract the function under test, verbatim, from the installer. It is
# defined (indented) inside the provisioning block, next to its call site.
sed -n '/^        _ensure_run_khptz() {/,/^        }$/p' "${INSTALL_SH}" > "${WORK}/func.sh"
[[ -s "${WORK}/func.sh" ]] || { echo "could not extract _ensure_run_khptz" >&2; exit 2; }

cat > "${WORK}/run.sh" <<'RUN'
#!/usr/bin/env bash
set -uo pipefail
info()  { echo "[INFO]  $*"; }
warn()  { echo "[WARN]  $*" >&2; }
source "${FUNC_SH}"
_ensure_run_khptz "${TARGET}" "${WIZARD_USER}"
RUN

export FUNC_SH="${WORK}/func.sh" TARGET WIZARD_USER="$(id -un)"
export INSTALL_CALLS="${WORK}/install.calls"
export PATH="${WORK}/bin:${PATH}"
export STAT_FAKE_OWNER="${STAT_FAKE_OWNER:-}" STAT_FAKE_GROUP="${STAT_FAKE_GROUP:-}"
export INSTALL_RC="${INSTALL_RC:-0}"

bash "${WORK}/run.sh"
echo "FUNC-RC=$?"
