"""Main publisher orchestrator."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set
import json
import shutil

import inflection

from obsidian_publisher.core.models import NoteMetadata, ProcessedContent, PublishResult
from obsidian_publisher.core.discovery import VaultDiscovery
from obsidian_publisher.core.processor import ContentProcessor, LinkIndex
from obsidian_publisher.images.optimizer import ImageOptimizer
from obsidian_publisher.transforms.links import LinkTransform, relative_link
from obsidian_publisher.transforms.tags import TagTransform
from obsidian_publisher.transforms.frontmatter import FrontmatterTransform


@dataclass
class PublisherConfig:
    """Configuration for Publisher."""

    vault_path: Path
    output_path: Path
    source_dir: str = "."
    content_dir: str = "content/posts"
    image_dir: str = "static/images"
    image_sources: List[str] = field(default_factory=lambda: ["assets"])
    required_tags: List[str] = field(default_factory=list)
    excluded_tags: List[str] = field(default_factory=list)
    link_index_path: Optional[Path] = None
    image_path_prefix: str = "/images"
    optimize_images: bool = True
    max_image_width: int = 1920
    webp_quality: int = 85
    enable_related_reading: bool = False
    link_prefix: str = ""


class Publisher:
    """Main orchestrator for publishing notes from Obsidian vault to static site.

    Coordinates:
    - VaultDiscovery: Finding and filtering publishable notes
    - ContentProcessor: Converting wikilinks, processing frontmatter
    - ImageOptimizer: Converting images to WebP with PNG fallback

    Provides operations:
    - republish(): Full republish of all eligible notes
    - add(note_name): Publish a specific note
    - delete(note_name): Remove a published note
    """

    def __init__(
        self,
        config: PublisherConfig,
        link_transform: Optional[LinkTransform] = None,
        tag_transform: Optional[TagTransform] = None,
        frontmatter_transform: Optional[FrontmatterTransform] = None,
    ):
        """Initialize Publisher.

        Args:
            config: PublisherConfig with paths and settings
            link_transform: Transform for converting links (default: relative_link)
            tag_transform: Optional transform for processing tags
            frontmatter_transform: Optional transform for processing frontmatter
        """
        self.config = config
        self.vault_path = Path(config.vault_path)
        self.output_path = Path(config.output_path)

        # Initialize components
        self.discovery = VaultDiscovery(
            vault_path=self.vault_path,
            source_dir=config.source_dir,
            required_tags=config.required_tags,
            excluded_tags=config.excluded_tags,
        )

        # Build link index
        self.link_index = self._build_link_index()

        # Initialize processor
        self.processor = ContentProcessor(
            link_index=self.link_index,
            link_transform=link_transform or relative_link(),
            tag_transform=tag_transform,
            frontmatter_transform=frontmatter_transform,
            image_path_prefix=config.image_path_prefix,
            output_image_extension=".webp" if config.optimize_images else None,
            enable_related_reading=config.enable_related_reading,
            link_prefix=config.link_prefix,
        )

        # Initialize image optimizer
        if config.optimize_images:
            self.optimizer = ImageOptimizer(
                max_width=config.max_image_width,
                webp_quality=config.webp_quality,
            )
        else:
            self.optimizer = None

        # Resolve image source directories
        self.image_sources = [
            self.vault_path / src for src in config.image_sources
        ]

        # Output directories
        self.content_output = self.output_path / config.content_dir
        self.image_output = self.output_path / config.image_dir

    def _build_link_index(self) -> LinkIndex:
        """Build or load the link index."""
        # Check for external link index file
        if self.config.link_index_path and self.config.link_index_path.exists():
            with open(self.config.link_index_path) as f:
                data = json.load(f)
                return LinkIndex.from_dict(data)

        # Build from vault
        notes = self.discovery.discover_all()
        return LinkIndex.from_notes(notes)

    def republish(self, dry_run: bool = False) -> PublishResult:
        """Full republish - discover all notes and publish them.

        Args:
            dry_run: If True, don't actually write files

        Returns:
            PublishResult with published notes and any failures
        """
        result = PublishResult(dry_run=dry_run)

        # Discover all publishable notes
        notes = self.discovery.discover_all()

        # Track all referenced images
        all_referenced_images: Set[str] = set()

        # Process each note
        for note in notes:
            try:
                processed = self._publish_note(note, dry_run)
                all_referenced_images.update(processed.referenced_images)
                result.published.append(note.title)
            except Exception as e:
                result.failed.append((note.title, str(e)))

        # Cleanup orphaned images
        if not dry_run and self.optimizer:
            orphans = self.optimizer.cleanup_orphans(
                self.image_output,
                all_referenced_images,
                dry_run=dry_run,
            )
            result.orphans_removed.extend(str(p) for p in orphans)

        return result

    def add(self, note_name: str, dry_run: bool = False) -> PublishResult:
        """Publish a specific note.

        Args:
            note_name: Name or path of the note to publish
            dry_run: If True, don't actually write files

        Returns:
            PublishResult for the operation
        """
        result = PublishResult(dry_run=dry_run)

        note = self.discovery.get_note(note_name)
        if note is None:
            result.failed.append((note_name, "Note not found"))
            return result

        # Check if publishable
        is_pub, reason = self.discovery.is_publishable(note)
        if not is_pub:
            result.failed.append((note_name, reason))
            return result

        try:
            self._publish_note(note, dry_run)
            result.published.append(note.title)
        except Exception as e:
            result.failed.append((note.title, str(e)))

        return result

    def delete(self, note_name: str, dry_run: bool = False) -> PublishResult:
        """Remove a published note and clean up orphaned images.

        Args:
            note_name: Name of the note to delete
            dry_run: If True, don't actually delete files

        Returns:
            PublishResult for the operation
        """
        result = PublishResult(dry_run=dry_run)

        # Get note info to determine slug
        note = self.discovery.get_note(note_name)
        if note is None:
            # Note might not exist in vault anymore, try to find by slug
            import inflection
            slug = inflection.parameterize(note_name)
        else:
            slug = note.slug

        # Find the published file
        published_file = self.content_output / f"{slug}.md"

        if not published_file.exists():
            result.failed.append((note_name, "Published file not found"))
            return result

        if not dry_run:
            published_file.unlink()

        result.published.append(note_name)

        # Collect all remaining referenced images
        all_referenced = self._collect_all_referenced_images()

        # Clean up orphans
        if self.optimizer:
            orphans = self.optimizer.cleanup_orphans(
                self.image_output,
                all_referenced,
                dry_run=dry_run,
            )
            result.orphans_removed.extend(str(p) for p in orphans)

        return result

    def _get_existing_frontmatter(self, slug: str) -> Optional[Dict]:
        """Get the frontmatter from an existing published file.

        Args:
            slug: The note slug

        Returns:
            The existing frontmatter dict, or None if not found
        """
        import yaml as yaml_lib

        output_file = self.content_output / f"{slug}.md"
        if not output_file.exists():
            return None

        try:
            content = output_file.read_text(encoding='utf-8')
            if content.startswith('---'):
                parts = content.split('---', 2)
                if len(parts) >= 2:
                    return yaml_lib.safe_load(parts[1])
        except Exception:
            pass

        return None

    def _format_date_value(self, date_val) -> Optional[str]:
        """Format a date value as a string.

        Args:
            date_val: Date value (string or datetime)

        Returns:
            Formatted date string
        """
        if isinstance(date_val, str):
            return date_val
        # Handle datetime objects
        import datetime
        if hasattr(date_val, 'strftime'):
            return date_val.strftime('%Y-%m-%d %H:%M:%S%z')
        return None

    def _publish_note(self, note: NoteMetadata, dry_run: bool) -> ProcessedContent:
        """Publish a single note.

        Args:
            note: NoteMetadata to publish
            dry_run: If True, don't write files

        Returns:
            ProcessedContent result
        """
        # Process content
        processed = self.processor.process(note)

        # Preserve existing date fields if available
        existing_fm = self._get_existing_frontmatter(note.slug)
        if existing_fm:
            for field in ('date', 'doc'):
                if field in existing_fm and field in processed.frontmatter:
                    formatted = self._format_date_value(existing_fm[field])
                    if formatted:
                        processed.frontmatter[field] = formatted

        # Build output
        output_content = self.processor.build_output(processed)

        # Write content file
        if not dry_run:
            self.content_output.mkdir(parents=True, exist_ok=True)
            output_file = self.content_output / f"{note.slug}.md"
            output_file.write_text(output_content, encoding='utf-8')

        # Process referenced images
        for image_name in processed.referenced_images:
            self._process_image(image_name, dry_run)

        return processed

    def _process_image(self, image_name: str, dry_run: bool) -> None:
        """Process and copy an image to the output directory.

        Args:
            image_name: Name of the image file
            dry_run: If True, don't write files
        """
        # Find the source image
        source_path = self._find_image(image_name)
        if source_path is None:
            print(f"Warning: Image not found: {image_name}")
            return

        if dry_run:
            return

        if self.optimizer:
            # Slugify the output name to match markdown references
            output_name = inflection.parameterize(Path(image_name).stem)
            # Optimize and create WebP + PNG versions
            self.optimizer.optimize(
                source_path,
                self.image_output,
                output_name=output_name,
            )
        else:
            # Just copy the original
            self.image_output.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_path, self.image_output / image_name)

    def _find_image(self, image_name: str) -> Optional[Path]:
        """Find an image in the configured source directories.

        Args:
            image_name: Name of the image file

        Returns:
            Path to the image or None if not found
        """
        for source_dir in self.image_sources:
            candidate = source_dir / image_name
            if candidate.exists():
                return candidate

        # Also check vault root
        candidate = self.vault_path / image_name
        if candidate.exists():
            return candidate

        return None

    def _collect_all_referenced_images(self) -> Set[str]:
        """Collect all images referenced by currently published notes.

        Returns:
            Set of image basenames still in use
        """
        referenced = set()

        if not self.content_output.exists():
            return referenced

        for md_file in self.content_output.glob("*.md"):
            content = md_file.read_text(encoding='utf-8')
            # Simple regex to find image references
            import re
            # Match markdown image syntax: ![alt](/images/name.ext)
            for match in re.finditer(r'!\[[^\]]*\]\([^)]+/([^/)]+)\)', content):
                referenced.add(match.group(1))

        return referenced


def create_publisher_from_config(config_path: Path) -> Publisher:
    """Create a Publisher from a YAML config file.

    Args:
        config_path: Path to config.yaml

    Returns:
        Configured Publisher instance
    """
    import yaml

    with open(config_path) as f:
        raw_config = yaml.safe_load(f)

    # Parse paths
    vault_path = Path(raw_config['vault_path']).expanduser()
    output_path = Path(raw_config['output_path']).expanduser()

    # Get link prefix for related reading section
    link_config = raw_config.get('link_transform', {})
    link_prefix = link_config.get('prefix', '')

    # Get features config
    features_config = raw_config.get('features', {})

    config = PublisherConfig(
        vault_path=vault_path,
        output_path=output_path,
        source_dir=raw_config.get('source_dir', '.'),
        content_dir=raw_config.get('content_dir', 'content/posts'),
        image_dir=raw_config.get('image_dir', 'static/images'),
        image_sources=raw_config.get('image_sources', ['assets']),
        required_tags=raw_config.get('required_tags', []),
        excluded_tags=raw_config.get('excluded_tags', []),
        image_path_prefix=raw_config.get('image_path_prefix', '/images'),
        optimize_images=raw_config.get('optimize_images', True),
        max_image_width=raw_config.get('max_image_width', 1920),
        webp_quality=raw_config.get('webp_quality', 85),
        enable_related_reading=features_config.get('enable_related_reading', False),
        link_prefix=link_prefix,
    )

    # Build transforms based on config
    link_transform = None
    tag_transform = None
    frontmatter_transform = None

    # Link transform
    link_config = raw_config.get('link_transform', {})
    link_type = link_config.get('type', 'relative')
    if link_type == 'absolute':
        from obsidian_publisher.transforms.links import absolute_link
        link_transform = absolute_link(link_config.get('prefix', ''))
    elif link_type == 'hugo_ref':
        from obsidian_publisher.transforms.links import hugo_ref
        link_transform = hugo_ref()
    else:
        link_transform = relative_link()

    # Tag transform
    tag_config = raw_config.get('tag_transform', {})
    if tag_config:
        from obsidian_publisher.transforms.tags import filter_by_prefix, replace_separator, sort_tags, compose
        transforms = []
        if 'prefixes' in tag_config:
            transforms.append(filter_by_prefix(*tag_config['prefixes']))
        if 'replace_separator' in tag_config:
            old, new = tag_config['replace_separator']
            transforms.append(replace_separator(old, new))
        # Always sort tags at the end
        transforms.append(sort_tags())
        if transforms:
            tag_transform = compose(*transforms)

    # Frontmatter transform
    fm_config = raw_config.get('frontmatter', {})
    if fm_config.get('hugo', False):
        from obsidian_publisher.transforms.frontmatter import hugo_frontmatter
        frontmatter_transform = hugo_frontmatter(fm_config.get('author'))

    return Publisher(
        config=config,
        link_transform=link_transform,
        tag_transform=tag_transform,
        frontmatter_transform=frontmatter_transform,
    )
