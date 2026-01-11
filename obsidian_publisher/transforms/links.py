"""Link transform factories for Obsidian Publisher.

These factories create transform functions that convert wikilinks
to various output formats.
"""

from typing import Callable

LinkTransform = Callable[[str, str], str]


def relative_link() -> LinkTransform:
    """Create a transform that produces relative markdown links.

    SSG-agnostic format: [[Note]] -> [Note](note-title.md)

    Returns:
        A transform function (title, slug) -> markdown_link
    """
    def transform(title: str, slug: str) -> str:
        return f'[{title}]({slug}.md)'
    return transform


def absolute_link(prefix: str = "") -> LinkTransform:
    """Create a transform that produces absolute path links.

    Format: [[Note]] -> [Note](/prefix/note-title)

    Args:
        prefix: URL path prefix (e.g., "/blog")

    Returns:
        A transform function (title, slug) -> markdown_link
    """
    def transform(title: str, slug: str) -> str:
        if prefix:
            path = f'{prefix}/{slug}'
        else:
            path = f'/{slug}'
        return f'[{title}]({path})'
    return transform


def hugo_ref() -> LinkTransform:
    """Create a transform that produces Hugo ref shortcode links.

    Format: [[Note]] -> [Note]({{< ref "note-title" >}})

    Returns:
        A transform function (title, slug) -> markdown_link
    """
    def transform(title: str, slug: str) -> str:
        return f'[{title}]({{{{< ref "{slug}" >}}}})'
    return transform
