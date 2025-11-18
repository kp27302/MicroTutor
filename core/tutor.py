import os
from typing import Dict, Optional

from google import genai
from google.genai import types

from core.page_map import PageMap, map_span_to_page


class TutorAssistant:
    """
    Handles Gemini RAG responses with File Search citations mapped to PDF pages.
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY environment variable must be set.")

        self.client = genai.Client(api_key=self.api_key)
        self.model_name = "gemini-2.5-flash"

    def answer(
        self,
        question: str,
        store_id: str,
        page_map: PageMap,
        filename: str,
    ) -> Dict:
        """
        Query Gemini File Search and return answer text plus PDF page citations.
        """
        if not store_id:
            raise ValueError("store_id is required for tutor chat.")

        tool = types.Tool(
            file_search=types.FileSearch(
                file_search_store_names=[store_id]
            )
        )

        response = self.client.models.generate_content(
            model=self.model_name,
            contents=[question],
            config=types.GenerateContentConfig(
                tools=[tool],
                max_output_tokens=1024,
            ),
        )

        answer_text = response.text or ""
        citation_lines = []
        unique_pages = set()  # Track unique pages to avoid duplicates

        # Extract citations from response candidates
        if response.candidates:
            for candidate in response.candidates:
                metadata = getattr(candidate, "citation_metadata", None)
                if not metadata:
                    continue
                
                citations = getattr(metadata, "citations", [])
                if not citations:
                    # Try alternative citation structure
                    citations = getattr(metadata, "citation", [])
                    if not isinstance(citations, list):
                        citations = [citations] if citations else []
                
                for citation in citations:
                    # Try multiple ways to get start_index and end_index
                    start_idx = None
                    end_idx = None
                    
                    if hasattr(citation, "start_index"):
                        start_idx = citation.start_index
                    elif hasattr(citation, "start"):
                        start_idx = citation.start
                    
                    if hasattr(citation, "end_index"):
                        end_idx = citation.end_index
                    elif hasattr(citation, "end"):
                        end_idx = citation.end
                    
                    if start_idx is not None and end_idx is not None:
                        page = map_span_to_page(page_map, start_idx, end_idx)
                        if page and page not in unique_pages:
                            unique_pages.add(page)
                            citation_lines.append(f"{filename} — Page {page}")
        
        # Always add citations section, even if empty
        if citation_lines:
            # Sort pages numerically
            citation_lines.sort(key=lambda x: int(x.split("Page ")[1]) if "Page " in x else 0)
            answer_text = f"{answer_text}\n\n---\n📄 Citations:\n" + "\n".join(
                f"- {line}" for line in citation_lines
            )
        else:
            # If no citations found, add a note
            answer_text = f"{answer_text}\n\n---\n📄 Citations:\n- No specific page citations found. This answer is based on the uploaded document content."

        return {"answer": answer_text, "citations": citation_lines}

