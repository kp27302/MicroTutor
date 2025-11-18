import os
import time
import uuid
from pathlib import Path
from typing import Dict, Optional

from google import genai


class FileSearchManager:
    """
    Handles Gemini File Search store creation and PDF uploads.
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY environment variable must be set.")

        self.client = genai.Client(api_key=self.api_key)
        self.records: Dict[str, Dict] = {}

    def index_pdf(self, pdf_path: str, display_name: Optional[str] = None) -> Dict:
        """
        Create a new File Search store and upload the provided PDF.

        Returns metadata with store_id, document info, and original filename.
        """
        pdf_path = Path(pdf_path)
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF not found: {pdf_path}")

        friendly_name = display_name or pdf_path.stem
        try:
            store = self.client.file_search_stores.create(
                config={"display_name": f"{friendly_name}-{uuid.uuid4().hex[:6]}"}
            )
            store_id = store.name
            if not store_id:
                raise ValueError("Failed to create file search store: no store ID returned")
        except Exception as e:
            raise RuntimeError(f"Failed to create file search store: {str(e)}")

        try:
            operation = self.client.file_search_stores.upload_to_file_search_store(
                file=str(pdf_path),
                file_search_store_name=store_id,
                config={"display_name": pdf_path.name},
            )
        except Exception as e:
            raise RuntimeError(f"Failed to upload PDF to Gemini File Search: {str(e)}")

        # Wait until import is complete (per official API docs)
        max_wait_time = 300  # 5 minutes max
        elapsed_time = 0
        poll_count = 0
        
        while not getattr(operation, 'done', False):
            time.sleep(2)
            elapsed_time += 2
            poll_count += 1
            
            if elapsed_time > max_wait_time:
                raise TimeoutError(f"PDF indexing timed out after {max_wait_time} seconds (polled {poll_count} times)")
            
            try:
                operation = self.client.operations.get(operation)
            except Exception as e:
                raise RuntimeError(f"Failed to check operation status: {str(e)}")
            
            # Check for errors in the operation
            if hasattr(operation, 'error') and operation.error:
                error_msg = str(operation.error)
                raise RuntimeError(f"PDF indexing failed: {error_msg}")
            
            # Also check if operation has a name (should always have one)
            if not hasattr(operation, 'name') or not operation.name:
                raise RuntimeError("Operation object missing required 'name' attribute")

        document_metadata = {}
        if getattr(operation, "response", None):
            response = operation.response
            document_metadata = {
                "name": getattr(response, "name", None),
                "size_bytes": getattr(response, "size_bytes", None),
                "mime_type": getattr(response, "mime_type", None),
            }

        record = {
            "store_id": store_id,
            "filename": pdf_path.name,
            "document": document_metadata,
            "path": str(pdf_path),
        }
        self.records[store_id] = record
        return record

