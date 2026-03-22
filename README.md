# Spotify Ad Muter

This project replaces the GNOME Shell extension in `extension/` with a standalone Python service.

It uses:
- Spotify's MPRIS interface on the session D-Bus to detect ads
- PulseAudio or PipeWire's Pulse compatibility layer to lower Spotify's stream volume

That makes it independent of GNOME Shell internals, which is useful when the extension breaks on GNOME 46 or later.

## What it does

- detects ads from Spotify track IDs that start with `spotify:ad` or `/com/spotify/ad/`
- lowers Spotify stream volume during ads
- restores the previous Spotify stream volume after a short delay
- keeps checking for new Spotify sink inputs while an ad is active

## Setup

From the repository root:

```bash
python3 -m venv python-muter/.venv
python-muter/.venv/bin/pip install -e python-muter
```

## Run it

```bash
python-muter/.venv/bin/spotify-ad-muter --log-level INFO
```

Useful flags:

```bash
python-muter/.venv/bin/spotify-ad-muter \
  --ad-volume-percent 0 \
  --unmute-delay-ms 500 \
  --poll-interval-ms 1000 \
  --stream-match-mode relaxed \
  --log-level DEBUG
```

## Optional config file

Create `~/.config/spotify-ad-muter/config.toml`:

```toml
ad_volume_percent = 0
unmute_delay_ms = 500
poll_interval_ms = 1000
log_level = "INFO"
stream_match_mode = "relaxed"
```

CLI flags override config file values.

## systemd user service

1. Copy `python-muter/systemd/spotify-ad-muter.service` to `~/.config/systemd/user/spotify-ad-muter.service`
2. Replace `<PROJECT_DIR>` with the absolute path to this repository
3. Enable and start it:

```bash
systemctl --user daemon-reload
systemctl --user enable --now spotify-ad-muter.service
```

## Notes

- The service restores each Spotify stream to its previous volume instead of always forcing 100%.
- It matches Spotify audio streams by Pulse properties, which works well for PulseAudio and PipeWire setups.
- If Spotify is not running, the service stays idle and keeps polling.

## Quick verification

```bash
python-muter/.venv/bin/python -m unittest discover -s python-muter/tests
python-muter/.venv/bin/spotify-ad-muter --log-level DEBUG
```

Then start Spotify and watch the log output when an ad plays.
