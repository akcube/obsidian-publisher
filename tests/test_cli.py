"""Tests for CLI commands."""

import pytest
from pathlib import Path
import tempfile
import shutil
from click.testing import CliRunner
from PIL import Image

from obsidian_publisher.cli.main import cli


class TestCLI:
    """Tests for CLI commands."""

    @pytest.fixture
    def temp_vault(self):
        """Create a temporary vault with test notes."""
        temp_dir = tempfile.mkdtemp()
        vault_path = Path(temp_dir)

        note = vault_path / "note.md"
        note.write_text("""---
title: Test Note
tags:
  - evergreen
---

# Test Note

Content here.
""")

        yield vault_path
        shutil.rmtree(temp_dir)

    @pytest.fixture
    def temp_output(self):
        """Create a temporary output directory."""
        temp_dir = tempfile.mkdtemp()
        yield Path(temp_dir)
        shutil.rmtree(temp_dir)

    @pytest.fixture
    def config_file(self, temp_vault, temp_output):
        """Create a test config file."""
        config_path = temp_vault / "config.yaml"
        config_path.write_text(f"""
vault_path: {temp_vault}
output_path: {temp_output}
required_tags:
  - evergreen
""")
        yield config_path

    def test_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ['--help'])

        assert result.exit_code == 0
        assert 'Obsidian to Static Site Publisher' in result.output

    def test_version(self):
        runner = CliRunner()
        result = runner.invoke(cli, ['--version'])

        assert result.exit_code == 0
        assert '0.1.0' in result.output

    def test_republish_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ['republish', '--help'])

        assert result.exit_code == 0
        assert '--config' in result.output
        assert '--dry-run' in result.output

    def test_republish(self, config_file, temp_output):
        runner = CliRunner()
        result = runner.invoke(cli, ['republish', '-c', str(config_file)])

        assert result.exit_code == 0
        assert 'Published' in result.output
        assert 'Success!' in result.output

    def test_republish_dry_run(self, config_file, temp_output):
        runner = CliRunner()
        result = runner.invoke(cli, ['republish', '-c', str(config_file), '--dry-run'])

        assert result.exit_code == 0
        assert 'DRY RUN' in result.output

        # No files should be created
        content_dir = temp_output / "content/posts"
        assert not content_dir.exists() or len(list(content_dir.glob("*.md"))) == 0

    def test_add(self, config_file, temp_output):
        runner = CliRunner()
        result = runner.invoke(cli, ['add', 'Test Note', '-c', str(config_file)])

        assert result.exit_code == 0
        assert 'Published' in result.output

    def test_add_nonexistent(self, config_file):
        runner = CliRunner()
        result = runner.invoke(cli, ['add', 'Nonexistent', '-c', str(config_file)])

        assert result.exit_code == 1
        assert 'Failed' in result.output

    def test_delete(self, config_file, temp_output):
        runner = CliRunner()

        # First publish
        runner.invoke(cli, ['republish', '-c', str(config_file)])

        # Then delete
        result = runner.invoke(cli, ['delete', 'Test Note', '-c', str(config_file)])

        assert result.exit_code == 0

    def test_list_notes(self, config_file):
        runner = CliRunner()
        result = runner.invoke(cli, ['list-notes', '-c', str(config_file)])

        assert result.exit_code == 0
        assert 'Test Note' in result.output

    def test_init(self):
        runner = CliRunner()

        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "config.yaml"

            result = runner.invoke(cli, ['init', str(config_path)])

            assert result.exit_code == 0
            assert config_path.exists()
            assert 'vault_path' in config_path.read_text()

    def test_init_already_exists(self):
        runner = CliRunner()

        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "config.yaml"
            config_path.write_text("existing")

            result = runner.invoke(cli, ['init', str(config_path)])

            assert result.exit_code == 1
            assert 'already exists' in result.output

    def test_missing_config(self):
        runner = CliRunner()
        result = runner.invoke(cli, ['republish', '-c', 'nonexistent.yaml'])

        assert result.exit_code == 2  # Click's error code for invalid path


class TestCLIWithImages:
    """Tests for CLI with image processing."""

    @pytest.fixture
    def temp_vault_with_images(self):
        temp_dir = tempfile.mkdtemp()
        vault_path = Path(temp_dir)

        note = vault_path / "note.md"
        note.write_text("""---
title: Test Note
tags:
  - evergreen
---

# Test Note

![[diagram.png]]
""")

        assets = vault_path / "assets"
        assets.mkdir()
        img = Image.new('RGB', (100, 100), color='red')
        img.save(assets / "diagram.png")

        yield vault_path
        shutil.rmtree(temp_dir)

    @pytest.fixture
    def temp_output(self):
        temp_dir = tempfile.mkdtemp()
        yield Path(temp_dir)
        shutil.rmtree(temp_dir)

    def test_republish_with_images(self, temp_vault_with_images, temp_output):
        config_path = temp_vault_with_images / "config.yaml"
        config_path.write_text(f"""
vault_path: {temp_vault_with_images}
output_path: {temp_output}
required_tags:
  - evergreen
image_sources:
  - assets
""")

        runner = CliRunner()
        result = runner.invoke(cli, ['republish', '-c', str(config_path)])

        assert result.exit_code == 0

        # Images should be processed
        assert (temp_output / "static/images/diagram.webp").exists()
        assert (temp_output / "static/images/diagram.png").exists()
