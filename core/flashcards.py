import os
from typing import List, Dict, Tuple, Optional

from google import genai


class FlashcardGenerator:
    """
    Generates deterministic flashcards and provides flip helpers.
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY environment variable must be set.")

        self.client = genai.Client(api_key=self.api_key)
        self.model_name = "gemini-2.5-flash"

    def generate(self, topic: str) -> List[Dict[str, str]]:
        prompt = f"""
Create exactly 5 concise flashcards about the topic below.

Format strictly as:
Q: question text
A: answer text
---

Topic: {topic}
"""
        response = self.client.models.generate_content(
            model=self.model_name,
            contents=[prompt],
        )
        return parse_flashcards(response.text or "")


def parse_flashcards(raw: str) -> List[Dict[str, str]]:
    cards: List[Dict[str, str]] = []
    for block in raw.split("Q:"):
        block = block.strip()
        if not block or "A:" not in block:
            continue
        question, answer = block.split("A:", 1)
        cards.append({"q": question.strip(), "a": answer.strip().split("---")[0].strip()})
    return cards[:5]


def start_flip(cards: List[Dict[str, str]]) -> Tuple[str, int, bool]:
    if not cards:
        return "No flashcards available.", 0, False
    return cards[0]["q"], 0, False


def flip_action(cards: List[Dict[str, str]], index: int, show_answer: bool, action: str) -> Tuple[str, int, bool]:
    if not cards:
        return "No flashcards available.", index, show_answer

    if action == "next":
        index = min(index + 1, len(cards) - 1)
        show_answer = False
    elif action == "prev":
        index = max(index - 1, 0)
        show_answer = False
    elif action == "flip":
        show_answer = not show_answer

    content = cards[index]["a"] if show_answer else cards[index]["q"]
    return content, index, show_answer

