"""Tests for diff and status operations."""

from envseal.diffing import DiffCalculator, DiffResult


def test_diff_added_keys():
    """Test detecting added keys."""
    old_content = "KEY1=value1\nKEY2=value2\n"
    new_content = "KEY1=value1\nKEY2=value2\nKEY3=value3\n"

    calculator = DiffCalculator()
    result = calculator.calculate(old_content, new_content)

    assert len(result.added) == 1
    assert "KEY3" in result.added
    assert len(result.removed) == 0
    assert len(result.modified) == 0


def test_diff_removed_keys():
    """Test detecting removed keys."""
    old_content = "KEY1=value1\nKEY2=value2\nKEY3=value3\n"
    new_content = "KEY1=value1\nKEY2=value2\n"

    calculator = DiffCalculator()
    result = calculator.calculate(old_content, new_content)

    assert len(result.removed) == 1
    assert "KEY3" in result.removed
    assert len(result.added) == 0
    assert len(result.modified) == 0


def test_diff_modified_keys():
    """Test detecting modified keys."""
    old_content = "KEY1=old_value\nKEY2=value2\n"
    new_content = "KEY1=new_value\nKEY2=value2\n"

    calculator = DiffCalculator()
    result = calculator.calculate(old_content, new_content)

    assert len(result.modified) == 1
    assert "KEY1" in result.modified
    assert len(result.added) == 0
    assert len(result.removed) == 0


def test_diff_no_changes():
    """Test when there are no changes."""
    content = "KEY1=value1\nKEY2=value2\n"

    calculator = DiffCalculator()
    result = calculator.calculate(content, content)

    assert result.is_clean()
    assert len(result.added) == 0
    assert len(result.removed) == 0
    assert len(result.modified) == 0


def test_diff_multiple_changes():
    """Test detecting multiple types of changes at once."""
    old_content = "KEY1=value1\nKEY2=value2\nKEY3=value3\n"
    new_content = "KEY1=modified\nKEY2=value2\nKEY4=new_value\n"

    calculator = DiffCalculator()
    result = calculator.calculate(old_content, new_content)

    assert len(result.added) == 1
    assert "KEY4" in result.added
    assert len(result.removed) == 1
    assert "KEY3" in result.removed
    assert len(result.modified) == 1
    assert "KEY1" in result.modified


def test_diff_result_has_changes():
    """Test has_changes method."""
    result = DiffResult(added={"KEY1"}, removed=set(), modified=set())
    assert result.has_changes()

    result = DiffResult(added=set(), removed={"KEY1"}, modified=set())
    assert result.has_changes()

    result = DiffResult(added=set(), removed=set(), modified={"KEY1"})
    assert result.has_changes()

    result = DiffResult(added=set(), removed=set(), modified=set())
    assert not result.has_changes()


def test_diff_handles_empty_content():
    """Test diffing with empty content."""
    calculator = DiffCalculator()

    # Old is empty, new has keys
    result = calculator.calculate("", "KEY1=value1\nKEY2=value2\n")
    assert len(result.added) == 2
    assert "KEY1" in result.added
    assert "KEY2" in result.added

    # New is empty, old has keys
    result = calculator.calculate("KEY1=value1\nKEY2=value2\n", "")
    assert len(result.removed) == 2
    assert "KEY1" in result.removed
    assert "KEY2" in result.removed


def test_diff_ignores_comments_and_empty_lines():
    """Test that diff properly handles comments and empty lines."""
    old_content = """
# Comment
KEY1=value1

KEY2=value2
"""
    new_content = """
KEY1=value1
# Different comment
KEY2=value2

"""

    calculator = DiffCalculator()
    result = calculator.calculate(old_content, new_content)

    # Should be clean - only comments/whitespace changed
    assert result.is_clean()


def test_diff_handles_quoted_values():
    """Test that diff properly handles quoted values."""
    old_content = 'KEY1="value with spaces"\nKEY2=simple\n'
    new_content = 'KEY1="different value"\nKEY2=simple\n'

    calculator = DiffCalculator()
    result = calculator.calculate(old_content, new_content)

    assert len(result.modified) == 1
    assert "KEY1" in result.modified
    assert len(result.added) == 0
    assert len(result.removed) == 0
