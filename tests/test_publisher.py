"""Tests for Publisher orchestrator class."""

import pytest
from pathlib import Path
import tempfile
import shutil
from PIL import Image

from obsidian_publisher.core.publisher import Publisher, PublisherConfig
from obsidian_publisher.transforms.links import absolute_link
from obsidian_publisher.transforms.tags import filter_by_prefix, replace_separator, compose
from obsidian_publisher.transforms.frontmatter import hugo_frontmatter


class TestPublisher:
    """Tests for Publisher class."""

    @pytest.fixture
    def temp_vault(self):
        """Create a temporary vault with test notes."""
        temp_dir = tempfile.mkdtemp()
        vault_path = Path(temp_dir)

        # Create a publishable note
        note1 = vault_path / "note1.md"
        note1.write_text("""---
title: First Note
tags:
  - evergreen
  - domain/cs
created: 2024-01-01
date: 2024-01-15
---

# First Note

This is the first note. See [[Second Note]] for more.

Here's an image: ![[diagram.png]]
""")

        # Create another publishable note
        note2 = vault_path / "note2.md"
        note2.write_text("""---
title: Second Note
tags:
  - evergreen
  - domain/math
---

# Second Note

Referenced from [[First Note]].
""")

        # Create a draft note
        note3 = vault_path / "draft.md"
        note3.write_text("""---
title: Draft Note
tags:
  - draft
---

This is a draft.
""")

        # Create assets directory with an image
        assets = vault_path / "assets"
        assets.mkdir()
        img = Image.new('RGB', (100, 100), color='red')
        img.save(assets / "diagram.png")

        yield vault_path

        shutil.rmtree(temp_dir)

    @pytest.fixture
    def temp_output(self):
        """Create a temporary output directory."""
        temp_dir = tempfile.mkdtemp()
        yield Path(temp_dir)
        shutil.rmtree(temp_dir)

    @pytest.fixture
    def publisher(self, temp_vault, temp_output):
        """Create a Publisher instance."""
        config = PublisherConfig(
            vault_path=temp_vault,
            output_path=temp_output,
            required_tags=["evergreen"],
            excluded_tags=["draft"],
            image_sources=["assets"],
        )
        return Publisher(config)

    def test_republish_discovers_notes(self, publisher, temp_output):
        result = publisher.republish()

        assert len(result.published_titles) == 2
        assert "First Note" in result.published_titles
        assert "Second Note" in result.published_titles

    def test_republish_excludes_drafts(self, publisher):
        result = publisher.republish()

        assert "Draft Note" not in result.published_titles

    def test_republish_creates_files(self, publisher, temp_output):
        publisher.republish()

        content_dir = temp_output / "content/posts"
        assert (content_dir / "first-note.md").exists()
        assert (content_dir / "second-note.md").exists()

    def test_republish_converts_wikilinks(self, publisher, temp_output):
        publisher.republish()

        content_file = temp_output / "content/posts/first-note.md"
        content = content_file.read_text()

        # Wikilink should be converted to markdown link
        assert "[[Second Note]]" not in content
        assert "[Second Note]" in content

    def test_republish_processes_images(self, publisher, temp_output):
        publisher.republish()

        image_dir = temp_output / "static/images"
        # Should have WebP and PNG versions
        assert (image_dir / "diagram.webp").exists()
        assert (image_dir / "diagram.png").exists()

    def test_republish_dry_run(self, publisher, temp_output):
        result = publisher.republish(dry_run=True)

        # Should report what would be published
        assert len(result.published_titles) == 2

        # But no files should be created
        content_dir = temp_output / "content/posts"
        assert not content_dir.exists() or len(list(content_dir.glob("*.md"))) == 0

    def test_add_specific_note(self, publisher, temp_output):
        result = publisher.add("First Note")

        assert len(result.published_titles) == 1
        assert "First Note" in result.published_titles

        content_dir = temp_output / "content/posts"
        assert (content_dir / "first-note.md").exists()
        # Second note should not be published
        assert not (content_dir / "second-note.md").exists()

    def test_add_nonexistent_note(self, publisher):
        result = publisher.add("Nonexistent Note")

        assert len(result.failures) == 1
        assert "Nonexistent Note" in str(result.failures[0].path)

    def test_add_draft_note(self, publisher):
        result = publisher.add("Draft Note")

        assert len(result.failures) == 1
        assert result.failures[0].title == "Draft Note"

    def test_delete_note(self, publisher, temp_output):
        # First publish
        publisher.republish()

        # Then delete
        result = publisher.delete("First Note")

        assert "First Note" in result.published_titles

        content_dir = temp_output / "content/posts"
        assert not (content_dir / "first-note.md").exists()
        # Second note should still exist
        assert (content_dir / "second-note.md").exists()

    def test_delete_cleans_orphan_images(self, publisher, temp_output):
        # First publish
        publisher.republish()

        # Then delete the only note that references the image
        result = publisher.delete("First Note")

        # Image should be cleaned up (orphaned)
        assert len(result.removed_image_paths) > 0

    def test_delete_nonexistent(self, publisher, temp_output):
        result = publisher.delete("Nonexistent Note")

        assert len(result.failures) == 1


class TestPublisherWithTransforms:
    """Tests for Publisher with custom transforms."""

    @pytest.fixture
    def temp_vault(self):
        temp_dir = tempfile.mkdtemp()
        vault_path = Path(temp_dir)

        note = vault_path / "note.md"
        note.write_text("""---
title: Test Note
tags:
  - evergreen
  - domain/cs
  - status/complete
created: 2024-01-01
date: 2024-01-15
---

# Test Note

Content here.
""")

        yield vault_path
        shutil.rmtree(temp_dir)

    @pytest.fixture
    def temp_output(self):
        temp_dir = tempfile.mkdtemp()
        yield Path(temp_dir)
        shutil.rmtree(temp_dir)

    def test_custom_link_transform(self, temp_vault, temp_output):
        config = PublisherConfig(
            vault_path=temp_vault,
            output_path=temp_output,
            required_tags=["evergreen"],
        )
        publisher = Publisher(
            config,
            link_transform=absolute_link("/blog"),
        )

        publisher.republish()

        content_file = temp_output / "content/posts/test-note.md"
        content = content_file.read_text()

        # Links should use absolute format with prefix
        # (No links in this note, but transform is applied)
        assert content  # Just verify it ran

    def test_tag_transform(self, temp_vault, temp_output):
        config = PublisherConfig(
            vault_path=temp_vault,
            output_path=temp_output,
            required_tags=["evergreen"],
        )

        tag_transform = compose(
            filter_by_prefix("domain"),
            replace_separator("/", "-")
        )

        fm_transform = hugo_frontmatter("Test Author")

        publisher = Publisher(
            config,
            tag_transform=tag_transform,
            frontmatter_transform=fm_transform,
        )

        publisher.republish()

        content_file = temp_output / "content/posts/test-note.md"
        content = content_file.read_text()

        # Should have processed tags
        assert "domain-cs" in content
        # Should not have status tag
        assert "status" not in content

    def test_frontmatter_transform(self, temp_vault, temp_output):
        config = PublisherConfig(
            vault_path=temp_vault,
            output_path=temp_output,
            required_tags=["evergreen"],
        )

        publisher = Publisher(
            config,
            frontmatter_transform=hugo_frontmatter("Test Author"),
        )

        publisher.republish()

        content_file = temp_output / "content/posts/test-note.md"
        content = content_file.read_text()

        assert "author: Test Author" in content
        assert "title: Test Note" in content


class TestPublisherConfig:
    """Tests for PublisherConfig options."""

    @pytest.fixture
    def temp_vault(self):
        temp_dir = tempfile.mkdtemp()
        vault_path = Path(temp_dir)

        note = vault_path / "note.md"
        note.write_text("""---
title: Test Note
---

# Test
""")

        yield vault_path
        shutil.rmtree(temp_dir)

    @pytest.fixture
    def temp_output(self):
        temp_dir = tempfile.mkdtemp()
        yield Path(temp_dir)
        shutil.rmtree(temp_dir)

    def test_custom_content_dir(self, temp_vault, temp_output):
        config = PublisherConfig(
            vault_path=temp_vault,
            output_path=temp_output,
            content_dir="posts",
        )
        publisher = Publisher(config)
        publisher.republish()

        assert (temp_output / "posts/test-note.md").exists()

    def test_custom_image_dir(self, temp_vault, temp_output):
        # Add an image reference
        note = temp_vault / "note.md"
        note.write_text("""---
title: Test Note
---

![[test.png]]
""")

        # Create image
        assets = temp_vault / "assets"
        assets.mkdir()
        img = Image.new('RGB', (10, 10), color='blue')
        img.save(assets / "test.png")

        config = PublisherConfig(
            vault_path=temp_vault,
            output_path=temp_output,
            image_dir="img",
            image_sources=["assets"],
        )
        publisher = Publisher(config)
        publisher.republish()

        assert (temp_output / "img/test.webp").exists()

    def test_no_image_optimization(self, temp_vault, temp_output):
        # Add an image reference
        note = temp_vault / "note.md"
        note.write_text("""---
title: Test Note
---

![[test.png]]
""")

        # Create image
        assets = temp_vault / "assets"
        assets.mkdir()
        img = Image.new('RGB', (10, 10), color='blue')
        img.save(assets / "test.png")

        config = PublisherConfig(
            vault_path=temp_vault,
            output_path=temp_output,
            image_sources=["assets"],
            optimize_images=False,
        )
        publisher = Publisher(config)
        publisher.republish()

        # Should just copy, not create WebP
        assert (temp_output / "static/images/test.png").exists()
        assert not (temp_output / "static/images/test.webp").exists()
