"""Zero-diff verification tests against existing publisher-v2 output.

These tests verify that the new obsidian-publisher produces output
compatible with the existing published website.
"""

import pytest
from pathlib import Path
import tempfile
import shutil
import os

from obsidian_publisher.core.publisher import Publisher, PublisherConfig, create_publisher_from_config
from obsidian_publisher.transforms.links import absolute_link
from obsidian_publisher.transforms.tags import filter_by_prefix, replace_separator, compose
from obsidian_publisher.transforms.frontmatter import hugo_frontmatter


# Skip these tests if the vault or website don't exist (CI environment)
VAULT_PATH = Path.home() / "Kishore-Brain"
WEBSITE_PATH = Path.home() / "akcube.github.io-worktree"
SKIP_INTEGRATION = not (VAULT_PATH.exists() and WEBSITE_PATH.exists())


@pytest.mark.skipif(SKIP_INTEGRATION, reason="Integration test requires vault and website")
class TestZeroDiffVerification:
    """Verify new publisher produces compatible output."""

    @pytest.fixture
    def temp_output(self):
        """Create a temporary output directory."""
        temp_dir = tempfile.mkdtemp()
        yield Path(temp_dir)
        shutil.rmtree(temp_dir)

    @pytest.fixture
    def publisher(self, temp_output):
        """Create publisher with same config as production."""
        config = PublisherConfig(
            vault_path=VAULT_PATH,
            output_path=temp_output,
            source_dir="Zettelkasten",
            content_dir="content/blog",
            image_dir="static/images",
            image_sources=["Files", "Zettelkasten"],
            required_tags=["status/evergreen"],
            excluded_tags=["status/seed", "status/sapling", "status/draft"],
            image_path_prefix="/images",
            optimize_images=True,
            max_image_width=1920,
            webp_quality=85,
        )

        tag_transform = compose(
            filter_by_prefix("domain", "type"),
            replace_separator("/", "-")
        )

        return Publisher(
            config=config,
            link_transform=absolute_link("/blog"),
            tag_transform=tag_transform,
            frontmatter_transform=hugo_frontmatter("Kishore Kumar"),
        )

    def test_discovers_same_notes(self, publisher):
        """New publisher should discover the same notes as existing."""
        notes = publisher.discovery.discover_all()

        # Should find same number as existing website
        existing_posts = list((WEBSITE_PATH / "content/blog").glob("*.md"))

        assert len(notes) == len(existing_posts), \
            f"Found {len(notes)} notes but {len(existing_posts)} existing posts"

    def test_generates_same_slugs(self, publisher):
        """Slugs should match existing file names."""
        notes = publisher.discovery.discover_all()
        generated_slugs = {n.slug for n in notes}

        existing_slugs = {p.stem for p in (WEBSITE_PATH / "content/blog").glob("*.md")}

        # Check for mismatches
        only_in_new = generated_slugs - existing_slugs
        only_in_existing = existing_slugs - generated_slugs

        if only_in_new:
            print(f"Only in new: {only_in_new}")
        if only_in_existing:
            print(f"Only in existing: {only_in_existing}")

        assert generated_slugs == existing_slugs

    def test_generates_valid_frontmatter(self, publisher, temp_output):
        """Generated frontmatter should be valid Hugo format."""
        result = publisher.republish()

        # Check all generated files have valid frontmatter
        for md_file in (temp_output / "content/blog").glob("*.md"):
            content = md_file.read_text()

            # Must start with frontmatter
            assert content.startswith("---\n"), f"{md_file.name} missing frontmatter"

            # Must have closing frontmatter
            assert "\n---\n" in content[4:], f"{md_file.name} missing frontmatter closing"

            # Parse and check required fields
            import yaml
            parts = content.split("---\n", 2)
            fm = yaml.safe_load(parts[1])

            assert "title" in fm, f"{md_file.name} missing title"
            assert "date" in fm or "doc" in fm, f"{md_file.name} missing date"

    def test_converts_wikilinks(self, publisher, temp_output):
        """Wikilinks should be converted to markdown links."""
        result = publisher.republish()

        # Check all files
        for md_file in (temp_output / "content/blog").glob("*.md"):
            content = md_file.read_text()

            # Should not contain raw wikilinks
            assert "[[" not in content.split("---\n", 2)[2], \
                f"{md_file.name} contains unconverted wikilinks"

    def test_processes_images(self, publisher, temp_output):
        """Images should be converted to WebP with PNG fallback."""
        result = publisher.republish()

        image_dir = temp_output / "static/images"

        if image_dir.exists():
            # For each image, should have both WebP and PNG
            webp_files = set(p.stem for p in image_dir.glob("*.webp"))
            png_files = set(p.stem for p in image_dir.glob("*.png"))

            # Every WebP should have a PNG fallback
            assert webp_files == png_files, \
                f"Mismatch: WebP={webp_files - png_files}, PNG={png_files - webp_files}"


@pytest.mark.skipif(SKIP_INTEGRATION, reason="Integration test requires vault and website")
class TestConfigCompatibility:
    """Test that config.yaml parsing works correctly."""

    def test_load_config(self):
        """Config file should load successfully."""
        config_path = Path(__file__).parent.parent / "config.yaml"

        if not config_path.exists():
            pytest.skip("config.yaml not found")

        publisher = create_publisher_from_config(config_path)

        assert publisher is not None
        assert publisher.vault_path.exists()

    def test_config_produces_output(self):
        """Config should produce valid output."""
        config_path = Path(__file__).parent.parent / "config.yaml"

        if not config_path.exists():
            pytest.skip("config.yaml not found")

        publisher = create_publisher_from_config(config_path)
        result = publisher.republish(dry_run=True)

        assert len(result.published_titles) > 0
        assert len(result.failures) == 0
