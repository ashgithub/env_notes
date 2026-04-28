# Env Notes

Env Notes is a local OneNote-style notes app built with FastAPI + vanilla JS.

## Features
- Notebook / section / page / subpage structure
- Freeform note canvas (drag and resize note blocks)
- Rich-text HTML note blocks
- Search across page titles and note content
- Local filesystem storage

## Tech Stack
- Python 3.13+
- FastAPI
- Uvicorn
- Plain HTML/CSS/JavaScript frontend

## Quick Start
```bash
cd ~/env_notes
uv sync
uv run python -m env_notes
```

Open: `http://127.0.0.1:9490`

## Private Notes Storage (Recommended)
Keep your personal notes in a separate local repo and point the app to it:

```bash
ENV_NOTES_DATA_ROOT=~/Documents/env-notes-private/notebooks uv run python -m env_notes
```

If `ENV_NOTES_DATA_ROOT` is not set, the app uses `data/notebooks` inside this repo.

## Stable Local URL: `http://env-notes`

To run reliably in the browser with launchd + Apache reverse proxy:

1. Install/start the app as a user LaunchAgent:
```bash
~/env_notes/scripts/install-launchd-agent.sh
```

2. Configure `/etc/hosts` and Apache reverse proxy (requires sudo):
```bash
sudo ~/env_notes/scripts/install-notes-test-apache.sh
```

3. Verify:
```bash
curl -I http://127.0.0.1:9490/
curl -I http://env-notes/
```

Notes:
- Safari is more reliable with `env-notes` (hyphen) than `env_notes` (underscore).
- The Apache vhost uses `ServerName env-notes` and aliases `notes` + `env_notes`.
- App traffic is proxied from Apache `:80` to `127.0.0.1:9490`.

## Public Repo Safety
This repo is intended to be public code only.

- `data/` is ignored by git.
- Personal notes should live outside this repo.
- Do not commit local secrets, tokens, keys, or private notebook exports.

## Development
```bash
uv sync
uv run uvicorn env_notes.app:app --host 127.0.0.1 --port 9490 --reload
```

## License
Private/internal use by default unless you add a license file.
