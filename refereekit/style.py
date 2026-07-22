from pathlib import Path


def load_style(path: str) -> str:
    """
    Load the style guide from a file.

    Args:
        path: Path to the style guide file.

    Returns:
        The content of the style guide as a string.

    Raises:
        FileNotFoundError: If the file does not exist.
    """
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"Style guide not found: {path}")
    return file_path.read_text()
