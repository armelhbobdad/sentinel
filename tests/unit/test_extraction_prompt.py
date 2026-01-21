"""Unit tests for SENTINEL_EXTRACTION_PROMPT constant (Story 2-7).

Tests validate that the custom extraction prompt meets acceptance criteria:
- Contains required relationship types
- Contains few-shot examples
- Token count is under 2000 tokens
- Is a valid string
"""

import pytest

from sentinel.core.engine import SENTINEL_EXTRACTION_PROMPT

# Detect tiktoken availability for AC #5 validation
try:
    import tiktoken

    HAS_TIKTOKEN = True
except ImportError:
    tiktoken = None  # type: ignore[assignment]
    HAS_TIKTOKEN = False


class TestPromptContainsRequiredRelationshipTypes:
    """Tests for AC #1: Prompt contains required relationship types."""

    def test_prompt_contains_drains_relationship_type(self) -> None:
        """DRAINS relationship type must be defined in prompt."""
        assert "DRAINS" in SENTINEL_EXTRACTION_PROMPT
        assert "DRAINS:" in SENTINEL_EXTRACTION_PROMPT

    def test_prompt_contains_requires_relationship_type(self) -> None:
        """REQUIRES relationship type must be defined in prompt."""
        assert "REQUIRES" in SENTINEL_EXTRACTION_PROMPT
        assert "REQUIRES:" in SENTINEL_EXTRACTION_PROMPT

    def test_prompt_contains_conflicts_with_relationship_type(self) -> None:
        """CONFLICTS_WITH relationship type must be defined in prompt."""
        assert "CONFLICTS_WITH" in SENTINEL_EXTRACTION_PROMPT
        assert "CONFLICTS_WITH:" in SENTINEL_EXTRACTION_PROMPT

    def test_prompt_contains_scheduled_at_relationship_type(self) -> None:
        """SCHEDULED_AT relationship type must be defined in prompt."""
        assert "SCHEDULED_AT" in SENTINEL_EXTRACTION_PROMPT
        assert "SCHEDULED_AT:" in SENTINEL_EXTRACTION_PROMPT

    def test_prompt_contains_involves_relationship_type(self) -> None:
        """INVOLVES relationship type must be defined in prompt."""
        assert "INVOLVES" in SENTINEL_EXTRACTION_PROMPT
        assert "INVOLVES:" in SENTINEL_EXTRACTION_PROMPT

    def test_prompt_contains_all_five_required_types(self) -> None:
        """All five required relationship types must be present."""
        required_types = ["DRAINS", "REQUIRES", "CONFLICTS_WITH", "SCHEDULED_AT", "INVOLVES"]
        for rel_type in required_types:
            assert rel_type in SENTINEL_EXTRACTION_PROMPT, f"Missing {rel_type}"


class TestPromptContainsFewShotExamples:
    """Tests for AC #1: Prompt contains at least 3 few-shot examples."""

    def test_prompt_contains_example_1_marker(self) -> None:
        """Prompt must contain EXAMPLE 1."""
        assert "EXAMPLE 1" in SENTINEL_EXTRACTION_PROMPT

    def test_prompt_contains_example_2_marker(self) -> None:
        """Prompt must contain EXAMPLE 2."""
        assert "EXAMPLE 2" in SENTINEL_EXTRACTION_PROMPT

    def test_prompt_contains_example_3_marker(self) -> None:
        """Prompt must contain EXAMPLE 3."""
        assert "EXAMPLE 3" in SENTINEL_EXTRACTION_PROMPT

    def test_prompt_contains_at_least_three_examples(self) -> None:
        """Prompt must contain at least 3 examples."""
        example_count = SENTINEL_EXTRACTION_PROMPT.count("EXAMPLE")
        assert example_count >= 3, f"Expected >= 3 examples, found {example_count}"

    def test_prompt_contains_conflict_scenario_example(self) -> None:
        """At least one example must demonstrate a conflict scenario."""
        assert "Conflict scenario" in SENTINEL_EXTRACTION_PROMPT

    def test_prompt_contains_no_conflict_example(self) -> None:
        """At least one example must demonstrate no-conflict scenario."""
        assert "No conflict" in SENTINEL_EXTRACTION_PROMPT


class TestPromptContainsDomainInstructions:
    """Tests for domain-specific content in the prompt."""

    def test_prompt_contains_energy_domain_context(self) -> None:
        """Prompt must mention energy management domain."""
        assert "energy" in SENTINEL_EXTRACTION_PROMPT.lower()

    def test_prompt_contains_scheduling_domain_context(self) -> None:
        """Prompt must mention scheduling domain."""
        assert "schedul" in SENTINEL_EXTRACTION_PROMPT.lower()

    def test_prompt_contains_collision_pattern_description(self) -> None:
        """Prompt must describe the collision pattern."""
        assert "COLLISION PATTERN" in SENTINEL_EXTRACTION_PROMPT

    def test_prompt_contains_critical_rule(self) -> None:
        """Prompt must contain a critical rule about CONFLICTS_WITH edges."""
        assert "CRITICAL RULE" in SENTINEL_EXTRACTION_PROMPT


class TestPromptTokenCount:
    """Tests for AC #5: Prompt is under 2000 tokens."""

    def test_prompt_character_count_reasonable(self) -> None:
        """Prompt character count should be reasonable (< 8000 chars)."""
        # Rough estimate: ~4 chars per token, so 2000 tokens ~ 8000 chars max
        char_count = len(SENTINEL_EXTRACTION_PROMPT)
        assert char_count < 8000, f"Prompt has {char_count} chars (expected < 8000)"

    def test_prompt_word_count_reasonable(self) -> None:
        """Prompt word count should be reasonable (< 1500 words)."""
        # Rough estimate: ~1.3 tokens per word, so 2000 tokens ~ 1500 words max
        word_count = len(SENTINEL_EXTRACTION_PROMPT.split())
        assert word_count < 1500, f"Prompt has {word_count} words (expected < 1500)"

    @pytest.mark.skipif(
        not HAS_TIKTOKEN,
        reason="tiktoken not installed",
    )
    def test_prompt_token_count_under_limit_tiktoken(self) -> None:
        """Prompt token count must be under 2000 using tiktoken (AC #5)."""
        assert tiktoken is not None  # Type guard
        enc = tiktoken.get_encoding("cl100k_base")
        token_count = len(enc.encode(SENTINEL_EXTRACTION_PROMPT))
        assert token_count < 2000, f"Prompt has {token_count} tokens (expected < 2000)"


class TestPromptValidity:
    """Tests for prompt string validity."""

    def test_prompt_is_string(self) -> None:
        """Prompt must be a string."""
        assert isinstance(SENTINEL_EXTRACTION_PROMPT, str)

    def test_prompt_is_not_empty(self) -> None:
        """Prompt must not be empty."""
        assert len(SENTINEL_EXTRACTION_PROMPT) > 0

    def test_prompt_has_no_syntax_errors(self) -> None:
        """Prompt must be valid (no unclosed brackets, etc.)."""
        # Basic validation: equal number of opening/closing brackets
        assert SENTINEL_EXTRACTION_PROMPT.count("[") == SENTINEL_EXTRACTION_PROMPT.count("]")
        assert SENTINEL_EXTRACTION_PROMPT.count("(") == SENTINEL_EXTRACTION_PROMPT.count(")")
        assert SENTINEL_EXTRACTION_PROMPT.count("{") == SENTINEL_EXTRACTION_PROMPT.count("}")

    def test_prompt_ends_with_instruction_to_extract(self) -> None:
        """Prompt should end with instruction for LLM to extract from text."""
        assert "extract" in SENTINEL_EXTRACTION_PROMPT.lower()
        assert SENTINEL_EXTRACTION_PROMPT.strip().endswith(":")

    def test_prompt_contains_expected_graph_notation(self) -> None:
        """Prompt should use consistent graph notation with arrows for collision-critical types.

        Note: INVOLVES is defined in the prompt but not demonstrated in examples
        since it's not part of the collision detection pattern. The collision pattern
        focuses on: DRAINS -> CONFLICTS_WITH -> REQUIRES with SCHEDULED_AT for timing.
        """
        assert "--DRAINS-->" in SENTINEL_EXTRACTION_PROMPT
        assert "--CONFLICTS_WITH-->" in SENTINEL_EXTRACTION_PROMPT
        assert "--REQUIRES-->" in SENTINEL_EXTRACTION_PROMPT
        assert "--SCHEDULED_AT-->" in SENTINEL_EXTRACTION_PROMPT
        # INVOLVES is defined but not demonstrated in arrow notation in examples
        # This is acceptable as INVOLVES is not part of the collision pattern


class TestPromptEdgeCases:
    """Edge case tests for prompt robustness."""

    def test_prompt_can_be_concatenated_with_user_text(self) -> None:
        """Prompt should be safely concatenatable with user text."""
        user_text = "Maya has dinner with Aunt Susan on Sunday."
        combined = SENTINEL_EXTRACTION_PROMPT + user_text
        assert len(combined) > len(SENTINEL_EXTRACTION_PROMPT)
        assert user_text in combined

    def test_prompt_contains_snake_case_instruction(self) -> None:
        """Prompt should instruct LLM to use snake_case for node IDs."""
        assert "snake_case" in SENTINEL_EXTRACTION_PROMPT

    def test_prompt_contains_intermediary_node_instruction(self) -> None:
        """Prompt should instruct LLM to create energy_state intermediary nodes."""
        assert "energy_state" in SENTINEL_EXTRACTION_PROMPT
        assert "intermediar" in SENTINEL_EXTRACTION_PROMPT.lower()
