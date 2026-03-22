#!/usr/bin/env bash

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="${PROJECT_ROOT}/.venv"
CONFIG_DIR="${HOME}/.config/spotify-ad-muter"
CONFIG_FILE="${CONFIG_DIR}/config.toml"
SYSTEMD_DIR="${HOME}/.config/systemd/user"
UNIT_TEMPLATE="${PROJECT_ROOT}/systemd/spotify-ad-muter.service"
UNIT_FILE="${SYSTEMD_DIR}/spotify-ad-muter.service"

log() {
  printf '[spotify-ad-muter] %s\n' "$1"
}

require_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    printf 'Missing required command: %s\n' "$1" >&2
    exit 1
  fi
}

require_command python3
require_command systemctl

log "Creating virtual environment"
python3 -m venv "${VENV_DIR}"

log "Installing project into virtual environment"
"${VENV_DIR}/bin/pip" install -e "${PROJECT_ROOT}"

log "Writing default user config if missing"
mkdir -p "${CONFIG_DIR}"
if [[ ! -f "${CONFIG_FILE}" ]]; then
  cat > "${CONFIG_FILE}" <<'EOF'
ad_volume_percent = 0
unmute_delay_ms = 500
poll_interval_ms = 1000
log_level = "INFO"
stream_match_mode = "relaxed"
EOF
fi

log "Installing systemd user service"
mkdir -p "${SYSTEMD_DIR}"
sed "s|@PROJECT_ROOT@|${PROJECT_ROOT}|g" "${UNIT_TEMPLATE}" > "${UNIT_FILE}"

log "Enabling and starting service"
systemctl --user daemon-reload
systemctl --user enable --now spotify-ad-muter.service

log "Install complete"
log "Check service status with: systemctl --user status spotify-ad-muter.service"
log "Follow logs with: journalctl --user -u spotify-ad-muter.service -f"
