# Sentinel

**Personal Energy Guardian** - A CLI tool for detecting schedule conflicts that calendars miss.

Sentinel uses knowledge graphs to find hidden energy collisions in your schedule. Unlike traditional calendar apps that only check for time conflicts, Sentinel understands how activities affect your energy levels and detects problems like an emotionally draining Sunday dinner cascading into poor performance at Monday's high-stakes presentation.

## Features

- **Schedule Ingestion**: Parse natural language schedule descriptions into a knowledge graph
- **Collision Detection**: Find multi-hop energy conflicts through graph traversal
- **Graph Exploration**: Explore relationships around any node
- **User Corrections**: Delete or modify AI-inferred relationships
- **Confidence Scoring**: See which collisions are most reliable

## Installation

### Prerequisites

- Python 3.11 or higher
- [uv](https://docs.astral.sh/uv/) package manager

### Setup

```bash
# Clone the repository
git clone https://github.com/armelhbobdad/sentinel
cd sentinel

# Install dependencies
uv sync

# Copy environment template and configure
cp .env.template .env
# Edit .env with your API keys
```

## Usage

```bash
# Show help
uv run sentinel --help

# Show version
uv run sentinel --version
```

## Development

### Running Tests

```bash
# Run all tests
uv run pytest tests/ -v

# Run fast unit tests only
uv run pytest tests/unit/ -v

# Run integration tests (MockEngine, fixtures)
uv run pytest tests/integration/ -v
```

### Code Quality

```bash
# Format code
uv run ruff format .

# Lint code
uv run ruff check .

# Fix linting issues
uv run ruff check --fix .

# Type check
uv run ty check
```

### Pre-commit Hooks

The project uses [lefthook](https://github.com/evilmartians/lefthook) for pre-commit hooks:

```bash
# Install lefthook as dev dependency
uv add --dev lefthook

# Install hooks
uv run lefthook install
```

For other installation methods, see [lefthook documentation](https://lefthook.dev/installation/index.html).

## Project Structure

```
sentinel/
├── src/
│   └── sentinel/
│       ├── __init__.py         # Package init with version
│       ├── __main__.py         # Entry point for python -m sentinel
│       ├── core/
│       │   ├── constants.py    # Exit codes, thresholds
│       │   ├── types.py        # Graph, Node, Edge, ScoredCollision
│       │   └── engine.py       # GraphEngine protocol + implementations
│       └── cli/
│           └── commands.py     # Click CLI commands
├── tests/
│   ├── conftest.py             # MockEngine and shared fixtures
│   ├── fixtures/
│   │   └── schedules/          # Test schedule files
│   ├── unit/                   # Fast unit tests
│   └── integration/            # MockEngine and fixture tests
├── pyproject.toml              # Project configuration
├── lefthook.yml                # Pre-commit hook configuration
└── README.md
```

## Architecture

Sentinel follows a modular architecture:

- **Core Module**: Contains types, constants, and the GraphEngine protocol. Never imports from CLI or visualization modules.
- **CLI Module**: Click-based command-line interface
- **GraphEngine Protocol**: Async interface for graph operations, enabling both mock and real implementations

## Technology Stack

| Tech         | Purpose                                 |
|--------------|-----------------------------------------|
| Python 3.11+ | Runtime (required for stdlib `tomllib`) |
| uv           | Package management                      |
| Click        | CLI framework                           |
| Rich         | Terminal styling                        |
| Cognee       | Knowledge graph + LLM                   |
| pytest       | Testing                                 |
| ruff         | Linting and formatting                  |
| ty           | Type Checking                           |

## License

MIT License — see [LICENSE](LICENSE) for details.
