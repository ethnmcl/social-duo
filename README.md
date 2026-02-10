# social-duo

A production-quality Python CLI where two AI agents collaborate to draft, critique, revise, and reply to social media content. The tool maintains a local workspace with config, history, and exports.

**Highlights**
- Two agents: Writer and Editor/Responder
- Iterative loop with PASS/FAIL gating
- Platform constraints and brand voice
- SQLite history with export
- JSON and rich CLI output

## Install

```bash
cd social-duo
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

Or with `pipx`:

```bash
pipx install -e .
```

## Setup

```bash
cp .env.example .env
export OPENAI_API_KEY=your_key_here
# Optional
export OPENAI_BASE_URL=https://api.openai.com/v1
export OPENAI_MODEL=gpt-4o-mini
```

Initialize the workspace:

```bash
social_duo init
```

## Examples

LinkedIn post about agentic workflows:

```bash
social_duo post --platform linkedin --goal educate --topic "agentic workflows" --audience "engineering leaders" --tone "confident" --length medium
```

X thread of 5 tweets about vector databases for semantic search:

```bash
social_duo post --platform x --thread 5 --goal educate --topic "vector databases for semantic search" --audience "ML engineers" --tone technical --length short
```

Replies to a critical comment (polite + direct):

```bash
social_duo reply --text "This feels like vaporware." --platform x --style polite --stance neutral
social_duo reply --text "This feels like vaporware." --platform x --style direct --stance disagree
```

Autonomous discuss mode (no topic provided):

```bash
social_duo discuss --platform x --turns 10 --verbose
```

MOLTBOOK-LITE simulation:

```bash
social_duo molt run --turns 25
social_duo molt watch --run-id <id>
social_duo molt export --run-id <id> --format md
```

Resume session via history and chat:

```bash
social_duo history --list
social_duo history --show 3
social_duo chat --session 3
```

## Commands

- `social_duo init`
- `social_duo post`
- `social_duo reply`
- `social_duo discuss`
- `social_duo molt`
- `social_duo chat`
- `social_duo history`
- `social_duo config`

## Troubleshooting

- Missing key: set `OPENAI_API_KEY` in your environment.
- Base URL errors: set `OPENAI_BASE_URL` (default is `https://api.openai.com/v1`).
- Model errors: set `OPENAI_MODEL` to a valid chat model name for your provider.

## Notes

- All artifacts are stored in `.social-duo/` in the current directory.
- Use `--json` for machine-readable output.
- Use `--verbose` to see full agent exchanges.

## NPM Wrapper

If you want an npm package that installs the Python CLI from GitHub:

```bash
npm i -g social-duo
social-duo --help
```

This uses the GitHub repo as the install source and creates a venv under `~/.social-duo/venv`.
