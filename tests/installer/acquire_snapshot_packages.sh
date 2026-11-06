#!/bin/bash
# Test-image-only acquisition. apt resolves dependencies against signed indexes;
# every downloaded archive must match that plan's SHA256 before installation.
set -euo pipefail

[[ $# -gt 0 ]] || { echo 'No packages requested' >&2; exit 2; }
cache=/var/cache/apt/archives
plan=$(mktemp)
trap 'rm -f "$plan" "$cache/khptz-acquire.partial"' EXIT
mkdir -p "$cache"

# Force a strong hash, not apt's legacy MD5 print-uris default. update is run by
# the Dockerfile with Error-Mode=any so missing indexes cannot go unnoticed.
apt-get -o Acquire::ForceHash=SHA256 --print-uris --yes --download-only \
    --no-install-recommends install "$@" > "$plan"

count=0
while read -r uri filename size digest extra; do
    [[ $uri == \'* ]] || continue  # apt also prints a human-readable summary
    uri=${uri#\'}
    uri=${uri%\'}
    [[ -z ${extra:-} && $filename != */* && $filename == *.deb \
       && $size =~ ^[0-9]+$ && $digest =~ ^SHA256:[a-f0-9]{64}$ ]] \
        || { echo 'Invalid apt acquisition record' >&2; exit 1; }
    case "$uri" in
        http://snapshot.debian.org/archive/debian/20260901T000000Z/pool/*|\
        http://snapshot.debian.org/archive/debian-security/20260901T000000Z/pool/*) ;;
        *) echo 'Unexpected package source in apt plan' >&2; exit 1 ;;
    esac
    # HTTP bootstraps ca-certificates on the slim base; authenticity comes from
    # the signed index SHA256, checked by apt-helper and sha256sum.
    mirror="http://snapshot-cloudflare.debian.org/${uri#http://snapshot.debian.org/}"
    success=false
    for attempt in 1 2 3; do
        for source in "$uri" "$mirror"; do
            rm -f "$cache/khptz-acquire.partial"
            if timeout --kill-after=5 45 /usr/lib/apt/apt-helper -o Acquire::Retries=0 \
                -o Acquire::http::Timeout=30 -o Acquire::https::Timeout=30 \
                download-file "$source" "$cache/khptz-acquire.partial" "$digest"; then
                # Verify again before atomically publishing to apt's cache.
                printf '%s  %s\n' "${digest#SHA256:}" "$cache/khptz-acquire.partial" | sha256sum -c -
                [[ $(stat -c %s "$cache/khptz-acquire.partial") == "$size" ]] \
                    || { echo 'Package size mismatch' >&2; exit 1; }
                mv -f "$cache/khptz-acquire.partial" "$cache/$filename"
                success=true
                break
            fi
        done
        [[ $success == true ]] && break
        [[ $attempt == 3 ]] || sleep "$((attempt * 2))"
    done
    [[ $success == true ]] || { echo "Package acquisition failed: $filename" >&2; exit 1; }
    count=$((count + 1))
done < "$plan"
echo "Verified $count package archives from the signed apt plan."
# No network fallback during installation. Any missing archive fails closed.
apt-get --no-download --yes --no-install-recommends install "$@"
