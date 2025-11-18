import os
from typing import Any, Dict, List, Optional

try:
    from mem0 import Memory as Mem0Memory
except ImportError:  # pragma: no cover - optional dependency
    Mem0Memory = None


class MemoryManager:
    """
    Thin wrapper around mem0 with graceful fallback to in-memory list.
    """

    def __init__(self, api_key: Optional[str] = None, user_id: str = "microtutor_user"):
        self.api_key = api_key or os.getenv("MEM0_API_KEY")
        openai_key = os.getenv("OPENAI_API_KEY")
        self.enabled = bool(self.api_key and openai_key and Mem0Memory)
        self.user_id = user_id
        # Always initialize fallback for graceful degradation
        self.fallback: List[Dict[str, Any]] = []
        if self.enabled:
            try:
                self.client = Mem0Memory()
            except Exception as e:
                print(f"Warning: Failed to initialize mem0: {e}, using fallback storage")
                self.client = None
                self.enabled = False
        else:
            self.client = None

    def add(self, content: str, metadata: Optional[Dict[str, Any]] = None):
        # Always add to fallback for easy retrieval
        metadata_with_user = metadata or {}
        metadata_with_user["user_id"] = self.user_id
        self.fallback.append({"content": content, "metadata": metadata_with_user})
        
        if self.client:
            # mem0 requires user_id, agent_id, or run_id
            data = {
                "content": content,
                "user_id": self.user_id,
                "metadata": metadata or {}
            }
            try:
                self.client.add(data)
            except Exception as e:
                # If mem0 fails, we already have it in fallback
                print(f"Warning: mem0.add() failed: {e}, using fallback storage")

    def search(self, query: str, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        if self.client:
            try:
                # mem0 search may require user_id
                search_params = {"query": query}
                if user_id:
                    search_params["user_id"] = user_id
                return self.client.search(**search_params)
            except Exception as e:
                print(f"Warning: mem0.search() failed: {e}, using fallback search")
                return [
                    entry for entry in self.fallback 
                    if query.lower() in entry["content"].lower()
                ]
        return [
            entry for entry in self.fallback if query.lower() in entry["content"].lower()
        ]

    def dump(self) -> List[Dict[str, Any]]:
        # Always use fallback for dump since we maintain it for all records
        # mem0's search is for semantic queries, but dump needs all records reliably
        return self.fallback.copy()

