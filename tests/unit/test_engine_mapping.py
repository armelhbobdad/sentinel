"""Unit tests for CogneeEngine entity and relationship mapping.

Tests the pure mapping functions that transform Cognee output
into Sentinel Graph types. No Cognee API calls required.
"""

from sentinel.core.types import Edge, Node


class TestDetermineSource:
    """Tests for _determine_source function."""

    def test_determine_source_user_stated_exact_match(self) -> None:
        """Entity label appearing in text should be user-stated."""
        # Import here to allow test to run even before implementation exists
        from sentinel.core.engine import _determine_source

        text = "Dinner with Aunt Susan on Sunday"
        source = _determine_source("Aunt Susan", text)
        assert source == "user-stated", f"Expected user-stated for exact match, got {source}"

    def test_determine_source_user_stated_case_insensitive(self) -> None:
        """Entity label matching case-insensitively should be user-stated."""
        from sentinel.core.engine import _determine_source

        text = "dinner with AUNT SUSAN on sunday"
        source = _determine_source("Aunt Susan", text)
        assert source == "user-stated", (
            f"Expected user-stated for case-insensitive match, got {source}"
        )

    def test_determine_source_ai_inferred(self) -> None:
        """Entity label NOT in text should be ai-inferred."""
        from sentinel.core.engine import _determine_source

        text = "Dinner with Aunt Susan on Sunday"
        source = _determine_source("Low Energy", text)
        assert source == "ai-inferred", f"Expected ai-inferred for non-match, got {source}"

    def test_determine_source_partial_match_not_user_stated(self) -> None:
        """Partial word match should not be user-stated."""
        from sentinel.core.engine import _determine_source

        text = "Working on sundown project"
        source = _determine_source("Sunday", text)
        # "Sunday" is not in "sundown" - should be ai-inferred
        assert source == "ai-inferred", f"Expected ai-inferred for partial match, got {source}"


class TestGenerateNodeId:
    """Tests for _generate_node_id function."""

    def test_generate_node_id_basic(self) -> None:
        """Node ID should be {type}-{slugified-label}."""
        from sentinel.core.engine import _generate_node_id

        node_id = _generate_node_id("Person", "Aunt Susan")
        assert node_id == "person-aunt-susan", f"Expected person-aunt-susan, got {node_id}"

    def test_generate_node_id_deterministic(self) -> None:
        """Same input should always produce same ID."""
        from sentinel.core.engine import _generate_node_id

        id1 = _generate_node_id("Activity", "Strategy Presentation")
        id2 = _generate_node_id("Activity", "Strategy Presentation")
        assert id1 == id2, f"Expected deterministic IDs, got {id1} != {id2}"

    def test_generate_node_id_special_characters(self) -> None:
        """Special characters should be handled in slugification."""
        from sentinel.core.engine import _generate_node_id

        node_id = _generate_node_id("Person", "María ☕")
        # Should produce a valid ID with special chars removed/simplified
        assert node_id.startswith("person-"), f"Expected person- prefix, got {node_id}"
        assert " " not in node_id, f"ID should not contain spaces: {node_id}"

    def test_generate_node_id_lowercase(self) -> None:
        """Node ID should be lowercase."""
        from sentinel.core.engine import _generate_node_id

        node_id = _generate_node_id("TimeSlot", "Monday Morning")
        assert node_id == node_id.lower(), f"Expected lowercase ID, got {node_id}"


class TestMapCogneeEntityToNode:
    """Tests for _map_cognee_entity_to_node function."""

    def test_map_person_entity(self) -> None:
        """PERSON entity type should map to Person node type."""
        from sentinel.core.engine import _map_cognee_entity_to_node

        cognee_entity = {
            "type": "PERSON",
            "label": "Aunt Susan",
        }
        text = "Dinner with Aunt Susan"

        node = _map_cognee_entity_to_node(cognee_entity, text)

        assert isinstance(node, Node), f"Expected Node, got {type(node)}"
        assert node.type == "Person", f"Expected Person type, got {node.type}"
        assert node.label == "Aunt Susan", f"Expected 'Aunt Susan', got {node.label}"
        assert node.source == "user-stated", f"Expected user-stated, got {node.source}"

    def test_map_event_entity(self) -> None:
        """EVENT entity type should map to Activity node type."""
        from sentinel.core.engine import _map_cognee_entity_to_node

        cognee_entity = {
            "type": "EVENT",
            "label": "Strategy Presentation",
        }
        text = "Strategy Presentation on Monday"

        node = _map_cognee_entity_to_node(cognee_entity, text)

        assert node.type == "Activity", f"Expected Activity type, got {node.type}"

    def test_map_time_entity(self) -> None:
        """TIME entity type should map to TimeSlot node type."""
        from sentinel.core.engine import _map_cognee_entity_to_node

        cognee_entity = {
            "type": "DATE",
            "label": "Sunday",
        }
        text = "Dinner on Sunday"

        node = _map_cognee_entity_to_node(cognee_entity, text)

        assert node.type == "TimeSlot", f"Expected TimeSlot type, got {node.type}"

    def test_map_emotion_entity(self) -> None:
        """EMOTION entity type should map to EnergyState node type."""
        from sentinel.core.engine import _map_cognee_entity_to_node

        cognee_entity = {
            "type": "EMOTION",
            "label": "drained",
        }
        text = "Feeling energized"  # Not mentioned - should be ai-inferred

        node = _map_cognee_entity_to_node(cognee_entity, text)

        assert node.type == "EnergyState", f"Expected EnergyState type, got {node.type}"
        assert node.source == "ai-inferred", f"Expected ai-inferred, got {node.source}"

    def test_map_unknown_entity_type_defaults_to_activity(self) -> None:
        """Unknown entity types should default to Activity."""
        from sentinel.core.engine import _map_cognee_entity_to_node

        cognee_entity = {
            "type": "UNKNOWN_TYPE",
            "label": "Something",
        }
        text = "Something happens"

        node = _map_cognee_entity_to_node(cognee_entity, text)

        assert node.type == "Activity", f"Expected Activity default, got {node.type}"


class TestMapCogneeRelationToEdge:
    """Tests for _map_cognee_relation_to_edge function."""

    def test_map_involves_relation(self) -> None:
        """Cognee 'involves' relation should map to INVOLVES edge."""
        from sentinel.core.engine import _map_cognee_relation_to_edge

        cognee_relation = {
            "type": "involves",
            "source_id": "activity-dinner",
            "target_id": "person-aunt-susan",
            "confidence": 0.85,
        }

        edge = _map_cognee_relation_to_edge(cognee_relation)

        assert edge is not None, "Edge should not be None for valid relation"
        assert isinstance(edge, Edge), f"Expected Edge, got {type(edge)}"
        assert edge.relationship == "INVOLVES", f"Expected INVOLVES, got {edge.relationship}"
        assert edge.confidence == 0.85, f"Expected 0.85, got {edge.confidence}"

    def test_map_drains_relation(self) -> None:
        """Cognee 'drains' relation should map to DRAINS edge."""
        from sentinel.core.engine import _map_cognee_relation_to_edge

        cognee_relation = {
            "type": "depletes",  # Synonym for drains
            "source_id": "person-aunt-susan",
            "target_id": "energy-low",
            "confidence": 0.75,
        }

        edge = _map_cognee_relation_to_edge(cognee_relation)

        assert edge is not None, "Edge should not be None for valid relation"
        assert edge.relationship == "DRAINS", f"Expected DRAINS, got {edge.relationship}"

    def test_map_unknown_relation_returns_none(self) -> None:
        """Unknown relation types should return None and be filtered out."""
        from sentinel.core.engine import _map_cognee_relation_to_edge

        cognee_relation = {
            "type": "unknown_relation",
            "source_id": "node-a",
            "target_id": "node-b",
            "confidence": 0.5,
        }

        edge = _map_cognee_relation_to_edge(cognee_relation)

        assert edge is None, f"Expected None for unknown relation, got {edge}"

    def test_map_relation_default_confidence(self) -> None:
        """Missing confidence should default to 0.8."""
        from sentinel.core.engine import _map_cognee_relation_to_edge

        cognee_relation = {
            "type": "requires",
            "source_id": "activity-presentation",
            "target_id": "energy-high",
            # No confidence provided
        }

        edge = _map_cognee_relation_to_edge(cognee_relation)

        assert edge is not None, "Edge should not be None"
        assert edge.confidence == 0.8, f"Expected default 0.8, got {edge.confidence}"

    def test_map_scheduled_at_relation(self) -> None:
        """Cognee 'at_time' relation should map to SCHEDULED_AT edge."""
        from sentinel.core.engine import _map_cognee_relation_to_edge

        cognee_relation = {
            "type": "at_time",
            "source_id": "activity-dinner",
            "target_id": "timeslot-sunday",
            "confidence": 0.9,
        }

        edge = _map_cognee_relation_to_edge(cognee_relation)

        assert edge is not None, "Edge should not be None for valid relation"
        assert edge.relationship == "SCHEDULED_AT", (
            f"Expected SCHEDULED_AT, got {edge.relationship}"
        )


class TestEdgeTypeValidation:
    """Tests for edge type filtering against allowed list."""

    def test_valid_edge_types(self) -> None:
        """All valid edge types should be accepted."""
        from sentinel.core.engine import VALID_EDGE_TYPES

        expected = {
            "DRAINS",
            "REQUIRES",
            "CONFLICTS_WITH",
            "SCHEDULED_AT",
            "INVOLVES",
            "BELONGS_TO",
        }
        assert VALID_EDGE_TYPES == expected, f"Expected {expected}, got {VALID_EDGE_TYPES}"

    def test_filter_invalid_edges(self) -> None:
        """Invalid edge types should be filtered out."""
        from sentinel.core.engine import _filter_valid_edges

        edges = [
            Edge("a", "b", "DRAINS", 0.8),
            Edge("c", "d", "INVALID_TYPE", 0.8),
            Edge("e", "f", "REQUIRES", 0.8),
        ]

        valid_edges = _filter_valid_edges(edges)

        assert len(valid_edges) == 2, f"Expected 2 valid edges, got {len(valid_edges)}"
        assert all(e.relationship in {"DRAINS", "REQUIRES"} for e in valid_edges)


class TestExtractEntities:
    """Tests for _extract_entities method (M1 fix)."""

    def test_extract_entities_from_list_with_type_and_label(self) -> None:
        """Entities in list format with type/label should be extracted."""
        from sentinel.core.engine import CogneeEngine

        engine = CogneeEngine()
        results = [
            {"type": "PERSON", "label": "Alice"},
            {"type": "EVENT", "label": "Meeting"},
        ]

        entities = engine._extract_entities(results)

        assert len(entities) == 2, f"Expected 2 entities, got {len(entities)}"
        assert entities[0]["label"] == "Alice", f"Expected Alice, got {entities[0]['label']}"

    def test_extract_entities_from_nested_entities_key(self) -> None:
        """Entities nested under 'entities' key should be extracted."""
        from sentinel.core.engine import CogneeEngine

        engine = CogneeEngine()
        results = [
            {
                "entities": [
                    {"type": "PERSON", "label": "Bob"},
                    {"type": "TIME", "label": "Monday"},
                ]
            }
        ]

        entities = engine._extract_entities(results)

        assert len(entities) == 2, f"Expected 2 entities, got {len(entities)}"

    def test_extract_entities_from_nested_nodes_key(self) -> None:
        """Entities nested under 'nodes' key should be extracted."""
        from sentinel.core.engine import CogneeEngine

        engine = CogneeEngine()
        results = {"nodes": [{"type": "PERSON", "label": "Carol"}]}

        entities = engine._extract_entities(results)

        assert len(entities) == 1, f"Expected 1 entity, got {len(entities)}"
        assert entities[0]["label"] == "Carol", f"Expected Carol, got {entities[0]['label']}"

    def test_extract_entities_from_empty_results(self) -> None:
        """Empty results should return empty list."""
        from sentinel.core.engine import CogneeEngine

        engine = CogneeEngine()

        assert engine._extract_entities([]) == [], "Expected empty list for empty results"
        assert engine._extract_entities({}) == [], "Expected empty list for empty dict"


class TestExtractRelations:
    """Tests for _extract_relations method (M1 fix)."""

    def test_extract_relations_from_list_with_source_target(self) -> None:
        """Relations in list format with source_id/target_id should be extracted."""
        from sentinel.core.engine import CogneeEngine

        engine = CogneeEngine()
        results = [
            {"source_id": "a", "target_id": "b", "type": "involves"},
            {"source_id": "c", "target_id": "d", "type": "drains"},
        ]

        relations = engine._extract_relations(results)

        assert len(relations) == 2, f"Expected 2 relations, got {len(relations)}"

    def test_extract_relations_from_nested_relations_key(self) -> None:
        """Relations nested under 'relations' key should be extracted."""
        from sentinel.core.engine import CogneeEngine

        engine = CogneeEngine()
        results = [
            {
                "relations": [
                    {"source_id": "x", "target_id": "y", "type": "requires"},
                ]
            }
        ]

        relations = engine._extract_relations(results)

        assert len(relations) == 1, f"Expected 1 relation, got {len(relations)}"

    def test_extract_relations_from_nested_edges_key(self) -> None:
        """Relations nested under 'edges' key should be extracted."""
        from sentinel.core.engine import CogneeEngine

        engine = CogneeEngine()
        results = {"edges": [{"source_id": "m", "target_id": "n", "type": "belongs_to"}]}

        relations = engine._extract_relations(results)

        assert len(relations) == 1, f"Expected 1 relation, got {len(relations)}"

    def test_extract_relations_from_empty_results(self) -> None:
        """Empty results should return empty list."""
        from sentinel.core.engine import CogneeEngine

        engine = CogneeEngine()

        assert engine._extract_relations([]) == [], "Expected empty list for empty results"
        assert engine._extract_relations({}) == [], "Expected empty list for empty dict"


class TestTransformCogneeResults:
    """Tests for _transform_cognee_results method (M2, M3 fixes)."""

    def test_transform_none_results_returns_empty_graph(self) -> None:
        """None results should return empty Graph (M3 fix)."""
        from sentinel.core.engine import CogneeEngine
        from sentinel.core.types import Graph

        engine = CogneeEngine()
        graph = engine._transform_cognee_results(None, "test text")

        assert isinstance(graph, Graph), f"Expected Graph, got {type(graph)}"
        assert len(graph.nodes) == 0, f"Expected 0 nodes, got {len(graph.nodes)}"
        assert len(graph.edges) == 0, f"Expected 0 edges, got {len(graph.edges)}"

    def test_transform_empty_list_returns_empty_graph(self) -> None:
        """Empty list results should return empty Graph (M3 fix)."""
        from sentinel.core.engine import CogneeEngine
        from sentinel.core.types import Graph

        engine = CogneeEngine()
        graph = engine._transform_cognee_results([], "test text")

        assert isinstance(graph, Graph), f"Expected Graph, got {type(graph)}"
        assert len(graph.nodes) == 0, f"Expected 0 nodes, got {len(graph.nodes)}"

    def test_transform_deduplicates_nodes_by_id(self) -> None:
        """Duplicate entities should produce single node (M2 fix)."""
        from sentinel.core.engine import CogneeEngine

        engine = CogneeEngine()
        # Two entities that will generate the same node ID
        results = [
            {"type": "PERSON", "label": "Alice", "id": "cognee-1"},
            {"type": "PERSON", "label": "Alice", "id": "cognee-2"},  # Duplicate label
        ]
        text = "Meeting with Alice"

        graph = engine._transform_cognee_results(results, text)

        # Should only have one node for "Alice"
        assert len(graph.nodes) == 1, f"Expected 1 node (deduplicated), got {len(graph.nodes)}"
        assert graph.nodes[0].label == "Alice", f"Expected Alice, got {graph.nodes[0].label}"


class TestMetadataPreservation:
    """Tests for metadata preservation in entity mapping (M4 fix)."""

    def test_map_entity_preserves_cognee_type_in_metadata(self) -> None:
        """Original Cognee type should be preserved in metadata (M4 fix)."""
        from sentinel.core.engine import _map_cognee_entity_to_node

        cognee_entity = {
            "type": "PERSON",
            "label": "David",
        }
        text = "Meeting with David"

        node = _map_cognee_entity_to_node(cognee_entity, text)

        assert "cognee_type" in node.metadata, "Expected cognee_type in metadata"
        assert node.metadata["cognee_type"] == "PERSON", (
            f"Expected PERSON, got {node.metadata['cognee_type']}"
        )

    def test_map_entity_preserves_custom_metadata(self) -> None:
        """Custom metadata from Cognee should be preserved (M4 fix)."""
        from sentinel.core.engine import _map_cognee_entity_to_node

        cognee_entity = {
            "type": "EVENT",
            "label": "Conference",
            "metadata": {"location": "NYC", "attendees": 100},
        }
        text = "Conference in NYC"

        node = _map_cognee_entity_to_node(cognee_entity, text)

        assert node.metadata.get("location") == "NYC", "Expected location metadata preserved"
        assert node.metadata.get("attendees") == 100, "Expected attendees metadata preserved"

    def test_map_entity_handles_empty_type(self) -> None:
        """Entity with empty type should default to Activity."""
        from sentinel.core.engine import _map_cognee_entity_to_node

        cognee_entity = {
            "type": "",
            "label": "Something",
        }
        text = "Something happens"

        node = _map_cognee_entity_to_node(cognee_entity, text)

        assert node.type == "Activity", f"Expected Activity default, got {node.type}"


class TestEdgeReferenceValidation:
    """Tests for edge reference validation (H2 fix)."""

    def test_validate_edge_references_filters_invalid_source(self) -> None:
        """Edges with invalid source_id should be filtered."""
        from sentinel.core.engine import CogneeEngine

        engine = CogneeEngine()
        edges = [
            Edge("valid-node", "another-valid", "DRAINS", 0.8),
            Edge("invalid-node", "another-valid", "REQUIRES", 0.8),
        ]
        valid_node_ids = {"valid-node", "another-valid"}

        result = engine._validate_edge_references(edges, valid_node_ids)

        assert len(result) == 1, f"Expected 1 valid edge, got {len(result)}"
        assert result[0].source_id == "valid-node", "Expected valid-node source"

    def test_validate_edge_references_filters_invalid_target(self) -> None:
        """Edges with invalid target_id should be filtered."""
        from sentinel.core.engine import CogneeEngine

        engine = CogneeEngine()
        edges = [
            Edge("node-a", "node-b", "INVOLVES", 0.8),
            Edge("node-a", "missing-node", "SCHEDULED_AT", 0.8),
        ]
        valid_node_ids = {"node-a", "node-b"}

        result = engine._validate_edge_references(edges, valid_node_ids)

        assert len(result) == 1, f"Expected 1 valid edge, got {len(result)}"
        assert result[0].target_id == "node-b", "Expected node-b target"

    def test_validate_edge_references_keeps_all_valid(self) -> None:
        """All valid edges should be kept."""
        from sentinel.core.engine import CogneeEngine

        engine = CogneeEngine()
        edges = [
            Edge("a", "b", "DRAINS", 0.8),
            Edge("b", "c", "REQUIRES", 0.8),
            Edge("c", "a", "CONFLICTS_WITH", 0.8),
        ]
        valid_node_ids = {"a", "b", "c"}

        result = engine._validate_edge_references(edges, valid_node_ids)

        assert len(result) == 3, f"Expected all 3 edges, got {len(result)}"
