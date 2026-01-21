"""GraphEngine protocol and implementations.

Defines the interface for knowledge graph operations and provides
implementations including Cognee-based extraction.
"""

import json
import logging
import re
import unicodedata
from datetime import UTC, datetime
from typing import Any, Protocol

import cognee
from cognee.api.v1.search import SearchType

from sentinel.core.exceptions import IngestionError, PersistenceError
from sentinel.core.persistence import ensure_data_directory, get_graph_db_path
from sentinel.core.types import (
    Correction,
    Edge,
    Graph,
    Node,
    NodeSource,
    ScoredCollision,
)

# RapidFuzz import with graceful degradation
try:
    from rapidfuzz import fuzz, process

    RAPIDFUZZ_AVAILABLE = True
except ImportError:
    RAPIDFUZZ_AVAILABLE = False
    fuzz = None  # type: ignore[assignment]
    process = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

# Valid edge types allowed in Sentinel graphs (AC #5)
VALID_EDGE_TYPES: set[str] = {
    "DRAINS",
    "REQUIRES",
    "CONFLICTS_WITH",
    "SCHEDULED_AT",
    "INVOLVES",
    "BELONGS_TO",
}

# Mapping from Cognee entity types to Sentinel node types
ENTITY_TYPE_MAP: dict[str, str] = {
    # Person types
    "PERSON": "Person",
    "ORGANIZATION": "Person",
    "ORG": "Person",
    # Activity types
    "EVENT": "Activity",
    "ACTIVITY": "Activity",
    "TASK": "Activity",
    "ACTION": "Activity",
    # Time types
    "TIME": "TimeSlot",
    "DATE": "TimeSlot",
    "DATETIME": "TimeSlot",
    "TEMPORAL": "TimeSlot",
    # Energy/emotion types
    "EMOTION": "EnergyState",
    "STATE": "EnergyState",
    "ENERGY": "EnergyState",
    "FEELING": "EnergyState",
    # Domain/context types
    "LOCATION": "Domain",
    "CONTEXT": "Domain",
    "PLACE": "Domain",
    "CATEGORY": "Domain",
}

# Mapping from Cognee relation types to Sentinel edge types
RELATION_TYPE_MAP: dict[str, str] = {
    # INVOLVES mappings
    "involves": "INVOLVES",
    "participant": "INVOLVES",
    "with": "INVOLVES",
    "has_participant": "INVOLVES",
    "includes": "INVOLVES",
    "contains": "INVOLVES",  # Cognee uses 'contains' for entity relationships
    "has": "INVOLVES",
    "attended_by": "INVOLVES",
    "organized_by": "INVOLVES",
    # SCHEDULED_AT mappings
    "scheduled_at": "SCHEDULED_AT",
    "at_time": "SCHEDULED_AT",
    "when": "SCHEDULED_AT",
    "occurs_at": "SCHEDULED_AT",
    "on_date": "SCHEDULED_AT",
    "scheduled_on": "SCHEDULED_AT",
    "takes_place": "SCHEDULED_AT",
    "happens_on": "SCHEDULED_AT",
    "at": "SCHEDULED_AT",
    "on": "SCHEDULED_AT",
    # BUG-002: Additional SCHEDULED_AT mappings (AC #3)
    "occurs_on": "SCHEDULED_AT",
    "happens_at": "SCHEDULED_AT",
    # DRAINS mappings
    "drains": "DRAINS",
    "depletes": "DRAINS",
    "exhausts": "DRAINS",
    "tires": "DRAINS",
    "fatigues": "DRAINS",
    "causes_fatigue": "DRAINS",
    "energy_drain": "DRAINS",
    # BUG-001: Cognee LLM-generated DRAINS variants
    "drains_energy": "DRAINS",
    "is_emotionally_draining": "DRAINS",
    "emotionally_draining": "DRAINS",
    "causes_exhaustion": "DRAINS",
    "energy_draining": "DRAINS",
    # BUG-002: Additional DRAINS mappings for causal relations (AC #1, #2)
    # Note: "causes" is semantically broad but maps to DRAINS in Sentinel's
    # energy-focused domain when target involves energy/exhaustion concepts.
    "causes": "DRAINS",
    "negatively_impacts": "DRAINS",
    "negatively_affects": "DRAINS",
    "leads_to_exhaustion": "DRAINS",
    "results_in_fatigue": "DRAINS",
    "impacts_energy": "DRAINS",
    # REQUIRES mappings
    "requires": "REQUIRES",
    "needs": "REQUIRES",
    "demands": "REQUIRES",
    "depends_on": "REQUIRES",
    "prerequisite": "REQUIRES",
    # BUG-001: Cognee LLM-generated REQUIRES variants
    "requires_high_focus": "REQUIRES",
    "needs_to_be_well_rested_for": "REQUIRES",
    "requires_focus": "REQUIRES",
    "needs_energy": "REQUIRES",
    "requires_energy": "REQUIRES",
    # CONFLICTS_WITH mappings
    "conflicts": "CONFLICTS_WITH",
    "conflicts_with": "CONFLICTS_WITH",
    "contradicts": "CONFLICTS_WITH",
    "opposes": "CONFLICTS_WITH",
    "clashes": "CONFLICTS_WITH",
    "overlaps": "CONFLICTS_WITH",
    # BELONGS_TO mappings
    "belongs_to": "BELONGS_TO",
    "category": "BELONGS_TO",
    "domain": "BELONGS_TO",
    "part_of": "BELONGS_TO",
    "is_a": "BELONGS_TO",
    "type_of": "BELONGS_TO",
    "instance_of": "BELONGS_TO",
    # Additional Cognee relation types (discovered from live testing)
    "has_note": "INVOLVES",  # Event has a note about context/feelings
    "about": "INVOLVES",  # Relation is about a topic
    "involves_person": "INVOLVES",  # Event involves a person
    # BUG-001: Cognee LLM-generated INVOLVES variants
    "attends": "INVOLVES",
    "presented_to": "INVOLVES",
    # BUG-002: Additional INVOLVES mappings (AC #4)
    "has_characteristic": "INVOLVES",
    "characterized_by": "INVOLVES",
}

# Semantic keywords for Tier 2 keyword matching (Story 2-6)
# Uses word stems to match variations (e.g., "deplet" matches "depletes", "depleted", "depletion")
SEMANTIC_KEYWORDS: dict[str, list[str]] = {
    "DRAINS": [
        "drain",
        "exhaust",
        "deplet",
        "fatigue",
        "tire",
        "sap",
        "wear",
        "stress",
        "burden",
        "overwhelm",
        "tax",
    ],
    "REQUIRES": [
        "require",
        "need",
        "demand",
        "depend",
        "necessitat",
        "essential",
        "must",
        "prerequisite",
    ],
    "CONFLICTS_WITH": [
        "conflict",
        "clash",
        "contradict",
        "interfer",
        "oppos",
        "threaten",
        "impair",
        "hinder",
        "block",
        "prevent",
        "incompatible",
    ],
    "SCHEDULED_AT": [
        "schedul",
        "occur",
        "happen",
        "preced",
        "follow",
        "before",
        "after",
        "during",
        "time",
    ],
    "INVOLVES": [
        "involve",
        "include",
        "contain",
        "feature",
        "characteriz",
        "present",
        "has",
        "with",
        "about",
        "relat",
        "associat",
        "contribut",
        "affect",
        "impact",
    ],
}


# Fuzzy candidate phrases for Tier 3 RapidFuzz matching (Story 2-6)
# Curated natural language phrases for semantic similarity scoring
FUZZY_CANDIDATES: dict[str, list[str]] = {
    "DRAINS": [
        "drains",
        "drains energy",
        "emotionally draining",
        "causes drain",
        "energy drain",
        "depletes",
        "exhausts",
        "tires out",
        "fatigues",
        "wears out",
        "stresses",
        "causes exhaustion",
        "leads to fatigue",
        "reduces energy",
        "saps energy",
    ],
    "REQUIRES": [
        "requires",
        "needs",
        "demands",
        "depends on",
        "necessitates",
        "needed by",
        "required by",
        "prerequisite for",
        "essential for",
        "must have",
    ],
    "CONFLICTS_WITH": [
        "conflicts with",
        "clashes with",
        "contradicts",
        "interferes with",
        "opposes",
        "threatens",
        "impairs",
        "hinders",
        "blocks",
        "prevents",
        "incompatible with",
        "at odds with",
        "undermines",
        "negatively impacts",
    ],
    "SCHEDULED_AT": [
        "scheduled at",
        "occurs on",
        "happens at",
        "takes place",
        "precedes",
        "follows",
        "before",
        "after",
        "during",
        "at time",
        "on date",
    ],
    "INVOLVES": [
        "involves",
        "includes",
        "contains",
        "features",
        "characterized by",
        "presented by",
        "has characteristic",
        "relates to",
        "associated with",
        "contributes to",
        "affects",
        "impacts",
        "connected to",
        "linked to",
        "part of",
    ],
}

# Default fuzzy matching threshold (0-100)
DEFAULT_FUZZY_THRESHOLD: int = 50

# Custom extraction prompt for energy-domain knowledge graphs (Story 2-7)
# Guides Cognee's LLM to create correct graph topology for collision detection.
# Token count: ~1100 tokens (well under 2000 token limit for optimal performance)
SENTINEL_EXTRACTION_PROMPT: str = """\
You are extracting a PERSONAL ENERGY knowledge graph for schedule conflict detection.

**DOMAIN**: Personal scheduling, energy management, activity conflicts.

**CRITICAL RULE**: When an activity DRAINS energy AND another activity REQUIRES
that same energy type, you MUST create a CONFLICTS_WITH edge between them.
This is the core pattern we need to detect.

**REQUIRED RELATIONSHIP TYPES** (use ONLY these exact names):
- DRAINS: Activity depletes energy/focus/motivation
  (e.g., "exhausting dinner" DRAINS "emotional_energy")
- REQUIRES: Activity needs energy/focus/resources
  (e.g., "presentation" REQUIRES "mental_focus")
- CONFLICTS_WITH: Connect energy states to activities that need them
  (e.g., "low_energy" CONFLICTS_WITH "important_meeting")
- SCHEDULED_AT: Activity occurs at time
  (e.g., "dinner" SCHEDULED_AT "sunday_evening")
- INVOLVES: Activity includes person/thing
  (e.g., "dinner" INVOLVES "aunt_susan")

**COLLISION PATTERN** (you MUST create this when applicable):
[draining_activity] --DRAINS--> (energy_state) --CONFLICTS_WITH-->
[requiring_activity] --REQUIRES--> (resource)

**EXAMPLE 1** (Conflict scenario):
Input: "Sunday: Emotionally draining dinner with complainers.
Monday: Strategy presentation needs sharp focus."
Expected Graph:
- [dinner] --DRAINS--> (emotional_energy)
- (emotional_energy) --CONFLICTS_WITH--> [strategy_presentation]
- [strategy_presentation] --REQUIRES--> (sharp_focus)
- [dinner] --SCHEDULED_AT--> [sunday]
- [strategy_presentation] --SCHEDULED_AT--> [monday]

**EXAMPLE 2** (Conflict scenario):
Input: "Morning HIIT workout will exhaust me.
Afternoon client meeting requires alertness."
Expected Graph:
- [hiit_workout] --DRAINS--> (physical_energy)
- (physical_energy) --CONFLICTS_WITH--> [client_meeting]
- [client_meeting] --REQUIRES--> (alertness)
- [hiit_workout] --SCHEDULED_AT--> [morning]
- [client_meeting] --SCHEDULED_AT--> [afternoon]

**EXAMPLE 3** (No conflict):
Input: "Monday standup meeting. Tuesday documentation work."
Expected Graph:
- [standup_meeting] --SCHEDULED_AT--> [monday]
- [documentation_work] --SCHEDULED_AT--> [tuesday]
(No DRAINS or CONFLICTS_WITH edges because neither activity drains energy)

**INSTRUCTIONS**:
1. Identify activities that DRAIN energy
   (look for: draining, exhausting, tiring, stressful, overwhelming)
2. Identify activities that REQUIRE energy
   (look for: requires, needs, demands, important, critical)
3. Create (energy_state) nodes as intermediaries
4. ALWAYS connect draining activities to requiring activities via CONFLICTS_WITH
   when they could impact each other
5. Use snake_case for node IDs (e.g., "strategy_presentation" not "Strategy Presentation")

Now extract the knowledge graph from the following text:
"""


def _fuzzy_match_relation(
    relation_type: str, threshold: int = DEFAULT_FUZZY_THRESHOLD
) -> str | None:
    """Match relation type using RapidFuzz fuzzy matching (Tier 3).

    Compares the relation type against curated candidate phrases using
    RapidFuzz's WRatio scorer for semantic similarity.

    Args:
        relation_type: The Cognee relation type string.
        threshold: Minimum similarity score (0-100) to accept a match.

    Returns:
        Canonical edge type if fuzzy match found above threshold, None otherwise.
    """
    if not RAPIDFUZZ_AVAILABLE:
        logger.warning("RapidFuzz not available - fuzzy matching disabled")
        return None

    # Normalize: lowercase and replace underscores with spaces
    normalized = relation_type.lower().replace("_", " ")

    best_match: str | None = None
    best_score: float = 0.0

    for canonical_type, candidates in FUZZY_CANDIDATES.items():
        # Use process.extractOne to find best match among candidates
        result = process.extractOne(normalized, candidates, scorer=fuzz.WRatio)
        if result is not None:
            match_str, score, _ = result
            if score > best_score and score >= threshold:
                best_score = score
                best_match = canonical_type

    if best_match is not None:
        logger.debug(
            "Fuzzy matched '%s' to %s (score: %.1f%%)",
            relation_type,
            best_match,
            best_score,
        )

    return best_match


def _keyword_match_relation(relation_type: str) -> str | None:
    """Match relation type using semantic keywords (Tier 2).

    Checks if the relation type contains any semantic keywords that indicate
    a known canonical type. Uses word stems for flexibility.

    Args:
        relation_type: The Cognee relation type string.

    Returns:
        Canonical edge type if keyword match found, None otherwise.
    """
    normalized = relation_type.lower()

    for canonical_type, keywords in SEMANTIC_KEYWORDS.items():
        for keyword in keywords:
            if keyword in normalized:
                return canonical_type

    return None


# Default confidence when Cognee doesn't provide one
DEFAULT_CONFIDENCE: float = 0.8


class Subgraph(Graph):
    """A subgraph representing a neighborhood around a node."""

    pass


class GraphEngine(Protocol):
    """Protocol defining the interface for graph operations.

    Async methods are used for operations that may involve LLM calls
    or external services. Sync methods are for local operations.
    """

    async def ingest(self, text: str) -> Graph:
        """Ingest text and build a knowledge graph.

        Args:
            text: Schedule text to parse and convert to graph.

        Returns:
            Graph containing extracted entities and relationships.
        """
        ...

    async def query_collisions(self, graph: Graph) -> list[ScoredCollision]:
        """Query the graph for energy collisions.

        Args:
            graph: The graph to analyze for collisions.

        Returns:
            List of scored collisions found in the graph.
        """
        ...

    async def get_neighbors(self, node_id: str, depth: int = 2) -> Subgraph:
        """Get neighbors of a node up to specified depth.

        Args:
            node_id: ID of the node to explore from.
            depth: Maximum depth to traverse (default 2).

        Returns:
            Subgraph containing the node and its neighbors.
        """
        ...

    def mutate(self, graph: Graph, correction: Correction) -> Graph:
        """Apply a correction to the graph.

        Args:
            graph: The graph to mutate.
            correction: The correction to apply.

        Returns:
            New graph with the correction applied.
        """
        ...

    def persist(self, graph: Graph) -> None:
        """Persist the graph to storage.

        Args:
            graph: The graph to persist.
        """
        ...

    def load(self) -> Graph | None:
        """Load persisted graph from storage.

        Returns:
            Loaded graph, or None if no graph exists.
        """
        ...


def _determine_source(entity_label: str, text: str) -> NodeSource:
    """Determine if entity was user-stated or AI-inferred.

    User-stated: Exact text appears in original input (case-insensitive)
    AI-inferred: Derived by Cognee's reasoning

    Args:
        entity_label: The label of the entity.
        text: The original input text.

    Returns:
        "user-stated" if label appears in text, "ai-inferred" otherwise.
    """
    # Use word boundary matching to avoid partial matches
    # Escape special regex characters in label
    escaped_label = re.escape(entity_label)
    pattern = rf"\b{escaped_label}\b"
    if re.search(pattern, text, re.IGNORECASE):
        return "user-stated"
    return "ai-inferred"


def _slugify(text: str) -> str:
    """Convert text to a URL-friendly slug.

    Args:
        text: Text to slugify.

    Returns:
        Lowercase, hyphenated slug.
    """
    # Normalize unicode characters
    text = unicodedata.normalize("NFKD", text)
    # Convert to ASCII, ignoring non-ASCII characters
    text = text.encode("ascii", "ignore").decode("ascii")
    # Convert to lowercase
    text = text.lower()
    # Replace spaces and underscores with hyphens
    text = re.sub(r"[\s_]+", "-", text)
    # Remove any remaining non-alphanumeric characters (except hyphens)
    text = re.sub(r"[^a-z0-9-]", "", text)
    # Remove multiple consecutive hyphens
    text = re.sub(r"-+", "-", text)
    # Strip leading/trailing hyphens
    text = text.strip("-")
    return text


def _generate_node_id(node_type: str, label: str) -> str:
    """Generate a unique, deterministic node ID.

    Format: {type}-{slugified-label}

    Args:
        node_type: The node type (e.g., "Person").
        label: The node label.

    Returns:
        Deterministic node ID.
    """
    type_slug = node_type.lower()
    label_slug = _slugify(label)
    return f"{type_slug}-{label_slug}"


def _map_cognee_entity_to_node(cognee_entity: dict[str, Any], text: str) -> Node:
    """Map a Cognee entity to a Sentinel Node.

    Args:
        cognee_entity: Entity dict from Cognee with 'type' and 'label'.
        text: Original input text for source determination.

    Returns:
        Sentinel Node with appropriate type and source.
    """
    entity_type = cognee_entity.get("type", "").upper()
    label = cognee_entity.get("label", "")

    # Map entity type, default to Activity for unknown types
    node_type = ENTITY_TYPE_MAP.get(entity_type, "Activity")

    # Determine source based on text presence
    source = _determine_source(label, text)

    # Generate deterministic ID
    node_id = _generate_node_id(node_type, label)

    # Build metadata with original Cognee type
    metadata: dict[str, Any] = {}
    if entity_type:
        metadata["cognee_type"] = entity_type
    if cognee_entity.get("metadata"):
        metadata.update(cognee_entity["metadata"])

    return Node(
        id=node_id,
        label=label,
        type=node_type,
        source=source,
        metadata=metadata,
    )


def _map_cognee_relation_to_edge(
    cognee_relation: dict[str, Any],
) -> Edge | None:
    """Map a Cognee relation to a Sentinel Edge using 3-tier strategy.

    Tier 1: Exact match from RELATION_TYPE_MAP (O(1), no overhead)
    Tier 2: Semantic keyword matching (_keyword_match_relation)
    Tier 3: RapidFuzz fuzzy matching (_fuzzy_match_relation)

    Args:
        cognee_relation: Relation dict from Cognee with 'type', 'source_id',
            'target_id', and optional 'confidence'.

    Returns:
        Sentinel Edge if relation type is valid, None otherwise.
    """
    relation_type = cognee_relation.get("type", "").lower()
    source_id = cognee_relation.get("source_id", "")
    target_id = cognee_relation.get("target_id", "")
    confidence = cognee_relation.get("confidence", DEFAULT_CONFIDENCE)

    # Tier 1: Exact match from RELATION_TYPE_MAP (fastest, O(1))
    edge_type = RELATION_TYPE_MAP.get(relation_type)
    if edge_type is not None:
        logger.debug("Tier 1 exact match: '%s' → %s", relation_type, edge_type)
        return Edge(
            source_id=source_id,
            target_id=target_id,
            relationship=edge_type,
            confidence=confidence,
            metadata={"cognee_type": relation_type, "match_tier": "exact"},
        )

    # Tier 2: Semantic keyword matching
    edge_type = _keyword_match_relation(relation_type)
    if edge_type is not None:
        logger.debug("Tier 2 keyword match: '%s' → %s", relation_type, edge_type)
        return Edge(
            source_id=source_id,
            target_id=target_id,
            relationship=edge_type,
            confidence=confidence,
            metadata={"cognee_type": relation_type, "match_tier": "keyword"},
        )

    # Tier 3: RapidFuzz fuzzy matching
    edge_type = _fuzzy_match_relation(relation_type)
    if edge_type is not None:
        logger.debug("Tier 3 fuzzy match: '%s' → %s", relation_type, edge_type)
        return Edge(
            source_id=source_id,
            target_id=target_id,
            relationship=edge_type,
            confidence=confidence,
            metadata={"cognee_type": relation_type, "match_tier": "fuzzy"},
        )

    # No match found in any tier
    logger.warning(
        "Unknown relation type '%s', filtering out (no match in any tier)",
        relation_type,
    )
    return None


def _filter_valid_edges(edges: list[Edge]) -> list[Edge]:
    """Filter edges to only include valid relationship types.

    Args:
        edges: List of edges to filter.

    Returns:
        List containing only edges with valid relationship types.
    """
    valid = []
    for edge in edges:
        if edge.relationship in VALID_EDGE_TYPES:
            valid.append(edge)
        else:
            logger.warning("Filtering out edge with invalid type '%s'", edge.relationship)
    return valid


class CogneeEngine:
    """Cognee-based implementation of GraphEngine.

    Uses Cognee's knowledge graph capabilities to extract entities
    and relationships from schedule text.
    """

    async def ingest(self, text: str, custom_prompt: str | None = None) -> Graph:
        """Ingest text and build a knowledge graph using Cognee.

        Calls Cognee's API to extract entities and relationships,
        then transforms them into Sentinel's Graph format.

        Args:
            text: Schedule text to parse and convert to graph.
            custom_prompt: Optional custom prompt for Cognee extraction.
                Defaults to SENTINEL_EXTRACTION_PROMPT for energy-domain graphs.
                Pass None to use Cognee's default extraction prompt.

        Returns:
            Graph containing extracted entities and relationships.

        Raises:
            IngestionError: If Cognee API call fails.
        """
        # Use Sentinel's custom prompt by default for energy-domain extraction
        prompt_to_use = custom_prompt if custom_prompt is not None else SENTINEL_EXTRACTION_PROMPT

        try:
            # Reset any previous state
            await cognee.prune.prune_data()
            await cognee.prune.prune_system(metadata=True)

            # Add text to Cognee
            await cognee.add(text)

            # Process with cognify using custom extraction prompt (Story 2-7)
            logger.debug(
                "Using custom extraction prompt for cognify (length: %d chars)",
                len(prompt_to_use),
            )
            await cognee.cognify(custom_prompt=prompt_to_use)

            # Query the graph for entities and relationships using Cypher
            # Get all nodes
            node_results = await cognee.search(
                query_text="MATCH (n) RETURN n",
                query_type=SearchType.CYPHER,
            )

            # Get all edges
            edge_results = await cognee.search(
                query_text="MATCH (a)-[r]->(b) RETURN a, r, b",
                query_type=SearchType.CYPHER,
            )

            # Transform Cognee results to Sentinel types
            return self._transform_cypher_results(node_results, edge_results, text)

        except IngestionError:
            raise
        except Exception as e:
            logger.exception("Cognee API call failed")
            raise IngestionError(f"Failed to process schedule: {e}") from e

    def _transform_cypher_results(self, node_results: Any, edge_results: Any, text: str) -> Graph:
        """Transform Cognee Cypher results into a Sentinel Graph.

        Args:
            node_results: Raw node results from Cypher query.
            edge_results: Raw edge results from Cypher query.
            text: Original input text for source determination.

        Returns:
            Graph with mapped nodes and edges.
        """
        nodes: list[Node] = []
        edges: list[Edge] = []
        seen_node_ids: set[str] = set()
        node_id_map: dict[str, str] = {}  # Map Cognee IDs to Sentinel IDs

        # Extract entities from Cypher node results
        entities = self._extract_entities_from_cypher(node_results)

        # Process entities (only Entity type, not DocumentChunk/EntityType/etc.)
        for entity in entities:
            node = _map_cognee_entity_to_node(entity, text)
            if node.id not in seen_node_ids:
                nodes.append(node)
                seen_node_ids.add(node.id)
                # Map original Cognee ID to our generated ID
                cognee_id = entity.get("id", "")
                if cognee_id:
                    node_id_map[cognee_id] = node.id

        # Extract relations from Cypher edge results
        relations = self._extract_relations_from_cypher(edge_results, node_id_map)

        # Process relations
        for relation in relations:
            edge = _map_cognee_relation_to_edge(relation)
            if edge is not None:
                edges.append(edge)

        # Filter to only valid edge types
        valid_edges = _filter_valid_edges(edges)

        # Validate all edges reference existing nodes
        valid_edges = self._validate_edge_references(valid_edges, seen_node_ids)

        return Graph(nodes=tuple(nodes), edges=tuple(valid_edges))

    def _extract_entities_from_cypher(self, results: Any) -> list[dict[str, Any]]:
        """Extract Entity nodes from Cypher MATCH (n) RETURN n results.

        Filters for only 'Entity' type nodes, excluding DocumentChunk,
        EntityType, TextDocument, TextSummary, etc.

        Args:
            results: Raw Cypher results.

        Returns:
            List of entity dictionaries with 'id', 'label', 'type'.
        """
        entities: list[dict[str, Any]] = []

        if not results or not isinstance(results, list):
            return entities

        # Results format: [{'search_result': [[[node1], [node2], ...]], ...}]
        for result_item in results:
            if not isinstance(result_item, dict):
                continue

            search_result = result_item.get("search_result", [])
            if not search_result or not isinstance(search_result, list):
                continue

            # search_result[0] is a list of node wrappers
            node_list = search_result[0] if search_result else []

            for node_wrapper in node_list:
                # Each node_wrapper is a list with the node dict inside
                if isinstance(node_wrapper, list) and len(node_wrapper) > 0:
                    node = node_wrapper[0]
                elif isinstance(node_wrapper, dict):
                    node = node_wrapper
                else:
                    continue

                if not isinstance(node, dict):
                    continue

                node_type = node.get("type", "")

                # Only process Entity nodes (not DocumentChunk, EntityType, etc.)
                if node_type != "Entity":
                    continue

                # Parse properties if it's a JSON string
                properties = node.get("properties", {})
                if isinstance(properties, str):
                    try:
                        properties = json.loads(properties)
                    except (json.JSONDecodeError, TypeError):
                        properties = {}

                # Map to our expected format
                entity = {
                    "id": node.get("id", ""),
                    "label": node.get("name", ""),
                    "type": self._infer_entity_type(node),
                    "metadata": properties,
                }

                if entity["id"] and entity["label"]:
                    entities.append(entity)

        return entities

    def _infer_entity_type(self, node: dict[str, Any]) -> str:
        """Infer Sentinel entity type from Cognee node properties.

        Args:
            node: Cognee node dict.

        Returns:
            Sentinel entity type string.
        """
        name = node.get("name", "").lower()
        properties = node.get("properties", {})

        # Try to parse properties JSON for description
        description = ""
        if isinstance(properties, str):
            try:
                props = json.loads(properties)
                description = props.get("description", "").lower()
            except (json.JSONDecodeError, TypeError):
                pass
        elif isinstance(properties, dict):
            description = properties.get("description", "").lower()

        # Infer type from name and description
        # Days of week -> TimeSlot
        days = {"monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"}
        if name in days or "day of week" in description:
            return "DATE"

        # Times -> TimeSlot
        if any(t in name for t in ["am", "pm", ":"]) or "time" in description:
            return "TIME"

        # People detection
        person_keywords = ["person", "aunt", "uncle", "relative", "colleague", "friend"]
        if any(kw in name or kw in description for kw in person_keywords):
            return "PERSON"

        # Events/activities
        event_keywords = ["dinner", "meeting", "presentation", "workout", "session"]
        if any(kw in name or kw in description for kw in event_keywords):
            return "EVENT"

        # Default to Activity
        return "ACTIVITY"

    def _extract_relations_from_cypher(
        self, results: Any, node_id_map: dict[str, str]
    ) -> list[dict[str, Any]]:
        """Extract relations from Cypher MATCH (a)-[r]->(b) RETURN a, r, b results.

        Args:
            results: Raw Cypher edge results.
            node_id_map: Map of Cognee node IDs to Sentinel node IDs.

        Returns:
            List of relation dictionaries.
        """
        relations: list[dict[str, Any]] = []

        if not results or not isinstance(results, list):
            return relations

        for result_item in results:
            if not isinstance(result_item, dict):
                continue

            search_result = result_item.get("search_result", [])
            if not search_result or not isinstance(search_result, list):
                continue

            # search_result[0] contains list of [source, edge, target] triples
            edge_list = search_result[0] if search_result else []

            for edge_triple in edge_list:
                if not isinstance(edge_triple, list) or len(edge_triple) < 3:
                    continue

                source_node = edge_triple[0]
                edge_data = edge_triple[1]
                target_node = edge_triple[2]

                if not all(isinstance(x, dict) for x in [source_node, edge_data, target_node]):
                    continue

                # Only process edges between Entity nodes
                if source_node.get("type") != "Entity" or target_node.get("type") != "Entity":
                    continue

                source_cognee_id = source_node.get("id", "")
                target_cognee_id = target_node.get("id", "")

                # Skip if we don't have these nodes mapped
                if source_cognee_id not in node_id_map or target_cognee_id not in node_id_map:
                    continue

                # Get relationship type
                rel_name = edge_data.get("relationship_name", "")

                relation = {
                    "source_id": node_id_map[source_cognee_id],
                    "target_id": node_id_map[target_cognee_id],
                    "type": rel_name,
                    "confidence": DEFAULT_CONFIDENCE,
                }

                relations.append(relation)

        return relations

    def _transform_cognee_results(self, results: Any, text: str) -> Graph:
        """Transform Cognee search results into a Sentinel Graph.

        Args:
            results: Raw results from Cognee search.
            text: Original input text for source determination.

        Returns:
            Graph with mapped nodes and edges.
        """
        nodes: list[Node] = []
        edges: list[Edge] = []
        seen_node_ids: set[str] = set()
        node_id_map: dict[str, str] = {}  # Map Cognee IDs to Sentinel IDs

        # Handle different result formats from Cognee
        if results is None:
            return Graph(nodes=(), edges=())

        # Extract entities and relations from results
        entities = self._extract_entities(results)
        relations = self._extract_relations(results)

        # Process entities
        for entity in entities:
            node = _map_cognee_entity_to_node(entity, text)
            if node.id not in seen_node_ids:
                nodes.append(node)
                seen_node_ids.add(node.id)
                # Map original Cognee ID to our generated ID
                cognee_id = entity.get("id", "")
                if cognee_id:
                    node_id_map[cognee_id] = node.id

        # Process relations
        for relation in relations:
            # Remap source/target IDs to our generated IDs
            source_cognee_id = relation.get("source_id", "")
            target_cognee_id = relation.get("target_id", "")

            # Skip edges where we can't map both source and target to known nodes
            if source_cognee_id not in node_id_map:
                logger.warning(
                    "Skipping edge: source_id '%s' not found in node map",
                    source_cognee_id,
                )
                continue
            if target_cognee_id not in node_id_map:
                logger.warning(
                    "Skipping edge: target_id '%s' not found in node map",
                    target_cognee_id,
                )
                continue

            relation_copy = dict(relation)
            relation_copy["source_id"] = node_id_map[source_cognee_id]
            relation_copy["target_id"] = node_id_map[target_cognee_id]

            edge = _map_cognee_relation_to_edge(relation_copy)
            if edge is not None:
                edges.append(edge)

        # Filter to only valid edge types
        valid_edges = _filter_valid_edges(edges)

        # Validate all edges reference existing nodes (H2 fix)
        valid_edges = self._validate_edge_references(valid_edges, seen_node_ids)

        return Graph(nodes=tuple(nodes), edges=tuple(valid_edges))

    def _extract_entities(self, results: Any) -> list[dict[str, Any]]:
        """Extract entities from Cognee results.

        Handles various result formats that Cognee may return.

        Args:
            results: Raw Cognee results.

        Returns:
            List of entity dictionaries.
        """
        entities: list[dict[str, Any]] = []

        if isinstance(results, list):
            for item in results:
                if isinstance(item, dict):
                    # Check for entity-like structure
                    if "type" in item and "label" in item:
                        entities.append(item)
                    # Check for nested entities
                    if "entities" in item:
                        entities.extend(item["entities"])
                    # Check for nodes list
                    if "nodes" in item:
                        entities.extend(item["nodes"])

        elif isinstance(results, dict):
            if "entities" in results:
                entities.extend(results["entities"])
            if "nodes" in results:
                entities.extend(results["nodes"])

        return entities

    def _extract_relations(self, results: Any) -> list[dict[str, Any]]:
        """Extract relations from Cognee results.

        Handles various result formats that Cognee may return.

        Args:
            results: Raw Cognee results.

        Returns:
            List of relation dictionaries.
        """
        relations: list[dict[str, Any]] = []

        if isinstance(results, list):
            for item in results:
                if isinstance(item, dict):
                    # Check for relation-like structure
                    if "source_id" in item and "target_id" in item:
                        relations.append(item)
                    # Check for nested relations
                    if "relations" in item:
                        relations.extend(item["relations"])
                    # Check for edges list
                    if "edges" in item:
                        relations.extend(item["edges"])

        elif isinstance(results, dict):
            if "relations" in results:
                relations.extend(results["relations"])
            if "edges" in results:
                relations.extend(results["edges"])

        return relations

    def _validate_edge_references(self, edges: list[Edge], valid_node_ids: set[str]) -> list[Edge]:
        """Validate that all edges reference existing nodes.

        Filters out edges where source_id or target_id doesn't exist
        in the set of valid node IDs.

        Args:
            edges: List of edges to validate.
            valid_node_ids: Set of valid node IDs from the graph.

        Returns:
            List of edges with valid node references.
        """
        valid_edges: list[Edge] = []
        for edge in edges:
            if edge.source_id not in valid_node_ids:
                logger.warning(
                    "Filtering edge: source_id '%s' not in graph nodes",
                    edge.source_id,
                )
                continue
            if edge.target_id not in valid_node_ids:
                logger.warning(
                    "Filtering edge: target_id '%s' not in graph nodes",
                    edge.target_id,
                )
                continue
            valid_edges.append(edge)
        return valid_edges

    async def query_collisions(self, graph: Graph) -> list[ScoredCollision]:
        """Query the graph for energy collisions using Cognee.

        Args:
            graph: The graph to analyze for collisions.

        Returns:
            List of scored collisions found in the graph.

        Raises:
            NotImplementedError: This is a stub implementation.
        """
        raise NotImplementedError("CogneeEngine.query_collisions not yet implemented")

    async def get_neighbors(self, node_id: str, depth: int = 2) -> Subgraph:
        """Get neighbors of a node using Cognee.

        Args:
            node_id: ID of the node to explore from.
            depth: Maximum depth to traverse (default 2).

        Returns:
            Subgraph containing the node and its neighbors.

        Raises:
            NotImplementedError: This is a stub implementation.
        """
        raise NotImplementedError("CogneeEngine.get_neighbors not yet implemented")

    def mutate(self, graph: Graph, correction: Correction) -> Graph:
        """Apply a correction to the graph.

        Args:
            graph: The graph to mutate.
            correction: The correction to apply.

        Returns:
            New graph with the correction applied.

        Raises:
            NotImplementedError: This is a stub implementation.
        """
        raise NotImplementedError("CogneeEngine.mutate not yet implemented")

    def persist(self, graph: Graph) -> None:
        """Persist graph to JSON file.

        Uses atomic write (temp file + rename) to prevent corruption.

        Args:
            graph: The graph to persist.

        Raises:
            PersistenceError: If file I/O fails.
        """
        ensure_data_directory()
        db_path = get_graph_db_path()

        now = datetime.now(UTC).isoformat().replace("+00:00", "Z")

        # Preserve created_at from existing file if it exists
        created_at = now
        if db_path.exists():
            try:
                with open(db_path, encoding="utf-8") as f:
                    existing = json.load(f)
                    created_at = existing.get("created_at", now)
            except (json.JSONDecodeError, OSError):
                # If existing file is corrupted, use current time
                pass

        data = {
            "version": "1.0",
            "created_at": created_at,
            "updated_at": now,
            "nodes": [self._node_to_dict(n) for n in graph.nodes],
            "edges": [self._edge_to_dict(e) for e in graph.edges],
        }

        # Atomic write: write to temp, then rename
        temp_path = db_path.with_suffix(".tmp")
        try:
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            temp_path.replace(db_path)  # Atomic on POSIX
        except OSError as e:
            raise PersistenceError(f"Failed to save graph: {e}") from e
        finally:
            # Clean up temp file if it still exists (e.g., if replace() failed)
            try:
                if temp_path.exists():
                    temp_path.unlink()
            except OSError:
                pass  # Best effort cleanup, ignore errors

    def _node_to_dict(self, node: Node) -> dict[str, Any]:
        """Serialize Node to dictionary."""
        return {
            "id": node.id,
            "label": node.label,
            "type": node.type,
            "source": node.source,
            "metadata": dict(node.metadata) if node.metadata else {},
        }

    def _edge_to_dict(self, edge: Edge) -> dict[str, Any]:
        """Serialize Edge to dictionary."""
        return {
            "source_id": edge.source_id,
            "target_id": edge.target_id,
            "relationship": edge.relationship,
            "confidence": edge.confidence,
            "metadata": dict(edge.metadata) if edge.metadata else {},
        }

    def load(self) -> Graph | None:
        """Load persisted graph from JSON file.

        Returns:
            Graph if successfully loaded, None if no graph.db file exists.

        Raises:
            PersistenceError: If file exists but is corrupted or unreadable.
        """
        db_path = get_graph_db_path()

        if not db_path.exists():
            return None

        try:
            with open(db_path, encoding="utf-8") as f:
                data = json.load(f)

            nodes = tuple(self._dict_to_node(n) for n in data.get("nodes", []))
            edges = tuple(self._dict_to_edge(e) for e in data.get("edges", []))

            return Graph(nodes=nodes, edges=edges)

        except json.JSONDecodeError as e:
            raise PersistenceError(
                "Graph database corrupted. Run `sentinel paste` to rebuild."
            ) from e
        except (KeyError, TypeError) as e:
            raise PersistenceError(
                "Graph database corrupted. Run `sentinel paste` to rebuild."
            ) from e

    def _dict_to_node(self, d: dict[str, Any]) -> Node:
        """Deserialize dictionary to Node."""
        return Node(
            id=d["id"],
            label=d["label"],
            type=d["type"],
            source=d["source"],
            metadata=d.get("metadata", {}),
        )

    def _dict_to_edge(self, d: dict[str, Any]) -> Edge:
        """Deserialize dictionary to Edge."""
        return Edge(
            source_id=d["source_id"],
            target_id=d["target_id"],
            relationship=d["relationship"],
            confidence=d.get("confidence", 0.8),
            metadata=d.get("metadata", {}),
        )
