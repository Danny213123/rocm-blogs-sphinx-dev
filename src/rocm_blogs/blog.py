"""
Blog class for ROCmBlogs package.
"""

import io
import json
import os
import pathlib
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

from PIL import Image
from sphinx.util import logging as sphinx_logging

# Initialize logger
sphinx_diagnostics = sphinx_logging.getLogger(__name__)


class Blog:
    """
    Represents a blog post with metadata, content, and associated images.

    This class handles blog metadata, image processing, author information,
    and date parsing for the ROCmBlogs package.
    """

    # Define date formats once as a class variable to avoid recreation
    DATE_FORMATS = [
        "%d-%m-%Y",  # e.g. 8-08-2024
        "%d/%m/%Y",  # e.g. 8/08/2024
        "%d-%B-%Y",  # e.g. 8-August-2024
        "%d-%b-%Y",  # e.g. 8-Aug-2024
        "%d %B %Y",  # e.g. 8 August 2024
        "%d %b %Y",  # e.g. 8 Aug 2024
        "%d %B, %Y",  # e.g. 8 August, 2024
        "%d %b, %Y",  # e.g. 8 Aug, 2024
        "%B %d, %Y",  # e.g. August 8, 2024
        "%b %d, %Y",  # e.g. Aug 8, 2024
        "%B %d %Y",  # e.g. August 8 2024
        "%b %d %Y",  # e.g. Aug 8 2024
    ]

    # Month name normalization mapping
    MONTH_NORMALIZATION = {"Sept": "Sep"}

    def __init__(
        self, file_path: str, metadata: Dict[str, Any], image: Optional[bytes] = None
    ):
        """Initialize a Blog instance."""
        self.file_path = file_path
        self.metadata = metadata
        self.image = image
        self.image_paths = []
        self.word_count = 0

        # Dynamically set attributes based on metadata
        for key, value in metadata.items():
            setattr(self, key, value)

        self.date = (
            self.parse_date(metadata.get("date")) if "date" in metadata else None
        )

    def set_word_count(self, word_count: int) -> None:
        """Set the word count for the blog."""
        self.word_count = word_count

    def set_file_path(self, file_path: str) -> None:
        """Set the file path for the blog."""
        self.file_path = file_path

    def normalize_date_string(self, date_str: str) -> str:
        """Normalize the date string for consistent parsing."""
        for original, replacement in self.MONTH_NORMALIZATION.items():
            date_str = date_str.replace(original, replacement)

        return date_str

    def grab_metadata(self) -> Dict[str, Any]:
        """Return the metadata dictionary."""
        return self.metadata

    def grab_og_image(self) -> str:
        return (
            self.metadata.get("myst")
            .get("html_meta")
            .get("property=og:image", "https://rocm.blogs.amd.com/_images/generic.jpg")
        )

    def grab_og_description(self) -> str:
        return (
            self.metadata.get("myst")
            .get("html_meta")
            .get("property=og:description", "No description available.")
        )

    def grab_og_href(self) -> str:
        return (
            self.metadata.get("myst")
            .get("html_meta")
            .get("property=og:url", "https://rocm.blogs.amd.com/")
        )

    def load_image_to_memory(self, image_path: str, format: str = "PNG") -> None:
        """Load an image into memory."""
        try:
            with Image.open(image_path) as img:
                buffer = io.BytesIO()
                img.save(buffer, format=format)
                buffer.seek(0)
                self.image = buffer.getvalue()
                sphinx_diagnostics.info(
                    f"Image loaded into memory; size: {len(self.image)} bytes."
                )
        except Exception as error:
            sphinx_diagnostics.error(f"Error loading image to memory: {error}")

    def to_json(self) -> str:
        """Convert the blog metadata to JSON format."""
        try:
            return json.dumps(self.metadata, indent=4)
        except Exception as error:
            sphinx_diagnostics.error(f"Error converting metadata to JSON: {error}")
            return "{}"

    def save_image(self, output_path: str) -> None:
        """Save the image to disk."""
        if self.image is None:
            sphinx_diagnostics.warning("No image data available in memory to save.")
            return

        try:
            with open(output_path, "wb") as file:
                file.write(self.image)
                sphinx_diagnostics.info(f"Image saved to disk at: {output_path}")
        except Exception as error:
            sphinx_diagnostics.error(f"Error saving image to disk: {error}")

    def save_image_path(self, image_path: str) -> None:
        """Save the image path for later use."""
        self.image_paths.append(image_path)

    def parse_date(self, date_str: Optional[str]) -> Optional[datetime]:
        """Parse the date string into a datetime object."""
        if not date_str:
            return None

        # Normalize the date string
        date_str = self.normalize_date_string(date_str)

        # Try each date format
        for fmt in self.DATE_FORMATS:
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue

        sphinx_diagnostics.warning(
            f"Invalid date format in {self.file_path}: {date_str}"
        )
        return None

    def grab_href(self) -> str:
        """Generate the HTML href for the blog."""
        return self.file_path.replace(".md", ".html").replace("\\", "/")

    def grab_authors_list(self) -> List[str]:
        """Extract authors from the metadata."""

        sphinx_diagnostics.info(f"Extracting authors from metadata: {self.file_path}")

        sphinx_diagnostics.info(f"Authors metadata: {self.author}")

        if not self.author:
            return []

        sphinx_diagnostics.info(f"Author type: {type(self.author)}")

        # Ensure authors is a list
        if isinstance(self.author, str):
            authors = list(self.author.split(", "))

        sphinx_diagnostics.info(f"Authors after split: {authors}")

        return authors

    def grab_authors(self, authors_list: List[Union[str, List[str]]], rocm_blogs) -> str:
        """Generate HTML links for authors, but only if their bio file exists."""
        # Filter out invalid authors
        valid_authors = []
        for author in authors_list:
            if isinstance(author, list):
                author_str = " ".join(author).strip()
            else:
                author_str = str(author).strip()

            if author_str and author_str.lower() != "no author":
                valid_authors.append(author_str)

        if not valid_authors:
            return ""

        # Process each author
        author_elements = []
        for author in valid_authors:
            # Check if author has a page using the more robust approach
            if pathlib.Path.exists(
                pathlib.Path(rocm_blogs.blogs_directory)
                / f"authors/{author.replace(' ', '-').lower()}.md"
            ):
                author_link = f"https://rocm.blogs.amd.com/authors/{author.replace(' ', '-').lower()}.html"
                author_elements.append(f'<a href="{author_link}">{author}</a>')
            else:
                # Use plain text if no author file exists
                author_elements.append(author)

        return ", ".join(author_elements)


    def grab_image(self, rocmblogs) -> pathlib.Path:
        """Find the image for the blog and return its path."""
        image = getattr(self, "thumbnail", None)

        if not image:
            # First check if generic.webp exists in blogs/images directory
            blogs_generic_webp = None
            if hasattr(rocmblogs, "blogs_directory") and rocmblogs.blogs_directory:
                blogs_generic_webp_path = os.path.join(
                    rocmblogs.blogs_directory, "images", "generic.webp"
                )
                if os.path.exists(blogs_generic_webp_path):
                    blogs_generic_webp = blogs_generic_webp_path

            # Then check if generic.webp exists in static/images directory
            static_generic_webp_path = os.path.join(
                os.path.dirname(os.path.dirname(__file__)),
                "static",
                "images",
                "generic.webp",
            )
            static_generic_webp = os.path.exists(static_generic_webp_path)

            # Use blogs/images/generic.webp if available, otherwise use
            # static/images/generic.webp
            if blogs_generic_webp:
                self.image = "generic.webp"
                self.save_image_path("generic.webp")
                return pathlib.Path("./images/generic.webp")
            elif static_generic_webp:
                self.image = "generic.webp"
                self.save_image_path("generic.webp")
                return pathlib.Path("./images/generic.webp")
            else:
                # Fall back to generic.jpg if no WebP version is available
                self.image = "generic.jpg"
                self.save_image_path("generic.jpg")
                return pathlib.Path("./images/generic.jpg")

        # Extract just the filename if a path is provided
        if "/" in image or "\\" in image:
            image = os.path.basename(image)

        # Check if it's an absolute path
        if os.path.isabs(image) and os.path.exists(image):
            full_image_path = pathlib.Path(image)
            self.save_image_path(os.path.basename(str(full_image_path)))
            return self._get_relative_path(full_image_path, rocmblogs.blogs_directory)

        # Find the image in various locations
        full_image_path = self._find_image_in_directories(
            image, rocmblogs.blogs_directory
        )

        if not full_image_path:
            # Check if generic.webp exists
            generic_webp_path = os.path.join(
                os.path.dirname(os.path.dirname(__file__)),
                "static",
                "images",
                "generic.webp",
            )
            if os.path.exists(generic_webp_path):
                self.image = "generic.webp"
                self.save_image_path("generic.webp")
                return pathlib.Path("./images/generic.webp")
            else:
                self.image = "generic.jpg"
                self.save_image_path("generic.jpg")
                return pathlib.Path("./images/generic.jpg")

        # Save the image path and return the relative path
        image_name = os.path.basename(str(full_image_path))
        self.save_image_path(image_name)

        return self._get_relative_path(full_image_path, rocmblogs.blogs_directory)

    def _find_image_in_directories(
        self, image: str, blogs_directory: str
    ) -> Optional[pathlib.Path]:
        """Search for an image in various directories."""
        blog_dir = pathlib.Path(self.file_path).parent
        blogs_dir = pathlib.Path(blogs_directory)

        # Check if there's a WebP version of the image
        image_base, image_ext = os.path.splitext(image)
        webp_image = image_base + ".webp"

        # Define search paths in order of priority
        search_paths = [
            blog_dir / webp_image,
            blog_dir / "images" / webp_image,
            blog_dir / image,
            blog_dir / "images" / image,
            blog_dir.parent / webp_image,
            blog_dir.parent / "images" / webp_image,
            blog_dir.parent / image,
            blog_dir.parent / "images" / image,
        ]

        parent2 = blog_dir.parent.parent
        if parent2 != blogs_dir:
            search_paths.extend(
                [
                    parent2 / webp_image,
                    parent2 / "images" / webp_image,
                    parent2 / image,
                    parent2 / "images" / image,
                ]
            )

            parent3 = parent2.parent
            if parent3 != blogs_dir:
                search_paths.extend(
                    [
                        parent3 / webp_image,
                        parent3 / "images" / webp_image,
                        parent3 / image,
                        parent3 / "images" / image,
                    ]
                )

        search_paths.extend(
            [
                blog_dir.parent / "images" / webp_image,
                blogs_dir / "images" / webp_image,
                blogs_dir / "images" / webp_image.lower(),
                blog_dir.parent / "images" / image,
                blogs_dir / "images" / image,
                blogs_dir / "images" / image.lower(),
            ]
        )

        # Check each path
        for path in search_paths:
            if path.exists() and path.is_file():
                if str(path).lower().endswith(".webp"):
                    sphinx_diagnostics.info(f"Using WebP version for image: {path}")
                return path

        # Try partial matching in the global images directory
        images_dir = blogs_dir / "images"
        if images_dir.exists():
            webp_base = os.path.splitext(image)[0].lower()
            for img_file in images_dir.glob("*.webp"):
                if img_file.is_file() and webp_base in img_file.name.lower():
                    sphinx_diagnostics.info(
                        f"Found WebP version by partial matching: {img_file}"
                    )
                    return img_file

            # If no WebP version found, try to find original image by partial
            # matching
            image_base = os.path.splitext(image)[0].lower()
            for img_file in images_dir.glob("*"):
                if img_file.is_file() and image_base in img_file.name.lower():
                    if not str(img_file).lower().endswith(".webp"):
                        try:
                            with Image.open(img_file) as img:
                                original_width, original_height = img.size

                                webp_img = img
                                if img.mode not in ("RGB", "RGBA"):
                                    webp_img = img.convert("RGB")

                                if original_width > 1200 or original_height > 700:
                                    scaling_factor = min(
                                        1200 / original_width, 700 / original_height
                                    )

                                    new_width = int(original_width * scaling_factor)
                                    new_height = int(original_height * scaling_factor)

                                    webp_img = webp_img.resize(
                                        (new_width, new_height), resample=Image.LANCZOS
                                    )
                                    sphinx_diagnostics.info(
                                        f"Resized image from {original_width}x{original_height} to {new_width}x{new_height}"
                                    )

                                webp_path = os.path.splitext(str(img_file))[0] + ".webp"
                                webp_img.save(
                                    webp_path, format="WEBP", quality=85, method=6
                                )

                                # Return the WebP version
                                sphinx_diagnostics.info(
                                    f"Successfully converted {img_file} to WebP: {webp_path}"
                                )
                                return pathlib.Path(webp_path)
                        except Exception as e:
                            sphinx_diagnostics.warning(
                                f"Failed to convert {img_file} to WebP: {e}"
                            )

                    return img_file

        return None

    def _get_relative_path(
        self, full_path: pathlib.Path, base_dir: str
    ) -> pathlib.Path:
        """Convert an absolute path to a relative path."""
        relative_path = os.path.relpath(str(full_path), str(base_dir))
        relative_path = relative_path.replace("\\", "/")

        if not relative_path.startswith("./"):
            relative_path = "./" + relative_path

        return pathlib.Path(relative_path)

    def __repr__(self) -> str:
        """Return a string representation of the class."""
        return f"Blog(file_path='{self.file_path}', metadata={self.metadata})"
