"""Frontmatter transform factories for Obsidian Publisher.

These factories create transform functions that process note frontmatter
for output to various static site generators.
"""

import titlecase as tc
from typing import Any, Callable, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from obsidian_publisher.core.models import ProcessedNote

FrontmatterTransform = Callable[[Dict[str, Any], "ProcessedNote"], Dict[str, Any]]


def identity() -> FrontmatterTransform:
    """Create a pass-through transform that returns frontmatter unchanged.

    Returns:
        A transform function (frontmatter, processed) -> frontmatter
    """
    def transform(fm: Dict[str, Any], processed: "ProcessedNote") -> Dict[str, Any]:
        return fm.copy()
    return transform


def prune_and_add(
    keep_keys: Optional[List[str]] = None,
    remove_keys: Optional[List[str]] = None,
    add_fields: Optional[Dict[str, Any]] = None
) -> FrontmatterTransform:
    """Create a transform that prunes keys and/or adds fields.

    If keep_keys is provided, only those keys are kept.
    If remove_keys is provided (and keep_keys is not), those keys are removed.
    add_fields are always added/updated at the end.

    Args:
        keep_keys: List of keys to keep (exclusive with remove_keys)
        remove_keys: List of keys to remove
        add_fields: Dict of fields to add/update

    Returns:
        A transform function
    """
    def transform(fm: Dict[str, Any], processed: "ProcessedNote") -> Dict[str, Any]:
        if keep_keys is not None:
            result = {k: v for k, v in fm.items() if k in keep_keys}
        elif remove_keys is not None:
            result = {k: v for k, v in fm.items() if k not in remove_keys}
        else:
            result = fm.copy()

        if add_fields:
            result.update(add_fields)

        return result
    return transform


def hugo_frontmatter(author: Optional[str] = None) -> FrontmatterTransform:
    """Create a transform that produces standard Hugo frontmatter.

    Output includes: title, date, doc (creation date), author (optional), tags.
    Title is converted to proper title case using the titlecase library.

    Args:
        author: Author name to include in frontmatter

    Returns:
        A transform function for Hugo frontmatter
    """
    def transform(fm: Dict[str, Any], processed: "ProcessedNote") -> Dict[str, Any]:
        meta = processed.metadata
        # Semicolons in titles break YAML parsing, replace with colons
        title = tc.titlecase(meta.title).replace(';', ':')
        result: Dict[str, Any] = {
            'title': title,
            'date': meta.publication_date,
            'doc': meta.creation_date,
        }
        if author:
            result['author'] = author
        # Use processed.tags (transformed) not meta.tags (original)
        if processed.tags:
            result['tags'] = processed.tags
        return result
    return transform
