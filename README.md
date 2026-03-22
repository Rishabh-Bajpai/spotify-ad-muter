# Spotify Ad Muter

`spotify-ad-muter` is a standalone Python service that detects Spotify ads over MPRIS and lowers only Spotify's stream volume while the ad is playing.

This repo is vibe-coded using ideas and ad-detection behavior from https://github.com/danigm/spotify-ad-blocker. The original GNOME Shell extension is kept here as archived reference in `docs/reference/extension`.

## Why this exists

The original extension depends on GNOME Shell internals and can break across GNOME releases. This version uses stable Linux interfaces instead:

- session D-Bus MPRIS metadata for ad detection
- PulseAudio or PipeWire's Pulse compatibility layer for per-app volume control

That makes it a better fit for GNOME 46+ systems.

## Features

- detects ads from track IDs starting with `spotify:ad` or `/com/spotify/ad/`
- lowers Spotify stream volume during ads
- restores each stream to its previous volume after a short delay
- keeps muting newly created Spotify streams while an ad is active
- runs cleanly as a foreground CLI app or a systemd user service

## Project layout

```text
.
├── src/spotify_ad_muter/
├── tests/
├── systemd/
└── docs/reference/extension/
```

## Setup

```bash
python3 -m venv .venv
.venv/bin/pip install -e .
```

## Run

```bash
.venv/bin/spotify-ad-muter --log-level INFO
```

Example with explicit flags:

```bash
.venv/bin/spotify-ad-muter \
  --ad-volume-percent 0 \
  --unmute-delay-ms 500 \
  --poll-interval-ms 1000 \
  --stream-match-mode relaxed \
  --log-level DEBUG
```

## Config

Create `~/.config/spotify-ad-muter/config.toml`:

```toml
ad_volume_percent = 0
unmute_delay_ms = 500
poll_interval_ms = 1000
log_level = "INFO"
stream_match_mode = "relaxed"
```

CLI flags override config values.

## systemd user service

```bash
mkdir -p ~/.config/systemd/user
cp systemd/spotify-ad-muter.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now spotify-ad-muter.service
```

## Verify

```bash
.venv/bin/python -m unittest discover -s tests
.venv/bin/spotify-ad-muter --log-level DEBUG
```

Then start Spotify and watch for `Ad detected` and `Restored Spotify stream volume` in the logs.

## Docs

- `docs/architecture.md`
- `docs/migration.md`
- `docs/reference/extension/`
