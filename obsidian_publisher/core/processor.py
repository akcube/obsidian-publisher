"""Content processor for transforming Obsidian notes."""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, List, Optional, Set
import inflection
import yaml

from obsidian_publisher.core.models import NoteMetadata, ProcessedContent
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

    def process(self, note: NoteMetadata) -> ProcessedContent:
        """Process a note's content for publishing.

        Args:
            note: The note metadata to process

        Returns:
            ProcessedContent with transformed content and metadata
        """
        content = note.content
        referenced_images: Set[str] = set()
        missing_links: List[str] = []

        # Extract and transform images first
        content, images = self._process_images(content)
        referenced_images.update(images)

        # Convert wikilinks to markdown links
        content, missing = self._process_wikilinks(content)
        missing_links.extend(missing)

        # Process tags
        processed_tags = None
        if self.tag_transform:
            processed_tags = self.tag_transform(note.tags)

        # Create updated note with processed tags for frontmatter transform
        note_with_tags = NoteMetadata(
            path=note.path,
            title=note.title,
            slug=note.slug,
            frontmatter=note.frontmatter,
            content=note.content,
            tags=note.tags,
            creation_date=note.creation_date,
            publication_date=note.publication_date,
            processed_tags=processed_tags,
        )

        # Process frontmatter
        new_frontmatter = note.frontmatter.copy()
        if self.frontmatter_transform:
            new_frontmatter = self.frontmatter_transform(new_frontmatter, note_with_tags)

        return ProcessedContent(
            content=content,
            frontmatter=new_frontmatter,
            referenced_images=list(referenced_images),
            missing_links=missing_links,
        )

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

            # Slugify the filename stem
            stem = Path(image_name).stem
            slug = inflection.parameterize(stem)

            # Determine output extension
            if self.output_image_extension:
                ext = self.output_image_extension
            else:
                ext = Path(image_name).suffix.lower()

            # Slugify alt text too
            alt_slug = inflection.parameterize(alt_text)

            # Convert to markdown image syntax
            image_url = f"{self.image_path_prefix}/{slug}{ext}"
            return f"![{alt_slug}]({image_url})"

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

        # First, skip image embeds (already processed)
        # Process only non-image wikilinks
        def replace_link(match: re.Match) -> str:
            target = match.group(1).strip()
            display = match.group(2)

            # Skip if this looks like an image (should have been handled)
            if any(target.lower().endswith(ext) for ext in ('.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg')):
                # This is an image that wasn't caught - convert it
                alt_text = display or Path(target).stem
                stem = Path(target).stem
                slug = inflection.parameterize(stem)
                if self.output_image_extension:
                    ext = self.output_image_extension
                else:
                    ext = Path(target).suffix.lower()
                alt_slug = inflection.parameterize(alt_text)
                image_url = f"{self.image_path_prefix}/{slug}{ext}"
                return f"![{alt_slug}]({image_url})"

            # Handle section links (e.g., [[Note#Section]])
            section = ""
            if "#" in target:
                target, section = target.split("#", 1)
                target = target.strip()

            # Look up the slug
            slug = self.link_index.get_slug(target)

            if slug is None:
                # Try generating slug from target
                slug = inflection.parameterize(target)
                if self.warn_on_missing_link:
                    missing_links.append(target)

            # Use display text or original target
            link_text = display or target

            # Apply link transform
            result = self.link_transform(link_text, slug)

            # Add section anchor if present
            if section:
                # Find the URL in the result and append anchor
                # This handles various link formats
                section_slug = inflection.parameterize(section)
                if ")" in result:
                    result = result[:-1] + f"#{section_slug})"

            return result

        result = self.WIKILINK_PATTERN.sub(replace_link, content)
        return result, missing_links

    def build_output(self, processed: ProcessedContent) -> str:
        """Build final markdown output with frontmatter.

        Args:
            processed: Processed content

        Returns:
            Complete markdown string with YAML frontmatter
        """
        # Build YAML frontmatter
        if processed.frontmatter:
            frontmatter_str = yaml.dump(
                processed.frontmatter,
                default_flow_style=False,
                allow_unicode=True,
                sort_keys=True,
            )
            return f"---\n{frontmatter_str}---\n{processed.content}"
        else:
            return processed.content
