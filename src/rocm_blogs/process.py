import importlib.resources as pkg_resources
import inspect
import json
import os
import re
import shutil
import threading
import time
import traceback
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

from sphinx.errors import SphinxError
from sphinx.util import logging as sphinx_logging

from ._rocmblogs import *
from .constants import *
from .grid import *
from .images import *
from .logger.logger import *
from .utils import *


def quickshare(blog_entry) -> str:
    """Generate social media sharing buttons for a blog post."""
    try:
        # Load template files
        social_css = import_file("rocm_blogs.static.css", "social-bar.css")
        social_html = import_file("rocm_blogs.templates", "social-bar.html")

        # Create base template with CSS
        social_bar_template = """
<style>
{CSS}
</style>
{HTML}
"""
        social_bar = social_bar_template.format(CSS=social_css, HTML=social_html)

        # Determine the blog URL
        if hasattr(blog_entry, "file_path"):
            blog_directory = os.path.basename(os.path.dirname(blog_entry.file_path))
            share_url = f"http://rocm.blogs.amd.com/artificial-intelligence/{blog_directory}/README.html"
        else:
            share_url = f"http://rocm.blogs.amd.com{blog_entry.grab_href()[1:]}"

        # Get blog title and description
        blog_title = getattr(blog_entry, "blog_title", "No Title")
        title_with_suffix = f"{blog_title} | ROCm Blogs"

        blog_description = "No Description"
        if hasattr(blog_entry, "myst"):
            blog_description = blog_entry.myst.get("html_meta", {}).get(
                "description lang=en", blog_description
            )

        # Add debug info for test blogs
        if (
            hasattr(blog_entry, "file_path")
            and "test" in str(blog_entry.file_path).lower()
        ):
            social_bar += (
                f"\n<!-- {title_with_suffix} -->\n<!-- {blog_description} -->\n"
            )

        # Replace placeholders with actual content
        social_bar = (
            social_bar.replace("{URL}", share_url)
            .replace("{TITLE}", title_with_suffix)
            .replace("{TEXT}", blog_description)
        )

        log_message(
            "debug",
            f"Generated quickshare buttons for blog: {getattr(blog_entry, 'blog_title', 'Unknown')}",
            "general",
            "process",
        )

        return social_bar
    except Exception as quickshare_error:
        log_message(
            "error",
            f"Error generating quickshare buttons for blog {getattr(blog_entry, 'blog_title', 'Unknown')}: {quickshare_error}",
            "general",
            "process",
        )
        log_message(
            "debug",
            f"Traceback: {traceback.format_exc()}",
            "general",
            "process",
        )
        return ""


def _create_pagination_controls(
    pagination_template, current_page, total_pages, base_name
):
    """Create pagination controls for navigation between pages."""
    # Create previous button
    if current_page > 1:
        previous_page = current_page - 1
        previous_file = (
            f"{base_name}-page{previous_page}.html"
            if previous_page > 1
            else f"{base_name}.html"
        )
        previous_button = (
            f'<a href="{previous_file}" class="pagination-button previous"> Prev</a>'
        )
    else:
        previous_button = '<span class="pagination-button disabled"> Prev</span>'

    # Create next button
    if current_page < total_pages:
        next_page = current_page + 1
        next_file = f"{base_name}-page{next_page}.html"
        next_button = f'<a href="{next_file}" class="pagination-button next">Next </a>'
    else:
        next_button = '<span class="pagination-button disabled">Next </span>'

    # Fill in pagination template
    return (
        pagination_template.replace("{prev_button}", previous_button)
        .replace("{current_page}", str(current_page))
        .replace("{total_pages}", str(total_pages))
        .replace("{next_button}", next_button)
    )


def _process_category(
    category_info,
    rocm_blogs,
    blogs_directory,
    pagination_template,
    css_content,
    pagination_css,
    current_datetime,
    category_template,
    category_blogs=None,
    log_file_handle=None,
):
    """Process a page with a specific filter criteria."""
    category_name = category_info["name"]
    template_name = category_info["template"]
    output_base = category_info["output_base"]
    category_key = category_info["category_key"]
    page_title = category_info["title"]
    page_description = category_info["description"]
    page_keywords = category_info["keywords"]

    filter_criteria = category_info.get("filter_criteria", {})

    log_message(
        "info",
        f"Generating paginated pages for category: {category_name}",
        "general",
        "process",
    )

    if log_file_handle:
        log_file_handle.write(
            f"Generating paginated pages for category: {category_name}\n"
        )

    template_html = import_file("rocm_blogs.templates", template_name)

    # If category_blogs is not provided, filter blogs based on filter_criteria
    if category_blogs is None:
        category_blogs = []
        all_blogs = rocm_blogs.blogs.get_blogs()

        # If no filter criteria, use category_key to filter blogs
        if not filter_criteria:
            category_blogs = rocm_blogs.blogs.get_blogs_by_category(category_key)
            log_message(
                "info",
                f"Using category_key '{category_key}' to filter blogs. Found {len(category_blogs)} blogs.",
                "general",
                "process",
            )
            if log_file_handle:
                log_file_handle.write(
                    f"Using category_key '{category_key}' to filter blogs. Found {len(category_blogs)} blogs.\n"
                )
        else:
            log_message(
                "info",
                f"Using filter_criteria to filter blogs: {filter_criteria}",
                "general",
                "process",
            )
            if log_file_handle:
                log_file_handle.write(
                    f"Using filter_criteria to filter blogs: {filter_criteria}\n"
                )
            for blog in all_blogs:
                matches_all_criteria = True

                for field, values in filter_criteria.items():
                    # Convert single value to list for consistent handling
                    if not isinstance(values, list):
                        values = [values]

                    # Get blog field value
                    if field == "category":
                        blog_value = getattr(blog, "category", "")
                        if blog_value not in values:
                            matches_all_criteria = False
                            log_message(
                                "debug",
                                f"Blog '{getattr(blog, 'blog_title', 'Unknown')}' category '{blog_value}' does not match any of {values}",
                                "general",
                                "process",
                            )
                            if log_file_handle:
                                log_file_handle.write(
                                    f"Blog '{getattr(blog, 'blog_title', 'Unknown')}' category '{blog_value}' does not match any of {values}\n"
                                )
                            break
                        else:
                            log_message(
                                "debug",
                                f"Blog '{getattr(blog, 'blog_title', 'Unknown')}' category '{blog_value}' matches one of {values}",
                                "general",
                                "process",
                            )
                            if log_file_handle:
                                log_file_handle.write(
                                    f"Blog '{getattr(blog, 'blog_title', 'Unknown')}' category '{blog_value}' matches one of {values}\n"
                                )
                    elif field == "vertical":
                        if not hasattr(blog, "metadata") or not blog.metadata:
                            matches_all_criteria = False
                            log_message(
                                "debug",
                                f"Blog '{getattr(blog, 'blog_title', 'Unknown')}' has no metadata",
                                "general",
                                "process",
                            )
                            if log_file_handle:
                                log_file_handle.write(
                                    f"Blog '{getattr(blog, 'blog_title', 'Unknown')}' has no metadata\n"
                                )
                            break

                        try:
                            myst_data = blog.metadata.get("myst", {})
                            html_meta = myst_data.get("html_meta", {})
                            vertical_str = html_meta.get("vertical", "")

                            if not vertical_str and hasattr(blog, "vertical"):
                                vertical_str = getattr(blog, "vertical", "")

                            # Split vertical string into list and strip
                            # whitespace
                            blog_verticals = [
                                v.strip() for v in vertical_str.split(",") if v.strip()
                            ]

                            # Debug log
                            log_message(
                                "debug",
                                f"Blog '{getattr(blog, 'blog_title', 'Unknown')}' verticals: {blog_verticals}",
                                "general",
                                "process",
                            )
                            if log_file_handle:
                                log_file_handle.write(
                                    f"Blog '{getattr(blog, 'blog_title', 'Unknown')}' verticals: {blog_verticals}\n"
                                )

                            # Check if any of the blog's verticals match any of
                            # the specified verticals
                            if not blog_verticals or not any(
                                bv in values for bv in blog_verticals
                            ):
                                matches_all_criteria = False
                                log_message(
                                    "debug",
                                    f"Blog '{getattr(blog, 'blog_title', 'Unknown')}' verticals {blog_verticals} do not match any of {values}",
                                    "general",
                                    "process",
                                )
                                if log_file_handle:
                                    log_file_handle.write(
                                        f"Blog '{getattr(blog, 'blog_title', 'Unknown')}' verticals {blog_verticals} do not match any of {values}\n"
                                    )
                                break
                            else:
                                log_message(
                                    "debug",
                                    f"Blog '{getattr(blog, 'blog_title', 'Unknown')}' verticals {blog_verticals} match one of {values}",
                                    "general",
                                    "process",
                                )
                                if log_file_handle:
                                    log_file_handle.write(
                                        f"Blog '{getattr(blog, 'blog_title', 'Unknown')}' verticals {blog_verticals} match one of {values}\n"
                                    )
                        except (AttributeError, KeyError) as e:
                            matches_all_criteria = False
                            log_message(
                                "debug",
                                f"Error getting vertical for blog '{getattr(blog, 'blog_title', 'Unknown')}': {e}",
                                "general",
                                "process",
                            )
                            if log_file_handle:
                                log_file_handle.write(
                                    f"Error getting vertical for blog '{getattr(blog, 'blog_title', 'Unknown')}': {e}\n"
                                )
                            break
                    elif field == "tags":
                        if not hasattr(blog, "tags") or not blog.tags:
                            matches_all_criteria = False
                            log_message(
                                "debug",
                                f"Blog '{getattr(blog, 'blog_title', 'Unknown')}' has no tags",
                                "general",
                                "process",
                            )
                            if log_file_handle:
                                log_file_handle.write(
                                    f"Blog '{getattr(blog, 'blog_title', 'Unknown')}' has no tags\n"
                                )
                            break

                        blog_tags = blog.tags
                        if isinstance(blog_tags, str):
                            blog_tags = [
                                tag.strip()
                                for tag in blog_tags.split(",")
                                if tag.strip()
                            ]

                        if not blog_tags or not any(tag in blog_tags for tag in values):
                            matches_all_criteria = False
                            log_message(
                                "debug",
                                f"Blog '{getattr(blog, 'blog_title', 'Unknown')}' tags {blog_tags} do not match any of {values}",
                                "general",
                                "process",
                            )
                            if log_file_handle:
                                log_file_handle.write(
                                    f"Blog '{getattr(blog, 'blog_title', 'Unknown')}' tags {blog_tags} do not match any of {values}\n"
                                )
                            break
                        else:
                            log_message(
                                "debug",
                                f"Blog '{getattr(blog, 'blog_title', 'Unknown')}' tags {blog_tags} match one of {values}",
                                "general",
                                "process",
                            )
                            if log_file_handle:
                                log_file_handle.write(
                                    f"Blog '{getattr(blog, 'blog_title', 'Unknown')}' tags {blog_tags} match one of {values}\n"
                                )
                    else:
                        blog_value = getattr(blog, field, None)
                        if blog_value is None or blog_value not in values:
                            matches_all_criteria = False
                            log_message(
                                "debug",
                                f"Blog '{getattr(blog, 'blog_title', 'Unknown')}' field '{field}' value '{blog_value}' does not match any of {values}",
                                "general",
                                "process",
                            )
                            if log_file_handle:
                                log_file_handle.write(
                                    f"Blog '{getattr(blog, 'blog_title', 'Unknown')}' field '{field}' value '{blog_value}' does not match any of {values}\n"
                                )
                            break
                        else:
                            log_message(
                                "debug",
                                f"Blog '{getattr(blog, 'blog_title', 'Unknown')}' field '{field}' value '{blog_value}' matches one of {values}",
                                "general",
                                "process",
                            )
                            if log_file_handle:
                                log_file_handle.write(
                                    f"Blog '{getattr(blog, 'blog_title', 'Unknown')}' field '{field}' value '{blog_value}' matches one of {values}\n"
                                )

                # If blog matches all criteria, add it to category_blogs
                if matches_all_criteria:
                    category_blogs.append(blog)
                    log_message(
                        "debug",
                        f"Blog '{getattr(blog, 'blog_title', 'Unknown')}' matches all filter criteria, adding to category_blogs",
                        "general",
                        "process",
                    )
                    if log_file_handle:
                        log_file_handle.write(
                            f"Blog '{getattr(blog, 'blog_title', 'Unknown')}' matches all filter criteria, adding to category_blogs\n"
                        )

            log_message(
                "info",
                f"Found {len(category_blogs)} blogs matching filter criteria",
                "general",
                "process",
            )
            if log_file_handle:
                log_file_handle.write(
                    f"Found {len(category_blogs)} blogs matching filter criteria\n"
                )

    # If no blogs were found for the category, log a warning and return
    if not category_blogs and not filter_criteria:
        log_message(
            "warning",
            f"No blogs found for category: {category_name} and no filter criteria provided",
            "general",
            "process",
        )
        if log_file_handle:
            log_file_handle.write(
                f"No blogs found for category: {category_name} and no filter criteria provided\n"
            )
        return
    elif not category_blogs:
        log_message(
            "warning",
            f"No blogs found for category: {category_name}",
            "general",
            "process",
        )
        if log_file_handle:
            log_file_handle.write(f"No blogs found for category: {category_name}\n")
        return

    # Calculate total number of pages
    total_pages = max(
        1,
        (len(category_blogs) + CATEGORY_BLOGS_PER_PAGE - 1) // CATEGORY_BLOGS_PER_PAGE,
    )

    log_message(
        "info",
        f"Category {category_name} has {len(category_blogs)} blogs, creating {total_pages} pages",
        "general",
        "process",
    )
    if log_file_handle:
        log_file_handle.write(
            f"Category {category_name} has {len(category_blogs)} blogs, creating {total_pages} pages\n"
        )

    all_grid_items = _generate_lazy_loaded_grid_items(rocm_blogs, category_blogs)

    # Check if any grid items were generated
    if not all_grid_items:
        log_message(
            "warning",
            f"No grid items were generated for category: {category_name}. Skipping page generation.",
            "general",
            "process",
        )
        return

    # Generate each page
    for page_num in range(1, total_pages + 1):
        start_index = (page_num - 1) * CATEGORY_BLOGS_PER_PAGE
        end_index = min(start_index + CATEGORY_BLOGS_PER_PAGE, len(all_grid_items))
        page_grid_items = all_grid_items[start_index:end_index]

        # Validate grid content before creating page
        if not page_grid_items:
            log_message(
                "warning",
                f"No grid items for category {category_name} page {page_num}/{total_pages}. Skipping page creation.",
                "general",
                "process",
            )
            if log_file_handle:
                log_file_handle.write(
                    f"WARNING: No grid items for category {category_name} page {page_num}/{total_pages}. Skipping page creation.\n"
                )
            continue

        fixed_grid_items = []
        for grid_item in page_grid_items:
            grid_item = grid_item.replace(":img-top: ./", ":img-top: /")
            grid_item = grid_item.replace(
                ":img-top: ./ecosystems", ":img-top: /ecosystems"
            )
            grid_item = grid_item.replace(
                ":img-top: ./applications", ":img-top: /applications"
            )
            fixed_grid_items.append(grid_item)

        grid_content = "\n".join(fixed_grid_items)

        # Additional validation: ensure grid content is meaningful
        if not grid_content or not grid_content.strip():
            log_message(
                "warning",
                f"Empty grid content for category {category_name} page {page_num}/{total_pages}. Skipping page creation.",
                "general",
                "process",
            )
            if log_file_handle:
                log_file_handle.write(
                    f"WARNING: Empty grid content for category {category_name} page {page_num}/{total_pages}. Skipping page creation.\n"
                )
            continue

        pagination_controls = _create_pagination_controls(
            pagination_template, page_num, total_pages, output_base
        )

        # Add page suffix for pages after the first
        page_title_suffix = f" - Page {page_num}" if page_num > 1 else ""
        page_description_suffix = (
            f" (Page {page_num} of {total_pages})" if page_num > 1 else ""
        )

        # Replace placeholders in the template
        updated_html = template_html.replace("{grid_items}", grid_content).replace(
            "{datetime}", current_datetime
        )

        final_content = category_template.format(
            title=page_title,
            description=page_description,
            keywords=page_keywords,
            CSS=css_content,
            PAGINATION_CSS=pagination_css,
            HTML=updated_html,
            pagination_controls=pagination_controls,
            page_title_suffix=page_title_suffix,
            page_description_suffix=page_description_suffix,
            current_page=page_num,
        )

        # Final validation: ensure page content is not empty
        if not final_content or len(final_content.strip()) < 100:
            log_message(
                "warning",
                f"Generated page content is too small or empty for category {category_name} page {page_num}/{total_pages}. Skipping file creation.",
                "general",
                "process",
            )
            if log_file_handle:
                log_file_handle.write(
                    f"WARNING: Page content too small for category {category_name} page {page_num}/{total_pages}. Skipping file creation.\n"
                )
            continue

        output_filename = (
            f"{output_base}.md" if page_num == 1 else f"{output_base}-page{page_num}.md"
        )
        output_path = Path(blogs_directory) / output_filename

        if log_file_handle:
            log_file_handle.write(
                f"Generated {output_filename} with {len(page_grid_items)} grid items\n"
            )
            log_file_handle.write(
                f"Page being written: {output_path} with file name: {output_filename}\n"
            )

        try:
            with output_path.open("w", encoding="utf-8") as output_file:
                output_file.write(final_content)

            if log_file_handle:
                log_file_handle.write(f"Successfully wrote to file {output_path}\n")

        except FileNotFoundError as fnf_error:
            log_message(
                "error",
                f"File not found error while writing to {output_path}: {fnf_error}",
                "general",
                "process",
            )
            if log_file_handle:
                log_file_handle.write(
                    f"File not found error while writing to {output_path}: {fnf_error}\n"
                )
            raise SphinxError(
                f"File not found error while writing to {output_path}: {fnf_error}"
            ) from fnf_error
        except Exception as write_error:
            log_message(
                "error",
                f"Error writing to file {output_path}: {write_error}",
                "general",
                "process",
            )
            log_message(
                "debug",
                f"Traceback: {traceback.format_exc()}",
                "general",
                "process",
            )

            if log_file_handle:
                log_file_handle.write(
                    f"Error writing to file {output_path}: {write_error}\n"
                )
                log_file_handle.write(f"Traceback: {traceback.format_exc()}\n")

            raise SphinxError(
                f"Error writing to file {output_path}: {write_error}"
            ) from write_error

        # verify the file was created successfully
        if not output_path.exists():
            log_message(
                "error",
                f"File {output_path} was not created successfully",
                "general",
                "process",
            )
            if log_file_handle:
                log_file_handle.write(
                    f"File {output_path} was not created successfully\n"
                )
            raise SphinxError(f"File {output_path} was not created successfully")

        log_message(
            "info",
            f"Created {output_path} with {len(page_grid_items)} grid items (page {page_num}/{total_pages})",
            "general",
            "process",
        )


def _generate_grid_items(
    rocm_blogs, blog_list, max_items, used_blogs, skip_used=False, use_og=False
):
    """Generate grid items in parallel using thread pool."""

    try:
        # Debug: Log the parameters received by this function
        log_message(
            "debug",
            f"_generate_grid_items called with: max_items={max_items}, skip_used={skip_used}, use_og={use_og}, blog_count={len(blog_list)}",
            "general",
            "process",
        )

        # Debug: Log the first few blog titles to identify which set of blogs this is
        if blog_list:
            first_few_titles = [
                getattr(blog, "blog_title", "Unknown") for blog in blog_list[:3]
            ]
            log_message(
                "debug",
                f"_generate_grid_items processing blogs starting with: {first_few_titles}",
                "general",
                "process",
            )

        grid_items = []
        item_count = 0
        error_count = 0

        grid_params = inspect.signature(generate_grid).parameters
        if "ROCmBlogs" not in grid_params or "blog" not in grid_params:
            log_message(
                "critical",
                "generate_grid function does not have the expected parameters. Grid items may not be generated correctly.",
                "general",
                "process",
            )
            log_message(
                "debug",
                f"Available parameters: {list(grid_params.keys())}",
                "general",
                "process",
            )
            log_message(
                "debug",
                f"Traceback: {traceback.format_exc()}",
                "general",
                "process",
            )

        # Generate grid items in parallel with proper deduplication
        with ThreadPoolExecutor() as executor:
            grid_futures = {}

            for blog_entry in blog_list:
                # Check if blog is already used (by ID for more reliable comparison)
                blog_id = id(blog_entry)
                blog_path = getattr(blog_entry, "file_path", None)

                # Check both ID and file path for comprehensive deduplication
                already_used = False
                if skip_used:
                    # Check by object ID
                    if any(id(used_blog) == blog_id for used_blog in used_blogs):
                        already_used = True
                    # Also check by file path as backup
                    elif blog_path and any(
                        getattr(used_blog, "file_path", None) == blog_path
                        for used_blog in used_blogs
                    ):
                        already_used = True

                if already_used:
                    log_message(
                        "debug",
                        f"Skipping blog '{getattr(blog_entry, 'blog_title', 'Unknown')}' because it's already used (path: {blog_path})",
                        "general",
                        "process",
                    )
                    continue

                # Check if we've reached the maximum number of items
                if item_count >= max_items:
                    log_message(
                        "debug",
                        f"Reached maximum number of items ({max_items}), skipping remaining blogs",
                        "general",
                        "process",
                    )
                    break

                # Add to used_blogs list if skip_used is enabled
                if skip_used:
                    used_blogs.append(blog_entry)

                grid_futures[
                    executor.submit(
                        generate_grid, rocm_blogs, blog_entry, False, use_og
                    )
                ] = blog_entry
                item_count += 1

            for future in grid_futures:
                try:
                    grid_result = future.result()
                    if not grid_result or not grid_result.strip():
                        blog_entry = grid_futures[future]
                        log_message(
                            "debug",
                            f"Empty grid HTML generated for blog: {getattr(blog_entry, 'blog_title', 'Unknown')} - likely skipped due to missing OpenGraph metadata",
                            "general",
                            "process",
                        )
                        # Don't count as error - this is expected behavior for blogs without OpenGraph metadata
                        continue

                    # Validate that grid result contains meaningful content
                    if (
                        len(grid_result.strip()) < 50
                    ):  # Minimum meaningful grid content size
                        blog_entry = grid_futures[future]
                        log_message(
                            "debug",
                            f"Grid HTML too small for blog: {getattr(blog_entry, 'blog_title', 'Unknown')} (length: {len(grid_result.strip())})",
                            "general",
                            "process",
                        )
                        continue

                    grid_items.append(grid_result)
                except Exception as future_error:
                    error_count += 1
                    blog_entry = grid_futures[future]
                    log_message(
                        "error",
                        f"Error generating grid item for blog {getattr(blog_entry, 'blog_title', 'Unknown')}: {future_error}",
                        "general",
                        "process",
                    )
                    log_message(
                        "debug",
                        f"Traceback: {traceback.format_exc()}",
                        "general",
                        "process",
                    )

        # Handle the case where no grid items were generated
        if not grid_items:
            # If there were no blogs to process or all were skipped, just
            # return an empty list
            if item_count == 0:
                log_message(
                    "warning",
                    "No blogs were available to generate grid items. Returning empty list.",
                    "general",
                    "process",
                )
                return []

            # If we tried to process blogs but none succeeded, log a warning
            # but don't raise an error
            log_message(
                "warning",
                "No grid items were generated despite having blogs to process. Check for errors in the generate_grid function.",
                "general",
                "process",
            )
            log_message(
                "debug",
                f"Traceback: {traceback.format_exc()}",
                "general",
                "process",
            )
            return []

        # Log errors and completion status
        elif error_count > 0:
            log_message(
                "warning",
                f"Generated {len(grid_items)} grid items with {error_count} errors",
                "general",
                "process",
            )
            log_message(
                "debug",
                f"Traceback: {traceback.format_exc()}",
                "general",
                "process",
            )
        else:
            log_message(
                "info",
                f"Successfully generated {len(grid_items)} grid items",
                "general",
                "process",
            )

        return grid_items
    except ROCmBlogsError:
        log_message(
            "debug",
            f"Traceback: {traceback.format_exc()}",
            "general",
            "process",
        )
        raise
    except Exception as grid_error:
        log_message(
            "error",
            f"Error generating grid items: {grid_error}",
            "general",
            "process",
        )
        log_message(
            "debug",
            f"Traceback: {traceback.format_exc()}",
            "general",
            "process",
        )
        return []


def _generate_lazy_loaded_grid_items(rocm_blogs, blog_list):
    """Generate grid items with lazy loading and thread-safe deduplication."""
    try:
        lazy_grid_items = []
        error_count = 0
        seen_paths = set()
        seen_titles = set()
        deduplicated_blog_list = []
        dedup_lock = threading.Lock()

        # Thread-safe deduplication
        for blog in blog_list:
            blog_path = getattr(blog, "file_path", None)
            blog_title = getattr(blog, "blog_title", None)

            with dedup_lock:
                is_duplicate = False
                if blog_path and blog_path in seen_paths:
                    is_duplicate = True
                if blog_title and blog_title in seen_titles:
                    is_duplicate = True

                if not is_duplicate and blog_path:
                    seen_paths.add(blog_path)
                    if blog_title:
                        seen_titles.add(blog_title)
                    deduplicated_blog_list.append(blog)

        log_message(
            "info",
            f"Deduplication: {len(blog_list)} -> {len(deduplicated_blog_list)} blogs",
            "general",
            "process",
        )

        # Check if lazy_load parameter is supported
        grid_params = inspect.signature(generate_grid).parameters
        if "lazy_load" not in grid_params:
            log_message(
                "warning",
                "Falling back to regular grid generation",
                "general",
                "process",
            )
            temp_used_blogs = []
            return _generate_grid_items(
                rocm_blogs,
                deduplicated_blog_list,
                len(deduplicated_blog_list),
                temp_used_blogs,
                skip_used=False,
            )

        # Generate grid items with lazy loading
        for blog_entry in deduplicated_blog_list:
            try:
                grid_html = generate_grid(rocm_blogs, blog_entry, lazy_load=True)
                if not grid_html or not grid_html.strip():
                    error_count += 1
                    log_message(
                        "debug",
                        f"Empty grid HTML for blog: {getattr(blog_entry, 'blog_title', 'Unknown')}",
                        "general",
                        "process",
                    )
                    continue

                # Validate that grid result contains meaningful content
                if len(grid_html.strip()) < 50:  # Minimum meaningful grid content size
                    error_count += 1
                    log_message(
                        "debug",
                        f"Grid HTML too small for blog: {getattr(blog_entry, 'blog_title', 'Unknown')} (length: {len(grid_html.strip())})",
                        "general",
                        "process",
                    )
                    continue

                lazy_grid_items.append(grid_html)
            except Exception as blog_error:
                error_count += 1
                log_message(
                    "error",
                    f"Error generating grid item for {getattr(blog_entry, 'blog_title', 'Unknown')}: {blog_error}",
                    "general",
                    "process",
                )

        if not lazy_grid_items:
            log_message("warning", "No grid items generated", "general", "process")
            return []

        if error_count > 0:
            log_message(
                "warning",
                f"Generated {len(lazy_grid_items)} items with {error_count} errors",
                "general",
                "process",
            )
        else:
            log_message(
                "info",
                f"Generated {len(lazy_grid_items)} items from {len(deduplicated_blog_list)} blogs",
                "general",
                "process",
            )

        return lazy_grid_items
    except Exception as lazy_load_error:
        log_message(
            "error",
            f"Error generating lazy-loaded grid items: {lazy_load_error}",
            "general",
            "process",
        )
        raise ROCmBlogsError(
            f"Error generating lazy-loaded grid-items: {lazy_load_error}"
        ) from lazy_load_error


def process_single_blog(blog_entry, rocm_blogs):
    """Process a single blog file - OPTIMIZED VERSION."""
    try:
        processing_start_time = time.time()
        readme_file_path = blog_entry.file_path
        blog_directory = os.path.dirname(readme_file_path)

        if not hasattr(blog_entry, "author") or not blog_entry.author:
            # Skip logging for performance - just return silently
            return

        # OPTIMIZATION 1: Read file once and cache content
        with open(
            readme_file_path, "r", encoding="utf-8", errors="replace"
        ) as source_file:
            file_content = source_file.read()
            content_lines = file_content.splitlines(True)

        # OPTIMIZATION 2: Restore essential image processing functionality
        webp_versions = {}

        # Essential image handling with WebP conversion
        if hasattr(blog_entry, "thumbnail") and blog_entry.thumbnail:
            try:
                blog_entry.grab_image(rocm_blogs)

                if blog_entry.image_paths:
                    for i, image_path in enumerate(blog_entry.image_paths):
                        try:
                            # Validate image path exists
                            if not os.path.exists(image_path):
                                image_filename = os.path.basename(image_path)
                                possible_paths = [
                                    os.path.join(blog_directory, image_filename),
                                    os.path.join(
                                        blog_directory, "images", image_filename
                                    ),
                                    os.path.join(
                                        rocm_blogs.blogs_directory,
                                        "images",
                                        image_filename,
                                    ),
                                ]

                                for possible_path in possible_paths:
                                    if os.path.exists(possible_path):
                                        blog_entry.image_paths[i] = possible_path
                                        image_path = possible_path
                                        break

                            if os.path.exists(image_path):
                                # Check if WebP version already exists (created by grid generation)
                                image_filename = os.path.basename(image_path)
                                name_without_ext = os.path.splitext(image_filename)[0]
                                webp_filename = f"{name_without_ext}.webp"

                                # Check multiple possible locations for WebP version
                                webp_locations = [
                                    os.path.join(
                                        rocm_blogs.blogs_directory,
                                        "_images",
                                        webp_filename,
                                    ),
                                    os.path.join(
                                        os.path.dirname(image_path), webp_filename
                                    ),
                                    os.path.join(
                                        os.path.dirname(image_path),
                                        "images",
                                        webp_filename,
                                    ),
                                ]

                                webp_found = False
                                webp_destination = None

                                for webp_location in webp_locations:
                                    if os.path.exists(webp_location):
                                        webp_found = True
                                        webp_destination = webp_location
                                        break

                                if webp_found:
                                    # Use existing WebP version
                                    blog_entry.image_paths[i] = webp_destination

                                    # Generate responsive variants if they don't exist
                                    from .images import \
                                        generate_responsive_images

                                    images_dir = os.path.dirname(webp_destination)
                                    generate_responsive_images(
                                        webp_destination, output_dir=images_dir
                                    )

                                    log_message(
                                        "info",
                                        f"Using existing WebP version and ensuring responsive variants: {webp_destination}",
                                        "general",
                                        "process",
                                    )
                                else:
                                    # WebP doesn't exist, create it for consistency with grid
                                    webp_destination = os.path.join(
                                        rocm_blogs.blogs_directory,
                                        "_images",
                                        webp_filename,
                                    )
                                    os.makedirs(
                                        os.path.dirname(webp_destination), exist_ok=True
                                    )

                                    try:
                                        from .images import (
                                            convert_to_webp,
                                            generate_responsive_images)

                                        # Convert to WebP first
                                        success, webp_path = convert_to_webp(image_path)
                                        if success and webp_path:
                                            # Copy the webp to destination
                                            if (
                                                os.path.exists(webp_path)
                                                and webp_path != webp_destination
                                            ):
                                                shutil.copy2(
                                                    webp_path, webp_destination
                                                )
                                            blog_entry.image_paths[i] = webp_destination

                                            # Generate responsive variants for blog thumbnails
                                            images_dir = os.path.dirname(
                                                webp_destination
                                            )
                                            generate_responsive_images(
                                                webp_destination, output_dir=images_dir
                                            )

                                            log_message(
                                                "info",
                                                f"Created WebP version and responsive variants for blog page: {webp_destination}",
                                                "general",
                                                "process",
                                            )
                                        else:
                                            raise Exception("WebP conversion failed")
                                    except Exception as webp_error:
                                        log_message(
                                            "warning",
                                            f"Failed to convert {image_path} to WebP, using original: {webp_error}",
                                            "general",
                                            "process",
                                        )
                                        # Fall back to copying original file
                                        original_destination = os.path.join(
                                            rocm_blogs.blogs_directory,
                                            "_images",
                                            image_filename,
                                        )
                                        os.makedirs(
                                            os.path.dirname(original_destination),
                                            exist_ok=True,
                                        )
                                        if not os.path.exists(original_destination):
                                            shutil.copy2(
                                                image_path, original_destination
                                            )
                                        blog_entry.image_paths[i] = original_destination

                        except Exception as img_error:
                            log_message(
                                "warning",
                                f"Error processing image {image_path}: {img_error}",
                                "general",
                                "process",
                            )
                            continue

            except Exception as grab_error:
                log_message(
                    "warning",
                    f"Error grabbing images for blog {readme_file_path}: {grab_error}",
                    "general",
                    "process",
                )

        # OPTIMIZATION 4: Reduce logging overhead - only log errors
        try:
            word_count = count_words_in_markdown(file_content)
            blog_entry.set_word_count(word_count)
            # Skip word count logging for performance
        except Exception:
            # Silent fail for performance - word count is not critical
            blog_entry.set_word_count(0)

        try:
            authors_list = blog_entry.author.split(",")
            formatted_date = (
                blog_entry.date.strftime("%B %d, %Y") if blog_entry.date else "No Date"
            )
            blog_language = getattr(blog_entry, "language", "en")
            blog_category = getattr(blog_entry, "category", "blog")
            blog_tags = getattr(blog_entry, "tags", "")
            # Extract market verticals from metadata or auto-assign from tags
            market_verticals = []
            if hasattr(blog_entry, "metadata") and blog_entry.metadata:
                try:
                    myst_data = blog_entry.metadata.get("myst", {})
                    html_meta = myst_data.get("html_meta", {})
                    vertical_str = html_meta.get("vertical", "")

                    if vertical_str:
                        market_verticals = [
                            v.strip() for v in vertical_str.split(",") if v.strip()
                        ]
                except (AttributeError, KeyError):
                    pass

            # If no market verticals found in metadata, try automatic assignment from tags
            if not market_verticals or market_verticals == [""]:
                if blog_tags:
                    try:
                        # Import the classification function from metadata.py
                        from .metadata import classify_blog_tags

                        # Get automatic vertical classification
                        classification_result = classify_blog_tags(blog_tags)

                        if classification_result and classification_result.get(
                            "vertical_counts"
                        ):
                            vertical_counts = classification_result["vertical_counts"]
                            # Get all verticals with non-zero scores
                            auto_verticals = [
                                v for v, score in vertical_counts.items() if score > 0
                            ]
                            if auto_verticals:
                                market_verticals = auto_verticals
                                log_message(
                                    "info",
                                    f"Auto-assigned market verticals {auto_verticals} for blog {readme_file_path} based on tags: {blog_tags}",
                                    "general",
                                    "process",
                                )
                    except Exception as auto_assign_error:
                        log_message(
                            "warning",
                            f"Error auto-assigning market verticals for {readme_file_path}: {auto_assign_error}",
                            "general",
                            "process",
                        )

            # Format market verticals for display
            if not market_verticals or market_verticals == [""]:
                market_vertical = "No Market Vertical"
            else:
                market_vertical = ", ".join(
                    [
                        f'<a href="https://rocm.blogs.amd.com/{vertical.lower().replace(" ", "-")}.html">{vertical}</a>'
                        for vertical in market_verticals
                        if vertical.strip()
                    ]
                )

            tag_html_list = []
            if blog_tags:
                tags_list = [tag.strip() for tag in blog_tags.split(",")]
                for tag in tags_list:
                    tag_link = truncate_string(tag)
                    tag_html = f'<a href="https://rocm.blogs.amd.com/blog/tag/{tag_link}.html">{tag}</a>'
                    tag_html_list.append(tag_html)

            tags_html = ", ".join(tag_html_list)

            category_link = truncate_string(blog_category)
            category_html = f'<a href="https://rocm.blogs.amd.com/blog/category/{category_link}.html">{blog_category.strip()}</a>'

            blog_read_time = (
                str(calculate_read_time(getattr(blog_entry, "word_count", 0)))
                if hasattr(blog_entry, "word_count")
                else "No Read Time"
            )

            authors_html = blog_entry.grab_authors(authors_list, rocm_blogs)
            if authors_html:
                authors_html = authors_html.replace("././", "../../").replace(
                    ".md", ".html"
                )

            has_valid_author = authors_html and "No author" not in authors_html

            title_line, title_line_number = None, None
            for i, line in enumerate(content_lines):
                if line.startswith("#") and line.count("#") == 1:
                    title_line = line
                    title_line_number = i
                    break

            if not title_line or title_line_number is None:
                log_message(
                    "warning",
                    f"Could not find title in blog {readme_file_path}",
                    "general",
                    "process",
                )
                return

            try:
                quickshare_button = quickshare(blog_entry)
                image_css = import_file("rocm_blogs.static.css", "image_blog.css")
                image_html = import_file("rocm_blogs.templates", "image_blog.html")
                blog_css = import_file("rocm_blogs.static.css", "blog.css")
                author_attribution_template = import_file(
                    "rocm_blogs.templates", "author_attribution.html"
                )
                giscus_html = import_file("rocm_blogs.templates", "giscus.html")
            except Exception as template_error:
                log_message(
                    "error",
                    f"Error loading templates for blog {readme_file_path}: {template_error}",
                    "general",
                    "process",
                )
                log_message(
                    "debug",
                    f"Traceback: {traceback.format_exc()}",
                    "general",
                    "process",
                )
                raise

            if has_valid_author:
                modified_author_template = author_attribution_template
            else:
                # Create a modified template without "by {authors_string}"
                modified_author_template = author_attribution_template.replace(
                    "<span> {date} by {authors_string}.</span>", "<span> {date}</span>"
                )

            authors_html_filled = (
                modified_author_template.replace("{authors_string}", authors_html)
                .replace("{date}", formatted_date)
                .replace("{language}", blog_language)
                .replace("{category}", category_html)
                .replace("{tags}", tags_html)
                .replace("{read_time}", blog_read_time)
                .replace(
                    "{word_count}",
                    str(getattr(blog_entry, "word_count", "No Word Count")),
                )
                .replace("{market_vertical}", market_vertical)
            )

            try:
                blog_path = Path(blog_entry.file_path)
                blogs_directory_path = Path(rocm_blogs.blogs_directory)

                try:
                    relative_path = blog_path.relative_to(blogs_directory_path)

                    directory_depth = len(relative_path.parts) - 1
                    log_message(
                        "info",
                        f"Blog depth: {directory_depth} for {blog_entry.file_path}",
                        "general",
                        "process",
                    )

                    parent_directories = "../" * directory_depth

                    log_message(
                        "info",
                        f"Using {parent_directories} for blog at depth {directory_depth}: {blog_entry.file_path}",
                        "general",
                        "process",
                    )

                    if blog_entry.image_paths:
                        full_image_path = blog_entry.image_paths[-1]
                        image_filename = os.path.basename(full_image_path)
                        log_message(
                            "info",
                            f"Blog '{getattr(blog_entry, 'blog_title', 'unknown')}' has image_path: {full_image_path}",
                            "general",
                            "process",
                        )

                        if not image_filename.lower().endswith(".webp"):
                            base_name, ext = os.path.splitext(image_filename)
                            webp_filename = f"{base_name}.webp"

                            # First, check if WebP version exists in the same directory as the original
                            webp_in_original_dir = os.path.join(
                                os.path.dirname(full_image_path), webp_filename
                            )
                            webp_in_images_dir = os.path.join(
                                rocm_blogs.blogs_directory, "_images", webp_filename
                            )

                            if os.path.exists(webp_in_original_dir):
                                # Use the WebP version from the original location
                                image_filename = webp_filename
                                # Copy it to _images if it doesn't exist there
                                if not os.path.exists(webp_in_images_dir):
                                    os.makedirs(
                                        os.path.dirname(webp_in_images_dir),
                                        exist_ok=True,
                                    )
                                    shutil.copy2(
                                        webp_in_original_dir, webp_in_images_dir
                                    )
                                    log_message(
                                        "info",
                                        f"Copied WebP to _images: {webp_filename}",
                                        "general",
                                        "process",
                                    )
                                    # Generate responsive variants
                                    from .images import \
                                        generate_responsive_images

                                    generate_responsive_images(webp_in_images_dir)
                                log_message(
                                    "info",
                                    f"Using WebP version: {image_filename} from original directory",
                                    "general",
                                    "process",
                                )
                            elif os.path.exists(webp_in_images_dir):
                                image_filename = webp_filename
                                log_message(
                                    "info",
                                    f"Using WebP version: {image_filename} from _images directory",
                                    "general",
                                    "process",
                                )
                            else:
                                # Check if original image exists and can be converted
                                if os.path.exists(full_image_path):
                                    log_message(
                                        "info",
                                        f"Original image found at {full_image_path}, will use it directly",
                                        "general",
                                        "process",
                                    )
                                    # Copy original to _images and keep original filename
                                    dest_path = os.path.join(
                                        rocm_blogs.blogs_directory,
                                        "_images",
                                        image_filename,
                                    )
                                    if not os.path.exists(dest_path):
                                        os.makedirs(
                                            os.path.dirname(dest_path), exist_ok=True
                                        )
                                        shutil.copy2(full_image_path, dest_path)
                                        log_message(
                                            "info",
                                            f"Copied original to _images: {image_filename}",
                                            "general",
                                            "process",
                                        )
                                        # Generate responsive variants
                                        from .images import \
                                            generate_responsive_images

                                        generate_responsive_images(dest_path)
                                else:
                                    log_message(
                                        "warning",
                                        f"Neither WebP nor original image found for {image_filename}, using generic",
                                        "general",
                                        "process",
                                    )
                                    image_filename = "generic.webp"
                        else:
                            # Image is already WebP - check if it exists and copy to _images if needed
                            webp_in_images_dir = os.path.join(
                                rocm_blogs.blogs_directory, "_images", image_filename
                            )
                            if os.path.exists(full_image_path):
                                if not os.path.exists(webp_in_images_dir):
                                    os.makedirs(
                                        os.path.dirname(webp_in_images_dir),
                                        exist_ok=True,
                                    )
                                    shutil.copy2(full_image_path, webp_in_images_dir)
                                    log_message(
                                        "info",
                                        f"Copied WebP to _images: {image_filename}",
                                        "general",
                                        "process",
                                    )
                                    # Generate responsive variants
                                    from .images import \
                                        generate_responsive_images

                                    generate_responsive_images(webp_in_images_dir)
                                log_message(
                                    "info",
                                    f"Using WebP image: {image_filename}",
                                    "general",
                                    "process",
                                )
                            else:
                                log_message(
                                    "warning",
                                    f"WebP image not found at {full_image_path}, using generic",
                                    "general",
                                    "process",
                                )
                                image_filename = "generic.webp"
                    else:
                        image_filename = "generic.webp"

                    blog_image_path = f"{parent_directories}_images/{image_filename}"

                    # Validate that the main image actually exists
                    main_image_full_path = os.path.join(
                        rocm_blogs.blogs_directory, "_images", image_filename
                    )
                    if not os.path.exists(main_image_full_path):
                        log_message(
                            "warning",
                            f"Main image not found at: {main_image_full_path}, falling back to generic",
                            "general",
                            "process",
                        )
                        image_filename = "generic.webp"
                        blog_image_path = (
                            f"{parent_directories}_images/{image_filename}"
                        )
                        main_image_full_path = os.path.join(
                            rocm_blogs.blogs_directory, "_images", image_filename
                        )

                    log_message(
                        "info",
                        f"Using image path for blog: {blog_image_path} (exists: {os.path.exists(main_image_full_path)})",
                        "general",
                        "process",
                    )

                except ValueError:
                    log_message(
                        "warning",
                        f"Could not determine relative path for {blog_entry.file_path}, using default image path",
                        "general",
                        "process",
                    )
                    if blog_entry.image_paths:
                        image_filename = os.path.basename(blog_entry.image_paths[0])
                        if not image_filename.lower().endswith(".webp"):
                            base_name, ext = os.path.splitext(image_filename)
                            webp_filename = f"{base_name}.webp"

                            # Check if the WebP version actually exists in the _images directory
                            webp_path = os.path.join(
                                rocm_blogs.blogs_directory, "_images", webp_filename
                            )
                            if os.path.exists(webp_path):
                                image_filename = webp_filename
                                log_message(
                                    "info",
                                    f"Using WebP version in fallback: {image_filename} instead of {os.path.basename(blog_entry.image_paths[0])}",
                                    "general",
                                    "process",
                                )
                            else:
                                log_message(
                                    "warning",
                                    f"WebP version not found at {webp_path} in fallback, using generic image",
                                    "general",
                                    "process",
                                )
                                image_filename = "generic.webp"
                        blog_image_path = f"../../_images/{image_filename}"
                    else:
                        blog_image_path = "../../_images/generic.webp"

                # Generate srcset for responsive images
                srcset_entries = []
                image_width = "1024"
                image_height = "576"

                # Build srcset based on available responsive variants
                if image_filename and image_filename != "generic.webp":
                    base_name_no_ext = os.path.splitext(image_filename)[0]
                    # Use the same directory path format as the main image
                    image_base_dir = os.path.dirname(blog_image_path)
                    images_dir = os.path.join(rocm_blogs.blogs_directory, "_images")

                    log_message(
                        "info",
                        f"Building srcset for {image_filename}: base_dir={image_base_dir}, images_dir={images_dir}",
                        "general",
                        "process",
                    )

                    # Add responsive variants - matching NVIDIA's proven breakpoints
                    variants_found = 0

                    # Get original image dimensions and validate path
                    actual_image_width = 1024  # Default
                    webp_full_path = os.path.join(images_dir, image_filename)

                    try:
                        if os.path.exists(webp_full_path):
                            from PIL import Image

                            with Image.open(webp_full_path) as img:
                                image_width = str(img.width)
                                image_height = str(img.height)
                                actual_image_width = img.width
                                log_message(
                                    "info",
                                    f"Original image dimensions: {image_width}x{image_height} for {image_filename}",
                                )
                        else:
                            log_message(
                                "warning",
                                f"Original image not found at: {webp_full_path}",
                            )
                    except Exception as dim_error:
                        log_message(
                            "error", f"Could not get image dimensions: {dim_error}"
                        )

                    # Optimized responsive breakpoints for performance and bandwidth efficiency
                    target_widths = [
                        320,  # Mobile portrait (saves ~75% bandwidth vs desktop)
                        480,  # Mobile landscape / small tablet
                        640,  # Tablet portrait (good balance for mid-range devices)
                        768,  # Large tablet / small desktop
                        1024,  # Desktop standard (covers most laptops)
                        1440,  # Large desktop / high-DPI mobile
                        1920,  # Full HD desktop / 2x mobile retina
                    ]

                    for width in target_widths:
                        # Skip widths larger than the original image
                        if width > actual_image_width:
                            continue

                        variant_filename = f"{base_name_no_ext}-{width}w.webp"
                        variant_file_path = os.path.join(images_dir, variant_filename)

                        # Only add to srcset if the variant file actually exists
                        if os.path.exists(variant_file_path):
                            variant_path = f"{image_base_dir}/{variant_filename}"
                            srcset_entries.append(f"{variant_path} {width}w")
                            variants_found += 1
                            log_message(
                                "debug", f"Found responsive variant: {variant_filename}"
                            )
                        else:
                            log_message(
                                "debug",
                                f"Responsive variant not found: {variant_file_path}",
                            )

                    # Always include the original image with its actual width if not already included
                    if not any(
                        f"{actual_image_width}w" in entry for entry in srcset_entries
                    ):
                        srcset_entries.append(
                            f"{blog_image_path} {actual_image_width}w"
                        )
                        log_message(
                            "info",
                            f"Added original image to srcset: {blog_image_path} at {actual_image_width}w",
                        )

                    if srcset_entries:
                        srcset_attr = ", ".join(srcset_entries)
                        log_message(
                            "info",
                            f"Generated srcset with {variants_found} responsive variants for {image_filename}",
                            "general",
                            "process",
                        )
                    else:
                        # Fallback if no responsive variants exist
                        srcset_attr = f"{blog_image_path} 1920w"
                        log_message(
                            "warning",
                            f"No responsive variants found for {image_filename}, using single image fallback",
                            "general",
                            "process",
                        )
                else:
                    # For generic image, just use the single image
                    srcset_attr = f"{blog_image_path} 1920w"
                    log_message("debug", f"Using generic image srcset: {srcset_attr}")

                log_message("debug", f"Final srcset: {srcset_attr}")

                image_template_filled = (
                    image_html.replace("{IMAGE}", blog_image_path)
                    .replace("{TITLE}", getattr(blog_entry, "blog_title", ""))
                    .replace("{SRCSET}", srcset_attr)
                    .replace("{WIDTH}", image_width)
                    .replace("{HEIGHT}", image_height)
                )
            except Exception as image_path_error:
                log_message(
                    "error",
                    f"Error determining image path for blog {readme_file_path}: {image_path_error}",
                    "general",
                    "process",
                )
                log_message(
                    "debug",
                    f"Traceback: {traceback.format_exc()}",
                    "general",
                    "process",
                )
                raise

            blog_template = f"""
<style>
{blog_css}
</style>
"""
            image_template = f"""
<style>
{image_css}
</style>
{image_template_filled}
"""

            try:
                updated_lines = content_lines.copy()
                updated_lines.insert(title_line_number + 1, f"\n{blog_template}\n")
                updated_lines.insert(title_line_number + 2, f"\n{image_template}\n")
                updated_lines.insert(
                    title_line_number + 3, f"\n{authors_html_filled}\n"
                )
                updated_lines.insert(title_line_number + 4, f"\n{quickshare_button}\n")

                updated_lines.append(f"\n\n{giscus_html}\n")

                with open(
                    readme_file_path, "w", encoding="utf-8", errors="replace"
                ) as output_file:
                    output_file.writelines(updated_lines)
            except Exception as write_error:
                log_message(
                    "error",
                    f"Error writing to blog file {readme_file_path}: {write_error}",
                    "general",
                    "process",
                )
                log_message(
                    "debug",
                    f"Traceback: {traceback.format_exc()}",
                    "general",
                    "process",
                )
                raise

            processing_end_time = time.time()
            processing_duration = processing_end_time - processing_start_time
            log_message(
                "info",
                f"\033[33mSuccessfully processed blog {readme_file_path} in \033[96m{processing_duration:.2f} milliseconds\033[33m\033[0m",
                "general",
                "process",
            )
        except Exception as metadata_error:
            log_message(
                "warning",
                f"Error processing metadata for blog {readme_file_path}: {metadata_error}",
                "general",
                "process",
            )
            log_message(
                "debug",
                f"Traceback: {traceback.format_exc()}",
                "general",
                "process",
            )
            raise

    except Exception as process_error:
        log_message(
            "error",
            f"Error processing blog {getattr(blog_entry, 'file_path', 'Unknown')}: {process_error}",
            "general",
            "process",
        )
        log_message(
            "debug",
            f"Traceback: {traceback.format_exc()}",
            "general",
            "process",
        )
        raise
