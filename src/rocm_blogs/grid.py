import os
import time
from pathlib import Path

from PIL import Image
from sphinx.util import logging as sphinx_logging

from .logger.logger import *


def generate_grid(ROCmBlogs, blog, lazy_load=False, use_og=False) -> str:
    """Takes a blog and creates a sphinx grid item with WebP image support."""
    grid_start_time = time.time()

    log_file_handle = None
    if is_logging_enabled_from_config():
        try:
            logs_dir = Path("logs")
            logs_dir.mkdir(exist_ok=True)
            log_filepath = logs_dir / "grid_generation.log"

            log_file_handle = open(log_filepath, "a", encoding="utf-8")
        except Exception as log_error:
            log_file_handle = None

    safe_log_write(
        log_file_handle,
        f"Starting grid generation for blog - lazy_load: {lazy_load}, use_og: {use_og}\n",
    )

    blog_title = blog.blog_title if hasattr(blog, "blog_title") else "No Title"
    blog_file_path = getattr(blog, "file_path", "Unknown path")

    safe_log_write(
        log_file_handle,
        f"Grid generation details - Title: '{blog_title}', Path: '{blog_file_path}', use_og: {use_og}, lazy_load: {lazy_load}\n",
    )

    grid_template = """
:::{{grid-item-card}}
:padding: 1
:img-top: {image}
:class-img-top: small-sd-card-img-top
:class-body: small-sd-card
:class: small-sd-card
:img-lazy-load: true
+++
<a href="{href}" class="small-card-header-link">
    <h2 class="card-header">{title}</h2>
</a>
<p class="paragraph">{description}</p>
<div class="date">{date} {authors_html}</div>
:::
"""

    title = blog_title
    safe_log_write(log_file_handle, f"Grid item title: '{title}'\n")

    date = blog.date.strftime("%B %d, %Y") if blog.date else "No Date"
    safe_log_write(log_file_handle, f"Grid item date: '{date}'\n")

    description = "No Description"
    if hasattr(blog, "myst") and blog.myst:
        html_meta = blog.myst.get("html_meta", {})
        if html_meta and "description lang=en" in html_meta:
            description = html_meta["description lang=en"]
            safe_log_write(
                log_file_handle,
                f"Using description from myst html_meta: '{description[:50]}...' (length: {len(description)})\n",
            )
        else:
            html_meta_keys = list(html_meta.keys()) if html_meta else []
            safe_log_write(
                log_file_handle,
                f"Myst metadata found but no 'description lang=en' field. Available keys: {html_meta_keys}\n",
            )
    else:
        has_myst = hasattr(blog, "myst")
        myst_value = getattr(blog, "myst", None)
        safe_log_write(
            log_file_handle,
            f"No myst metadata found, using default description. has_myst: {has_myst}, myst_value: {myst_value}\n",
        )

    authors_list = getattr(blog, "author", "").split(",")
    safe_log_write(
        log_file_handle,
        f"Authors list for grid item: {authors_list} (count: {len(authors_list)})\n",
    )

    if use_og:
        safe_log_write(
            log_file_handle,
            f"AUTHOR PAGE MODE: Using OpenGraph metadata for grid item: '{title}'\n",
        )
        safe_log_write(
            log_file_handle,
            f"AUTHOR PAGE: Blog path: '{blog_file_path}', use_og: {use_og}\n",
        )

        try:
            og_image = blog.grab_og_grid_image()
            safe_log_write(
                log_file_handle,
                f"AUTHOR PAGE: Retrieved OpenGraph image: '{og_image}' for blog: '{title}'\n",
            )

            if og_image is None:
                safe_log_write(
                    log_file_handle,
                    f"AUTHOR PAGE: No OpenGraph image found for '{title}', falling back to regular image processing\n",
                )
                try:
                    regular_image = blog.grab_image(ROCmBlogs)
                    image_str = str(regular_image)
                    if image_str.startswith("./"):
                        image_str = image_str[2:]
                    image_str = image_str.replace("\\", "/")

                    image_filename = os.path.basename(image_str)
                    if image_filename.lower().endswith((".jpg", ".jpeg", ".png")):
                        base_name = os.path.splitext(image_filename)[0]
                        image_filename = f"{base_name}.webp"
                        safe_log_write(
                            log_file_handle,
                            f"AUTHOR PAGE: Converted image filename to WebP: '{image_filename}'\n",
                        )

                    image = f"https://rocm.blogs.amd.com/_images/{image_filename}"
                    safe_log_write(
                        log_file_handle,
                        f"AUTHOR PAGE: Using fallback image: '{image}' for blog: '{title}'\n",
                    )
                except Exception as fallback_error:
                    safe_log_write(
                        log_file_handle,
                        f"AUTHOR PAGE: Error getting fallback image for '{title}': {fallback_error}\n",
                    )
                    image = "https://rocm.blogs.amd.com/_images/generic.webp"
            else:
                image = og_image
        except Exception as og_image_error:
            safe_log_write(
                log_file_handle,
                f"AUTHOR PAGE: Error getting OpenGraph image for '{title}': {og_image_error}\n",
            )
            image = "https://rocm.blogs.amd.com/_images/generic.webp"

        try:
            og_href = blog.grab_og_href()
            safe_log_write(
                log_file_handle,
                f"AUTHOR PAGE: Retrieved OpenGraph href: '{og_href}' for blog: '{title}'\n",
            )

            if og_href is None:
                safe_log_write(
                    log_file_handle,
                    f"AUTHOR PAGE: No OpenGraph href found for '{title}', falling back to regular href processing\n",
                )
                try:
                    raw_href = blog.grab_href()
                    if hasattr(raw_href, "split"):
                        href = raw_href.replace(".md", ".html").replace("\\", "/")
                    else:
                        href = str(raw_href).replace(".md", ".html").replace("\\", "/")

                    if not href.startswith("http"):
                        if "/blogs/" in href:
                            blog_path = href.split("/blogs/")[-1]
                            href = f"https://rocm.blogs.amd.com/{blog_path}"
                        else:
                            if href.startswith("./"):
                                href = href[2:]
                            href = f"https://rocm.blogs.amd.com/{href}"

                    safe_log_write(
                        log_file_handle,
                        f"AUTHOR PAGE: Using fallback href: '{href}' for blog: '{title}'\n",
                    )
                except Exception as fallback_error:
                    safe_log_write(
                        log_file_handle,
                        f"AUTHOR PAGE: Error getting fallback href for '{title}': {fallback_error}\n",
                    )
                    href = "#"
            else:
                href = og_href
        except Exception as og_href_error:
            safe_log_write(
                log_file_handle,
                f"AUTHOR PAGE: Error getting OpenGraph href for '{title}': {og_href_error}\n",
            )
            href = "#"

        safe_log_write(
            log_file_handle,
            f"AUTHOR PAGE: Final OpenGraph values for '{title}' - Image: '{image}', Href: '{href}'\n",
        )

    else:
        safe_log_write(
            log_file_handle,
            f"REGULAR MODE: Processing regular image for grid item: '{title}'\n",
        )

        if hasattr(blog, "thumbnail") and blog.thumbnail:
            thumbnail_path = blog.thumbnail
            webp_thumbnail_path = os.path.splitext(thumbnail_path)[0] + ".webp"

            safe_log_write(
                log_file_handle,
                f"REGULAR MODE: Blog has thumbnail: '{thumbnail_path}', checking for WebP version: '{webp_thumbnail_path}'\n",
            )

            if os.path.exists(
                os.path.join(ROCmBlogs.blogs_directory, webp_thumbnail_path)
            ):
                safe_log_write(
                    log_file_handle,
                    f"REGULAR MODE: Using WebP version from blogs directory: '{webp_thumbnail_path}'\n",
                )
                blog.thumbnail = webp_thumbnail_path
            elif os.path.exists(
                os.path.join(os.path.dirname(blog.file_path), webp_thumbnail_path)
            ):
                safe_log_write(
                    log_file_handle,
                    f"REGULAR MODE: Using WebP version from blog directory: '{webp_thumbnail_path}'\n",
                )
                blog.thumbnail = webp_thumbnail_path
            elif os.path.exists(
                os.path.join(
                    os.path.dirname(blog.file_path), "images", webp_thumbnail_path
                )
            ):
                safe_log_write(
                    log_file_handle,
                    f"REGULAR MODE: Using WebP version from blog images directory: '{webp_thumbnail_path}'\n",
                )
                blog.thumbnail = webp_thumbnail_path
            else:
                safe_log_write(
                    log_file_handle,
                    f"REGULAR MODE: No WebP version found for thumbnail: '{thumbnail_path}'\n",
                )

        safe_log_write(
            log_file_handle, f"REGULAR MODE: Calling blog.grab_image() for: '{title}'\n"
        )

        try:
            try:
                log_file_handle.write(
                    f"REGULAR MODE: Attempting to call blog.grab_grid_image() for '{title}'\n"
                )
                image = blog.grab_grid_image(ROCmBlogs)
                log_file_handle.write(
                    f"REGULAR MODE: Successfully retrieved image from blog.grab_grid_image(): '{image}' (type: {type(image).__name__})\n"
                )
            except AttributeError:
                image = blog.grab_image(ROCmBlogs)
            image_str = str(image)

            safe_log_write(
                log_file_handle,
                f"REGULAR MODE: Retrieved image from blog.grab_image(): '{image_str}' (type: {type(image).__name__})\n",
            )
        except Exception as grab_image_error:
            safe_log_write(
                log_file_handle,
                f"REGULAR MODE: Error calling blog.grab_image() for '{title}': {grab_image_error}\n",
            )
            image_str = "generic.webp"

        if image_str.startswith("./"):
            image_str = image_str[2:]
            safe_log_write(
                log_file_handle,
                f"REGULAR MODE: Removed './' prefix from image path: '{image_str}'\n",
            )

        image_str = image_str.replace("\\", "/")
        image = image_str

        safe_log_write(
            log_file_handle,
            f"REGULAR MODE: Final processed image path: '{image_str}'\n",
        )

        if "generic.jpg" in image_str.lower():
            generic_webp_path = os.path.join(
                os.path.dirname(os.path.dirname(__file__)),
                "static",
                "images",
                "generic.webp",
            )

            webp_exists = os.path.exists(generic_webp_path)
            safe_log_write(
                log_file_handle,
                f"REGULAR MODE: Detected generic image, checking for WebP version at: '{generic_webp_path}' (exists: {webp_exists})\n",
            )

            if webp_exists:
                image = (
                    str(image)
                    .replace("generic.jpg", "generic.webp")
                    .replace("generic.JPG", "generic.webp")
                )
                safe_log_write(
                    log_file_handle,
                    f"REGULAR MODE: Using WebP version for generic image: '{image}'\n",
                )

        elif any(
            image_str.lower().endswith(ext)
            for ext in (".jpg", ".jpeg", ".png", ".JPG", ".JPEG", ".PNG")
        ):
            base_name = os.path.splitext(image_str)[0]
            webp_image = base_name + ".webp"

            safe_log_write(
                log_file_handle,
                f"REGULAR MODE: Detected non-WebP image format, looking for WebP version: '{webp_image}'\n",
            )

            webp_exists = False
            webp_location = None

            if os.path.exists(os.path.join(ROCmBlogs.blogs_directory, webp_image)):
                image = webp_image
                webp_exists = True
                webp_location = "blogs_directory"
            elif os.path.exists(
                os.path.join(os.path.dirname(blog.file_path), webp_image)
            ):
                image = webp_image
                webp_exists = True
                webp_location = "blog_directory"
            elif os.path.exists(
                os.path.join(
                    os.path.dirname(blog.file_path),
                    "images",
                    os.path.basename(webp_image),
                )
            ):
                image = os.path.join(
                    os.path.dirname(image_str), os.path.basename(webp_image)
                )
                webp_exists = True
                webp_location = "blog_images_directory"

            if webp_exists:
                safe_log_write(
                    log_file_handle,
                    f"REGULAR MODE: Found existing WebP version: '{image}' in {webp_location}\n",
                )
            else:
                safe_log_write(
                    log_file_handle,
                    f"REGULAR MODE: No WebP version found for '{image_str}', attempting conversion\n",
                )

                original_image_path = None
                search_locations = []

                if os.path.exists(os.path.join(ROCmBlogs.blogs_directory, image_str)):
                    original_image_path = os.path.join(
                        ROCmBlogs.blogs_directory, image_str
                    )
                    search_locations.append("blogs_directory")
                elif os.path.exists(
                    os.path.join(os.path.dirname(blog.file_path), image_str)
                ):
                    original_image_path = os.path.join(
                        os.path.dirname(blog.file_path), image_str
                    )
                    search_locations.append("blog_directory")
                elif os.path.exists(
                    os.path.join(
                        os.path.dirname(blog.file_path),
                        "images",
                        os.path.basename(image_str),
                    )
                ):
                    original_image_path = os.path.join(
                        os.path.dirname(blog.file_path),
                        "images",
                        os.path.basename(image_str),
                    )
                    search_locations.append("blog_images_directory")

                safe_log_write(
                    log_file_handle,
                    f"REGULAR MODE: Searched for original image in locations: {search_locations}, found: {original_image_path}\n",
                )

                if original_image_path:
                    try:
                        safe_log_write(
                            log_file_handle,
                            f"REGULAR MODE: Starting WebP conversion for: '{original_image_path}'\n",
                        )

                        with Image.open(original_image_path) as img:
                            original_width, original_height = img.size

                            safe_log_write(
                                log_file_handle,
                                f"REGULAR MODE: Original image dimensions: {original_width}x{original_height}\n",
                            )

                            webp_img = img
                            if img.mode not in ("RGB", "RGBA"):
                                webp_img = img.convert("RGB")
                                safe_log_write(
                                    log_file_handle,
                                    f"REGULAR MODE: Converted image mode from {img.mode} to RGB\n",
                                )

                            if original_width > 1280 or original_height > 720:
                                scaling_factor = min(
                                    1280 / original_width, 720 / original_height
                                )
                                new_width = int(original_width * scaling_factor)
                                new_height = int(original_height * scaling_factor)

                                webp_img = webp_img.resize(
                                    (new_width, new_height), resample=Image.LANCZOS
                                )
                                safe_log_write(
                                    log_file_handle,
                                    f"REGULAR MODE: Resized image from {original_width}x{original_height} to {new_width}x{new_height} (factor: {scaling_factor:.3f})\n",
                                )

                            webp_path = (
                                os.path.splitext(original_image_path)[0] + ".webp"
                            )
                            webp_img.save(
                                webp_path, format="WEBP", quality=98, method=6
                            )

                            image = webp_image
                            safe_log_write(
                                log_file_handle,
                                f"REGULAR MODE: Successfully converted to WebP: '{webp_path}' -> using '{webp_image}'\n",
                            )
                    except Exception as conversion_error:
                        safe_log_write(
                            log_file_handle,
                            f"REGULAR MODE: Failed to convert '{image_str}' to WebP: {conversion_error}\n",
                        )
                else:
                    safe_log_write(
                        log_file_handle,
                        f"REGULAR MODE: Could not find original image file for conversion: '{image_str}'\n",
                    )

        safe_log_write(
            log_file_handle, f"REGULAR MODE: Final image for grid item: '{image}'\n"
        )

        try:
            raw_href = blog.grab_href()
            if hasattr(raw_href, "split"):
                href = "." + raw_href.split("/blogs")[-1].replace("\\", "/")
            else:
                href = "." + str(raw_href).split("/blogs")[-1].replace("\\", "/")

            safe_log_write(
                log_file_handle,
                f"REGULAR MODE: Generated href: '{href}' from raw_href: '{raw_href}'\n",
            )
        except Exception as href_error:
            safe_log_write(
                log_file_handle,
                f"REGULAR MODE: Error generating href for '{title}': {href_error}\n",
            )
            href = "#"

    authors_html = ""
    if authors_list:
        try:
            authors_html = blog.grab_authors(authors_list, ROCmBlogs)
            safe_log_write(
                log_file_handle,
                f"Generated authors HTML: '{authors_html}' (count: {len(authors_list)})\n",
            )
        except Exception as authors_error:
            safe_log_write(
                log_file_handle,
                f"Error generating authors HTML: {authors_error}, authors_list: {authors_list}\n",
            )

    if authors_html:
        authors_html = f"by {authors_html}"
        safe_log_write(
            log_file_handle, f"Final authors HTML with prefix: '{authors_html}'\n"
        )
    else:
        safe_log_write(
            log_file_handle,
            f"No valid authors found for grid item, authors_list: {authors_list}\n",
        )

    try:
        grid_content = grid_template.format(
            title=title,
            date=date,
            description=description,
            authors_html=authors_html,
            image=image,
            href=href,
        )

        grid_end_time = time.time()
        grid_duration = grid_end_time - grid_start_time

        safe_log_write(
            log_file_handle,
            f"Successfully generated grid item for '{title}' in {grid_duration:.4f}s\n",
        )
        safe_log_write(
            log_file_handle, f"Grid content length: {len(grid_content)} characters\n"
        )

        safe_log_write(
            log_file_handle,
            f"Generated grid content for '{title}':\n{'-' * 40}\n{grid_content}\n{'-' * 40}\n",
        )

        if use_og:
            safe_log_write(
                log_file_handle,
                f"AUTHOR PAGE SUMMARY: '{title}' -> Image: '{image}', Href: '{href}', Mode: OpenGraph\n",
            )
        else:
            safe_log_write(
                log_file_handle,
                f"REGULAR SUMMARY: '{title}' -> Image: '{image}', Href: '{href}', Mode: Regular\n",
            )

        if not grid_content or len(grid_content.strip()) < 50:
            safe_log_write(
                log_file_handle,
                f"WARNING: Generated grid content is too small or empty for '{title}' (length: {len(grid_content.strip()) if grid_content else 0}). Returning empty string.\n",
            )
            if log_file_handle:
                try:
                    log_file_handle.close()
                except:
                    pass
            return ""

        if log_file_handle:
            try:
                log_file_handle.close()
            except:
                pass

        return grid_content

    except Exception as template_error:
        safe_log_write(
            log_file_handle,
            f"Error formatting grid template for '{title}': {template_error}\n",
        )
        safe_log_write(
            log_file_handle,
            f"Template variables - title: '{title}', date: '{date}', description: '{description[:50]}...', authors_html: '{authors_html}', image: '{image}', href: '{href}'\n",
        )
        if log_file_handle:
            try:
                log_file_handle.close()
            except:
                pass
        raise
