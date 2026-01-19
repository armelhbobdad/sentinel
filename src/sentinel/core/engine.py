"""GraphEngine protocol and implementations.

Defines the interface for knowledge graph operations and provides
implementations including Cognee-based extraction.
"""

import logging
import re
import unicodedata
from typing import Any, Protocol

import cognee
from cognee.api.v1.search import SearchType

from sentinel.core.exceptions import IngestionError
from sentinel.core.types import (
    Correction,
    Edge,
    Graph,
    Node,
    NodeSource,
    ScoredCollision,
)

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
    # SCHEDULED_AT mappings
    "scheduled_at": "SCHEDULED_AT",
    "at_time": "SCHEDULED_AT",
    "when": "SCHEDULED_AT",
    "occurs_at": "SCHEDULED_AT",
    "on_date": "SCHEDULED_AT",
    # DRAINS mappings
    "drains": "DRAINS",
    "depletes": "DRAINS",
    "exhausts": "DRAINS",
    "tires": "DRAINS",
    "fatigues": "DRAINS",
    # REQUIRES mappings
    "requires": "REQUIRES",
    "needs": "REQUIRES",
    "demands": "REQUIRES",
    "depends_on": "REQUIRES",
    # CONFLICTS_WITH mappings
    "conflicts": "CONFLICTS_WITH",
    "conflicts_with": "CONFLICTS_WITH",
    "contradicts": "CONFLICTS_WITH",
    "opposes": "CONFLICTS_WITH",
    "clashes": "CONFLICTS_WITH",
    # BELONGS_TO mappings
    "belongs_to": "BELONGS_TO",
    "category": "BELONGS_TO",
    "domain": "BELONGS_TO",
    "part_of": "BELONGS_TO",
}

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
    """Map a Cognee relation to a Sentinel Edge.

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

    # Map relation type to Sentinel edge type
    edge_type = RELATION_TYPE_MAP.get(relation_type)
    if edge_type is None:
        logger.warning("Unknown relation type '%s', filtering out", relation_type)
        return None

    return Edge(
        source_id=source_id,
        target_id=target_id,
        relationship=edge_type,
        confidence=confidence,
        metadata={"cognee_type": relation_type},
    )


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

    async def ingest(self, text: str) -> Graph:
        """Ingest text and build a knowledge graph using Cognee.

        Calls Cognee's API to extract entities and relationships,
        then transforms them into Sentinel's Graph format.

        Args:
            text: Schedule text to parse and convert to graph.

        Returns:
            Graph containing extracted entities and relationships.

        Raises:
            IngestionError: If Cognee API call fails.
        """
        try:
            # Reset any previous state
            await cognee.prune.prune_data()
            await cognee.prune.prune_system(metadata=True)

            # Add text to Cognee
            await cognee.add(text)

            # Process with cognify (extracts entities + relationships)
            await cognee.cognify()

            # Query the graph for entities and relationships
            results = await cognee.search(
                query_text="*",  # Get all entities
                query_type=SearchType.GRAPH_COMPLETION,
            )

            # Transform Cognee results to Sentinel types
            return self._transform_cognee_results(results, text)

        except IngestionError:
            raise
        except Exception as e:
            logger.exception("Cognee API call failed")
            raise IngestionError(f"Failed to process schedule: {e}") from e

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
            return Graph(nodes=[], edges=[])

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

        return Graph(nodes=nodes, edges=valid_edges)

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
        """Persist the graph to storage.

        Args:
            graph: The graph to persist.

        Raises:
            NotImplementedError: This is a stub implementation.
        """
        raise NotImplementedError("CogneeEngine.persist not yet implemented")
