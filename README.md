<div align="center">

<img src="assets/logo.png" alt="Sentinel Logo" width="180" />

# Sentinel

**Personal Energy Guardian**

[![CI](https://github.com/armelhbobdad/sentinel/actions/workflows/ci.yml/badge.svg)](https://github.com/armelhbobdad/sentinel/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![uv](https://img.shields.io/badge/uv-package%20manager-blueviolet)](https://docs.astral.sh/uv/)
[![Cognee](https://img.shields.io/badge/powered%20by-Cognee-orange)](https://github.com/topoteretes/cognee)

*A CLI tool for detecting schedule conflicts that calendars miss.*

</div>

> **Challenge Project** — This is a submission for the [Cognee Mini Challenge 2026 - January Edition](https://discord.com/channels/1120795297094832337/1317073613446185074/1461737840538025984). Primarily developed and tested on **Debian GNU/Linux 13 (trixie)** with **Python 3.11**. If you encounter any bugs, please [open an issue](https://github.com/armelhbobdad/sentinel/issues).

---

Sentinel uses knowledge graphs to find hidden energy collisions in your schedule. Unlike traditional calendar apps that only check for time conflicts, Sentinel understands how activities affect your energy levels and detects problems like an emotionally draining Sunday dinner cascading into poor performance at Monday's high-stakes presentation.

## Articles

Learn more about the project and the technical challenges solved:

| Article | Platform | Description |
|---------|----------|-------------|
| [Why Your Calendar App Misses the Real Conflicts](https://medium.com/@armelhbobdad/why-your-calendar-app-misses-the-real-conflicts-39f980bb1791) | Medium | The "why" behind energy conflicts |
| [Taming LLM Output Chaos: A 3-Tier Normalization Pattern](https://dev.to/armelhbobdad/taming-llm-output-chaos-a-3-tier-normalisation-pattern-41jm) | dev.to | How Sentinel handles LLM variability |
| [Building a CLI Tool with Cognee: Lessons from 5 Epics](https://dev.to/armelhbobdad/building-a-cli-tool-with-cognee-lessons-from-5-epics-8mi) | dev.to | 9 hard-won lessons integrating with Cognee |

## Features

- **Schedule Ingestion**: Parse natural language schedule descriptions into a knowledge graph
- **Collision Detection**: Find multi-hop energy conflicts through graph traversal
- **Graph Exploration**: Explore relationships around any node with HTML export
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

## Quick Start: The Golden Path

This walkthrough demonstrates Sentinel's core flow: **paste → check → graph**.

### Step 1: Create a Test Schedule

Create a file called `schedule.txt` with a schedule containing an energy conflict:

```
Monday: Strategy presentation with the exec team, need to be sharp
Sunday: Dinner with Aunt Susan - always emotionally draining
Tuesday: HIIT workout at 6am
Wednesday: One-on-one with Steve about project delays
```

### Step 2: Ingest the Schedule (paste)

```bash
uv run sentinel paste < schedule.txt
```

**Expected Output:**

```
Schedule received. Processing...
Received 189 characters.
✓ Extracted 7 entities
Found 6 relationships.
✓ Graph saved to /home/user/.local/share/sentinel/graph.db

Knowledge Graph:
                          [Aunt Susan]
                               │
                             DRAINS
                               ↓
                           (drained)
                               │
                         CONFLICTS_WITH
                               ↓
[Strategy Presentation]──REQUIRES──▶(focused)

Legend: [name] = user-stated, (name) = AI-inferred
```

### Step 3: Detect Collisions (check)

```bash
uv run sentinel check
```

**Expected Output:**

```
⚠️  COLLISION DETECTED                    Confidence: 85%
╭──────────────────────────────────────────────────────────────────────╮
│                                                                      │
│  [SOCIAL] Aunt Susan                                                 │
│      │                                                               │
│      ├──DRAINS──▶ drained                                            │
│      │                                                               │
│      └──CONFLICTS_WITH──▶ focused                                    │
│                              │                                       │
│                              └──REQUIRES── [PROFESSIONAL] Strategy   │
│                                            Presentation              │
│                                                                      │
╰──────────────────────────────────────────────────────────────────────╯

Knowledge Graph:
(collision paths highlighted with >>)

  >> [Aunt Susan]
  >>      │
  >>    DRAINS
  >>      ↓
  >> (drained)
  >>      │
  >> CONFLICTS_WITH
  >>      ↓
  >> (focused) ◀──REQUIRES── [Strategy Presentation]

Found 1 collision affecting your schedule.
```

**Exit code:** `1` (collision detected)

### Step 4: Export Collision Report (check --format html)

Generate an HTML report with collision paths highlighted:

```bash
uv run sentinel check --format html --output collision-report.html
```

**Expected Output:**

```
✓ Report saved to collision-report.html
```

Open `collision-report.html` in your browser to see:
- Collision paths highlighted in red
- Warning cards showing each collision with confidence scores
- Node styling distinguishing user-stated vs AI-inferred
- Relationship labels on edges

**Note:** Use `sentinel check -f html` for collision highlighting. The `sentinel graph -f html` command exports the graph without collision analysis.

### HTML Visualization Examples

Sentinel generates self-contained HTML files with interactive SVG visualizations.

#### Collision Report (`sentinel check -f html`)

Shows collision paths highlighted in red with warning cards:

<!-- TODO: Add screenshot of collision report -->
![Collision Report](assets/screenshots/check-collision.png)

#### Graph After Ingestion (`sentinel paste -f html`)

Displays the full knowledge graph with node types color-coded:

<!-- TODO: Add screenshot of paste output -->
![Graph Visualization](assets/screenshots/paste-output.png)

**Legend:**
- 🟢 **Green nodes**: User-stated facts (from your schedule text)
- ⚪ **Gray nodes**: AI-inferred entities (energy states, time slots)
- 🔴 **Red highlight**: Collision path

> **Try it yourself:** Open the demo files in `assets/html-demos/` to explore the visualizations interactively.

### Complete Flow (One-Liner)

```bash
# Ingest, check, and export collision report
uv run sentinel paste < schedule.txt && \
uv run sentinel check -f html -o report.html
```

## Command Reference

### Basic Commands

```bash
# Show help
uv run sentinel --help

# Show version
uv run sentinel --version
```

### paste - Analyze Your Schedule

Ingest schedule text and build a knowledge graph:

```bash
# Interactive mode: type/paste text, then press Ctrl+D (EOF) to submit
uv run sentinel paste

# Pipe from a file
cat schedule.txt | uv run sentinel paste

# Redirect from file
uv run sentinel paste < schedule.txt

# Export directly to HTML instead of terminal
uv run sentinel paste --format html --output my-graph.html
```

### check - Detect Collisions

Analyze the graph for energy conflicts:

```bash
# Run collision detection
uv run sentinel check

# Show low-confidence speculative collisions too
uv run sentinel check --verbose

# Include previously acknowledged collisions
uv run sentinel check --show-acked

# Export check results as HTML
uv run sentinel check --format html --output collision-report.html
```

**Exit Codes:**
- `0` - No collisions detected
- `1` - Collisions detected
- `2` - Error (graph not found, processing failure)

### graph - Explore the Knowledge Graph

Visualize the full graph or explore around a specific node:

```bash
# Show full graph in terminal
uv run sentinel graph

# Explore neighborhood around a node (fuzzy matching)
uv run sentinel graph "Aunt Susan"

# Control exploration depth (1-5 hops)
uv run sentinel graph "Aunt Susan" --depth 3

# Export as HTML
uv run sentinel graph --format html --output visualization.html

# Explore specific node and export
uv run sentinel graph "presentation" -f html -o presentation-context.html
```

### correct - Fix AI Inferences

Correct mistakes in AI-inferred relationships:

```bash
# Delete an AI-inferred node
uv run sentinel correct delete "drained"

# Skip confirmation prompt
uv run sentinel correct delete "drained" --yes

# Modify a relationship type
uv run sentinel correct modify "Aunt Susan" --target "drained" --relationship ENERGIZES

# Remove a specific edge
uv run sentinel correct remove-edge "Aunt Susan" --target "drained"

# List all corrections
uv run sentinel correct list
```

**Notes:**
- Only AI-inferred nodes can be deleted (user-stated facts are protected)
- Fuzzy matching handles variations: "aunt-susan", "Aunt Susan", "aunt susan"
- Corrections persist to `~/.local/share/sentinel/corrections.json`

### ack - Acknowledge Unavoidable Collisions

Mark collisions as acknowledged to suppress warnings:

```bash
# Acknowledge a collision
uv run sentinel ack "sunday-dinner"

# List all acknowledgments
uv run sentinel ack --list

# Remove an acknowledgment
uv run sentinel ack "sunday-dinner" --remove
```

Acknowledged collisions are hidden by default. Use `sentinel check --show-acked` to display them with an `[ACKED]` label.

### config - Manage Settings

View or modify Sentinel configuration:

```bash
# Show all current settings
uv run sentinel config

# View a specific setting
uv run sentinel config energy_threshold

# Change collision sensitivity (low, medium, high)
uv run sentinel config energy_threshold high

# Configure for local Ollama (no API keys needed)
uv run sentinel config llm_provider ollama
uv run sentinel config llm_model llama3.1:8b
uv run sentinel config embedding_provider ollama

# Reset all settings to defaults
uv run sentinel config --reset
```

**Available Settings:**

| Key | Values                                | Description |
|-----|---------------------------------------|-------------|
| `energy_threshold` | low, medium, high                     | Collision detection sensitivity |
| `llm_provider` | openai, anthropic, ollama             | LLM provider for Cognee |
| `llm_model` | e.g., `openai/gpt-5-mini`             | Model identifier |
| `llm_endpoint` | URL                                   | Custom endpoint (required for ollama) |
| `embedding_provider` | openai, ollama                        | Embedding provider |
| `embedding_model` | e.g., `openai/text-embedding-3-large` | Embedding model |
| `default_format` | text, html                            | Default output format |
| `telemetry_enabled` | true, false                           | Cognee telemetry (default: false) |

Configuration is stored at `~/.config/sentinel/config.toml`.

### Debug Mode

For troubleshooting or seeing Cognee operations:

```bash
# Enable verbose logging
uv run sentinel --debug paste < schedule.txt

# Short form
uv run sentinel -d check
```

## Development

### Running Tests

```bash
# Run all tests (excludes live API tests by default)
uv run pytest tests/ -v

# Run fast unit tests only
uv run pytest tests/unit/ -v

# Run integration tests (MockEngine, fixtures)
uv run pytest tests/integration/ -v

# Run the golden demo path test specifically
uv run pytest tests/integration/test_golden_demo_path.py -v

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
│           ├── ascii.py        # ASCII graph visualization (phart)
│           └── html.py         # HTML/SVG graph export
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
- **Viz Module**: ASCII and HTML graph visualization. Imports only types from core.
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
