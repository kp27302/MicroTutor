import os
import json
from typing import List, Dict, Optional

from google import genai


class ScheduleGenerator:
    """
    Generates intelligent study schedules by dividing content into subtopics with summaries.
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY environment variable must be set.")
        self.client = genai.Client(api_key=self.api_key)
        self.model_name = "gemini-2.5-flash"

    def build_schedule(self, full_text: str, days: int) -> List[Dict]:
        """
        Intelligently divide content into subtopics using LLM.
        """
        if not full_text:
            return []
        days = max(1, min(days, 30))  # Limit to 30 days

        # Truncate text if too long (keep first 100k chars for context)
        text_for_llm = full_text[:100000] if len(full_text) > 100000 else full_text

        prompt = f"""Analyze the following course content and divide it into exactly {days} meaningful study sessions.

Each session should:
1. Cover related subtopics that form a cohesive learning unit
2. Have a clear, descriptive title (not just "Day X")
3. Include a concise summary (2-3 sentences) of what will be learned

Output format (JSON array):
[
  {{
    "day": 1,
    "title": "Descriptive title of the learning session",
    "summary": "2-3 sentence summary of what students will learn",
    "estimated_pages": "X-Y pages or sections covered"
  }},
  ...
]

Content to analyze:
{text_for_llm[:80000]}

Generate exactly {days} sessions with intelligent topic division:
"""

        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=[prompt],
            )
            
            text = response.text or ""
            # Try to extract JSON from response
            json_start = text.find('[')
            json_end = text.rfind(']') + 1
            if json_start >= 0 and json_end > json_start:
                json_str = text[json_start:json_end]
                schedule = json.loads(json_str)
                
                # Validate and format
                formatted_schedule = []
                for i, session in enumerate(schedule[:days], start=1):
                    formatted_schedule.append({
                        "day": i,
                        "title": session.get("title", f"Day {i} Study Session"),
                        "summary": session.get("summary", "Study session"),
                        "estimated_pages": session.get("estimated_pages", ""),
                    })
                return formatted_schedule
        except Exception as e:
            print(f"LLM schedule generation failed: {e}, falling back to simple division")
        
        # Fallback: Simple division if LLM fails
        return self._simple_division(full_text, days)

    def _simple_division(self, full_text: str, days: int) -> List[Dict]:
        """Fallback: Simple word-based division."""
        words = full_text.split()
        total_words = len(words)
        chunk_size = max(1, total_words // days)

        schedule = []
        for day in range(days):
            start = day * chunk_size
            end = (day + 1) * chunk_size if day < days - 1 else total_words
            slice_words = words[start:end]
            summary = " ".join(slice_words[:100])
            schedule.append({
                "day": day + 1,
                "title": f"Day {day + 1} Study Session",
                "summary": summary + "..." if len(slice_words) > 100 else summary,
                "key_concepts": [],
                "estimated_pages": f"Approx. {len(slice_words)} words",
            })
        return schedule


# Backward compatibility
def build_schedule(full_text: str, days: int) -> List[Dict]:
    generator = ScheduleGenerator()
    return generator.build_schedule(full_text, days)
