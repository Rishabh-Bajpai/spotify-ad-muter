# Contributing

Thanks for considering a contribution.

## Development setup

```bash
python3 -m venv .venv
.venv/bin/pip install -e .
```

## Test before opening a PR

```bash
.venv/bin/python -m unittest discover -s tests
.venv/bin/python -m compileall src tests
```

## Guidelines

- keep changes focused and small when possible
- follow the existing project structure in `src/spotify_ad_muter/`
- add or update tests for behavior changes
- update docs when commands, setup, or behavior changes

## Reporting bugs

Include:

- your Linux desktop environment and version
- whether you use PulseAudio or PipeWire
- relevant command output or service logs
- steps to reproduce
