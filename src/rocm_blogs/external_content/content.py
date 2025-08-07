"""
External Content management for ROCm Blogs.

Handles loading and displaying external content from CSV files in a minimalist,
modern design that integrates seamlessly with the existing blog system.
"""

import csv
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import urlparse

from ..logger.logger import log_message, safe_log_write, create_step_log_file, safe_log_close



class ExternalContent:
    """Represents external content item with metadata."""

    def __init__(self, data: Dict[str, str], row_number: Optional[int] = None):
        """Initialize ExternalContent from CSV row data."""
        self.row_number = row_number
        
        log_message("debug", f"Initializing ExternalContent from row {row_number or 'unknown'}", 
                   "external_content", "content_init")
        
        self.title = data.get("title", "").strip()
        self.description = data.get("description", "").strip()
        self.url = data.get("url", "").strip()
        self.author = data.get("author", "").strip()
        self.category = data.get("category", "").strip()
        self.tags = data.get("tags", "").strip()
        self.content_type = data.get("content_type", "article").strip().lower()
        self.source_domain = data.get("source_domain", "").strip()
        
        log_message("debug", f"Parsed content fields - Title: '{self.title}', Type: '{self.content_type}', Category: '{self.category}'", 
                   "external_content", "content_init")
        date_str = data.get("date", "").strip()
        try:
            self.date = datetime.strptime(date_str, "%Y-%m-%d")
            log_message("debug", f"Successfully parsed date: {date_str} -> {self.date.strftime('%Y-%m-%d')}", 
                       "external_content", "date_parsing")
        except ValueError as e:
            log_message("warning", f"Invalid date format for external content row {row_number}: '{date_str}' - {e}", 
                       "external_content", "date_parsing")
            self.date = None
        
        if not self.source_domain and self.url:
            try:
                parsed_url = urlparse(self.url)
                self.source_domain = parsed_url.netloc.replace("www.", "")
                log_message("debug", f"Extracted source domain from URL: {self.source_domain}", 
                           "external_content", "domain_extraction")
            except Exception as e:
                log_message("warning", f"Failed to extract domain from URL '{self.url}': {e}", 
                           "external_content", "domain_extraction")
                self.source_domain = "external"
        
        valid = self.is_valid()
        log_message("debug" if valid else "warning", 
                   f"External content validation {'passed' if valid else 'failed'}: {self.title}", 
                   "external_content", "content_validation")
    
    def is_valid(self) -> bool:
        """Check if external content has required fields."""
        required_fields = [self.title, self.description, self.url]
        missing_fields = []
        
        if not self.title:
            missing_fields.append("title")
        if not self.description:
            missing_fields.append("description")  
        if not self.url:
            missing_fields.append("url")
            
        if missing_fields:
            log_message("debug", f"Missing required fields for external content: {missing_fields}", 
                       "external_content", "validation")
            
        return len(missing_fields) == 0
    
    def get_content_type_icon(self) -> str:
        """Get icon class for content type."""
        icons = {
            "article": "📄",
            "tutorial": "📚", 
            "video": "📹",
            "repository": "📂",
            "documentation": "📋",
            "tool": "🔧",
            "library": "📦"
        }
        icon = icons.get(self.content_type, "🔗")
        log_message("debug", f"Content type icon for '{self.content_type}': {icon}", 
                   "external_content", "icon_mapping")
        return icon
    
    def to_dict(self) -> Dict[str, any]:
        """Convert external content to dictionary for debugging."""
        return {
            "title": self.title,
            "description": self.description,
            "url": self.url,
            "author": self.author,
            "category": self.category,
            "tags": self.tags,
            "content_type": self.content_type,
            "source_domain": self.source_domain,
            "date": self.date.isoformat() if self.date else None,
            "is_valid": self.is_valid(),
            "row_number": self.row_number
        }


class ExternalContentLoader:
    """Loads and manages external content from CSV files."""
    
    def __init__(self, blogs_directory: str):
        """Initialize loader with blogs directory."""
        self.blogs_directory = Path(blogs_directory)
        self.external_content: List[ExternalContent] = []
        
        log_message("info", f"Initializing ExternalContentLoader with directory: {self.blogs_directory}", 
                   "external_content", "loader_init")
    
    def load_from_csv(self, csv_filename: str = "external-content.csv") -> List[ExternalContent]:
        """Load external content from CSV file."""
        csv_path = self.blogs_directory / csv_filename
        
        log_file_path, log_file_handle = create_step_log_file("external_content_loading")
        
        log_message("info", f"Starting to load external content from: {csv_path}", 
                   "external_content", "csv_loading")
        if log_file_handle:
            safe_log_write(log_file_handle, f"=== External Content Loading Session ===\n")
            safe_log_write(log_file_handle, f"CSV Path: {csv_path}\n")
            safe_log_write(log_file_handle, f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        
        if not csv_path.exists():
            error_msg = f"External content CSV not found: {csv_path}"
            log_message("warning", error_msg, "external_content", "csv_loading")
            if log_file_handle:
                safe_log_write(log_file_handle, f"ERROR: {error_msg}\n")
                safe_log_close(log_file_handle)
            return []
        
        try:
            file_size = csv_path.stat().st_size
            info_msg = f"CSV file found - Size: {file_size} bytes"
            log_message("info", info_msg, "external_content", "csv_loading")
            if log_file_handle:
                safe_log_write(log_file_handle, f"File Info: {info_msg}\n")
        except Exception as e:
            warning_msg = f"Could not get CSV file stats: {e}"
            log_message("warning", warning_msg, "external_content", "csv_loading")
            if log_file_handle:
                safe_log_write(log_file_handle, f"WARNING: {warning_msg}\n")
        
        external_content = []
        skipped_count = 0
        total_rows = 0
        
        try:
            with open(csv_path, "r", newline="", encoding="utf-8") as file:
                reader = csv.DictReader(file)
                
                fieldnames = reader.fieldnames
                headers_msg = f"CSV headers: {list(fieldnames) if fieldnames else 'None'}"
                log_message("info", headers_msg, "external_content", "csv_parsing")
                if log_file_handle:
                    safe_log_write(log_file_handle, f"Headers: {headers_msg}\n")
                    safe_log_write(log_file_handle, f"Processing rows...\n\n")
                
                for row_num, row in enumerate(reader, start=1):
                    total_rows += 1
                    
                    log_message("debug", f"Processing CSV row {row_num}: {dict(row)}", 
                               "external_content", "csv_parsing")
                    if log_file_handle:
                        safe_log_write(log_file_handle, f"Row {row_num}: {dict(row)}\n")
                    
                    content = ExternalContent(row, row_number=row_num)
                    
                    if content.is_valid():
                        external_content.append(content)
                        success_msg = f"Successfully loaded external content #{len(external_content)}: '{content.title}' from {content.source_domain}"
                        log_message("debug", success_msg, "external_content", "content_loading")
                        if log_file_handle:
                            safe_log_write(log_file_handle, f"  ✓ LOADED: {success_msg}\n")
                    else:
                        skipped_count += 1
                        error_msg = f"Skipped invalid external content at row {row_num}: missing required fields - Title: '{content.title}', URL: '{content.url}', Description: '{content.description}'"
                        log_message("warning", error_msg, "external_content", "content_loading")
                        if log_file_handle:
                            safe_log_write(log_file_handle, f"  ✗ SKIPPED: {error_msg}\n")
        
        except FileNotFoundError:
            error_msg = f"CSV file not found: {csv_path}"
            log_message("error", error_msg, "external_content", "csv_loading")
            if log_file_handle:
                safe_log_write(log_file_handle, f"FATAL ERROR: {error_msg}\n")
                safe_log_close(log_file_handle)
            return []
        except csv.Error as e:
            error_msg = f"CSV parsing error: {e}"
            log_message("error", error_msg, "external_content", "csv_loading")
            if log_file_handle:
                safe_log_write(log_file_handle, f"FATAL ERROR: {error_msg}\n")
                safe_log_close(log_file_handle)
            return []
        except UnicodeDecodeError as e:
            error_msg = f"CSV encoding error: {e}"
            log_message("error", error_msg, "external_content", "csv_loading")
            if log_file_handle:
                safe_log_write(log_file_handle, f"FATAL ERROR: {error_msg}\n")
                safe_log_close(log_file_handle)
            return []
        except Exception as e:
            error_msg = f"Unexpected error loading external content CSV: {e}"
            log_message("error", error_msg, "external_content", "csv_loading")
            if log_file_handle:
                safe_log_write(log_file_handle, f"FATAL ERROR: {error_msg}\n")
                safe_log_close(log_file_handle)
            if not external_content:
                log_message("warning", "No external content loaded, using fallback empty list", "external_content", "csv_loading")
            return external_content
        
        summary_msg = f"External content loading complete - Total rows: {total_rows}, Loaded: {len(external_content)}, Skipped: {skipped_count}"
        log_message("info", summary_msg, "external_content", "csv_loading")
        if log_file_handle:
            safe_log_write(log_file_handle, f"\n=== LOADING SUMMARY ===\n")
            safe_log_write(log_file_handle, f"{summary_msg}\n")
        
        if external_content:
            categories = {}
            content_types = {}
            domains = {}
            
            for content in external_content:
                cat = content.category or "uncategorized"
                categories[cat] = categories.get(cat, 0) + 1
                
                content_types[content.content_type] = content_types.get(content.content_type, 0) + 1
                
                domain = content.source_domain or "unknown"
                domains[domain] = domains.get(domain, 0) + 1
            
            categories_msg = f"Content breakdown - Categories: {dict(categories)}"
            types_msg = f"Content breakdown - Types: {dict(content_types)}"
            domains_msg = f"Content breakdown - Domains: {dict(domains)}"
            
            log_message("info", categories_msg, "external_content", "statistics")
            log_message("info", types_msg, "external_content", "statistics") 
            log_message("info", domains_msg, "external_content", "statistics")
            
            if log_file_handle:
                safe_log_write(log_file_handle, f"\n=== CONTENT STATISTICS ===\n")
                safe_log_write(log_file_handle, f"{categories_msg}\n")
                safe_log_write(log_file_handle, f"{types_msg}\n")
                safe_log_write(log_file_handle, f"{domains_msg}\n")
                
                safe_log_write(log_file_handle, f"\n=== LOADED ITEMS ===\n")
                for i, content in enumerate(external_content, 1):
                    item_summary = f"{i:2d}. '{content.title}' ({content.content_type}) - {content.category} - {content.source_domain}"
                    safe_log_write(log_file_handle, f"{item_summary}\n")
        
        if log_file_handle:
            safe_log_write(log_file_handle, f"\n=== SESSION COMPLETE ===\n")
            safe_log_write(log_file_handle, f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        
        if log_file_path:
            log_message("info", f"External content detailed log written to: {log_file_path}", 
                       "external_content", "csv_loading")
        
        if log_file_handle:
            safe_log_close(log_file_handle)
        
        
        self.external_content = external_content
        return external_content
    
    def get_by_category(self, category: str) -> List[ExternalContent]:
        """Get external content filtered by category."""
        log_message("debug", f"Filtering external content by category: '{category}'", 
                   "external_content", "filtering")
        
        filtered_content = [
            content for content in self.external_content 
            if content.category.lower() == category.lower()
        ]
        
        log_message("info", f"Found {len(filtered_content)} items for category '{category}'", 
                   "external_content", "filtering")
        
        return filtered_content
    
    def get_recent(self, limit: int = 5) -> List[ExternalContent]:
        """Get most recent external content."""
        log_message("debug", f"Getting {limit} most recent external content items", 
                   "external_content", "filtering")
        
        dated_content = [c for c in self.external_content if c.date]
        undated_content = [c for c in self.external_content if not c.date]
        
        log_message("debug", f"Content with dates: {len(dated_content)}, without dates: {len(undated_content)}", 
                   "external_content", "filtering")
        
        sorted_content = sorted(
            dated_content,
            key=lambda x: x.date,
            reverse=True
        )
        
        recent_content = sorted_content[:limit]
        
        log_message("info", f"Retrieved {len(recent_content)} recent external content items", 
                   "external_content", "filtering")
        
        return recent_content
    
    def get_statistics(self) -> Dict[str, any]:
        """Get detailed statistics about loaded external content."""
        log_message("debug", "Generating external content statistics", 
                   "external_content", "statistics")
        
        if not self.external_content:
            return {
                "total_items": 0,
                "categories": {},
                "content_types": {},
                "domains": {},
                "dated_items": 0,
                "undated_items": 0
            }
        
        stats = {
            "total_items": len(self.external_content),
            "categories": {},
            "content_types": {},
            "domains": {},
            "dated_items": 0,
            "undated_items": 0
        }
        
        for content in self.external_content:
            cat = content.category or "uncategorized"
            stats["categories"][cat] = stats["categories"].get(cat, 0) + 1
            
            stats["content_types"][content.content_type] = stats["content_types"].get(content.content_type, 0) + 1
            
            domain = content.source_domain or "unknown"
            stats["domains"][domain] = stats["domains"].get(domain, 0) + 1
            
            if content.date:
                stats["dated_items"] += 1
            else:
                stats["undated_items"] += 1
        
        log_message("info", f"Generated statistics for {stats['total_items']} external content items", 
                   "external_content", "statistics")
        
        return stats