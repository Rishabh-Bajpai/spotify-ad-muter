# Architecture

The app has three core pieces:

- `mpris.py` polls Spotify's MPRIS metadata over the session D-Bus
- `audio.py` finds Spotify sink inputs and adjusts only those volumes through PulseAudio/PipeWire
- `service.py` coordinates ad detection, delayed restore, and stream reconciliation

## Flow

1. Read `Metadata["mpris:trackid"]` from `org.mpris.MediaPlayer2.spotify`
2. Treat IDs starting with `spotify:ad` or `/com/spotify/ad/` as ads
3. Snapshot current Spotify stream volumes
4. Lower Spotify stream volume to the configured percentage
5. When the ad ends, wait for the configured delay and restore the saved volumes

## Why polling

The service uses lightweight polling for both MPRIS state and active Spotify sink inputs. That keeps the implementation simple and robust across GNOME, PipeWire, and PulseAudio setups.
