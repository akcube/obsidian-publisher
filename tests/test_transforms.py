"""Tests for transform factories."""

import pytest
import tempfile
import shutil
from pathlib import Path

from obsidian_publisher.transforms.links import relative_link, absolute_link, hugo_ref
from obsidian_publisher.transforms.tags import identity, filter_by_prefix, replace_separator, compose
from obsidian_publisher.transforms.frontmatter import (
    identity as fm_identity,
    prune_and_add,
    hugo_frontmatter,
)
from obsidian_publisher.core.models import NoteContext, NoteMetadata, ProcessedNote


class TestLinkTransforms:
    """Tests for link transform factories."""

    def test_relative_link(self):
        transform = relative_link()
        assert transform("My Note", "my-note") == "[My Note](my-note.md)"

    def test_relative_link_with_spaces(self):
        transform = relative_link()
        assert transform("A Long Note Title", "a-long-note-title") == "[A Long Note Title](a-long-note-title.md)"

    def test_absolute_link_with_prefix(self):
        transform = absolute_link("/blog")
        assert transform("My Note", "my-note") == "[My Note](/blog/my-note)"

    def test_absolute_link_without_prefix(self):
        transform = absolute_link()
        assert transform("My Note", "my-note") == "[My Note](/my-note)"

    def test_absolute_link_empty_prefix(self):
        transform = absolute_link("")
        assert transform("My Note", "my-note") == "[My Note](/my-note)"

    def test_hugo_ref(self):
        transform = hugo_ref()
        assert transform("My Note", "my-note") == '[My Note]({{< ref "my-note" >}})'


class TestTagTransforms:
    """Tests for tag transform factories."""

    def test_identity(self):
        transform = identity()
        tags = ["a", "b", "c"]
        assert transform(tags) == ["a", "b", "c"]

    def test_identity_empty(self):
        transform = identity()
        assert transform([]) == []

    def test_filter_by_prefix_single(self):
        transform = filter_by_prefix("domain")
        tags = ["domain/cs", "status/ok", "domain/math"]
        assert transform(tags) == ["domain/cs", "domain/math"]

    def test_filter_by_prefix_multiple(self):
        transform = filter_by_prefix("domain", "type")
        tags = ["domain/cs", "type/post", "status/ok"]
        result = transform(tags)
        assert "domain/cs" in result
        assert "type/post" in result
        assert "status/ok" not in result

    def test_filter_by_prefix_no_match(self):
        transform = filter_by_prefix("domain")
        tags = ["status/ok", "type/post"]
        assert transform(tags) == []

    def test_replace_separator(self):
        transform = replace_separator("/", "-")
        assert transform(["a/b/c"]) == ["a-b-c"]

    def test_replace_separator_multiple_tags(self):
        transform = replace_separator("/", "-")
        result = transform(["domain/cs/algo", "type/post"])
        assert result == ["domain-cs-algo", "type-post"]

    def test_compose_two_transforms(self):
        transform = compose(
            filter_by_prefix("domain"),
            replace_separator("/", "-")
        )
        tags = ["domain/cs", "status/ok"]
        assert transform(tags) == ["domain-cs"]

    def test_compose_with_sorted(self):
        transform = compose(
            filter_by_prefix("domain"),
            replace_separator("/", "-"),
            sorted
        )
        tags = ["status/ok", "domain/z", "domain/a"]
        assert transform(tags) == ["domain-a", "domain-z"]


class TestFrontmatterTransforms:
    """Tests for frontmatter transform factories."""

    @pytest.fixture
    def temp_dir(self):
        temp_dir = tempfile.mkdtemp()
        yield Path(temp_dir)
        shutil.rmtree(temp_dir)

    @pytest.fixture
    def mock_processed(self, temp_dir):
        """Create a mock ProcessedNote for testing frontmatter transforms."""
        # Create a temp file for NoteContext
        file_path = temp_dir / "test-note.md"
        file_path.write_text("---\ntitle: Test Note\n---\n# Test")

        metadata = NoteMetadata(
            context=NoteContext(path=file_path),
            title="Test Note",
            slug="test-note",
            frontmatter={"original": "data"},
            tags=["domain/cs"],
            creation_date="2024-01-01 00:00:00+0000",
            publication_date="2024-01-01 00:00:00+0000",
        )

        return ProcessedNote(
            metadata=metadata,
            content="# Test",
            frontmatter={"original": "data"},
            tags=["domain-cs"],  # Processed tags
            referenced_images=[],
            missing_links=[],
        )

    def test_identity(self, mock_processed):
        transform = fm_identity()
        fm = {"a": 1, "b": 2}
        result = transform(fm, mock_processed)
        assert result == {"a": 1, "b": 2}

    def test_identity_empty(self, mock_processed):
        transform = fm_identity()
        assert transform({}, mock_processed) == {}

    def test_prune_keep_keys(self, mock_processed):
        transform = prune_and_add(keep_keys=["a"])
        fm = {"a": 1, "b": 2, "c": 3}
        assert transform(fm, mock_processed) == {"a": 1}

    def test_prune_remove_keys(self, mock_processed):
        transform = prune_and_add(remove_keys=["b"])
        fm = {"a": 1, "b": 2, "c": 3}
        result = transform(fm, mock_processed)
        assert result == {"a": 1, "c": 3}

    def test_prune_add_fields(self, mock_processed):
        transform = prune_and_add(add_fields={"x": 1})
        fm = {"a": 1}
        result = transform(fm, mock_processed)
        assert result == {"a": 1, "x": 1}

    def test_prune_combined(self, mock_processed):
        transform = prune_and_add(keep_keys=["a"], add_fields={"x": 1})
        fm = {"a": 1, "b": 2}
        result = transform(fm, mock_processed)
        assert result == {"a": 1, "x": 1}

    def test_hugo_frontmatter_with_author(self, mock_processed):
        transform = hugo_frontmatter("Kishore Kumar")
        fm = {"original": "data"}
        result = transform(fm, mock_processed)
        assert result["title"] == "Test Note"
        assert result["author"] == "Kishore Kumar"
        assert result["date"] == "2024-01-01 00:00:00+0000"
        assert result["doc"] == "2024-01-01 00:00:00+0000"
        assert result["tags"] == ["domain-cs"]

    def test_hugo_frontmatter_without_author(self, mock_processed):
        transform = hugo_frontmatter()
        fm = {}
        result = transform(fm, mock_processed)
        assert "author" not in result
        assert "title" in result

    def test_hugo_frontmatter_no_processed_tags(self, temp_dir):
        """Test hugo_frontmatter when there are no processed tags."""
        file_path = temp_dir / "no-tags.md"
        file_path.write_text("---\ntitle: Test\n---\nContent")

        metadata = NoteMetadata(
            context=NoteContext(path=file_path),
            title="Test",
            slug="test",
            frontmatter={},
            tags=[],
            creation_date="2024-01-01",
            publication_date="2024-01-01",
        )

        processed = ProcessedNote(
            metadata=metadata,
            content="Content",
            frontmatter={},
            tags=[],  # Empty tags
            referenced_images=[],
            missing_links=[],
        )

        transform = hugo_frontmatter("Author")
        result = transform({}, processed)
        assert "tags" not in result
