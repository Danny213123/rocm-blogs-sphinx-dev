"""
External Content Sidebar Generator - Hugging Face Style

Generates minimal, text-only external content items for the homepage sidebar.
"""

import re
from datetime import datetime
from typing import List

from ..logger.logger import (create_step_log_file, log_message, safe_log_close,
                             safe_log_write)
from .content import ExternalContent


def generate_external_item_html(content: ExternalContent) -> str:
    """Generate a single external content item HTML (HF-style)."""

    log_message(
        "debug",
        f"Generating HTML for external item: '{content.title}'",
        "external_content",
        "html_generation",
    )

    # Format date
    date_str = ""
    if content.date:
        try:
            date_str = content.date.strftime("%b %d")
            # Add year if not current year
            if content.date.year != datetime.now().year:
                date_str = content.date.strftime("%b %d, %Y")
            log_message(
                "debug",
                f"Formatted date for '{content.title}': {date_str}",
                "external_content",
                "date_formatting",
            )
        except Exception as e:
            log_message(
                "warning",
                f"Error formatting date for '{content.title}': {e}",
                "external_content",
                "date_formatting",
            )
            date_str = ""

    # Build author string
    author_html = ""
    if content.author:
        author_html = f'<span class="external-article-author">{content.author}</span>'
        log_message(
            "debug",
            f"Added author for '{content.title}': {content.author}",
            "external_content",
            "html_generation",
        )

    # Build meta string with separator
    meta_parts = []
    if author_html:
        meta_parts.append(author_html)
    if date_str:
        meta_parts.append(f'<span class="external-article-date">{date_str}</span>')

    meta_html = " · ".join(meta_parts) if meta_parts else ""
    log_message(
        "debug",
        f"Built meta HTML for '{content.title}': {len(meta_parts)} parts",
        "external_content",
        "html_generation",
    )

    # Add source domain
    source_html = ""
    if content.source_domain:
        source_html = f"""
            <span class="external-article-source">
                {content.source_domain}
                <svg class="external-link-icon" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                </svg>
            </span>"""
        log_message(
            "debug",
            f"Added source domain for '{content.title}': {content.source_domain}",
            "external_content",
            "html_generation",
        )

    # Validate URL
    if not content.url:
        log_message(
            "warning",
            f"External content '{content.title}' has no URL",
            "external_content",
            "html_generation",
        )
        return ""

    if not content.url.startswith(("http://", "https://")):
        log_message(
            "warning",
            f"External content '{content.title}' has invalid URL: {content.url}",
            "external_content",
            "html_generation",
        )

    # Generate the item HTML
    description_html = ""
    if content.description:
        description_html = (
            f'<p class="external-article-description">{content.description}</p>'
        )
        log_message(
            "debug",
            f"Added description for '{content.title}': {len(content.description)} chars",
            "external_content",
            "html_generation",
        )

    item_html = f"""
        <article class="external-article-item">
            <a href="{content.url}" target="_blank" rel="noopener noreferrer" class="external-article-link">
                <h3 class="external-article-title">{content.title}</h3>
                <div class="external-article-meta">
                    {meta_html}
                    {source_html}
                </div>
                {description_html}
            </a>
        </article>""".strip()

    log_message(
        "debug",
        f"Generated HTML for '{content.title}': {len(item_html)} characters",
        "external_content",
        "html_generation",
    )

    return item_html


def generate_external_sidebar_content(
    external_items: List[ExternalContent],
    max_items: int = 8,
    show_descriptions: bool = True,
) -> str:
    """
    Generate the complete external content sidebar HTML.

    Args:
        external_items: List of ExternalContent objects
        max_items: Maximum number of items to display
        show_descriptions: Whether to show descriptions

    Returns:
        HTML string for all external content items
    """

    # Create dedicated log file for sidebar generation
    log_file_path, log_file_handle = create_step_log_file("external_content_sidebar")

    log_message(
        "info",
        f"Generating external sidebar content with {len(external_items)} items (max: {max_items}, descriptions: {show_descriptions})",
        "external_content",
        "sidebar_generation",
    )

    if log_file_handle:
        safe_log_write(
            log_file_handle, f"=== External Content Sidebar Generation ===\n"
        )
        safe_log_write(log_file_handle, f"Input items: {len(external_items)}\n")
        safe_log_write(log_file_handle, f"Max items: {max_items}\n")
        safe_log_write(log_file_handle, f"Show descriptions: {show_descriptions}\n")
        safe_log_write(
            log_file_handle,
            f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n",
        )

    if not external_items:
        warning_msg = "No external content items to display in sidebar"
        log_message("warning", warning_msg, "external_content", "sidebar_generation")
        if log_file_handle:
            safe_log_write(log_file_handle, f"WARNING: {warning_msg}\n")
            safe_log_close(log_file_handle)
        return '<p style="color: #718096; font-size: 14px;">No external content available.</p>'

    # Sort by date (most recent first)
    dated_items = [item for item in external_items if item.date]
    undated_items = [item for item in external_items if not item.date]

    log_message(
        "debug",
        f"Sorting external items - Dated: {len(dated_items)}, Undated: {len(undated_items)}",
        "external_content",
        "sidebar_generation",
    )

    try:
        sorted_items = sorted(dated_items, key=lambda x: x.date, reverse=True)
        log_message(
            "debug",
            f"Successfully sorted {len(sorted_items)} dated items",
            "external_content",
            "sidebar_generation",
        )
    except Exception as e:
        log_message(
            "error",
            f"Error sorting external content by date: {e}",
            "external_content",
            "sidebar_generation",
        )
        sorted_items = dated_items

    # Add items without dates at the end
    sorted_items.extend(undated_items)

    # Limit items
    display_items = sorted_items[:max_items]
    log_message(
        "info",
        f"Selected {len(display_items)} items for display (from {len(sorted_items)} total)",
        "external_content",
        "sidebar_generation",
    )

    # Generate HTML for each item
    items_html = []
    failed_items = 0

    for i, item in enumerate(display_items):
        try:
            log_message(
                "debug",
                f"Processing item {i+1}/{len(display_items)}: '{item.title}'",
                "external_content",
                "item_processing",
            )

            item_html = generate_external_item_html(item)

            if not item_html:
                log_message(
                    "warning",
                    f"Generated empty HTML for external item: '{item.title}'",
                    "external_content",
                    "item_processing",
                )
                failed_items += 1
                continue

            # Optionally remove descriptions for more compact display
            if (
                not show_descriptions
                and '<p class="external-article-description">' in item_html
            ):
                # Remove description paragraph
                original_length = len(item_html)
                item_html = re.sub(
                    r'<p class="external-article-description">.*?</p>',
                    "",
                    item_html,
                    flags=re.DOTALL,
                )
                log_message(
                    "debug",
                    f"Removed description from '{item.title}': {original_length} -> {len(item_html)} chars",
                    "external_content",
                    "item_processing",
                )

            items_html.append(item_html)

        except Exception as e:
            failed_items += 1
            log_message(
                "error",
                f"Failed to generate external item HTML for '{item.title}': {e}",
                "external_content",
                "item_processing",
            )

    if failed_items > 0:
        log_message(
            "warning",
            f"Failed to generate HTML for {failed_items} external content items",
            "external_content",
            "sidebar_generation",
        )

    final_html = "\n".join(items_html)

    # Final summary logging
    summary_msg = (
        f"Generated sidebar HTML: {len(items_html)} items, {len(final_html)} characters"
    )
    log_message("info", summary_msg, "external_content", "sidebar_generation")

    if log_file_handle:
        safe_log_write(log_file_handle, f"\n=== GENERATION SUMMARY ===\n")
        safe_log_write(log_file_handle, f"{summary_msg}\n")
        safe_log_write(log_file_handle, f"Failed items: {failed_items}\n")
        safe_log_write(
            log_file_handle, f"Final HTML length: {len(final_html)} characters\n"
        )
        safe_log_write(
            log_file_handle,
            f"Session complete: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n",
        )

    if log_file_path:
        log_message(
            "info",
            f"Sidebar generation detailed log written to: {log_file_path}",
            "external_content",
            "sidebar_generation",
        )

    if log_file_handle:
        safe_log_close(log_file_handle)

    return final_html


def generate_external_content(
    main_grid_items: str,
    external_content: List[ExternalContent],
    main_title: str = "Latest Blogs",
    max_external: int = 8,
) -> str:
    """
    Generate complete homepage HTML with external content sidebar.

    Args:
        main_grid_items: HTML string of main blog grid items
        external_content: List of ExternalContent objects
        main_title: Title for main content section
        max_external: Maximum external items to show

    Returns:
        Complete HTML for homepage with sidebar
    """

    log_message(
        "info",
        f"Generating homepage with external content - Main title: '{main_title}', Max external: {max_external}",
        "external_content",
        "homepage_generation",
    )

    log_message(
        "debug",
        f"Main grid items length: {len(main_grid_items)} chars",
        "external_content",
        "homepage_generation",
    )

    external_items_html = generate_external_sidebar_content(
        external_content, max_items=max_external, show_descriptions=True
    )

    if not external_items_html:
        log_message(
            "warning",
            "No external items HTML generated for homepage",
            "external_content",
            "homepage_generation",
        )
        external_items_html = '<p style="color: #718096; font-size: 14px;">No external content available.</p>'

    template = """
<link rel="stylesheet" href="/_static/css/external_sidebar.css">

<div class="homepage-container">
    <!-- Main Blog Content -->
    <div class="main-content">
        <h1>{main_title}</h1>
        
        :::{{grid}} 1 2 3 3
        :margin 2
        {main_grid_items}
        :::
    </div>
    
    <!-- External Content Sidebar -->
    <aside class="external-content-sidebar">
        <div class="external-content-header">
            <h2 class="external-content-title">Community & Resources</h2>
            <span class="external-indicator">
                <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                </svg>
                External
            </span>
        </div>
        
        <div class="external-articles-list">
            {external_content_items}
        </div>
    </aside>
</div>"""

    final_homepage = template.format(
        main_title=main_title,
        main_grid_items=main_grid_items,
        external_content_items=external_items_html,
    ).strip()

    log_message(
        "info",
        f"Generated complete homepage HTML: {len(final_homepage)} characters",
        "external_content",
        "homepage_generation",
    )

    return final_homepage


def validate_external_content_html(html: str, content_title: str = "unknown") -> bool:
    """Validate generated external content HTML for common issues."""

    log_message(
        "debug",
        f"Validating HTML for external content: '{content_title}'",
        "external_content",
        "html_validation",
    )

    issues = []

    # Check for basic HTML structure
    if not html.strip():
        issues.append("Empty HTML")

    # Check for required elements
    required_elements = [
        'class="external-article-item"',
        'class="external-article-link"',
        'class="external-article-title"',
    ]

    for element in required_elements:
        if element not in html:
            issues.append(f"Missing required element: {element}")

    # Check for malformed URLs
    if 'href=""' in html or 'href=" "' in html:
        issues.append("Empty or invalid href attribute")

    # Check for unclosed tags (basic check)
    open_tags = html.count("<") - html.count("</")
    close_tags = html.count("</")
    if open_tags != close_tags:
        issues.append(
            f"Potential tag mismatch: {open_tags} opening tags, {close_tags} closing tags"
        )

    if issues:
        log_message(
            "warning",
            f"HTML validation issues for '{content_title}': {', '.join(issues)}",
            "external_content",
            "html_validation",
        )
        return False
    else:
        log_message(
            "debug",
            f"HTML validation passed for '{content_title}'",
            "external_content",
            "html_validation",
        )
        return True
