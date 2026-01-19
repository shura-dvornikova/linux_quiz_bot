# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A Telegram quiz bot built with aiogram 3.x that presents Linux-related questions to users. Users select a topic and answer multiple-choice questions, receiving a score summary at the end. The bot also supports user feedback.

## Commands

### Run the bot locally
```bash
python -m bot
```
Requires `BOT_TOKEN` environment variable (or set in `.env` file).

### Linting and Formatting
```bash
flake8 --config .flake8 .
black --check .   # check only
black .           # format
```

### Tests
```bash
pytest -q
```

### Docker
```bash
docker build -t linux-quiz-bot .
docker compose -f docker-compose.dev.yml --env-file .env.dev up -d
```

## Architecture

The bot is a single-module aiogram application in `bot/__main__.py`:

- **Entry point**: `bot/__main__.py` - Contains all handlers, FSM states, and bot initialization
- **Config**: `bot/config.py` - Loads environment variables from `.env` file
- **Quiz data**: `bot/data/quizzes.json` - JSON file with quiz topics and questions

### Key Patterns

- Uses aiogram 3.x with FSM (Finite State Machine) for tracking quiz progress and feedback states
- Questions are organized by topic in a JSON dictionary; the bot loads them at startup
- Markdown escaping via `escape_md()` for Telegram's MarkdownV2 format
- Inline keyboards for topic selection and answer choices
- Answer options are shuffled randomly for each question

### Environment Variables

- `BOT_TOKEN` - Telegram bot token (required)
- `ENV` - Environment name (dev/prod), defaults to "dev"
- `LOG_LEVEL` - Logging level, defaults to "DEBUG"
- `ENV_FILE` - Path to env file, defaults to ".env"

## CI/CD

GitHub Actions workflow (`.github/workflows/ci_cd.yml`):
- Runs flake8 and black on all pushes/PRs
- Builds Docker image and pushes to DockerHub on push to main/develop
- Deploys to dev (develop branch) or prod (main branch) via self-hosted runner
