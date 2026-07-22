import pytest
from pathlib import Path
from refereekit.style import load_style


def test_load_style_returns_string():
    """load_style returns the file content as a string."""
    style_path = Path(__file__).parent.parent / "style" / "STYLE.md"
    result = load_style(str(style_path))
    assert isinstance(result, str)


def test_load_style_content_over_200_chars():
    """Loaded style guide is substantial (over 200 chars)."""
    style_path = Path(__file__).parent.parent / "style" / "STYLE.md"
    result = load_style(str(style_path))
    assert len(result) > 200


def test_load_style_contains_required_phrase():
    """Loaded style guide contains the required phrase."""
    style_path = Path(__file__).parent.parent / "style" / "STYLE.md"
    result = load_style(str(style_path))
    assert "The authors may consider" in result


def test_load_style_raises_file_not_found():
    """load_style raises FileNotFoundError for missing file."""
    with pytest.raises(FileNotFoundError):
        load_style("/nonexistent/path/to/style.md")
