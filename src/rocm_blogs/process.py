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
        social_css = import_file("rocm_blogs.static.css", "social-bar.css")
        social_html = import_file("rocm_blogs.templates", "social-bar.html")

        social_bar_template = """
<style>
{CSS}
</style>
{HTML}
"""
        social_bar = social_bar_template.format(CSS=social_css, HTML=social_html)

        if hasattr(blog_entry, "file_path"):
            blog_directory = os.path.basename(os.path.dirname(blog_entry.file_path))
            share_url = f"http://rocm.blogs.amd.com/artificial-intelligence/{blog_directory}/README.html"
        else:
            share_url = f"http://rocm.blogs.amd.com{blog_entry.grab_href()[1:]}"

        blog_title = getattr(blog_entry, "blog_title", "No Title")
        title_with_suffix = f"{blog_title} | ROCm Blogs"

        blog_description = "No Description"
        if hasattr(blog_entry, "myst"):
            blog_description = blog_entry.myst.get("html_meta", {}).get(
                "description lang=en", blog_description
            )

        if (
            hasattr(blog_entry, "file_path")
            and "test" in str(blog_entry.file_path).lower()
        ):
            social_bar += (
                f"\n<!-- {title_with_suffix} -->\n<!-- {blog_description} -->\n"
            )

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

    if current_page < total_pages:
        next_page = current_page + 1
        next_file = f"{base_name}-page{next_page}.html"
        next_button = f'<a href="{next_file}" class="pagination-button next">Next </a>'
    else:
        next_button = '<span class="pagination-button disabled">Next </span>'

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

    if category_blogs is None:
        category_blogs = []
        all_blogs = rocm_blogs.blogs.get_blogs()

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
                    if not isinstance(values, list):
                        values = [values]

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

                            blog_verticals = [
                                v.strip() for v in vertical_str.split(",") if v.strip()
                            ]

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

    if not all_grid_items:
        log_message(
            "warning",
            f"No grid items were generated for category: {category_name}. Skipping page generation.",
            "general",
            "process",
        )
        return

    for page_num in range(1, total_pages + 1):
        start_index = (page_num - 1) * CATEGORY_BLOGS_PER_PAGE
        end_index = min(start_index + CATEGORY_BLOGS_PER_PAGE, len(all_grid_items))
        page_grid_items = all_grid_items[start_index:end_index]

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

        page_title_suffix = f" - Page {page_num}" if page_num > 1 else ""
        page_description_suffix = (
            f" (Page {page_num} of {total_pages})" if page_num > 1 else ""
        )

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
        log_message(
            "debug",
            f"_generate_grid_items called with: max_items={max_items}, skip_used={skip_used}, use_og={use_og}, blog_count={len(blog_list)}",
            "general",
            "process",
        )

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

        with ThreadPoolExecutor() as executor:
            grid_futures = {}

            for blog_entry in blog_list:
                blog_id = id(blog_entry)
                blog_path = getattr(blog_entry, "file_path", None)

                already_used = False
                if skip_used:
                    if any(id(used_blog) == blog_id for used_blog in used_blogs):
                        already_used = True
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

                if item_count >= max_items:
                    log_message(
                        "debug",
                        f"Reached maximum number of items ({max_items}), skipping remaining blogs",
                        "general",
                        "process",
                    )
                    break

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
                        continue

                    if (
                        len(grid_result.strip()) < 50
                    ):
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

        if not grid_items:
            if item_count == 0:
                log_message(
                    "warning",
                    "No blogs were available to generate grid items. Returning empty list.",
                    "general",
                    "process",
                )
                return []

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

                if len(grid_html.strip()) < 50:
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
            return

        with open(
            readme_file_path, "r", encoding="utf-8", errors="replace"
        ) as source_file:
            file_content = source_file.read()
            content_lines = file_content.splitlines(True)

        webp_versions = {}

        if hasattr(blog_entry, "thumbnail") and blog_entry.thumbnail:
            try:
                blog_entry.grab_image(rocm_blogs)

                if blog_entry.image_paths:
                    for i, image_path in enumerate(blog_entry.image_paths):
                        try:
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
                                image_filename = os.path.basename(image_path)
                                name_without_ext = os.path.splitext(image_filename)[0]
                                webp_filename = f"{name_without_ext}.webp"

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
                                    blog_entry.image_paths[i] = webp_destination
                                    log_message(
                                        "info",
                                        f"Using existing WebP version: {webp_destination}",
                                        "general",
                                        "process",
                                    )
                                else:
                                    webp_destination = os.path.join(
                                        rocm_blogs.blogs_directory,
                                        "_images",
                                        webp_filename,
                                    )
                                    os.makedirs(
                                        os.path.dirname(webp_destination), exist_ok=True
                                    )

                                    try:
                                        from .images import convert_to_webp

                                        convert_to_webp(image_path, webp_destination)
                                        blog_entry.image_paths[i] = webp_destination
                                        log_message(
                                            "info",
                                            f"Created WebP version for blog page: {webp_destination}",
                                            "general",
                                            "process",
                                        )
                                    except Exception as webp_error:
                                        log_message(
                                            "warning",
                                            f"Failed to convert {image_path} to WebP, using original: {webp_error}",
                                            "general",
                                            "process",
                                        )
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

        try:
            word_count = count_words_in_markdown(file_content)
            blog_entry.set_word_count(word_count)
        except Exception:
            blog_entry.set_word_count(0)

        try:
            authors_list = blog_entry.author.split(",")
            formatted_date = (
                blog_entry.date.strftime("%B %d, %Y") if blog_entry.date else "No Date"
            )
            blog_language = getattr(blog_entry, "language", "en")
            blog_category = getattr(blog_entry, "category", "blog")
            blog_tags = getattr(blog_entry, "tags", "")
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

            if not market_verticals or market_verticals == [""]:
                if blog_tags:
                    try:
                        from .metadata import classify_blog_tags

                        classification_result = classify_blog_tags(blog_tags)

                        if classification_result and classification_result.get(
                            "vertical_counts"
                        ):
                            vertical_counts = classification_result["vertical_counts"]
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
                        image_filename = os.path.basename(blog_entry.image_paths[0])
                    else:
                        image_filename = "generic.jpg"

                    blog_image_path = f"{parent_directories}_images/{image_filename}"

                    log_message(
                        "info",
                        f"Using image path for blog: {blog_image_path}",
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
                        blog_image_path = f"../../_images/{blog_entry.image_paths[0]}"
                    else:
                        blog_image_path = "../../_images/generic.jpg"

                image_template_filled = image_html.replace(
                    "{IMAGE}", blog_image_path
                ).replace("{TITLE}", getattr(blog_entry, "blog_title", ""))
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
