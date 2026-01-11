"""
Obsidian Publisher - Publish Obsidian notes to static site generators

A modular, configurable library for converting Obsidian vault notes
to various static site generator formats with support for:
- Wikilink conversion
- Hierarchical tag processing
- Image optimization
- Frontmatter transformation
"""

from obsidian_publisher.core.models import NoteContext, NoteError, NoteMetadata, ProcessedNote, PublishResult
from obsidian_publisher.core.discovery import VaultDiscovery
from obsidian_publisher.core.processor import ContentProcessor
from obsidian_publisher.core.publisher import Publisher
from obsidian_publisher.images.optimizer import ImageOptimizer

__version__ = "0.1.0"

__all__ = [
    "NoteContext",
    "NoteError",
    "NoteMetadata",
    "ProcessedNote",
    "PublishResult",
    "VaultDiscovery",
    "ContentProcessor",
    "Publisher",
    "ImageOptimizer",
]
