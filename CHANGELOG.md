# Changelog

## 0.1.1 - 2026-11-22

- fix: Spotify could stay muted indefinitely after an ad, leaving playback silent
- fix: a stream already muted from a previous run was mistaken for "muted by the user" and never unmuted; such streams are now healed and unmuted
- fix: stale mute snapshots for a vanished stream index (Spotify restarting or re-creating its audio stream) blocked tracking and restoring the live stream; they are now dropped each poll
- fix: `recover_stuck_streams()` and `restore_volumes()` aborted on `PulseOperationFailed` from a redundant volume write, leaving earlier streams muted; unmuting no longer depends on the volume call
- feat: idle reconcile loop clears stuck Spotify mutes when no ad is active
- feat: add `release_all()` so shutdown and abnormal exits always release the mute
- feat: `cli` now unmutes in a `finally` block on SIGINT/SIGTERM or crash
- test: cover stuck-stream healing, vanished stream indexes, fault-tolerant restore, and forced release (32 passing tests)

## 0.1.0 - 2026-03-22

- initial standalone Python release
- MPRIS-based Spotify ad detection
- per-stream PulseAudio/PipeWire volume muting and restoration
- CLI runner, config support, systemd user service example
- one-click installer and uninstall scripts for local setup
- GitHub Actions CI for test and compile verification
- archived GNOME extension reference moved under `docs/reference/extension/`
- expanded automated unit test suite to 21 passing tests
