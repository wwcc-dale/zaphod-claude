#!/usr/bin/env python3
"""
# Zaphod
# Copyright (c) 2026 Dale Chapman
# Licensed under the MIT License. See LICENSE in the project root.

html_to_markdown.py

Convert Canvas HTML back to clean markdown format for import operations.

This module handles:
1. Converting Canvas HTML to markdown using html2text
2. Extracting Canvas content (removing wrapper divs)
3. Stripping template headers/footers to recover original content
4. Extracting media references (images, videos, etc.)
5. Cleaning up Canvas-specific HTML artifacts

The converter is designed to reverse the export process, recovering the original
markdown content that was published to Canvas.

Usage:
    from html_to_markdown import convert_canvas_html_to_markdown

    markdown = convert_canvas_html_to_markdown(
        html_content,
        strip_template=True,
        course_root=Path("/path/to/course")
    )

Command-line usage:
    python html_to_markdown.py input.html output.md
    python html_to_markdown.py input.html output.md --strip-template
    python html_to_markdown.py --stdin < input.html
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from urllib.parse import urlparse, unquote

import html2text
from bs4 import BeautifulSoup, Tag

from errors import ZaphodError


# ============================================================================
# Custom Exceptions
# ============================================================================

class HTMLConversionError(ZaphodError):
    """Error during HTML to Markdown conversion"""
    pass


# ============================================================================
# HTML to Markdown Conversion
# ============================================================================

def configure_html2text() -> html2text.HTML2Text:
    """
    Configure html2text converter with Zaphod-friendly settings.

    Returns:
        Configured HTML2Text instance
    """
    h = html2text.HTML2Text()

    # Basic options
    h.body_width = 0  # Don't wrap lines
    h.unicode_snob = True  # Use unicode instead of ASCII
    h.ignore_links = False  # Keep links
    h.ignore_images = False  # Keep images
    h.ignore_emphasis = False  # Keep bold/italic

    # Formatting options
    h.skip_internal_links = False
    h.inline_links = True  # Use inline [text](url) format
    h.protect_links = True  # Don't modify URLs
    h.wrap_links = False
    h.mark_code = True  # Mark code blocks properly

    # List and table handling
    h.ul_item_mark = '-'  # Use - for unordered lists (standard markdown)
    h.emphasis_mark = '*'  # Use * for emphasis
    h.strong_mark = '**'  # Use ** for strong

    # Don't escape special characters in markdown
    h.escape_snob = True

    return h


def extract_canvas_content(html: str) -> str:
    """
    Extract the main content from Canvas HTML wrapper divs.

    Canvas often wraps page content in divs with specific classes or IDs.
    This function attempts to find and extract just the main content area,
    removing Canvas chrome and navigation elements.

    Args:
        html: Raw Canvas HTML

    Returns:
        Cleaned HTML with Canvas wrappers removed

    Example:
        >>> html = '<div class="user_content"><p>Hello</p></div>'
        >>> extract_canvas_content(html)
        '<p>Hello</p>'
    """
    if not html or not html.strip():
        return ""

    soup = BeautifulSoup(html, 'html.parser')

    # Canvas commonly uses these wrapper classes/IDs
    # Priority order: most specific to least specific
    content_selectors = [
        '.user_content',  # Most common Canvas content wrapper
        '.show-content',  # Sometimes used for page content
        '#wiki_page_show',  # Wiki page wrapper
        '.page-content',  # Generic page content
        'article',  # Semantic HTML content
        '.content',  # Generic content class
    ]

    # Try each selector
    for selector in content_selectors:
        content = soup.select_one(selector)
        if content:
            return str(content)

    # If no wrapper found, check if we have a body tag
    body = soup.find('body')
    if body:
        return str(body)

    # Fall back to original HTML if no wrappers found
    # This handles cases where HTML is already clean
    return html


def strip_template_content(
    html: str,
    course_root: Optional[Path] = None,
    template_name: str = "default"
) -> str:
    """
    Attempt to strip template header/footer from Canvas HTML.

    This is a best-effort operation that tries to identify and remove
    template content that was added during publishing. It works by:
    1. Loading the template files used during export
    2. Converting them to HTML
    3. Finding and removing matching content from the Canvas HTML

    Note: This may not be perfect due to Canvas HTML processing,
    but should handle most common cases.

    Args:
        html: Canvas HTML content
        course_root: Path to course root (to load templates)
        template_name: Name of template set that was used

    Returns:
        HTML with template content removed (best effort)

    Raises:
        HTMLConversionError: If template loading fails
    """
    if not course_root or not course_root.exists():
        # Can't strip templates without course root
        return html

    try:
        # Import here to avoid circular dependency
        from canvas_publish import load_template_files
        import markdown

        # Load template files
        templates = load_template_files(course_root, template_name)

        if not any(templates.values()):
            # No templates to strip
            return html

        soup = BeautifulSoup(html, 'html.parser')

        # Convert markdown templates to HTML for matching
        header_md_html = ""
        footer_md_html = ""

        if templates['header_md']:
            header_md_html = markdown.markdown(
                templates['header_md'],
                extensions=['extra', 'codehilite', 'tables', 'fenced_code']
            )

        if templates['footer_md']:
            footer_md_html = markdown.markdown(
                templates['footer_md'],
                extensions=['extra', 'codehilite', 'tables', 'fenced_code']
            )

        # Try to find and remove header content
        # Start with HTML headers, then markdown-converted headers
        for header_html in [templates['header_html'], header_md_html]:
            if header_html and header_html.strip():
                header_soup = BeautifulSoup(header_html, 'html.parser')
                # Try to find matching content in the main HTML
                # This is approximate due to Canvas processing
                if _find_and_remove_similar_content(soup, header_soup):
                    break

        # Try to find and remove footer content
        for footer_html in [footer_md_html, templates['footer_html']]:
            if footer_html and footer_html.strip():
                footer_soup = BeautifulSoup(footer_html, 'html.parser')
                if _find_and_remove_similar_content(soup, footer_soup, from_end=True):
                    break

        return str(soup)

    except Exception as e:
        # Template stripping failed - return original HTML
        # This is non-fatal as we can still convert to markdown
        print(f"Warning: Could not strip templates: {e}", file=sys.stderr)
        return html


def _find_and_remove_similar_content(
    main_soup: BeautifulSoup,
    template_soup: BeautifulSoup,
    from_end: bool = False
) -> bool:
    """
    Find and remove content similar to template in main HTML.

    This is a heuristic match that looks for similar text content,
    since Canvas may modify the exact HTML structure.

    Args:
        main_soup: Main content soup
        template_soup: Template content soup
        from_end: If True, search from end (for footers)

    Returns:
        True if content was found and removed
    """
    # Get text content from template (normalized)
    template_text = template_soup.get_text().strip()
    if not template_text:
        return False

    # Normalize: remove extra whitespace, lowercase for comparison
    template_normalized = ' '.join(template_text.split()).lower()

    # Find all top-level elements in main content
    elements = list(main_soup.children)
    if from_end:
        elements = list(reversed(elements))

    # Look for matching content
    for elem in elements:
        if not isinstance(elem, Tag):
            continue

        elem_text = elem.get_text().strip()
        elem_normalized = ' '.join(elem_text.split()).lower()

        # Check for similarity (fuzzy match)
        if template_normalized in elem_normalized or elem_normalized in template_normalized:
            # Found matching content - remove it
            elem.decompose()
            return True

    return False


def extract_media_references(html: str) -> List[Dict[str, str]]:
    """
    Extract media file references from Canvas HTML.

    Finds images, videos, audio, and other embedded media, extracting:
    - File URLs
    - File names
    - Alt text / captions
    - Media type

    Args:
        html: Canvas HTML content

    Returns:
        List of media reference dicts with keys:
        - type: 'image', 'video', 'audio', 'embed', 'link'
        - url: Full URL to the media
        - filename: Extracted filename
        - alt_text: Alt text or caption (if available)
        - canvas_file_id: Canvas file ID (if identifiable)

    Example:
        >>> html = '<img src="/courses/123/files/456/download?..." alt="diagram">'
        >>> refs = extract_media_references(html)
        >>> refs[0]
        {'type': 'image', 'url': '...', 'filename': 'diagram.png',
         'alt_text': 'diagram', 'canvas_file_id': '456'}
    """
    if not html or not html.strip():
        return []

    soup = BeautifulSoup(html, 'html.parser')
    media_refs = []

    # Extract images
    for img in soup.find_all('img'):
        src = img.get('src', '')
        if src:
            media_refs.append({
                'type': 'image',
                'url': src,
                'filename': _extract_filename_from_url(src),
                'alt_text': img.get('alt', ''),
                'canvas_file_id': _extract_canvas_file_id(src)
            })

    # Extract videos
    for video in soup.find_all('video'):
        src = video.get('src', '')
        if src:
            media_refs.append({
                'type': 'video',
                'url': src,
                'filename': _extract_filename_from_url(src),
                'alt_text': video.get('title', ''),
                'canvas_file_id': _extract_canvas_file_id(src)
            })

        # Check for source tags within video
        for source in video.find_all('source'):
            src = source.get('src', '')
            if src:
                media_refs.append({
                    'type': 'video',
                    'url': src,
                    'filename': _extract_filename_from_url(src),
                    'alt_text': video.get('title', ''),
                    'canvas_file_id': _extract_canvas_file_id(src)
                })

    # Extract audio
    for audio in soup.find_all('audio'):
        src = audio.get('src', '')
        if src:
            media_refs.append({
                'type': 'audio',
                'url': src,
                'filename': _extract_filename_from_url(src),
                'alt_text': audio.get('title', ''),
                'canvas_file_id': _extract_canvas_file_id(src)
            })

        # Check for source tags within audio
        for source in audio.find_all('source'):
            src = source.get('src', '')
            if src:
                media_refs.append({
                    'type': 'audio',
                    'url': src,
                    'filename': _extract_filename_from_url(src),
                    'alt_text': audio.get('title', ''),
                    'canvas_file_id': _extract_canvas_file_id(src)
                })

    # Extract iframes (embedded content)
    for iframe in soup.find_all('iframe'):
        src = iframe.get('src', '')
        if src:
            media_refs.append({
                'type': 'embed',
                'url': src,
                'filename': _extract_filename_from_url(src),
                'alt_text': iframe.get('title', ''),
                'canvas_file_id': _extract_canvas_file_id(src)
            })

    # Extract file links (anchors pointing to files)
    for link in soup.find_all('a'):
        href = link.get('href', '')
        if href and _looks_like_file_url(href):
            media_refs.append({
                'type': 'link',
                'url': href,
                'filename': _extract_filename_from_url(href),
                'alt_text': link.get_text().strip(),
                'canvas_file_id': _extract_canvas_file_id(href)
            })

    return media_refs


def _extract_filename_from_url(url: str) -> str:
    """
    Extract filename from a URL.

    Handles various URL formats including:
    - Direct file URLs: /path/to/file.jpg
    - Canvas file URLs: /courses/123/files/456/download?...
    - Query parameters: ?file=something.pdf

    Args:
        url: URL to extract filename from

    Returns:
        Filename (may be empty if not extractable)
    """
    if not url:
        return ""

    try:
        parsed = urlparse(url)
        path = unquote(parsed.path)

        # Try to get filename from path
        if path:
            filename = Path(path).name
            if filename and '.' in filename:
                return filename

        # Try to get from query parameters
        if parsed.query:
            # Look for common query params that contain filenames
            query_parts = parsed.query.split('&')
            for part in query_parts:
                if '=' in part:
                    key, value = part.split('=', 1)
                    if key.lower() in ('file', 'filename', 'download'):
                        return unquote(value)

        # Fall back to last path component
        if path:
            return Path(path).name

        return ""

    except Exception:
        return ""


def _extract_canvas_file_id(url: str) -> str:
    """
    Extract Canvas file ID from a URL.

    Canvas file URLs typically look like:
    /courses/123/files/456/download
    /files/456/download

    Args:
        url: URL to extract file ID from

    Returns:
        File ID (as string) or empty string if not found
    """
    if not url:
        return ""

    # Pattern: /files/{id}/
    match = re.search(r'/files/(\d+)(?:/|$|\?)', url)
    if match:
        return match.group(1)

    return ""


def _looks_like_file_url(url: str) -> bool:
    """
    Check if URL looks like it points to a file.

    Args:
        url: URL to check

    Returns:
        True if URL appears to point to a downloadable file
    """
    if not url:
        return False

    # Check for common file patterns
    file_indicators = [
        '/files/',
        '/download',
        'download?',
        '.pdf',
        '.doc',
        '.docx',
        '.xls',
        '.xlsx',
        '.ppt',
        '.pptx',
        '.zip',
        '.tar',
        '.gz',
    ]

    url_lower = url.lower()
    return any(indicator in url_lower for indicator in file_indicators)


def convert_html_to_markdown(
    html: str,
    strip_canvas_wrappers: bool = True
) -> str:
    """
    Convert HTML to markdown format.

    Basic conversion using html2text with Zaphod-friendly settings.

    Args:
        html: HTML content to convert
        strip_canvas_wrappers: If True, remove Canvas wrapper divs first

    Returns:
        Markdown formatted text

    Raises:
        HTMLConversionError: If conversion fails
    """
    if not html or not html.strip():
        return ""

    try:
        # Strip Canvas wrappers if requested
        if strip_canvas_wrappers:
            html = extract_canvas_content(html)

        # Configure and run converter
        converter = configure_html2text()
        markdown = converter.handle(html)

        # Clean up output
        markdown = _cleanup_markdown(markdown)

        return markdown

    except Exception as e:
        raise HTMLConversionError(
            message="Failed to convert HTML to markdown",
            suggestion="Check that HTML is well-formed and contains valid content",
            context={
                "html_length": len(html),
                "html_preview": html[:200] + "..." if len(html) > 200 else html
            },
            cause=e
        )


def _cleanup_markdown(markdown: str) -> str:
    """
    Clean up markdown output from html2text.

    Removes common artifacts and normalizes formatting.

    Args:
        markdown: Raw markdown from html2text

    Returns:
        Cleaned markdown
    """
    if not markdown:
        return ""

    # Remove excessive blank lines (more than 2 consecutive)
    markdown = re.sub(r'\n{3,}', '\n\n', markdown)

    # Remove leading/trailing whitespace
    markdown = markdown.strip()

    # Normalize line endings
    markdown = markdown.replace('\r\n', '\n')

    # Remove trailing whitespace from lines
    lines = markdown.split('\n')
    lines = [line.rstrip() for line in lines]
    markdown = '\n'.join(lines)

    return markdown


def convert_canvas_html_to_markdown(
    html: str,
    course_root: Optional[Path] = None,
    template_name: str = "default",
    strip_template: bool = True,
    strip_canvas_wrappers: bool = True,
    extract_media: bool = False
) -> Tuple[str, List[Dict[str, str]]]:
    """
    Complete conversion pipeline: Canvas HTML → clean markdown.

    This is the main entry point for converting Canvas HTML back to
    markdown format. It handles:
    1. Extracting Canvas content wrappers
    2. Stripping template headers/footers (optional)
    3. Converting HTML to markdown
    4. Extracting media references (optional)

    Args:
        html: Canvas HTML content
        course_root: Path to course root (needed for template stripping)
        template_name: Name of template set to strip (default: "default")
        strip_template: If True, attempt to remove template content
        strip_canvas_wrappers: If True, remove Canvas wrapper divs
        extract_media: If True, also return media references

    Returns:
        Tuple of (markdown, media_refs)
        - markdown: Converted markdown text
        - media_refs: List of media reference dicts (empty if extract_media=False)

    Raises:
        HTMLConversionError: If conversion fails

    Example:
        >>> html = '<div class="user_content"><h1>Hello</h1></div>'
        >>> md, refs = convert_canvas_html_to_markdown(html)
        >>> print(md)
        # Hello
    """
    if not html or not html.strip():
        return "", []

    try:
        # Step 1: Extract Canvas content wrappers
        if strip_canvas_wrappers:
            html = extract_canvas_content(html)

        # Step 2: Strip templates if requested and possible
        if strip_template and course_root:
            html = strip_template_content(html, course_root, template_name)

        # Step 3: Extract media references if requested
        media_refs = []
        if extract_media:
            media_refs = extract_media_references(html)

        # Step 4: Convert to markdown
        markdown = convert_html_to_markdown(html, strip_canvas_wrappers=False)

        return markdown, media_refs

    except HTMLConversionError:
        raise
    except Exception as e:
        raise HTMLConversionError(
            message="Failed to complete HTML to markdown conversion",
            suggestion="Check that all inputs are valid and course_root exists (if provided)",
            context={
                "html_length": len(html),
                "course_root": str(course_root) if course_root else None,
                "template_name": template_name
            },
            cause=e
        )


# ============================================================================
# CLI Interface
# ============================================================================

def main():
    """Command-line interface for HTML to Markdown conversion."""
    parser = argparse.ArgumentParser(
        description="Convert Canvas HTML to Markdown",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Convert a file
  python html_to_markdown.py input.html output.md

  # Convert from stdin
  python html_to_markdown.py --stdin < input.html

  # Strip templates during conversion
  python html_to_markdown.py input.html output.md --strip-template --course-root /path/to/course

  # Extract media references
  python html_to_markdown.py input.html output.md --extract-media
        """
    )

    parser.add_argument(
        'input',
        nargs='?',
        help='Input HTML file (or use --stdin)'
    )
    parser.add_argument(
        'output',
        nargs='?',
        help='Output markdown file (or stdout if omitted)'
    )
    parser.add_argument(
        '--stdin',
        action='store_true',
        help='Read HTML from stdin'
    )
    parser.add_argument(
        '--strip-template',
        action='store_true',
        help='Attempt to strip template headers/footers'
    )
    parser.add_argument(
        '--course-root',
        type=Path,
        help='Path to course root (required for template stripping)'
    )
    parser.add_argument(
        '--template-name',
        default='default',
        help='Template set name to strip (default: default)'
    )
    parser.add_argument(
        '--extract-media',
        action='store_true',
        help='Extract and print media references'
    )
    parser.add_argument(
        '--no-strip-wrappers',
        action='store_true',
        help='Don\'t strip Canvas wrapper divs'
    )

    args = parser.parse_args()

    # Read input
    if args.stdin:
        html = sys.stdin.read()
    elif args.input:
        try:
            with open(args.input, 'r', encoding='utf-8') as f:
                html = f.read()
        except Exception as e:
            print(f"Error reading input file: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        parser.print_help()
        sys.exit(1)

    # Validate template stripping requirements
    if args.strip_template and not args.course_root:
        print("Error: --course-root required when using --strip-template", file=sys.stderr)
        sys.exit(1)

    # Convert
    try:
        markdown, media_refs = convert_canvas_html_to_markdown(
            html,
            course_root=args.course_root,
            template_name=args.template_name,
            strip_template=args.strip_template,
            strip_canvas_wrappers=not args.no_strip_wrappers,
            extract_media=args.extract_media
        )

        # Write output
        if args.output:
            with open(args.output, 'w', encoding='utf-8') as f:
                f.write(markdown)
            print(f"Wrote markdown to: {args.output}")
        else:
            print(markdown)

        # Print media references if requested
        if args.extract_media and media_refs:
            print("\nMedia References:", file=sys.stderr)
            for i, ref in enumerate(media_refs, 1):
                print(f"\n{i}. {ref['type'].upper()}", file=sys.stderr)
                print(f"   URL: {ref['url']}", file=sys.stderr)
                print(f"   Filename: {ref['filename']}", file=sys.stderr)
                if ref['alt_text']:
                    print(f"   Alt Text: {ref['alt_text']}", file=sys.stderr)
                if ref['canvas_file_id']:
                    print(f"   Canvas File ID: {ref['canvas_file_id']}", file=sys.stderr)

    except HTMLConversionError as e:
        print(f"\n{e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
