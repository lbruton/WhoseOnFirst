# Contributing to WhoseOnFirst

Thanks for your interest in contributing!

## Getting Started

1. Fork the repository
2. Create a feature branch from `dev`
3. Make your changes
4. Run tests: `pytest --cov=src`
5. Open a pull request targeting `dev`

## Development Setup

```bash
# Clone and set up
git clone <your-fork-url>
cd WhoseOnFirst

# Docker dev environment (recommended)
docker-compose -f docker-compose.dev.yml up -d

# Or local virtualenv
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Branch Strategy

- `main` — production, deployed via GitOps
- `dev` — integration branch, all PRs target here
- Feature branches off `dev` for all changes

## Code Standards

- Python 3.12+, FastAPI conventions
- SQLAlchemy ORM only (no raw SQL)
- Phone numbers in E.164 format (`+1XXXXXXXXXX`)
- Timezones via `pytz` using `America/Chicago`
- All inputs validated with Pydantic

## Testing

Maintain 80%+ test coverage. Run the full suite before submitting:

```bash
pytest --cov=src --cov-report=html
```

## Commit Messages

Follow [Conventional Commits](https://www.conventionalcommits.org/):

- `feat:` — new feature
- `fix:` — bug fix
- `docs:` — documentation only
- `chore:` — maintenance, cleanup
- `release:` — version bumps

## License

By contributing, you agree that your contributions will be licensed under the [MIT License](LICENSE).
