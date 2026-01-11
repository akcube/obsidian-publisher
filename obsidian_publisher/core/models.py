"""Data models for Obsidian Publisher."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class NoteContext:
    """Cheapest possible note reference - just location.

    Provides lazy content loading to avoid reading all notes into memory
    during discovery.
    """
    path: Path

    def read_raw(self) -> str:
        """Read file contents on demand."""
        return self.path.read_text(encoding='utf-8')


@dataclass
class NoteMetadata:
    """Parsed note metadata - what we learn from reading the file once.

    Does NOT store content - get it via context.read_raw() when needed.
    Does NOT store processed_tags - that belongs in ProcessedNote.
    """
    context: NoteContext
    title: str
    slug: str
    frontmatter: Dict[str, Any]
    tags: List[str]
    creation_date: str
    publication_date: str

    @property
    def path(self) -> Path:
        """Convenience accessor for the note's path."""
        return self.context.path


@dataclass
class ProcessedNote:
    """Result of transforming a note for publishing.

    Contains the transformed content, frontmatter, and tags,
    along with a reference to the original metadata.
    """
    metadata: NoteMetadata
    content: str
    frontmatter: Dict[str, Any]
    tags: List[str]
    referenced_images: List[str]
    missing_links: List[str]


@dataclass
class PublishResult:
    """Result of a publish operation."""
    published: List[str] = field(default_factory=list)
    failed: List[Tuple[str, str]] = field(default_factory=list)  # (name, error)
    orphans_removed: List[str] = field(default_factory=list)
    dry_run: bool = False
