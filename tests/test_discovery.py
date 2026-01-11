"""Tests for VaultDiscovery class."""

import pytest
from pathlib import Path
import tempfile
import shutil

from obsidian_publisher.core.discovery import VaultDiscovery


class TestVaultDiscovery:
    """Tests for VaultDiscovery class."""

    @pytest.fixture
    def temp_vault(self):
        """Create a temporary vault with test notes."""
        temp_dir = tempfile.mkdtemp()
        vault_path = Path(temp_dir)

        # Create a simple note with tags
        note1 = vault_path / "note1.md"
        note1.write_text("""---
title: Test Note One
tags:
  - evergreen
  - domain/cs
created: 2024-01-01
date: 2024-01-15
---

# Test Note One

This is test content.
""")

        # Create note with excluded tag
        note2 = vault_path / "note2.md"
        note2.write_text("""---
title: Draft Note
tags:
  - draft
  - domain/math
---

# Draft content
""")

        # Create note without frontmatter
        note3 = vault_path / "note3.md"
        note3.write_text("""# No Frontmatter

Just plain content.
""")

        # Create note with string tag
        note4 = vault_path / "note4.md"
        note4.write_text("""---
title: Single Tag Note
tags: evergreen
---

Content here.
""")

        yield vault_path

        # Cleanup
        shutil.rmtree(temp_dir)

    def test_discover_all_finds_notes(self, temp_vault):
        discovery = VaultDiscovery(temp_vault)
        notes = discovery.discover_all()
        # Should find all 4 notes (no filtering)
        assert len(notes) == 4

    def test_discover_with_required_tags(self, temp_vault):
        discovery = VaultDiscovery(temp_vault, required_tags=["evergreen"])
        notes = discovery.discover_all()
        # Should find note1 and note4 (both have evergreen tag)
        assert len(notes) == 2
        titles = {n.title for n in notes}
        assert "Test Note One" in titles
        assert "Single Tag Note" in titles

    def test_discover_with_excluded_tags(self, temp_vault):
        discovery = VaultDiscovery(temp_vault, excluded_tags=["draft"])
        notes = discovery.discover_all()
        # Should exclude note2 (has draft tag)
        assert len(notes) == 3
        titles = {n.title for n in notes}
        assert "Draft Note" not in titles

    def test_discover_with_both_filters(self, temp_vault):
        discovery = VaultDiscovery(
            temp_vault,
            required_tags=["evergreen"],
            excluded_tags=["draft"]
        )
        notes = discovery.discover_all()
        # Should find note1 and note4 (evergreen, not draft)
        assert len(notes) == 2

    def test_get_note_by_filename(self, temp_vault):
        discovery = VaultDiscovery(temp_vault)
        note = discovery.get_note("note1.md")
        assert note is not None
        assert note.title == "Test Note One"

    def test_get_note_by_filename_without_extension(self, temp_vault):
        discovery = VaultDiscovery(temp_vault)
        note = discovery.get_note("note1")
        assert note is not None
        assert note.title == "Test Note One"

    def test_get_note_by_title(self, temp_vault):
        discovery = VaultDiscovery(temp_vault)
        note = discovery.get_note("Test Note One")
        assert note is not None
        assert note.path.name == "note1.md"

    def test_get_note_not_found(self, temp_vault):
        discovery = VaultDiscovery(temp_vault)
        note = discovery.get_note("nonexistent")
        assert note is None

    def test_is_publishable_with_required_tags(self, temp_vault):
        discovery = VaultDiscovery(temp_vault, required_tags=["evergreen"])
        note = discovery.get_note("note1")
        is_pub, reason = discovery.is_publishable(note)
        assert is_pub is True
        assert reason == "OK"

    def test_is_publishable_missing_required_tags(self, temp_vault):
        discovery = VaultDiscovery(temp_vault, required_tags=["evergreen"])
        note = discovery.get_note("note2")
        is_pub, reason = discovery.is_publishable(note)
        assert is_pub is False
        assert "Missing required tags" in reason

    def test_is_publishable_has_excluded_tags(self, temp_vault):
        discovery = VaultDiscovery(temp_vault, excluded_tags=["draft"])
        note = discovery.get_note("note2")
        is_pub, reason = discovery.is_publishable(note)
        assert is_pub is False
        assert "excluded tags" in reason

    def test_note_metadata_has_correct_fields(self, temp_vault):
        discovery = VaultDiscovery(temp_vault)
        note = discovery.get_note("note1")

        assert note.title == "Test Note One"
        assert note.slug == "test-note-one"
        assert "evergreen" in note.tags
        assert "domain/cs" in note.tags
        assert note.creation_date == "2024-01-01"
        assert note.publication_date == "2024-01-15"
        # Content is accessed via lazy loading
        assert "# Test Note One" in note.context.read_raw()

    def test_note_without_frontmatter(self, temp_vault):
        discovery = VaultDiscovery(temp_vault)
        note = discovery.get_note("note3")

        assert note is not None
        assert note.title == "note3"  # Falls back to filename
        assert note.tags == []
        # Content is accessed via lazy loading
        assert "# No Frontmatter" in note.context.read_raw()

    def test_source_dirs_subdirectory(self, temp_vault):
        subdir = temp_vault / "posts"
        subdir.mkdir()
        (subdir / "post1.md").write_text("""---
title: Post One
tags:
  - evergreen
---

Post content.
""")

        discovery = VaultDiscovery(temp_vault, source_dirs=["posts"])
        notes = discovery.discover_all()

        assert len(notes) == 1
        assert notes[0].title == "Post One"

    def test_source_dirs_multiple(self, temp_vault):
        posts = temp_vault / "posts"
        posts.mkdir()
        (posts / "post1.md").write_text("""---
title: Post One
tags:
  - evergreen
---
""")

        projects = temp_vault / "projects"
        projects.mkdir()
        (projects / "project1.md").write_text("""---
title: Project One
tags:
  - evergreen
---
""")

        discovery = VaultDiscovery(temp_vault, source_dirs=["posts", "projects"])
        notes = discovery.discover_all()

        assert len(notes) == 2
        titles = {n.title for n in notes}
        assert titles == {"Post One", "Project One"}

    def test_source_dirs_not_found(self, temp_vault):
        discovery = VaultDiscovery(temp_vault, source_dirs=["nonexistent"])
        with pytest.raises(FileNotFoundError):
            discovery.discover_all()

    def test_source_dirs_partial_missing(self, temp_vault):
        posts = temp_vault / "posts"
        posts.mkdir()
        (posts / "post1.md").write_text("""---
title: Post One
tags:
  - evergreen
---
""")

        discovery = VaultDiscovery(temp_vault, source_dirs=["posts", "nonexistent"])
        notes = discovery.discover_all()

        assert len(notes) == 1
        assert notes[0].title == "Post One"

    def test_string_tag_format(self, temp_vault):
        discovery = VaultDiscovery(temp_vault)
        note = discovery.get_note("note4")

        assert note is not None
        assert "evergreen" in note.tags

    def test_get_note_by_full_path(self, temp_vault):
        discovery = VaultDiscovery(temp_vault)
        full_path = str(temp_vault / "note1.md")
        note = discovery.get_note(full_path)

        assert note is not None
        assert note.title == "Test Note One"

    def test_get_note_rejects_non_md_absolute_path(self, temp_vault):
        # Create a non-.md file
        txt_file = temp_vault / "notes.txt"
        txt_file.write_text("not a markdown file")

        discovery = VaultDiscovery(temp_vault)
        note = discovery.get_note(str(txt_file))

        assert note is None

    def test_get_note_rejects_non_md_existing_path(self, temp_vault):
        # Create a non-.md file with same stem as a note
        txt_file = temp_vault / "note1.txt"
        txt_file.write_text("not a markdown file")

        discovery = VaultDiscovery(temp_vault)
        # Should reject the .txt file, not fall through to find note1.md
        note = discovery.get_note("note1.txt")

        assert note is None

    def test_get_note_non_md_name_does_not_find_md_file(self, temp_vault):
        discovery = VaultDiscovery(temp_vault)
        # "note1.txt" should NOT find "note1.md" - this was the original bug
        note = discovery.get_note("note1.txt")

        # Since note1.txt doesn't exist on disk, it's treated as a name
        # The name "note1.txt" (with .txt) should not match "note1.md"
        assert note is None


class TestFrontmatterParsing:
    """Tests for frontmatter parsing edge cases."""

    @pytest.fixture
    def temp_vault(self):
        temp_dir = tempfile.mkdtemp()
        yield Path(temp_dir)
        shutil.rmtree(temp_dir)

    def test_malformed_yaml(self, temp_vault):
        note = temp_vault / "bad.md"
        note.write_text("""---
title: Bad YAML
tags: [unclosed bracket
---

Content.
""")

        discovery = VaultDiscovery(temp_vault)
        result = discovery.get_note("bad")

        assert result is None
        assert len(discovery.errors) == 1
        assert discovery.errors[0].path == note
        assert "unclosed" in discovery.errors[0].error.lower() or "bracket" in discovery.errors[0].error.lower()

    def test_frontmatter_without_closing(self, temp_vault):
        note = temp_vault / "unclosed.md"
        note.write_text("""---
title: Unclosed
tags:
  - test

Content without closing frontmatter.
""")

        discovery = VaultDiscovery(temp_vault)
        result = discovery.get_note("unclosed")
        # Should handle gracefully
        assert result is not None

    def test_datetime_in_frontmatter(self, temp_vault):
        note = temp_vault / "dated.md"
        note.write_text("""---
title: Dated Note
created: 2024-01-15 10:30:00+0000
date: 2024-02-01
---

Content.
""")

        discovery = VaultDiscovery(temp_vault)
        result = discovery.get_note("dated")

        assert result is not None
        # Dates should be converted to strings
        assert "2024" in result.creation_date
        assert "2024-02-01" in result.publication_date


class TestErrorHandling:
    """Tests for error handling and collection."""

    @pytest.fixture
    def temp_vault(self):
        temp_dir = tempfile.mkdtemp()
        yield Path(temp_dir)
        shutil.rmtree(temp_dir)

    def test_errors_collected_during_discover_all(self, temp_vault):
        (temp_vault / "good.md").write_text("""---
title: Good Note
tags:
  - evergreen
---
Content.
""")
        (temp_vault / "bad.md").write_text("""---
title: Bad YAML
tags: [unclosed
---
Content.
""")

        discovery = VaultDiscovery(temp_vault)
        notes = discovery.discover_all()

        assert len(notes) == 1
        assert notes[0].title == "Good Note"
        assert len(discovery.errors) == 1
        assert discovery.errors[0].path.name == "bad.md"

    def test_fail_fast_raises_on_first_error(self, temp_vault):
        (temp_vault / "bad.md").write_text("""---
tags: [unclosed
---
""")

        discovery = VaultDiscovery(temp_vault, fail_fast=True)

        with pytest.raises(Exception):
            discovery.discover_all()

    def test_multiple_errors_collected(self, temp_vault):
        (temp_vault / "bad1.md").write_text("""---
tags: [unclosed
---
""")
        (temp_vault / "bad2.md").write_text("""---
title: Also Bad
invalid yaml: [
---
""")
        (temp_vault / "good.md").write_text("""---
title: Good
---
Content.
""")

        discovery = VaultDiscovery(temp_vault)
        notes = discovery.discover_all()

        assert len(notes) == 1
        assert len(discovery.errors) == 2
