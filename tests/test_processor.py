"""Tests for ContentProcessor class."""

import pytest
from pathlib import Path
import tempfile
import shutil

from obsidian_publisher.core.processor import ContentProcessor, LinkIndex
from obsidian_publisher.core.models import NoteContext, NoteMetadata
from obsidian_publisher.transforms.links import relative_link, absolute_link, hugo_ref
from obsidian_publisher.transforms.tags import filter_by_prefix, replace_separator, compose
from obsidian_publisher.transforms.frontmatter import hugo_frontmatter


class TestLinkIndex:
    """Tests for LinkIndex class."""

    def test_from_notes(self, tmp_path):
        # Create temporary files for NoteContext
        (tmp_path / "note1.md").write_text("---\ntitle: First Note\n---\nContent")
        (tmp_path / "note2.md").write_text("---\ntitle: Second Note\n---\nContent")

        notes = [
            NoteMetadata(
                context=NoteContext(path=tmp_path / "note1.md"),
                title="First Note",
                slug="first-note",
                frontmatter={},
                tags=[],
                creation_date="",
                publication_date="",
            ),
            NoteMetadata(
                context=NoteContext(path=tmp_path / "note2.md"),
                title="Second Note",
                slug="second-note",
                frontmatter={},
                tags=[],
                creation_date="",
                publication_date="",
            ),
        ]

        index = LinkIndex.from_notes(notes)

        assert index.get_slug("First Note") == "first-note"
        assert index.get_slug("Second Note") == "second-note"

    def test_from_dict(self):
        data = {
            "My Note": "my-note",
            "Another Note": "another-note",
        }

        index = LinkIndex.from_dict(data)

        assert index.get_slug("My Note") == "my-note"
        assert index.get_slug("Another Note") == "another-note"

    def test_case_insensitive(self):
        index = LinkIndex.from_dict({"My Note": "my-note"})

        assert index.get_slug("my note") == "my-note"
        assert index.get_slug("MY NOTE") == "my-note"
        assert index.get_slug("My Note") == "my-note"

    def test_missing_slug(self):
        index = LinkIndex.from_dict({"My Note": "my-note"})

        assert index.get_slug("Nonexistent") is None


class TestContentProcessor:
    """Tests for ContentProcessor class."""

    @pytest.fixture
    def temp_dir(self):
        temp_dir = tempfile.mkdtemp()
        yield Path(temp_dir)
        shutil.rmtree(temp_dir)

    @pytest.fixture
    def link_index(self):
        return LinkIndex.from_dict({
            "First Note": "first-note",
            "Second Note": "second-note",
            "Note With Spaces": "note-with-spaces",
        })

    def _create_note(self, temp_dir: Path, content: str, title: str = "Test Note") -> NoteMetadata:
        """Helper to create a NoteMetadata with a real file."""
        frontmatter = f"""---
title: {title}
tags:
  - domain/cs
  - evergreen
created: 2024-01-01 00:00:00+0000
date: 2024-01-15 00:00:00+0000
---
"""
        file_path = temp_dir / f"{title.lower().replace(' ', '-')}.md"
        file_path.write_text(frontmatter + content)

        return NoteMetadata(
            context=NoteContext(path=file_path),
            title=title,
            slug=title.lower().replace(' ', '-'),
            frontmatter={"original": "data"},
            tags=["domain/cs", "evergreen"],
            creation_date="2024-01-01 00:00:00+0000",
            publication_date="2024-01-15 00:00:00+0000",
        )

    def test_simple_wikilink_conversion(self, link_index, temp_dir):
        processor = ContentProcessor(
            link_index=link_index,
            link_transform=relative_link(),
        )
        note = self._create_note(temp_dir, "Check out [[First Note]] for more info.")

        result = processor.process(note)

        assert "[First Note](first-note.md)" in result.content

    def test_wikilink_with_display_text(self, link_index, temp_dir):
        processor = ContentProcessor(
            link_index=link_index,
            link_transform=relative_link(),
        )
        note = self._create_note(temp_dir, "See [[First Note|this article]] here.")

        result = processor.process(note)

        assert "[this article](first-note.md)" in result.content

    def test_wikilink_with_absolute_link_transform(self, link_index, temp_dir):
        processor = ContentProcessor(
            link_index=link_index,
            link_transform=absolute_link("/blog"),
        )
        note = self._create_note(temp_dir, "Read [[First Note]].")

        result = processor.process(note)

        assert "[First Note](/blog/first-note)" in result.content

    def test_wikilink_with_hugo_ref_transform(self, link_index, temp_dir):
        processor = ContentProcessor(
            link_index=link_index,
            link_transform=hugo_ref(),
        )
        note = self._create_note(temp_dir, "Read [[First Note]].")

        result = processor.process(note)

        assert '[First Note]({{< ref "first-note" >}})' in result.content

    def test_multiple_wikilinks(self, link_index, temp_dir):
        processor = ContentProcessor(
            link_index=link_index,
            link_transform=relative_link(),
        )
        note = self._create_note(temp_dir, "See [[First Note]] and [[Second Note]].")

        result = processor.process(note)

        assert "[First Note](first-note.md)" in result.content
        assert "[Second Note](second-note.md)" in result.content

    def test_missing_link_tracked(self, link_index, temp_dir):
        processor = ContentProcessor(
            link_index=link_index,
            link_transform=relative_link(),
            warn_on_missing_link=True,
        )
        note = self._create_note(temp_dir, "See [[Nonexistent Note]].")

        result = processor.process(note)

        assert "Nonexistent Note" in result.missing_links
        # Should still generate a link using the parameterized slug
        assert "[Nonexistent Note](nonexistent-note.md)" in result.content

    def test_section_link(self, link_index, temp_dir):
        processor = ContentProcessor(
            link_index=link_index,
            link_transform=relative_link(),
        )
        note = self._create_note(temp_dir, "See [[First Note#Introduction]].")

        result = processor.process(note)

        assert "[First Note](first-note.md#introduction)" in result.content

    def test_section_link_with_display_text(self, link_index, temp_dir):
        processor = ContentProcessor(
            link_index=link_index,
            link_transform=relative_link(),
        )
        note = self._create_note(temp_dir, "See [[First Note#Section|the section]].")

        result = processor.process(note)

        assert "[the section](first-note.md#section)" in result.content

    def test_image_embed_conversion(self, link_index, temp_dir):
        processor = ContentProcessor(
            link_index=link_index,
            link_transform=relative_link(),
            image_path_prefix="/images",
        )
        note = self._create_note(temp_dir, "Here's an image: ![[diagram.png]]")

        result = processor.process(note)

        # Filename and alt text are slugified
        assert "![diagram](/images/diagram.png)" in result.content
        assert "diagram.png" in result.referenced_images

    def test_image_embed_with_alt_text(self, link_index, temp_dir):
        processor = ContentProcessor(
            link_index=link_index,
            link_transform=relative_link(),
            image_path_prefix="/img",
        )
        note = self._create_note(temp_dir, "![[photo.jpg|My vacation photo]]")

        result = processor.process(note)

        # Alt text is slugified
        assert "![my-vacation-photo](/img/photo.jpg)" in result.content
        assert "photo.jpg" in result.referenced_images

    def test_multiple_images(self, link_index, temp_dir):
        processor = ContentProcessor(
            link_index=link_index,
            link_transform=relative_link(),
        )
        note = self._create_note(temp_dir, "![[img1.png]] and ![[img2.jpg]]")

        result = processor.process(note)

        assert "img1.png" in result.referenced_images
        assert "img2.jpg" in result.referenced_images

    def test_tag_transform(self, link_index, temp_dir):
        tag_transform = compose(
            filter_by_prefix("domain"),
            replace_separator("/", "-")
        )
        processor = ContentProcessor(
            link_index=link_index,
            link_transform=relative_link(),
            tag_transform=tag_transform,
        )
        note = self._create_note(temp_dir, "Some content")

        result = processor.process(note)

        # The processed tags should be in ProcessedNote.tags
        assert result.tags == ["domain-cs"]

    def test_frontmatter_transform(self, link_index, temp_dir):
        tag_transform = compose(
            filter_by_prefix("domain"),
            replace_separator("/", "-")
        )
        fm_transform = hugo_frontmatter("Test Author")
        processor = ContentProcessor(
            link_index=link_index,
            link_transform=relative_link(),
            tag_transform=tag_transform,
            frontmatter_transform=fm_transform,
        )
        note = self._create_note(temp_dir, "Some content")

        result = processor.process(note)

        assert result.frontmatter["title"] == "Test Note"
        assert result.frontmatter["author"] == "Test Author"
        assert result.frontmatter["tags"] == ["domain-cs"]

    def test_build_output_with_frontmatter(self, link_index, temp_dir):
        processor = ContentProcessor(
            link_index=link_index,
            link_transform=relative_link(),
        )
        note = self._create_note(temp_dir, "# Heading\n\nParagraph.")

        processed = processor.process(note)
        output = processor.build_output(processed)

        assert output.startswith("---\n")
        assert "---\n# Heading" in output
        assert "Paragraph." in output

    def test_build_output_empty_frontmatter(self, link_index, temp_dir):
        processor = ContentProcessor(
            link_index=link_index,
            link_transform=relative_link(),
        )
        # Create a note file with empty frontmatter
        file_path = temp_dir / "empty-fm.md"
        file_path.write_text("Just content")

        note = NoteMetadata(
            context=NoteContext(path=file_path),
            title="Test",
            slug="test",
            frontmatter={},
            tags=[],
            creation_date="",
            publication_date="",
        )

        processed = processor.process(note)
        output = processor.build_output(processed)

        # Empty frontmatter should not be rendered
        assert output == "Just content\n"

    def test_preserves_code_blocks(self, link_index, temp_dir):
        processor = ContentProcessor(
            link_index=link_index,
            link_transform=relative_link(),
        )
        content = """
```python
# This is [[not a link]]
print("hello")
```
And [[First Note]] is a link.
"""
        note = self._create_note(temp_dir, content)

        result = processor.process(note)

        # The wikilink in code block should still be processed
        # (code block preservation would require more sophisticated parsing)
        assert "[First Note](first-note.md)" in result.content

    def test_complex_document(self, link_index, temp_dir):
        processor = ContentProcessor(
            link_index=link_index,
            link_transform=absolute_link("/posts"),
            image_path_prefix="/static/images",
        )
        content = """
# Introduction

This document discusses [[First Note]] and shows this diagram:

![[architecture.png|System architecture]]

For more details, see [[Second Note#Details|the details section]].
"""
        note = self._create_note(temp_dir, content)

        result = processor.process(note)

        assert "[First Note](/posts/first-note)" in result.content
        # Alt text is slugified
        assert "![system-architecture](/static/images/architecture.png)" in result.content
        assert "[the details section](/posts/second-note#details)" in result.content
        assert "architecture.png" in result.referenced_images


class TestEdgeCases:
    """Tests for edge cases in content processing."""

    @pytest.fixture
    def temp_dir(self):
        temp_dir = tempfile.mkdtemp()
        yield Path(temp_dir)
        shutil.rmtree(temp_dir)

    @pytest.fixture
    def link_index(self):
        return LinkIndex.from_dict({"Test Note": "test-note"})

    def _create_note(self, temp_dir: Path, content: str) -> NoteMetadata:
        """Helper to create a NoteMetadata with a real file."""
        file_path = temp_dir / "test.md"
        file_path.write_text(content)

        return NoteMetadata(
            context=NoteContext(path=file_path),
            title="Test",
            slug="test",
            frontmatter={},
            tags=[],
            creation_date="",
            publication_date="",
        )

    def test_empty_content(self, link_index, temp_dir):
        processor = ContentProcessor(
            link_index=link_index,
            link_transform=relative_link(),
        )
        note = self._create_note(temp_dir, "")

        result = processor.process(note)

        assert result.content == ""
        assert result.referenced_images == []
        assert result.missing_links == []

    def test_no_links_or_images(self, link_index, temp_dir):
        processor = ContentProcessor(
            link_index=link_index,
            link_transform=relative_link(),
        )
        note = self._create_note(temp_dir, "Just plain text with no special syntax.")

        result = processor.process(note)

        assert result.content == "Just plain text with no special syntax."
        assert result.referenced_images == []
        assert result.missing_links == []

    def test_nested_brackets(self, link_index, temp_dir):
        processor = ContentProcessor(
            link_index=link_index,
            link_transform=relative_link(),
        )
        note = self._create_note(temp_dir, "Text with [regular](markdown) links and [[Test Note]].")

        result = processor.process(note)

        assert "[regular](markdown)" in result.content
        assert "[Test Note](test-note.md)" in result.content

    def test_image_with_spaces_in_name(self, link_index, temp_dir):
        processor = ContentProcessor(
            link_index=link_index,
            link_transform=relative_link(),
            image_path_prefix="/images",
        )
        note = self._create_note(temp_dir, "![[my diagram.png]]")

        result = processor.process(note)

        assert "my diagram.png" in result.referenced_images

    def test_webp_and_svg_images(self, link_index, temp_dir):
        processor = ContentProcessor(
            link_index=link_index,
            link_transform=relative_link(),
        )
        note = self._create_note(temp_dir, "![[photo.webp]] and ![[icon.svg]]")

        result = processor.process(note)

        assert "photo.webp" in result.referenced_images
        assert "icon.svg" in result.referenced_images


class TestRegexEdgeCases:
    """Tests for regex pattern edge cases - wikilinks and image embeds."""

    @pytest.fixture
    def temp_dir(self):
        temp_dir = tempfile.mkdtemp()
        yield Path(temp_dir)
        shutil.rmtree(temp_dir)

    @pytest.fixture
    def link_index(self):
        return LinkIndex.from_dict({
            "Test Note": "test-note",
            "File]Name": "file-name",
            "Note (with) brackets": "note-with-brackets",
            "Naïve Approach": "naive-approach",
        })

    def _create_note(self, temp_dir: Path, content: str) -> NoteMetadata:
        """Helper to create a NoteMetadata with a real file."""
        file_path = temp_dir / "test.md"
        file_path.write_text(content)

        return NoteMetadata(
            context=NoteContext(path=file_path),
            title="Test",
            slug="test",
            frontmatter={},
            tags=[],
            creation_date="",
            publication_date="",
        )

    # --- Wikilink edge cases ---

    def test_wikilink_with_bracket_in_target(self, link_index, temp_dir):
        """Single ] in target should be handled correctly."""
        processor = ContentProcessor(
            link_index=link_index,
            link_transform=relative_link(),
        )
        note = self._create_note(temp_dir, "See [[File]Name]]")

        result = processor.process(note)

        assert "[File]Name](file-name.md)" in result.content

    def test_wikilink_with_parentheses(self, link_index, temp_dir):
        """Parentheses in target should work."""
        processor = ContentProcessor(
            link_index=link_index,
            link_transform=relative_link(),
        )
        note = self._create_note(temp_dir, "See [[Note (with) brackets]]")

        result = processor.process(note)

        assert "[Note (with) brackets](note-with-brackets.md)" in result.content

    def test_wikilink_with_unicode(self, link_index, temp_dir):
        """Unicode characters in target should work."""
        processor = ContentProcessor(
            link_index=link_index,
            link_transform=relative_link(),
        )
        note = self._create_note(temp_dir, "See [[Naïve Approach]]")

        result = processor.process(note)

        assert "[Naïve Approach](naive-approach.md)" in result.content

    def test_wikilink_display_text_with_bracket(self, link_index, temp_dir):
        """Display text containing ] should work."""
        processor = ContentProcessor(
            link_index=link_index,
            link_transform=relative_link(),
        )
        note = self._create_note(temp_dir, "See [[Test Note|display]text]]")

        result = processor.process(note)

        assert "[display]text](test-note.md)" in result.content

    def test_wikilink_display_text_with_pipe(self, link_index, temp_dir):
        """Display text containing | should work (everything after first |)."""
        processor = ContentProcessor(
            link_index=link_index,
            link_transform=relative_link(),
        )
        note = self._create_note(temp_dir, "See [[Test Note|A|B|C]]")

        result = processor.process(note)

        # Display text should be everything after first |
        assert "[A|B|C](test-note.md)" in result.content

    def test_consecutive_wikilinks(self, link_index, temp_dir):
        """Consecutive wikilinks without space should work."""
        processor = ContentProcessor(
            link_index=link_index,
            link_transform=relative_link(),
        )
        note = self._create_note(temp_dir, "[[Test Note]][[Test Note]]")

        result = processor.process(note)

        assert result.content.count("[Test Note](test-note.md)") == 2

    def test_wikilink_section_only(self, link_index, temp_dir):
        """Section-only link like [[#Section]] should work."""
        processor = ContentProcessor(
            link_index=link_index,
            link_transform=relative_link(),
        )
        note = self._create_note(temp_dir, "See [[#My Section]]")

        result = processor.process(note)

        # Section-only links should be preserved with anchor
        assert "#my-section" in result.content

    # --- Image embed edge cases ---

    def test_image_with_bracket_in_name(self, link_index, temp_dir):
        """Single ] in image filename should work."""
        processor = ContentProcessor(
            link_index=link_index,
            link_transform=relative_link(),
            image_path_prefix="/images",
        )
        note = self._create_note(temp_dir, "![[image]bracket.png]]")

        result = processor.process(note)

        assert "image]bracket.png" in result.referenced_images

    def test_image_with_multiple_dots(self, link_index, temp_dir):
        """Image with multiple dots in name should work."""
        processor = ContentProcessor(
            link_index=link_index,
            link_transform=relative_link(),
            image_path_prefix="/images",
        )
        note = self._create_note(temp_dir, "![[my.complex.name.png]]")

        result = processor.process(note)

        assert "my.complex.name.png" in result.referenced_images

    def test_image_case_insensitive_extension(self, link_index, temp_dir):
        """Image extensions should be case-insensitive."""
        processor = ContentProcessor(
            link_index=link_index,
            link_transform=relative_link(),
            image_path_prefix="/images",
        )
        note = self._create_note(temp_dir, "![[photo.PNG]] and ![[other.JpG]]")

        result = processor.process(note)

        assert "photo.PNG" in result.referenced_images
        assert "other.JpG" in result.referenced_images

    def test_image_alt_text_with_bracket(self, link_index, temp_dir):
        """Alt text containing ] should work."""
        processor = ContentProcessor(
            link_index=link_index,
            link_transform=relative_link(),
            image_path_prefix="/images",
        )
        note = self._create_note(temp_dir, "![[photo.png|Alt [with] brackets]]")

        result = processor.process(note)

        assert "photo.png" in result.referenced_images
        # Alt text should be preserved (slugified)
        assert "alt-with-brackets" in result.content

    def test_image_with_path(self, link_index, temp_dir):
        """Image with folder path should be tracked."""
        processor = ContentProcessor(
            link_index=link_index,
            link_transform=relative_link(),
            image_path_prefix="/images",
        )
        note = self._create_note(temp_dir, "![[assets/subfolder/image.png]]")

        result = processor.process(note)

        assert "assets/subfolder/image.png" in result.referenced_images

    # --- Mixed edge cases ---

    def test_wikilink_and_image_interleaved(self, link_index, temp_dir):
        """Mixed wikilinks and images should all be processed."""
        processor = ContentProcessor(
            link_index=link_index,
            link_transform=relative_link(),
            image_path_prefix="/images",
        )
        note = self._create_note(temp_dir, "[[Test Note]] then ![[img.png]] then [[Test Note|alias]]")

        result = processor.process(note)

        assert "[Test Note](test-note.md)" in result.content
        assert "[alias](test-note.md)" in result.content
        assert "img.png" in result.referenced_images
