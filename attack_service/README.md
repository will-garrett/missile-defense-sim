# Attack Service

A service for managing missile launches and platform installations in the missile defense simulation system.

## Project Structure

This project follows the recommended pytest best practices with a `src` layout:

```
attack_service/
├── src/
│   └── attack_service/
│       ├── __init__.py
│       ├── api.py
│       ├── main.py
│       └── messaging.py
├── tests/
│   └── attack_service/
│       ├── __init__.py
│       ├── test_api.py
│       ├── test_messaging.py
│       └── test_main.py
├── pyproject.toml
├── tox.ini
├── requirements.txt
├── run_tests.py
├── Dockerfile
└── README.md
```

## Installation

### Development Installation

Install the package in development mode with test dependencies:

```bash
# Using the test runner
python run_tests.py install

# Or manually
pip install -e .[test]
```

### Production Installation

```bash
pip install .
```

## Testing

This project uses pytest with the `importlib` import mode for better test isolation and follows modern Python packaging practices.

### Running Tests

#### Using the Test Runner

```bash
# Run all tests
python run_tests.py

# Run only unit tests
python run_tests.py unit

# Run only integration tests
python run_tests.py integration

# Run linting checks
python run_tests.py lint

# Run tox for all environments
python run_tests.py tox
```

#### Using pytest directly

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src --cov-report=html

# Run specific test file
pytest tests/attack_service/test_api.py

# Run tests matching a pattern
pytest -k "test_launch"
```

#### Using tox

```bash
# Run all environments
tox

# Run specific environment
tox -e py311

# Run linting only
tox -e lint

# Run coverage only
tox -e coverage
```

## Development

### Code Quality

The project includes several tools for maintaining code quality:

- **pytest**: Testing framework
- **pytest-cov**: Coverage reporting
- **flake8**: Code linting
- **black**: Code formatting
- **isort**: Import sorting
- **mypy**: Type checking

### Adding New Tests

1. Create test files in `tests/attack_service/` following the naming convention `test_*.py`
2. Use absolute imports for the attack_service package: `from attack_service.api import AttackServiceAPI`
3. Mark async tests with `@pytest.mark.asyncio`
4. Use appropriate markers for test categorization (`@pytest.mark.unit`, `@pytest.mark.integration`)

### Running the Service

```bash
# Using the installed script
attack-service

# Or directly
python -m attack_service.main
```

## Configuration

The service uses environment variables for configuration:

- `DB_DSN`: PostgreSQL connection string (required)
- `NATS_URL`: NATS server URL (default: `nats://nats:4222`)

## API Endpoints

The service provides REST API endpoints for:

- Platform management
- Installation management
- Missile launching
- Active missile tracking
- Event history (detections, engagements, detonations)
- Health checks

See the API documentation for detailed endpoint specifications.

## Contributing

1. Install the package in development mode
2. Write tests for new features
3. Ensure all tests pass
4. Run linting checks
5. Submit a pull request

## License

This project is part of the Missile Defense Simulation system. 