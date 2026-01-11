"""Transform protocols and factories for Obsidian Publisher.

This module defines the transform type aliases and exports factory functions
for creating transforms.

Type Aliases:
    LinkTransform: Callable[[str, str], str]
        Takes (title, slug) and returns a markdown link string.

    TagTransform: Callable[[List[str]], List[str]]
        Takes a list of tags and returns a transformed list.

    FrontmatterTransform: Callable[[Dict[str, Any], NoteMetadata], Dict[str, Any]]
        Takes (original_frontmatter, note_metadata) and returns transformed frontmatter.
"""

from typing import Any, Callable, Dict, List, TYPE_CHECKING

if TYPE_CHECKING:
    from obsidian_publisher.core.models import NoteMetadata

# Transform type aliases
LinkTransform = Callable[[str, str], str]
"""Transform function for wikilinks: (title, slug) -> markdown_link"""

TagTransform = Callable[[List[str]], List[str]]
"""Transform function for tags: tags -> transformed_tags"""

FrontmatterTransform = Callable[[Dict[str, Any], "NoteMetadata"], Dict[str, Any]]
"""Transform function for frontmatter: (frontmatter, metadata) -> transformed_frontmatter"""

# Import factory functions for convenience
from obsidian_publisher.transforms.links import (
    relative_link,
    absolute_link,
    hugo_ref,
)
from obsidian_publisher.transforms.tags import (
    identity as tag_identity,
    filter_by_prefix,
    replace_separator,
    compose as tag_compose,
)
from obsidian_publisher.transforms.frontmatter import (
    identity as frontmatter_identity,
    prune_and_add,
    hugo_frontmatter,
)

__all__ = [
    # Type aliases
    "LinkTransform",
    "TagTransform",
    "FrontmatterTransform",
    # Link transforms
    "relative_link",
    "absolute_link",
    "hugo_ref",
    # Tag transforms
    "tag_identity",
    "filter_by_prefix",
    "replace_separator",
    "tag_compose",
    # Frontmatter transforms
    "frontmatter_identity",
    "prune_and_add",
    "hugo_frontmatter",
]
