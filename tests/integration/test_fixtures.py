"""Tests to verify fixture loading works correctly."""


def test_maya_typical_week_fixture_loads(maya_typical_week_text: str) -> None:
    """maya_typical_week fixture should load and contain expected content."""
    assert "Aunt Susan" in maya_typical_week_text, "Fixture should contain 'Aunt Susan'"
    assert "Strategy presentation" in maya_typical_week_text
    assert len(maya_typical_week_text) > 0, "Fixture should not be empty"


def test_maya_boring_week_fixture_loads(maya_boring_week_text: str) -> None:
    """maya_boring_week fixture should load and contain expected content."""
    assert "Regular standup" in maya_boring_week_text
    assert "Team lunch" in maya_boring_week_text
    assert len(maya_boring_week_text) > 0, "Fixture should not be empty"


def test_maya_edge_cases_fixture_loads(maya_edge_cases_text: str) -> None:
    """maya_edge_cases fixture should load and handle Unicode/emoji."""
    assert "María" in maya_edge_cases_text, "Fixture should contain accented character"
    assert "☕" in maya_edge_cases_text, "Fixture should contain emoji"
    assert "über" in maya_edge_cases_text, "Fixture should contain umlaut"
    assert "日本語" in maya_edge_cases_text, "Fixture should contain Japanese characters"
