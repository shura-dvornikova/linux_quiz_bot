# LinuxQuiz Bot

Telegram bot for learning Linux through interactive quizzes and practice questions.

## About the project

LinuxQuiz Bot helps users improve their Linux knowledge by answering quiz questions directly in Telegram.

The project was created to combine Python development with DevOps practices such as containerization, CI/CD automation, environment separation, and reproducible deployments.

## Features

* Interactive Linux quizzes
* Telegram Bot integration
* Environment-specific configuration
* Automated testing
* Docker-based deployment
* CI/CD automation

## Architecture

Telegram User
↓
Telegram Bot API
↓
LinuxQuiz Bot (Python)
↓
Docker Container

CI/CD:
GitHub Actions → Build → Test → Deploy

## Tech Stack

### Application

* Python
* Telegram Bot API

### DevOps

* Docker
* Docker Compose
* GitHub Actions
* Linux (Ubuntu)
* Bash
* Pytest

## Project Structure

```text
bot/
tests/
.github/workflows/

Dockerfile
docker-compose.dev.yml
docker-compose.prod.yml

.env.dev
.env.prod
```

## Running locally

```bash
git clone <repository-url>

cd linuxquiz-bot

cp .env.dev .env

docker compose -f docker-compose.dev.yml up --build
```

## Testing

```bash
pytest
```

## CI/CD

GitHub Actions pipeline performs:

* code validation
* automated tests
* Docker image build
* deployment workflow

## Future Improvements

* Kubernetes deployment
* Prometheus monitoring
* Grafana dashboards
* Terraform infrastructure provisioning

## Author

Alexandra Tsyganok

DevOps Engineer
