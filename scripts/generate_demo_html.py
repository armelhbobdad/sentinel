#!/usr/bin/env python3
"""Generate demo HTML files for README documentation.

This script creates sample HTML visualizations using fixture data,
demonstrating the different output formats Sentinel can produce.
"""

from pathlib import Path

from sentinel.core.types import Edge, Graph, Node
from sentinel.viz.html import render_html


def create_collision_graph() -> Graph:
    """Create the standard collision scenario graph (Aunt Susan example)."""
    nodes = (
        Node(
            id="person-aunt-susan",
            label="Aunt Susan",
            type="Person",
            source="user-stated",
            metadata={"extracted_from": "Sunday dinner"},
        ),
        Node(
            id="activity-dinner",
            label="Dinner with Aunt Susan",
            type="Activity",
            source="user-stated",
            metadata={"day": "Sunday"},
        ),
        Node(
            id="energy-low",
            label="Low Energy",
            type="EnergyState",
            source="ai-inferred",
            metadata={"level": "depleted"},
        ),
        Node(
            id="energy-high",
            label="High Focus Required",
            type="EnergyState",
            source="ai-inferred",
            metadata={"level": "peak"},
        ),
        Node(
            id="activity-presentation",
            label="Strategy Presentation",
            type="Activity",
            source="user-stated",
            metadata={"day": "Monday"},
        ),
        Node(
            id="timeslot-sunday-evening",
            label="Sunday Evening",
            type="TimeSlot",
            source="ai-inferred",
            metadata={"day": "Sunday", "time": "evening"},
        ),
        Node(
            id="timeslot-monday-morning",
            label="Monday Morning",
            type="TimeSlot",
            source="ai-inferred",
            metadata={"day": "Monday", "time": "morning"},
        ),
    )

    edges = (
        Edge(
            source_id="person-aunt-susan",
            target_id="energy-low",
            relationship="DRAINS",
            confidence=0.85,
            metadata={"reason": "emotionally draining"},
        ),
        Edge(
            source_id="activity-dinner",
            target_id="person-aunt-susan",
            relationship="INVOLVES",
            confidence=0.95,
            metadata={},
        ),
        Edge(
            source_id="activity-dinner",
            target_id="timeslot-sunday-evening",
            relationship="SCHEDULED_AT",
            confidence=0.90,
            metadata={},
        ),
        Edge(
            source_id="energy-low",
            target_id="energy-high",
            relationship="CONFLICTS_WITH",
            confidence=0.80,
            metadata={"type": "energy_conflict"},
        ),
        Edge(
            source_id="activity-presentation",
            target_id="energy-high",
            relationship="REQUIRES",
            confidence=0.88,
            metadata={"reason": "need to be sharp"},
        ),
        Edge(
            source_id="activity-presentation",
            target_id="timeslot-monday-morning",
            relationship="SCHEDULED_AT",
            confidence=0.90,
            metadata={},
        ),
    )

    return Graph(nodes=nodes, edges=edges)


def create_no_collision_graph() -> Graph:
    """Create a graph with no collisions (boring week)."""
    nodes = (
        Node(
            id="activity-standup",
            label="Daily Standup",
            type="Activity",
            source="user-stated",
            metadata={"day": "Monday"},
        ),
        Node(
            id="activity-docs",
            label="Documentation Updates",
            type="Activity",
            source="user-stated",
            metadata={"day": "Tuesday"},
        ),
        Node(
            id="activity-lunch",
            label="Team Lunch",
            type="Activity",
            source="user-stated",
            metadata={"day": "Wednesday"},
        ),
        Node(
            id="energy-moderate",
            label="Moderate Focus",
            type="EnergyState",
            source="ai-inferred",
            metadata={"level": "normal"},
        ),
    )

    edges = (
        Edge(
            source_id="activity-standup",
            target_id="energy-moderate",
            relationship="REQUIRES",
            confidence=0.70,
            metadata={},
        ),
        Edge(
            source_id="activity-docs",
            target_id="energy-moderate",
            relationship="REQUIRES",
            confidence=0.65,
            metadata={},
        ),
    )

    return Graph(nodes=nodes, edges=edges)


def main() -> None:
    """Generate all demo HTML files."""
    output_dir = Path("assets/html-demos")
    output_dir.mkdir(parents=True, exist_ok=True)

    # 1. Graph with collision (paste output)
    collision_graph = create_collision_graph()
    paste_html = render_html(
        collision_graph,
        title="Sentinel Graph - After Schedule Ingestion",
    )
    (output_dir / "demo-paste-output.html").write_text(paste_html)
    print(f"Generated: {output_dir}/demo-paste-output.html")

    # 2. Graph with collision highlights (check output)
    collision_paths = [
        (
            "Aunt Susan",
            "DRAINS",
            "Low Energy",
            "CONFLICTS_WITH",
            "High Focus Required",
            "REQUIRES",
            "Strategy Presentation",
        ),
    ]
    check_html = render_html(
        collision_graph,
        collision_paths=collision_paths,
        title="Sentinel Collision Report",
    )
    (output_dir / "demo-check-collision.html").write_text(check_html)
    print(f"Generated: {output_dir}/demo-check-collision.html")

    # 3. Graph without collision (no warnings)
    no_collision_graph = create_no_collision_graph()
    clean_html = render_html(
        no_collision_graph,
        title="Sentinel Graph - No Collisions",
    )
    (output_dir / "demo-no-collision.html").write_text(clean_html)
    print(f"Generated: {output_dir}/demo-no-collision.html")

    print("\nDone! Open the HTML files in a browser to preview.")
    print("Take screenshots and save to assets/ for README.")


if __name__ == "__main__":
    main()
