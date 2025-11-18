from pathlib import Path
from typing import Dict, Tuple, Optional

import fitz


PageMap = Dict[Tuple[int, int], int]


def build_page_map(pdf_path: str) -> Tuple[PageMap, str]:
    """
    Extract page-level character ranges and concatenate full text.

    Returns:
        page_map: {(start_idx, end_idx): page_number}
        full_text: entire PDF text for scheduling
    """
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    document = fitz.open(pdf_path)
    page_map: PageMap = {}
    full_text_parts = []
    cursor = 0

    for page_number, page in enumerate(document, start=1):
        text = page.get_text()
        start = cursor
        end = start + len(text)
        page_map[(start, end)] = page_number
        cursor = end
        full_text_parts.append(text)

    return page_map, "".join(full_text_parts)


def map_span_to_page(page_map: PageMap, start: Optional[int], end: Optional[int]) -> Optional[int]:
    """
    Find the page number that contains the provided character span.
    Handles cases where citation spans overlap page boundaries.
    """
    if start is None or end is None:
        return None

    # First try exact match (citation fully contained in a page)
    for (span_start, span_end), page in page_map.items():
        if span_start <= start and end <= span_end:
            return page
    
    # If no exact match, find the page with the most overlap
    best_page = None
    max_overlap = 0
    
    for (span_start, span_end), page in page_map.items():
        # Calculate overlap
        overlap_start = max(start, span_start)
        overlap_end = min(end, span_end)
        overlap = max(0, overlap_end - overlap_start)
        
        if overlap > max_overlap:
            max_overlap = overlap
            best_page = page
    
    # If there's significant overlap, return that page
    if best_page and max_overlap > (end - start) * 0.3:  # At least 30% overlap
        return best_page
    
    # Fallback: return the page that contains the start position
    for (span_start, span_end), page in page_map.items():
        if span_start <= start <= span_end:
            return page
    
    return None

