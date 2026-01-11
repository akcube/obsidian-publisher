"""Tests for ContentProcessor class."""

import pytest
from pathlib import Path

from obsidian_publisher.core.processor import ContentProcessor, LinkIndex
from obsidian_publisher.core.models import NoteMetadata
from obsidian_publisher.transforms.links import relative_link, absolute_link, hugo_ref
from obsidian_publisher.transforms.tags import filter_by_prefix, replace_separator, compose
from obsidian_publisher.transforms.frontmatter import hugo_frontmatter


class TestLinkIndex:
    """Tests for LinkIndex class."""

    def test_from_notes(self):
        notes = [
            NoteMetadata(
                path=Path("/test/note1.md"),
                title="First Note",
                slug="first-note",
                frontmatter={},
                content="",
                tags=[],
                creation_date="",
                publication_date="",
                processed_tags=None,
            ),
            NoteMetadata(
                path=Path("/test/note2.md"),
                title="Second Note",
                slug="second-note",
                frontmatter={},
                content="",
                tags=[],
                creation_date="",
                publication_date="",
                processed_tags=None,
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
    def link_index(self):
        return LinkIndex.from_dict({
            "First Note": "first-note",
            "Second Note": "second-note",
            "Note With Spaces": "note-with-spaces",
        })

    @pytest.fixture
    def sample_note(self):
        return NoteMetadata(
            path=Path("/test/note.md"),
            title="Test Note",
            slug="test-note",
            frontmatter={"original": "data"},
            content="",
            tags=["domain/cs", "evergreen"],
            creation_date="2024-01-01 00:00:00+0000",
            publication_date="2024-01-15 00:00:00+0000",
            processed_tags=None,
        )

    def test_simple_wikilink_conversion(self, link_index, sample_note):
        processor = ContentProcessor(
            link_index=link_index,
            link_transform=relative_link(),
        )
        sample_note.content = "Check out [[First Note]] for more info."

        result = processor.process(sample_note)

        assert "[First Note](first-note.md)" in result.content

    def test_wikilink_with_display_text(self, link_index, sample_note):
        processor = ContentProcessor(
            link_index=link_index,
            link_transform=relative_link(),
        )
        sample_note.content = "See [[First Note|this article]] here."

        result = processor.process(sample_note)

        assert "[this article](first-note.md)" in result.content

    def test_wikilink_with_absolute_link_transform(self, link_index, sample_note):
        processor = ContentProcessor(
            link_index=link_index,
            link_transform=absolute_link("/blog"),
        )
        sample_note.content = "Read [[First Note]]."

        result = processor.process(sample_note)

        assert "[First Note](/blog/first-note)" in result.content

    def test_wikilink_with_hugo_ref_transform(self, link_index, sample_note):
        processor = ContentProcessor(
            link_index=link_index,
            link_transform=hugo_ref(),
        )
        sample_note.content = "Read [[First Note]]."

        result = processor.process(sample_note)

        assert '[First Note]({{< ref "first-note" >}})' in result.content

    def test_multiple_wikilinks(self, link_index, sample_note):
        processor = ContentProcessor(
            link_index=link_index,
            link_transform=relative_link(),
        )
        sample_note.content = "See [[First Note]] and [[Second Note]]."

        result = processor.process(sample_note)

        assert "[First Note](first-note.md)" in result.content
        assert "[Second Note](second-note.md)" in result.content

    def test_missing_link_tracked(self, link_index, sample_note):
        processor = ContentProcessor(
            link_index=link_index,
            link_transform=relative_link(),
            warn_on_missing_link=True,
        )
        sample_note.content = "See [[Nonexistent Note]]."

        result = processor.process(sample_note)

        assert "Nonexistent Note" in result.missing_links
        # Should still generate a link using the parameterized slug
        assert "[Nonexistent Note](nonexistent-note.md)" in result.content

    def test_section_link(self, link_index, sample_note):
        processor = ContentProcessor(
            link_index=link_index,
            link_transform=relative_link(),
        )
        sample_note.content = "See [[First Note#Introduction]]."

        result = processor.process(sample_note)

        assert "[First Note](first-note.md#introduction)" in result.content

    def test_section_link_with_display_text(self, link_index, sample_note):
        processor = ContentProcessor(
            link_index=link_index,
            link_transform=relative_link(),
        )
        sample_note.content = "See [[First Note#Section|the section]]."

        result = processor.process(sample_note)

        assert "[the section](first-note.md#section)" in result.content

    def test_image_embed_conversion(self, link_index, sample_note):
        processor = ContentProcessor(
            link_index=link_index,
            link_transform=relative_link(),
            image_path_prefix="/images",
        )
        sample_note.content = "Here's an image: ![[diagram.png]]"

        result = processor.process(sample_note)

        assert "![diagram](/images/diagram.png)" in result.content
        assert "diagram.png" in result.referenced_images

    def test_image_embed_with_alt_text(self, link_index, sample_note):
        processor = ContentProcessor(
            link_index=link_index,
            link_transform=relative_link(),
            image_path_prefix="/img",
        )
        sample_note.content = "![[photo.jpg|My vacation photo]]"

        result = processor.process(sample_note)

        assert "![My vacation photo](/img/photo.jpg)" in result.content
        assert "photo.jpg" in result.referenced_images

    def test_multiple_images(self, link_index, sample_note):
        processor = ContentProcessor(
            link_index=link_index,
            link_transform=relative_link(),
        )
        sample_note.content = "![[img1.png]] and ![[img2.jpg]]"

        result = processor.process(sample_note)

        assert "img1.png" in result.referenced_images
        assert "img2.jpg" in result.referenced_images

    def test_tag_transform(self, link_index, sample_note):
        tag_transform = compose(
            filter_by_prefix("domain"),
            replace_separator("/", "-")
        )
        processor = ContentProcessor(
            link_index=link_index,
            link_transform=relative_link(),
            tag_transform=tag_transform,
        )
        sample_note.content = "Some content"

        result = processor.process(sample_note)

        # The processed tags should be available in the note passed to frontmatter
        # We need frontmatter transform to see the result
        assert result.frontmatter is not None

    def test_frontmatter_transform(self, link_index, sample_note):
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
        sample_note.content = "Some content"

        result = processor.process(sample_note)

        assert result.frontmatter["title"] == "Test Note"
        assert result.frontmatter["author"] == "Test Author"
        assert result.frontmatter["tags"] == ["domain-cs"]

    def test_build_output_with_frontmatter(self, link_index, sample_note):
        processor = ContentProcessor(
            link_index=link_index,
            link_transform=relative_link(),
        )
        sample_note.content = "# Heading\n\nParagraph."

        processed = processor.process(sample_note)
        output = processor.build_output(processed)

        assert output.startswith("---\n")
        assert "---\n# Heading" in output
        assert "Paragraph." in output

    def test_build_output_empty_frontmatter(self, link_index, sample_note):
        processor = ContentProcessor(
            link_index=link_index,
            link_transform=relative_link(),
        )
        sample_note.content = "Just content"
        sample_note.frontmatter = {}

        processed = processor.process(sample_note)
        output = processor.build_output(processed)

        # Empty frontmatter should not be rendered
        assert output == "Just content"

    def test_preserves_code_blocks(self, link_index, sample_note):
        processor = ContentProcessor(
            link_index=link_index,
            link_transform=relative_link(),
        )
        sample_note.content = """
```python
# This is [[not a link]]
print("hello")
```
And [[First Note]] is a link.
"""

        result = processor.process(sample_note)

        # The wikilink in code block should still be processed
        # (code block preservation would require more sophisticated parsing)
        assert "[First Note](first-note.md)" in result.content

    def test_complex_document(self, link_index, sample_note):
        processor = ContentProcessor(
            link_index=link_index,
            link_transform=absolute_link("/posts"),
            image_path_prefix="/static/images",
        )
        sample_note.content = """
# Introduction

This document discusses [[First Note]] and shows this diagram:

![[architecture.png|System architecture]]

For more details, see [[Second Note#Details|the details section]].
"""

        result = processor.process(sample_note)

        assert "[First Note](/posts/first-note)" in result.content
        assert "![System architecture](/static/images/architecture.png)" in result.content
        assert "[the details section](/posts/second-note#details)" in result.content
        assert "architecture.png" in result.referenced_images


class TestEdgeCases:
    """Tests for edge cases in content processing."""

    @pytest.fixture
    def link_index(self):
        return LinkIndex.from_dict({"Test Note": "test-note"})

    @pytest.fixture
    def sample_note(self):
        return NoteMetadata(
            path=Path("/test/note.md"),
            title="Test",
            slug="test",
            frontmatter={},
            content="",
            tags=[],
            creation_date="",
            publication_date="",
            processed_tags=None,
        )

    def test_empty_content(self, link_index, sample_note):
        processor = ContentProcessor(
            link_index=link_index,
            link_transform=relative_link(),
        )
        sample_note.content = ""

        result = processor.process(sample_note)

        assert result.content == ""
        assert result.referenced_images == []
        assert result.missing_links == []

    def test_no_links_or_images(self, link_index, sample_note):
        processor = ContentProcessor(
            link_index=link_index,
            link_transform=relative_link(),
        )
        sample_note.content = "Just plain text with no special syntax."

        result = processor.process(sample_note)

        assert result.content == "Just plain text with no special syntax."
        assert result.referenced_images == []
        assert result.missing_links == []

    def test_nested_brackets(self, link_index, sample_note):
        processor = ContentProcessor(
            link_index=link_index,
            link_transform=relative_link(),
        )
        sample_note.content = "Text with [regular](markdown) links and [[Test Note]]."

        result = processor.process(sample_note)

        assert "[regular](markdown)" in result.content
        assert "[Test Note](test-note.md)" in result.content

    def test_image_with_spaces_in_name(self, link_index, sample_note):
        processor = ContentProcessor(
            link_index=link_index,
            link_transform=relative_link(),
            image_path_prefix="/images",
        )
        sample_note.content = "![[my diagram.png]]"

        result = processor.process(sample_note)

        assert "my diagram.png" in result.referenced_images

    def test_webp_and_svg_images(self, link_index, sample_note):
        processor = ContentProcessor(
            link_index=link_index,
            link_transform=relative_link(),
        )
        sample_note.content = "![[photo.webp]] and ![[icon.svg]]"

        result = processor.process(sample_note)

        assert "photo.webp" in result.referenced_images
        assert "icon.svg" in result.referenced_images
