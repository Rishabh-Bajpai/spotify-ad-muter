# Migration Notes

This repository started from the idea behind `danigm/spotify-ad-blocker`, a GNOME Shell extension that muted Spotify ads by watching MPRIS metadata.

This version keeps the same core ad detection behavior, but moves the runtime into a standalone Python service so it no longer depends on GNOME Shell extension APIs.

## Legacy reference

The original extension code used as reference is preserved in `docs/reference/extension/`.

## Differences from the extension

- no GNOME panel button or preferences UI
- no dependency on GNOME Shell version compatibility
- restores previous per-stream volume instead of always forcing max volume
- can run as a regular CLI app or a systemd user service
