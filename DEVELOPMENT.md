# Development Guide

This guide covers setting up a development environment for Alithia, including both backend and frontend development.

## Prerequisites

- Python 3.10 or higher
- Node.js 18+ and npm
- Git

## Development Installation

Clone the repository and install with development dependencies:

```bash
git clone https://github.com/caesar0301/alithia.git
cd alithia

# Install with development dependencies
pip install -e ".[default,dev]"
```

This installs:
- All default Alithia dependencies
- Development tools (pytest, mypy, etc.)
- Testing dependencies

## Development Workflow

### Backend Development

The backend is a FastAPI application that serves the API and WebSocket endpoints.

**Running the backend in development mode:**

```bash
python -m alithia.run dashboard --config alithia_config.json --dev
```

The `--dev` flag enables auto-reload using uvicorn's reload feature.

**Backend options:**

| Option | Default | Description |
|--------|---------|-------------|
| `--config` | - | Path to configuration JSON file |
| `--host` | `0.0.0.0` | Server host address |
| `--port` | `8080` | Server port |
| `--dev` | - | Enable auto-reload for development |

**Running tests:**

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=alithia

# Run specific test file
pytest tests/test_paperscout.py
```

**Code formatting and linting:**

```bash
# Format code with black
black alithia/

# Check with mypy
mypy alithia/

# Run flake8
flake8 alithia/
```

### Frontend Development

The frontend is a React application built with Vite.

**Setup:**

```bash
cd dashboard-frontend
npm install
```

**Running the frontend in development mode:**

```bash
npm run dev
```

This starts the Vite dev server at http://localhost:5173. The dev server proxies API calls to the backend.

**Frontend scripts:**

| Command | Description |
|---------|-------------|
| `npm run dev` | Start development server with hot-reload |
| `npm run build` | Build for production (outputs to `dist/`) |
| `npm run preview` | Preview production build locally |
| `npm run lint` | Run ESLint |

**Building for production:**

```bash
npm run build
cd ..
python -m alithia.run dashboard --config alithia_config.json
```

The production build serves the built frontend from the FastAPI backend.

## Project Structure

```
alithia/
├── alithia/                 # Main Python package
│   ├── dashboard/          # Dashboard backend (FastAPI)
│   ├── paperscout/         # PaperScout agent
│   ├── paperlens/          # PaperLens agent (PDF analysis)
│   ├── storage/            # Storage backend (Supabase/SQLite)
│   └── run.py              # CLI entry point
├── dashboard-frontend/     # React frontend
│   ├── src/
│   │   ├── components/     # React components
│   │   ├── pages/          # Page components
│   │   └── services/       # API services
│   ├── public/
│   └── package.json
├── tests/                  # Test files
├── docs/                   # Documentation
│   └── screenshots/        # Screenshots for README
├── Dockerfile              # Docker image definition
├── pyproject.toml          # Python project configuration
└── README.md              # User documentation
```

## Configuration

Create a `alithia_config.json` file in the project root for local development. See `alithia_config_example.json` for a complete example.

**Minimum configuration for development:**

```json
{
  "llm": {
    "api_key": "your_openai_api_key",
    "base_url": "https://api.openai.com/v1",
    "model": "gpt-4o-mini"
  },
  "storage": {
    "backend": "sqlite"
  }
}
```

## Testing

### Running Tests

```bash
# Run all tests
pytest

# Run with verbosity
pytest -v

# Run specific test module
pytest tests/test_storage.py

# Run with coverage report
pytest --cov=alithia --cov-report=html
```

### Writing Tests

Tests should be placed in the `tests/` directory, mirroring the structure of the `alithia/` package.

```python
# tests/example_test.py
import pytest
from alithia.module import function

def test_function():
    result = function("input")
    assert result == "expected"
```

## Building Docker Image

```bash
# Build the image
docker build -t alithia:dev .

# Run the container
docker run -d -p 8080:8080 \
  -v $(pwd)/alithia_config.json:/app/config.json \
  alithia:dev \
  python -m alithia.run dashboard --config /app/config.json --dev
```

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Add tests for new functionality
5. Ensure all tests pass (`pytest`)
6. Format your code (`black alithia/`)
7. Commit your changes (`git commit -m 'Add amazing feature'`)
8. Push to the branch (`git push origin feature/amazing-feature`)
9. Open a Pull Request

## Code Style

- **Python**: Follow PEP 8, use Black for formatting
- **Type hints**: Use mypy for type checking
- **Frontend**: Follow ESLint configuration, use Prettier for formatting
- **Commit messages**: Use conventional commit format

## Troubleshooting

### Backend Issues

**Import errors**: Make sure you've installed the package in development mode:
```bash
pip install -e ".[default,dev]"
```

**Port already in use**: Change the port with the `--port` option or stop the existing process.

### Frontend Issues

**Module not found**: Ensure you've installed dependencies:
```bash
cd dashboard-frontend
npm install
```

**API connection issues**: Make sure the backend is running and the Vite proxy is configured correctly.

## Resources

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [React Documentation](https://react.dev/)
- [Vite Documentation](https://vitejs.dev/)
- [Supabase Documentation](https://supabase.com/docs)