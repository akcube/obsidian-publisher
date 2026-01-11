"""Data models for Obsidian Publisher."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple


@dataclass
class NoteMetadata:
    """Metadata for an Obsidian note."""
    path: Path
    title: str
    slug: str
    frontmatter: Dict[str, Any]
    content: str
    tags: List[str]
    creation_date: str
    publication_date: str
    processed_tags: Optional[List[str]] = None


@dataclass
class ProcessedContent:
    """Result of processing markdown content."""
    content: str
    frontmatter: Dict[str, Any]
    referenced_images: List[str]
    missing_links: List[str]


@dataclass
class PublishResult:
    """Result of a publish operation."""
    published: List[str] = field(default_factory=list)
    failed: List[Tuple[str, str]] = field(default_factory=list)  # (name, error)
    orphans_removed: List[str] = field(default_factory=list)
    dry_run: bool = False
