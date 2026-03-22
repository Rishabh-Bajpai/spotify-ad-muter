#!/usr/bin/env bash

set -euo pipefail

UNIT_FILE="${HOME}/.config/systemd/user/spotify-ad-muter.service"

if command -v systemctl >/dev/null 2>&1; then
  systemctl --user disable --now spotify-ad-muter.service >/dev/null 2>&1 || true
  systemctl --user daemon-reload || true
fi

rm -f "${UNIT_FILE}"

printf 'Removed systemd unit: %s\n' "${UNIT_FILE}"
printf 'The project files, virtualenv, and config directory were left in place.\n'
