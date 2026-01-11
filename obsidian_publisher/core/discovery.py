"""Vault discovery module for finding publishable notes."""

from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
import yaml
import inflection
import datetime

from obsidian_publisher.core.models import NoteContext, NoteMetadata


class VaultDiscovery:
    """Discovers and filters notes eligible for publishing from an Obsidian vault."""

    def __init__(
        self,
        vault_path: Path,
        source_dirs: Optional[List[str]] = None,
        required_tags: Optional[List[str]] = None,
        excluded_tags: Optional[List[str]] = None,
    ):
        """Initialize VaultDiscovery.

        Args:
            vault_path: Path to the Obsidian vault root
            source_dirs: Subdirectories within vault to scan (default: vault root)
            required_tags: Tags that must be present for a note to be publishable
            excluded_tags: Tags that exclude a note from publishing
        """
        self.vault_path = Path(vault_path)
        self.source_dirs = [
            self.vault_path / d for d in (source_dirs or ["."])
        ]
        self.required_tags = set(required_tags or [])
        self.excluded_tags = set(excluded_tags or [])

    def discover_all(self) -> List[NoteMetadata]:
        """Find all publishable notes in the vault.

        Returns:
            List of NoteMetadata for all notes passing the tag filters
        """
        existing_dirs = [d for d in self.source_dirs if d.exists()]

        for d in self.source_dirs:
            if not d.exists():
                print(f"Warning: Source directory not found: {d}")

        if not existing_dirs:
            dirs = ', '.join(str(d) for d in self.source_dirs)
            raise FileNotFoundError(f"No source directories found: {dirs}")

        publishable = []
        for source_dir in existing_dirs:
            for note_path in source_dir.glob("*.md"):
                metadata = self._get_note_metadata(note_path)
                if metadata is None:
                    continue

                is_pub, _ = self.is_publishable(metadata)
                if is_pub:
                    publishable.append(metadata)

        return publishable

    def get_note(self, name_or_path: str) -> Optional[NoteMetadata]:
        """Get a single note by name or path.

        Args:
            name_or_path: Note title, filename (with or without .md), or full path

        Returns:
            NoteMetadata if found, None otherwise
        """
        # Try as full path first
        path = Path(name_or_path)
        if path.exists() and path.suffix == '.md':
            return self._get_note_metadata(path)

        stem = Path(name_or_path).stem
        filename = f"{stem}.md"
        search_name = stem.lower()

        # Search all source directories
        for source_dir in self.source_dirs:
            if not source_dir.exists():
                continue

            # Try as filename in source_dir
            note_path = source_dir / filename
            if note_path.exists():
                return self._get_note_metadata(note_path)

            # Try to find by title match
            for note_path in source_dir.glob("*.md"):
                metadata = self._get_note_metadata(note_path)
                if metadata and metadata.title.lower() == search_name:
                    return metadata

        return None

    def is_publishable(self, note: NoteMetadata) -> Tuple[bool, str]:
        """Check if a note meets publishing criteria.

        Args:
            note: NoteMetadata to check

        Returns:
            Tuple of (is_publishable, reason)
        """
        note_tags = set(note.tags)

        if self.required_tags and not self.required_tags.intersection(note_tags):
            missing = ', '.join(self.required_tags)
            return False, f"Missing required tags: {missing}"

        excluded_found = self.excluded_tags.intersection(note_tags)
        if excluded_found:
            found = ', '.join(excluded_found)
            return False, f"Contains excluded tags: {found}"

        return True, "OK"

    def _get_note_metadata(self, file_path: Path) -> Optional[NoteMetadata]:
        """Parse a note file and extract metadata.

        Note: Content is NOT stored in NoteMetadata. Use context.read_raw()
        when content is needed during processing.

        Args:
            file_path: Path to the markdown file

        Returns:
            NoteMetadata or None if parsing fails
        """
        try:
            context = NoteContext(path=file_path)
            frontmatter = self._parse_frontmatter(file_path)
            tags = self._extract_tags(frontmatter)
            title = frontmatter.get('title', file_path.stem)
            slug = inflection.parameterize(title)
            creation_date = self._get_date_string(frontmatter.get('created'))
            publication_date = self._get_date_string(frontmatter.get('date'))

            return NoteMetadata(
                context=context,
                title=title,
                slug=slug,
                frontmatter=frontmatter,
                tags=tags,
                creation_date=creation_date,
                publication_date=publication_date,
            )
        except Exception as e:
            print(f"Warning: Failed to parse {file_path.name}: {e}")
            return None

    def _parse_frontmatter(self, file_path: Path) -> Dict:
        """Parse YAML frontmatter from markdown file.

        Args:
            file_path: Path to the markdown file

        Returns:
            Frontmatter dict (empty if not found or invalid)
        """
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        if not content.startswith('---'):
            return {}

        try:
            parts = content.split('---\n', 2)
            if len(parts) < 3:
                return {}

            frontmatter = yaml.safe_load(parts[1])
            if not isinstance(frontmatter, dict):
                return {}

            return frontmatter

        except yaml.YAMLError as e:
            print(f"Warning: Failed to parse YAML in {file_path.name}: {e}")
            return {}

    def _extract_tags(self, frontmatter: Dict) -> List[str]:
        """Extract all tags from frontmatter.

        Handles both list and string formats.

        Args:
            frontmatter: Parsed frontmatter dict

        Returns:
            List of tag strings
        """
        tags = []

        if 'tags' in frontmatter:
            tag_data = frontmatter['tags']
            if isinstance(tag_data, list):
                tags.extend(str(tag) for tag in tag_data)
            elif isinstance(tag_data, str):
                tags.append(tag_data)

        return tags

    def _get_date_string(self, date_value) -> str:
        """Convert various date formats to string.

        Args:
            date_value: Date in various formats (str, datetime, date, None)

        Returns:
            Date string or empty string
        """
        if date_value is None:
            return ""

        if isinstance(date_value, str):
            return date_value

        if isinstance(date_value, datetime.datetime):
            return date_value.strftime('%Y-%m-%d %H:%M:%S%z')

        if isinstance(date_value, datetime.date):
            return date_value.strftime('%Y-%m-%d')

        return str(date_value)
