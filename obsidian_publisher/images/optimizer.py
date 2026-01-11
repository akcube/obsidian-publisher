"""Image optimization module."""

from pathlib import Path
from typing import List, Optional, Set, Tuple
from PIL import Image
import inflection
import os


class ImageOptimizer:
    """Optimizes images for web: resize, WebP conversion, PNG fallback.

    Creates both WebP and PNG versions of each image for maximum browser compatibility.
    WebP is used where supported, PNG as fallback for older browsers.
    """

    # Supported input image formats
    SUPPORTED_FORMATS = {'.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp', '.tiff'}

    def __init__(
        self,
        max_width: int = 1920,
        webp_quality: int = 85,
        png_optimize: bool = True,
        preserve_transparency: bool = True,
    ):
        """Initialize ImageOptimizer.

        Args:
            max_width: Maximum width for resized images (maintains aspect ratio)
            webp_quality: Quality setting for WebP output (1-100)
            png_optimize: Whether to use PNG optimization
            preserve_transparency: Whether to preserve transparency in images
        """
        self.max_width = max_width
        self.webp_quality = webp_quality
        self.png_optimize = png_optimize
        self.preserve_transparency = preserve_transparency

    def optimize(
        self,
        source_path: Path,
        dest_dir: Path,
        output_name: Optional[str] = None,
    ) -> Tuple[Path, Path]:
        """Optimize an image and create WebP and PNG versions.

        Args:
            source_path: Path to source image
            dest_dir: Directory for output images
            output_name: Base name for output (without extension).
                        If None, uses source filename stem.

        Returns:
            Tuple of (webp_path, png_path) for the created files

        Raises:
            FileNotFoundError: If source image doesn't exist
            ValueError: If source format is not supported
        """
        source_path = Path(source_path)
        dest_dir = Path(dest_dir)

        if not source_path.exists():
            raise FileNotFoundError(f"Source image not found: {source_path}")

        ext = source_path.suffix.lower()
        if ext not in self.SUPPORTED_FORMATS:
            raise ValueError(f"Unsupported image format: {ext}")

        # Determine output name
        base_name = output_name or source_path.stem

        # Create destination directory if needed
        dest_dir.mkdir(parents=True, exist_ok=True)

        # Open and process image
        with Image.open(source_path) as img:
            # Convert to RGB or RGBA based on transparency
            if img.mode in ('RGBA', 'LA') or (img.mode == 'P' and 'transparency' in img.info):
                # Image has transparency
                if self.preserve_transparency:
                    img = img.convert('RGBA')
                else:
                    img = img.convert('RGB')
            elif img.mode != 'RGB':
                img = img.convert('RGB')

            # Resize if needed
            img = self._resize_if_needed(img)

            # Create output paths
            webp_path = dest_dir / f"{base_name}.webp"
            png_path = dest_dir / f"{base_name}.png"

            # Save WebP version
            self._save_webp(img, webp_path)

            # Save PNG version
            self._save_png(img, png_path)

        return webp_path, png_path

    def optimize_batch(
        self,
        source_paths: List[Path],
        dest_dir: Path,
    ) -> List[Tuple[Path, Path]]:
        """Optimize multiple images.

        Args:
            source_paths: List of paths to source images
            dest_dir: Directory for output images

        Returns:
            List of (webp_path, png_path) tuples for each processed image
        """
        results = []
        for source in source_paths:
            try:
                result = self.optimize(source, dest_dir)
                results.append(result)
            except (FileNotFoundError, ValueError) as e:
                print(f"Warning: Skipping {source}: {e}")
        return results

    def find_orphaned_images(
        self,
        image_dir: Path,
        referenced_images: Set[str],
    ) -> List[Path]:
        """Find images in a directory that are not in the referenced set.

        Args:
            image_dir: Directory containing images
            referenced_images: Set of image basenames that are still in use

        Returns:
            List of paths to orphaned images that can be deleted
        """
        image_dir = Path(image_dir)
        if not image_dir.exists():
            return []

        # Normalize referenced images to slugified basenames without extension
        ref_basenames = set()
        for img in referenced_images:
            # Slugify to match the output filenames
            ref_basenames.add(inflection.parameterize(Path(img).stem))

        orphans = []
        for img_path in image_dir.iterdir():
            if img_path.is_file() and img_path.suffix.lower() in {'.webp', '.png', '.jpg', '.jpeg', '.gif'}:
                # Slugify disk filename stem to match against slugified references
                disk_stem = inflection.parameterize(img_path.stem)
                if disk_stem not in ref_basenames:
                    orphans.append(img_path)

        return orphans

    def cleanup_orphans(
        self,
        image_dir: Path,
        referenced_images: Set[str],
        dry_run: bool = False,
    ) -> List[Path]:
        """Remove orphaned images from directory.

        Args:
            image_dir: Directory containing images
            referenced_images: Set of image basenames that are still in use
            dry_run: If True, don't actually delete, just return what would be deleted

        Returns:
            List of paths to deleted (or would-be-deleted) images
        """
        orphans = self.find_orphaned_images(image_dir, referenced_images)

        if not dry_run:
            for orphan in orphans:
                orphan.unlink()

        return orphans

    def _resize_if_needed(self, img: Image.Image) -> Image.Image:
        """Resize image if it exceeds max_width.

        Args:
            img: PIL Image object

        Returns:
            Resized image (or original if no resize needed)
        """
        if img.width <= self.max_width:
            return img

        # Calculate new height maintaining aspect ratio
        ratio = self.max_width / img.width
        new_height = int(img.height * ratio)

        return img.resize((self.max_width, new_height), Image.Resampling.LANCZOS)

    def _save_webp(self, img: Image.Image, output_path: Path) -> None:
        """Save image as WebP.

        Args:
            img: PIL Image object
            output_path: Path for output file
        """
        img.save(
            output_path,
            'WEBP',
            quality=self.webp_quality,
            method=6,  # Slowest but best compression
        )

    def _save_png(self, img: Image.Image, output_path: Path) -> None:
        """Save image as PNG.

        Args:
            img: PIL Image object
            output_path: Path for output file
        """
        img.save(
            output_path,
            'PNG',
            optimize=self.png_optimize,
        )
