"""Tests for ImageOptimizer class."""

import pytest
from pathlib import Path
import tempfile
import shutil
from PIL import Image

from obsidian_publisher.images.optimizer import ImageOptimizer


class TestImageOptimizer:
    """Tests for ImageOptimizer class."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory."""
        temp = tempfile.mkdtemp()
        yield Path(temp)
        shutil.rmtree(temp)

    @pytest.fixture
    def sample_rgb_image(self, temp_dir):
        """Create a sample RGB image."""
        img_path = temp_dir / "sample.png"
        img = Image.new('RGB', (200, 100), color='red')
        img.save(img_path)
        return img_path

    @pytest.fixture
    def sample_rgba_image(self, temp_dir):
        """Create a sample RGBA image with transparency."""
        img_path = temp_dir / "transparent.png"
        img = Image.new('RGBA', (200, 100), color=(255, 0, 0, 128))
        img.save(img_path)
        return img_path

    @pytest.fixture
    def large_image(self, temp_dir):
        """Create a large image that needs resizing."""
        img_path = temp_dir / "large.png"
        img = Image.new('RGB', (3000, 2000), color='blue')
        img.save(img_path)
        return img_path

    def test_optimize_creates_webp_and_png(self, temp_dir, sample_rgb_image):
        optimizer = ImageOptimizer()
        dest_dir = temp_dir / "output"

        webp_path, png_path = optimizer.optimize(sample_rgb_image, dest_dir)

        assert webp_path.exists()
        assert png_path.exists()
        assert webp_path.suffix == ".webp"
        assert png_path.suffix == ".png"

    def test_optimize_preserves_name(self, temp_dir, sample_rgb_image):
        optimizer = ImageOptimizer()
        dest_dir = temp_dir / "output"

        webp_path, png_path = optimizer.optimize(sample_rgb_image, dest_dir)

        assert webp_path.stem == "sample"
        assert png_path.stem == "sample"

    def test_optimize_custom_name(self, temp_dir, sample_rgb_image):
        optimizer = ImageOptimizer()
        dest_dir = temp_dir / "output"

        webp_path, png_path = optimizer.optimize(
            sample_rgb_image, dest_dir, output_name="custom"
        )

        assert webp_path.stem == "custom"
        assert png_path.stem == "custom"

    def test_optimize_creates_dest_dir(self, temp_dir, sample_rgb_image):
        optimizer = ImageOptimizer()
        dest_dir = temp_dir / "nested" / "output"

        optimizer.optimize(sample_rgb_image, dest_dir)

        assert dest_dir.exists()

    def test_optimize_resizes_large_images(self, temp_dir, large_image):
        optimizer = ImageOptimizer(max_width=1920)
        dest_dir = temp_dir / "output"

        optimizer.optimize(large_image, dest_dir)

        # Check that output image is resized
        with Image.open(dest_dir / "large.png") as img:
            assert img.width == 1920
            # Check aspect ratio preserved
            assert img.height == 1280  # 2000 * (1920/3000)

    def test_optimize_preserves_smaller_images(self, temp_dir, sample_rgb_image):
        optimizer = ImageOptimizer(max_width=1920)
        dest_dir = temp_dir / "output"

        optimizer.optimize(sample_rgb_image, dest_dir)

        # Check that small image is not resized
        with Image.open(dest_dir / "sample.png") as img:
            assert img.width == 200
            assert img.height == 100

    def test_optimize_preserves_transparency(self, temp_dir, sample_rgba_image):
        optimizer = ImageOptimizer(preserve_transparency=True)
        dest_dir = temp_dir / "output"

        optimizer.optimize(sample_rgba_image, dest_dir)

        # Check that PNG preserves transparency
        with Image.open(dest_dir / "transparent.png") as img:
            assert img.mode == 'RGBA'

    def test_optimize_nonexistent_source(self, temp_dir):
        optimizer = ImageOptimizer()
        dest_dir = temp_dir / "output"

        with pytest.raises(FileNotFoundError):
            optimizer.optimize(temp_dir / "nonexistent.png", dest_dir)

    def test_optimize_unsupported_format(self, temp_dir):
        optimizer = ImageOptimizer()
        dest_dir = temp_dir / "output"

        # Create a file with unsupported extension
        fake_file = temp_dir / "file.txt"
        fake_file.write_text("not an image")

        with pytest.raises(ValueError, match="Unsupported"):
            optimizer.optimize(fake_file, dest_dir)

    def test_optimize_batch(self, temp_dir):
        optimizer = ImageOptimizer()
        dest_dir = temp_dir / "output"

        # Create multiple images
        images = []
        for i in range(3):
            img_path = temp_dir / f"image{i}.png"
            img = Image.new('RGB', (100, 100), color='green')
            img.save(img_path)
            images.append(img_path)

        results = optimizer.optimize_batch(images, dest_dir)

        assert len(results) == 3
        for webp_path, png_path in results:
            assert webp_path.exists()
            assert png_path.exists()

    def test_optimize_batch_skips_errors(self, temp_dir):
        optimizer = ImageOptimizer()
        dest_dir = temp_dir / "output"

        # Create valid and invalid paths
        valid = temp_dir / "valid.png"
        img = Image.new('RGB', (100, 100), color='blue')
        img.save(valid)

        invalid = temp_dir / "nonexistent.png"

        results = optimizer.optimize_batch([valid, invalid], dest_dir)

        # Should only get result for valid image
        assert len(results) == 1


class TestOrphanDetection:
    """Tests for orphan image detection and cleanup."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory."""
        temp = tempfile.mkdtemp()
        yield Path(temp)
        shutil.rmtree(temp)

    @pytest.fixture
    def image_dir(self):
        """Create a directory with test images."""
        temp = tempfile.mkdtemp()
        image_dir = Path(temp)

        # Create some images
        for name in ["used1", "used2", "orphan1", "orphan2"]:
            for ext in [".webp", ".png"]:
                img = Image.new('RGB', (10, 10), color='white')
                img.save(image_dir / f"{name}{ext}")

        yield image_dir
        shutil.rmtree(temp)

    def test_find_orphaned_images(self, image_dir):
        optimizer = ImageOptimizer()

        referenced = {"used1.png", "used2.webp"}  # Reference with various extensions
        orphans = optimizer.find_orphaned_images(image_dir, referenced)

        orphan_stems = {p.stem for p in orphans}
        assert "orphan1" in orphan_stems
        assert "orphan2" in orphan_stems
        assert "used1" not in orphan_stems
        assert "used2" not in orphan_stems

    def test_find_orphaned_empty_dir(self, temp_dir):
        optimizer = ImageOptimizer()

        orphans = optimizer.find_orphaned_images(temp_dir / "nonexistent", set())

        assert orphans == []

    def test_cleanup_orphans_dry_run(self, image_dir):
        optimizer = ImageOptimizer()

        referenced = {"used1.png", "used2.png"}
        orphans = optimizer.cleanup_orphans(image_dir, referenced, dry_run=True)

        # Should return orphans but not delete them
        assert len(orphans) > 0
        for orphan in orphans:
            assert orphan.exists()  # Still exists

    def test_cleanup_orphans_delete(self, image_dir):
        optimizer = ImageOptimizer()

        referenced = {"used1.png", "used2.png"}
        orphans = optimizer.cleanup_orphans(image_dir, referenced, dry_run=False)

        # Orphans should be deleted
        for orphan in orphans:
            assert not orphan.exists()

        # Referenced images should still exist
        assert (image_dir / "used1.webp").exists()
        assert (image_dir / "used1.png").exists()


class TestImageFormats:
    """Tests for various image format handling."""

    @pytest.fixture
    def temp_dir(self):
        temp = tempfile.mkdtemp()
        yield Path(temp)
        shutil.rmtree(temp)

    def test_jpg_input(self, temp_dir):
        optimizer = ImageOptimizer()
        dest_dir = temp_dir / "output"

        # Create JPG image
        img_path = temp_dir / "test.jpg"
        img = Image.new('RGB', (100, 100), color='red')
        img.save(img_path, 'JPEG')

        webp_path, png_path = optimizer.optimize(img_path, dest_dir)

        assert webp_path.exists()
        assert png_path.exists()

    def test_gif_input(self, temp_dir):
        optimizer = ImageOptimizer()
        dest_dir = temp_dir / "output"

        # Create GIF image
        img_path = temp_dir / "test.gif"
        img = Image.new('P', (100, 100))
        img.save(img_path, 'GIF')

        webp_path, png_path = optimizer.optimize(img_path, dest_dir)

        assert webp_path.exists()
        assert png_path.exists()

    def test_webp_input(self, temp_dir):
        optimizer = ImageOptimizer()
        dest_dir = temp_dir / "output"

        # Create WebP image
        img_path = temp_dir / "test.webp"
        img = Image.new('RGB', (100, 100), color='green')
        img.save(img_path, 'WEBP')

        webp_path, png_path = optimizer.optimize(img_path, dest_dir)

        assert webp_path.exists()
        assert png_path.exists()

    def test_quality_settings(self, temp_dir):
        dest_dir = temp_dir / "output"

        # Create source image with a gradient (shows quality differences better)
        img_path = temp_dir / "test.png"
        img = Image.new('RGB', (500, 500))
        pixels = img.load()
        for i in range(500):
            for j in range(500):
                pixels[i, j] = (i % 256, j % 256, (i + j) % 256)
        img.save(img_path)

        # High quality
        optimizer_high = ImageOptimizer(webp_quality=95)
        high_webp, _ = optimizer_high.optimize(img_path, dest_dir / "high")

        # Low quality
        optimizer_low = ImageOptimizer(webp_quality=20)
        low_webp, _ = optimizer_low.optimize(img_path, dest_dir / "low")

        # Both files should exist and be valid
        assert high_webp.exists()
        assert low_webp.exists()
        # Lower quality should result in smaller file for complex images
        assert low_webp.stat().st_size < high_webp.stat().st_size
