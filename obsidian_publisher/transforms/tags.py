"""Tag transform factories for Obsidian Publisher.

These factories create transform functions that filter and modify tag lists.
"""

from typing import Callable, List

TagTransform = Callable[[List[str]], List[str]]


def identity() -> TagTransform:
    """Create a pass-through transform that returns tags unchanged.

    Returns:
        A transform function tags -> tags
    """
    return lambda tags: tags


def filter_by_prefix(*prefixes: str) -> TagTransform:
    """Create a transform that keeps only tags with given prefixes.

    Args:
        *prefixes: One or more prefix strings to filter by

    Returns:
        A transform function that filters tags

    Example:
        >>> transform = filter_by_prefix("domain", "type")
        >>> transform(["domain/cs", "status/ok", "type/post"])
        ["domain/cs", "type/post"]
    """
    def transform(tags: List[str]) -> List[str]:
        return [t for t in tags if any(t.startswith(p) for p in prefixes)]
    return transform


def replace_separator(old: str = "/", new: str = "-") -> TagTransform:
    """Create a transform that replaces separators in tags.

    Useful for converting hierarchical tags to URL-safe formats.

    Args:
        old: The separator to replace (default: "/")
        new: The replacement separator (default: "-")

    Returns:
        A transform function that replaces separators

    Example:
        >>> transform = replace_separator("/", "-")
        >>> transform(["domain/cs/algo"])
        ["domain-cs-algo"]
    """
    def transform(tags: List[str]) -> List[str]:
        return [t.replace(old, new) for t in tags]
    return transform


def compose(*transforms: TagTransform) -> TagTransform:
    """Chain multiple tag transforms together.

    Transforms are applied in order, with each transform receiving
    the output of the previous one.

    Args:
        *transforms: Transform functions to chain

    Returns:
        A composite transform function

    Example:
        >>> transform = compose(
        ...     filter_by_prefix("domain"),
        ...     replace_separator("/", "-"),
        ...     sorted
        ... )
        >>> transform(["status/ok", "domain/b", "domain/a"])
        ["domain-a", "domain-b"]
    """
    def transform(tags: List[str]) -> List[str]:
        result = tags
        for t in transforms:
            result = t(result)
        return result
    return transform
