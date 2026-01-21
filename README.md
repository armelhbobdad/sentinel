# Sentinel

**Personal Energy Guardian** - A CLI tool for detecting schedule conflicts that calendars miss.

Sentinel uses knowledge graphs to find hidden energy collisions in your schedule. Unlike traditional calendar apps that only check for time conflicts, Sentinel understands how activities affect your energy levels and detects problems like an emotionally draining Sunday dinner cascading into poor performance at Monday's high-stakes presentation.

## Features

- **Schedule Ingestion**: Parse natural language schedule descriptions into a knowledge graph
- **Collision Detection**: Find multi-hop energy conflicts through graph traversal
- **Graph Exploration**: Explore relationships around any node
- **User Corrections**: Delete nodes, modify relationships, or remove edges from AI inferences
- **Warning Acknowledgment**: Mark unavoidable collisions as acknowledged to suppress repeated warnings
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

### Basic Commands

```bash
# Show help
uv run sentinel --help

# Show version
uv run sentinel --version
```

### Analyzing Your Schedule (paste)

Use the `paste` command to analyze schedule text and build a knowledge graph:

```bash
# Interactive mode: type/paste text, then press Ctrl+D (EOF) to submit
uv run sentinel paste

# Pipe from a file
cat schedule.txt | uv run sentinel paste

# Redirect from file
uv run sentinel paste < schedule.txt

# Pipe inline text
echo "Saturday: Football with Jean at 8am. Monday: Presentation at 6pm." | uv run sentinel paste
```

**Example Output:**

```
Schedule received. Processing...
Received 65 characters.
✓ Extracted 5 entities
Found 2 relationships.
✓ Graph saved to /home/user/.local/share/sentinel/graph.db

Knowledge Graph:
[football]
     ↓
[saturday]

[presentation]
       ↓
   [monday]

Relationships:
  [football] --SCHEDULED_AT--> [saturday]
  [presentation] --SCHEDULED_AT--> [monday]

Legend: [name] = user-stated, (name) = AI-inferred
```

### Detecting Collisions (check)

Use the `check` command to detect energy collisions in your schedule:

```bash
# Run collision detection
uv run sentinel check

# Show low-confidence collisions too
uv run sentinel check --verbose

# Filter by minimum confidence (0.0-1.0)
uv run sentinel check --min-confidence 0.7
```

**Example Output:**

```
Detecting collisions...
Analyzing 12 relationships...

⚠️  COLLISION DETECTED (confidence: 0.85)

[Dinner with Aunt Susan] → [drained] → [low_focus] → [Monday Presentation]

Your Sunday dinner historically precedes energy dips.
Monday's presentation requires high cognitive load.
Risk: Entering high-stakes meeting already depleted.

─────────────────────────────────────────────────
✗ 1 collision detected
```

**Exit Codes:**
- `0` - Success, no collisions detected
- `1` - Success, collisions detected (warnings present)
- `2` - Error (graph not found, processing failure)

### Managing Acknowledged Warnings

Use `--show-acked` to include previously acknowledged collisions in the output:

```bash
# Show all collisions including acknowledged ones
uv run sentinel check --show-acked
```

Acknowledged collisions display with an `[ACKED]` label.

### Correcting AI Inferences (correct)

Sentinel's AI may sometimes infer incorrect relationships. Use the `correct` command to fix them:

```bash
# Delete an AI-inferred node (removes node and all connected edges)
uv run sentinel correct delete "drained"

# Skip confirmation prompt
uv run sentinel correct delete "drained" --yes

# Modify a relationship type between nodes
uv run sentinel correct modify "Aunt Susan" --target "drained" --relationship ENERGIZES

# Remove a specific edge while keeping both nodes
uv run sentinel correct remove-edge "Aunt Susan" --target "drained"

# List all corrections made
uv run sentinel correct list
```

**Example Output (delete):**

```
Found node: drained (score: 100)

This will delete the AI-inferred node 'drained' and remove 2 connected edge(s).
Connected edges:
  • Aunt Susan --DRAINS--> drained
  • drained --CONFLICTS_WITH--> focused

Proceed? [y/N]: y
✓ Deleted node 'drained' and 2 connected edge(s)
```

**Notes:**
- Only AI-inferred nodes can be deleted (user-stated facts are protected)
- Fuzzy matching handles variations: "aunt-susan", "Aunt Susan", "aunt susan"
- Corrections persist to `~/.local/share/sentinel/corrections.json`

### Acknowledging Collisions (ack)

Some collisions are unavoidable. Acknowledge them to stop repeated warnings:

```bash
# Acknowledge a collision involving a node
uv run sentinel ack "sunday-dinner"

# List all acknowledged collisions
uv run sentinel ack --list

# Remove an acknowledgment (warnings will reappear)
uv run sentinel ack "sunday-dinner" --remove
```

**Example Output:**

```
✓ Acknowledged collision: sunday-dinner
  Collision will be hidden in future checks.
  Use 'sentinel check --show-acked' to see all collisions.
```

**Notes:**
- Acknowledgments persist to `~/.local/share/sentinel/acks.json`
- Fuzzy matching works for node names
- Use `sentinel check --show-acked` to see hidden collisions

### Debug Mode

For troubleshooting or seeing what Cognee does behind the scenes:

```bash
# Enable verbose logging
uv run sentinel --debug paste < schedule.txt

# Short form
uv run sentinel -d paste < schedule.txt
```

Debug mode shows Cognee's internal pipeline progress, entity extraction details, and graph database operations.

## Development

### Running Tests

```bash
# Run all tests (excludes live API tests by default)
uv run pytest tests/ -v

# Run fast unit tests only
uv run pytest tests/unit/ -v

# Run integration tests (MockEngine, fixtures)
uv run pytest tests/integration/ -v

# Run live API tests (requires API keys in .env)
uv run pytest tests/live/ -v -m live

# Run everything including live tests
uv run pytest tests/ -v -m ""
```

**Test Categories:**

| Category | Location | Requires API Key | Description |
|----------|----------|------------------|-------------|
| Unit | `tests/unit/` | No | Fast, isolated function tests |
| Integration | `tests/integration/` | No | MockEngine with fixtures |
| Live | `tests/live/` | Yes | Real Cognee API validation |

**Live Tests** verify that the system works correctly with the actual Cognee API, catching issues that mocked tests might miss (like LLM output variability).

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
│       │   ├── constants.py    # Exit codes, thresholds, fuzzy matching config
│       │   ├── types.py        # Graph, Node, Edge, ScoredCollision
│       │   ├── engine.py       # GraphEngine protocol + CogneeEngine + 3-tier mapping
│       │   ├── rules.py        # Collision detection logic (BFS traversal)
│       │   ├── consolidation.py # Semantic node consolidation (RapidFuzz)
│       │   ├── persistence.py  # Graph persistence (JSON-based)
│       │   └── exceptions.py   # Custom exception classes
│       ├── cli/
│       │   └── commands.py     # Click CLI commands
│       └── viz/
│           ├── __init__.py     # Module exports
│           └── ascii.py        # ASCII graph visualization (phart)
├── tests/
│   ├── conftest.py             # MockEngine and shared fixtures
│   ├── fixtures/
│   │   └── schedules/          # Test schedule files
│   ├── unit/                   # Fast unit tests
│   ├── integration/            # MockEngine and fixture tests
│   └── live/                   # Live API tests (requires API keys)
├── pyproject.toml              # Project configuration
├── lefthook.yml                # Pre-commit hook configuration
└── README.md
```

## Architecture

Sentinel follows a modular architecture:

- **Core Module**: Contains types, constants, persistence, collision detection, and the GraphEngine protocol. Never imports from CLI or visualization modules.
  - `engine.py` - GraphEngine protocol with 3-tier relation type mapping
  - `rules.py` - BFS-based collision detection logic
  - `consolidation.py` - Semantic node merging using RapidFuzz
- **CLI Module**: Click-based command-line interface with Rich terminal styling
- **Viz Module**: ASCII graph visualization using phart library. Imports only types from core.
- **GraphEngine Protocol**: Async interface for graph operations, enabling both mock and real implementations

```
core/  ←── viz/ (types only)
  ↑         ↑
  └── cli/ ─┘
```

### LLM Integration

Sentinel handles LLM output variability through a 3-layer approach:

1. **Custom Extraction Prompt**: Guides Cognee to produce energy-domain relationships
2. **3-Tier Relation Mapping**: Exact → Keyword → Fuzzy matching (RapidFuzz)
3. **Semantic Node Consolidation**: Merges equivalent nodes like "drained"/"exhausted"

## Technology Stack

| Tech         | Purpose                                 |
|--------------|-----------------------------------------|
| Python 3.11+ | Runtime (required for stdlib `tomllib`) |
| uv           | Package management                      |
| Click        | CLI framework                           |
| Rich         | Terminal styling                        |
| Cognee       | Knowledge graph + LLM entity extraction |
| RapidFuzz    | Fuzzy string matching for LLM output normalization |
| phart        | ASCII graph visualization               |
| NetworkX     | Graph data structure (phart dependency) |
| pytest       | Testing                                 |
| ruff         | Linting and formatting                  |
| ty           | Type Checking                           |

## License

MIT License — see [LICENSE](LICENSE) for details.
