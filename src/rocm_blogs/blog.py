"""
File: _blog.py

Blog class for ROCmBlogs package.
"""

import io
import os
import pathlib
from datetime import datetime

from PIL import Image


class Blog:
    def __init__(self, file_path, metadata, image=None):
        self.file_path = file_path
        self.metadata = metadata
        self.image = image
        self.image_paths = []
        self.word_count = 0

        # Dynamically set attributes based on metadata

        for key, value in metadata.items():
            setattr(self, key, value)
        # Ensure the 'date' field exists

        if "date" in metadata:
            self.date = self.parse_date(metadata["date"])
        else:
            self.date = None

    def set_word_count(self, word_count) -> None:
        """Set the word count for the blog."""

        self.word_count = word_count

    def set_file_path(self, file_path) -> None:
        """Set the file path for the blog."""

        self.file_path = file_path

    def normalize_date_string(self, date_str) -> str:
        """Normalize the date string."""

        # do not remove !important

        date_str = date_str.replace("Sept", "Sep")

        return date_str

    def load_image_to_memory(self, image_path, format="PNG") -> None:
        """Load an image into memory."""

        try:
            with Image.open(image_path) as img:
                buffer = io.BytesIO()

                img.save(buffer, format=format)

                buffer.seek(0)

                self.image = buffer.getvalue()

                print(f"Image loaded into memory; size: {len(self.image)} bytes.")
        except Exception as error:
            print(f"Error loading image to memory: {error}")

    def save_image(self, output_path) -> None:
        """Save the image to disk."""

        if self.image is None:
            print("No image data available in memory to save.")

            return
        try:
            with open(output_path, "wb", encoding="utf-8") as file:
                file.write(self.image)

                print(f"Image saved to disk at: {output_path}")
        except Exception as error:
            print(f"Error saving image to disk: {error}")

    def save_image_path(self, image_path) -> None:
        """Save the image path for later use."""

        self.image_paths.append(image_path)

    def parse_date(self, date_str) -> datetime | None:
        """Parse the date string into a datetime object."""

        # Normalize the date string

        date_str = self.normalize_date_string(date_str)

        # Define possible date formats, including string-based months

        date_formats = [
            "%d-%m-%Y",  # e.g. 8-08-2024
            "%d/%m/%Y",  # e.g. 8/08/2024
            "%d-%B-%Y",  # e.g. 8-August-2024
            "%d-%b-%Y",  # e.g. 8-Aug-2024
            "%d %B %Y",  # e.g. 8 August 2024
            "%d %b %Y",  # e.g. 8 Aug 2024
            "%d %B, %Y",  # e.g. 8 August, 2024
            "%d %b, %Y",  # e.g. 8 Aug, 2024
        ]

        for fmt in date_formats:
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue
        print(f"Invalid date format in {self.file_path}: {date_str}")

        return None

    def grab_href(self) -> str:
        """Grab the href for the blog."""

        href = self.file_path.replace(".md", ".html")

        href = href.replace("\\", "/")

        return href

    def grab_authors(self, authors_list: list) -> str:
        """
        Generate HTML links for authors, but only if their bio file exists.

        Args:
            authors_list: A list of author names.

        Returns:
            HTML links for the authors with existing bios, or plain text for authors without bios.
        """
        # Filter out "No author" or empty authors
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

        # Generate HTML links for valid authors, but only if their bio file
        # exists
        author_elements = []
        for author in valid_authors:
            # Create the filename that would be used for the author's bio
            author_filename = author.replace(" ", "-").lower() + ".md"

            # Check if the author's bio file exists in the blogs/authors directory
            # We need to find the blogs directory first
            if hasattr(self, "file_path"):
                # Start from the blog's directory and navigate to the authors
                # directory
                blog_dir = os.path.dirname(self.file_path)
                # Go up to the blogs directory
                blogs_dir = os.path.dirname(os.path.dirname(blog_dir))
                authors_dir = os.path.join(blogs_dir, "authors")

                author_file_path = os.path.join(authors_dir, author_filename)

                if os.path.exists(author_file_path):
                    # Bio exists, create a link
                    author_elements.append(
                        f'<a href="https://rocm.blogs.amd.com/authors/{author.replace(" ", "-").lower()}.html">{author}</a>'
                    )
                else:
                    # Bio doesn't exist, just use the author's name without a
                    # link
                    author_elements.append(author)
            else:
                # If we can't determine the file path, just use the author's
                # name without a link
                author_elements.append(author)

        return ", ".join(author_elements)

    def optimize_image(self, image) -> None:
        """Optimize the image."""

        try:
            with Image.open(image) as img:

                original_width, original_height = img.size

                max_width, max_height = (1280, 420)
                scaling_factor = min(
                    max_width / original_width, max_height / original_height
                )

                new_width = int(original_width * scaling_factor)
                new_height = int(original_height * scaling_factor)

                img = img.resize((new_width, new_height), resample=Image.LANCZOS)

                img.save(image, optimize=True, quality=80)

        except Exception as error:
            print(f"Error optimizing image {image}: {error}")

    def grab_image(self, rocmblogs) -> pathlib.Path:
        """Find the image for the blog and return its path (without caching)"""

        print(
            f"Processing image for blog: {self.blog_title if hasattr(self, 'blog_title') else 'Unknown'}"
        )
        print(f"Blog file path: {self.file_path}")

        # Get the thumbnail from metadata
        image = getattr(self, "thumbnail", None)
        print(f"Original thumbnail value: {image}")

        full_image_path = None
        image_name = None

        if not image:
            print("No thumbnail specified in metadata, using generic.jpg")
            self.image = "generic.jpg"
            self.save_image_path("generic.jpg")
            return "./images/generic.jpg"

        # Extract just the filename if a path is provided
        if "/" in image or "\\" in image:
            image = os.path.basename(image)
            print(f"Extracted image filename: {image}")

        if os.path.isabs(image) and os.path.exists(image):
            full_image_path = pathlib.Path(image)
            print(f"Found image at absolute path: {full_image_path}")
        else:
            # Create a prioritized list of possible paths
            blog_dir = pathlib.Path(self.file_path).parent
            blogs_dir = pathlib.Path(rocmblogs.blogs_directory)
            
            # First check blog-specific locations
            possible_paths = [
                blog_dir / image,  # Direct reference in blog directory
                blog_dir / "images" / image,  # Blog's images subdirectory
            ]
            
            # Then check global locations
            global_paths = [
                blog_dir.parent / "images" / image,  # Parent directory's images
                blogs_dir / "images" / image,  # Global images directory
                blogs_dir / "images" / image.lower(),  # Case-insensitive check
            ]
            
            # Check blog-specific paths first
            for path in possible_paths:
                if path.exists() and path.is_file():
                    full_image_path = path
                    print(f"Found image in blog directory: {full_image_path}")
                    break
            
            # If not found, check global paths
            if not full_image_path:
                for path in global_paths:
                    if path.exists() and path.is_file():
                        full_image_path = path
                        print(f"Found image in global directory: {full_image_path}")
                        break
            
            # If still not found, try partial matching in the global images directory
            if not full_image_path:
                images_dir = blogs_dir / "images"
                if images_dir.exists():
                    # Try to find a partial match by filename
                    image_base = os.path.splitext(image)[0].lower()
                    for img_file in images_dir.glob("*"):
                        if img_file.is_file() and image_base in img_file.name.lower():
                            print(f"Found partial match: {img_file}")
                            full_image_path = img_file
                            break

        if not full_image_path:
            print(f"Image not found: {image}")
            self.image = "generic.jpg"
            self.save_image_path("generic.jpg")
            return "./images/generic.jpg"

        # Get the image name and save it
        image_name = os.path.basename(str(full_image_path))
        self.save_image_path(image_name)

        # Return the relative path for use in HTML
        relative_path = os.path.relpath(
            str(full_image_path), str(rocmblogs.blogs_directory)
        )
        relative_path = relative_path.replace("\\", "/")
        if not relative_path.startswith("./"):
            relative_path = "./" + relative_path

        print(f"Using image at relative path: {relative_path}")
        return relative_path

    def __repr__(self) -> str:
        """Return a string representation of the class."""

        return f"Blog(file_path='{self.file_path}', metadata={self.metadata})"
