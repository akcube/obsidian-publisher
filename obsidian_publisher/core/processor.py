"""Content processor for transforming Obsidian notes."""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, List, Optional, Set
import inflection
import yaml

from obsidian_publisher.core.models import NoteMetadata, ProcessedNote
from obsidian_publisher.transforms.links import LinkTransform
from obsidian_publisher.transforms.tags import TagTransform
from obsidian_publisher.transforms.frontmatter import FrontmatterTransform


@dataclass
class LinkIndex:
    """Index mapping note titles to their slugs."""

    title_to_slug: Dict[str, str]
    slug_to_title: Dict[str, str]

    @classmethod
    def from_notes(cls, notes: List[NoteMetadata]) -> "LinkIndex":
        """Build a link index from a list of notes."""
        title_to_slug = {}
        slug_to_title = {}

        for note in notes:
            title_to_slug[note.title.lower()] = note.slug
            slug_to_title[note.slug] = note.title

        return cls(title_to_slug, slug_to_title)

    @classmethod
    def from_dict(cls, data: Dict[str, str]) -> "LinkIndex":
        """Build a link index from a title->slug dictionary."""
        title_to_slug = {k.lower(): v for k, v in data.items()}
        slug_to_title = {v: k for k, v in data.items()}
        return cls(title_to_slug, slug_to_title)

    def get_slug(self, title: str) -> Optional[str]:
        """Get slug for a title, case-insensitive."""
        return self.title_to_slug.get(title.lower())


class ContentProcessor:
    """Processes Obsidian note content for publishing.

    Handles:
    - Wikilink to markdown link conversion
    - Image reference extraction
    - Tag transformation
    - Frontmatter transformation
    """

    # Pattern for wikilinks: [[target]] or [[target|display]]
    WIKILINK_PATTERN = re.compile(r'\[\[([^\]|]+)(?:\|([^\]]+))?\]\]')

    # Pattern for image embeds: ![[image.png]] or ![[image.png|alt]]
    IMAGE_EMBED_PATTERN = re.compile(r'!\[\[([^\]|]+\.(?:png|jpg|jpeg|gif|webp|svg))(?:\|([^\]]+))?\]\]', re.IGNORECASE)

    # Pattern for generic embeds (notes): ![[note]]
    NOTE_EMBED_PATTERN = re.compile(r'!\[\[([^\]|]+)(?:\|([^\]]+))?\]\]')

    def __init__(
        self,
        link_index: LinkIndex,
        link_transform: LinkTransform,
        tag_transform: Optional[TagTransform] = None,
        frontmatter_transform: Optional[FrontmatterTransform] = None,
        image_path_prefix: str = "/images",
        warn_on_missing_link: bool = True,
        output_image_extension: Optional[str] = None,
    ):
        """Initialize ContentProcessor.

        Args:
            link_index: Index mapping note titles to slugs
            link_transform: Transform for converting links
            tag_transform: Optional transform for processing tags
            frontmatter_transform: Optional transform for processing frontmatter
            image_path_prefix: Prefix for image URLs in output
            warn_on_missing_link: Whether to warn about unresolved wikilinks
            output_image_extension: Extension for output images (e.g., ".webp").
                                   If None, keeps original extension.
        """
        self.link_index = link_index
        self.link_transform = link_transform
        self.tag_transform = tag_transform
        self.frontmatter_transform = frontmatter_transform
        self.image_path_prefix = image_path_prefix.rstrip('/')
        self.warn_on_missing_link = warn_on_missing_link
        self.output_image_extension = output_image_extension

    def process(self, note: NoteMetadata) -> ProcessedNote:
        """Process a note's content for publishing.

        Reads content lazily via note.context.read_raw().

        Args:
            note: The note metadata to process

        Returns:
            ProcessedNote with transformed content and metadata
        """
        raw_content = note.context.read_raw()
        content = self._extract_content(raw_content)

        referenced_images: Set[str] = set()
        missing_links: List[str] = []

        # Images must be processed before wikilinks to avoid double-processing
        content, images = self._process_images(content)
        referenced_images.update(images)

        content, missing = self._process_wikilinks(content)
        missing_links.extend(missing)

        processed_tags = note.tags.copy()
        if self.tag_transform:
            processed_tags = self.tag_transform(note.tags)

        processed = ProcessedNote(
            metadata=note,
            content=content,
            frontmatter=note.frontmatter.copy(),
            tags=processed_tags,
            referenced_images=list(referenced_images),
            missing_links=missing_links,
        )

        if self.frontmatter_transform:
            processed.frontmatter = self.frontmatter_transform(
                note.frontmatter.copy(), processed
            )

        return processed

    def _extract_content(self, raw_content: str) -> str:
        """Extract content after frontmatter.

        Args:
            raw_content: Full file content including frontmatter

        Returns:
            Content without frontmatter
        """
        if not raw_content.startswith('---'):
            return raw_content

        parts = raw_content.split('---\n', 2)
        if len(parts) >= 3:
            return parts[2]
        return raw_content

    def _process_images(self, content: str) -> tuple[str, Set[str]]:
        """Process image embeds in content.

        Args:
            content: Note content

        Returns:
            Tuple of (transformed content, set of image filenames)
        """
        images = set()

        def replace_image(match: re.Match) -> str:
            image_name = match.group(1)
            alt_text = match.group(2) or Path(image_name).stem
            images.add(image_name)

            stem = Path(image_name).stem
            slug = inflection.parameterize(stem)
            ext = self.output_image_extension or Path(image_name).suffix.lower()
            alt_slug = inflection.parameterize(alt_text)

            return f"![{alt_slug}]({self.image_path_prefix}/{slug}{ext})"

        result = self.IMAGE_EMBED_PATTERN.sub(replace_image, content)
        return result, images

    def _process_wikilinks(self, content: str) -> tuple[str, List[str]]:
        """Process wikilinks in content.

        Args:
            content: Note content

        Returns:
            Tuple of (transformed content, list of missing link targets)
        """
        missing_links = []

        def replace_link(match: re.Match) -> str:
            target = match.group(1).strip()
            display = match.group(2)

            # Handle image links that weren't caught by IMAGE_EMBED_PATTERN (e.g., [[image.png]] without !)
            if any(target.lower().endswith(ext) for ext in ('.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg')):
                alt_text = display or Path(target).stem
                stem = Path(target).stem
                slug = inflection.parameterize(stem)
                ext = self.output_image_extension or Path(target).suffix.lower()
                alt_slug = inflection.parameterize(alt_text)
                return f"![{alt_slug}]({self.image_path_prefix}/{slug}{ext})"

            section = ""
            note_target = target
            if "#" in target:
                note_target, section = target.split("#", 1)
                note_target = note_target.strip()

            slug = self.link_index.get_slug(note_target)
            if slug is None:
                slug = inflection.parameterize(note_target)
                if self.warn_on_missing_link:
                    missing_links.append(note_target)

            link_text = display or note_target
            result = self.link_transform(link_text, slug)

            # Append section anchor by inserting before closing paren
            if section and ")" in result:
                section_slug = inflection.parameterize(section)
                result = result[:-1] + f"#{section_slug})"

            return result

        result = self.WIKILINK_PATTERN.sub(replace_link, content)
        return result, missing_links

    def build_output(self, processed: ProcessedNote) -> str:
        """Build final markdown output with frontmatter.

        Args:
            processed: Processed note

        Returns:
            Complete markdown string with YAML frontmatter
        """
        if processed.frontmatter:
            frontmatter_str = yaml.dump(
                processed.frontmatter,
                default_flow_style=False,
                allow_unicode=True,
                sort_keys=True,
            )
            content = processed.content.rstrip('\n')
            return f"---\n{frontmatter_str}---\n{content}\n"
        else:
            return processed.content.rstrip('\n') + "\n"
