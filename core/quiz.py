import os
from typing import Optional

from google import genai


class QuizGenerator:
    """
    Generates 10-question multiple-choice quizzes using PDF content/chunks with LLM aid.
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY environment variable must be set.")

        self.client = genai.Client(api_key=self.api_key)
        self.model_name = "gemini-2.5-flash"

    def generate(self, topic: str, full_text: Optional[str] = None) -> str:
        """
        Generate quiz using topic and optionally PDF content/chunks.
        If full_text is provided, uses it as context for grounded questions.
        """
        if full_text:
            # Use PDF content to generate grounded quiz questions
            # Truncate to avoid token limits (keep first 50k chars)
            content = full_text[:50000] if len(full_text) > 50000 else full_text
            prompt = f"""Create a 10-question multiple-choice quiz on the topic: {topic}

Use the following course content as the basis for all questions. All questions must be answerable using only this content.

Course Content:
{content}

Rules:
- Generate exactly 10 questions labeled Q1...Q10.
- Each question must have 4 options labeled A) through D).
- Include a "Correct: X" line for each question indicating the correct answer (A, B, C, or D).
- Base all questions on the provided content - questions should test understanding of the material.
- Keep questions concise and factual.
- Ensure questions cover different aspects of the topic from the content.

Format:
Q1: [Question text]
A) [Option A]
B) [Option B]
C) [Option C]
D) [Option D]
Correct: [A/B/C/D]
---
Q2: ...
"""
        else:
            # Fallback to topic-only quiz
            prompt = f"""
Create a 10-question multiple-choice quiz on: {topic}

Rules:
- Use exactly 10 questions labeled Q1...Q10.
- Each question must have options A) through D).
- Include a "Correct: X" line for each question.
- Keep questions concise and factual.
"""

        response = self.client.models.generate_content(
            model=self.model_name,
            contents=[prompt],
        )
        return response.text or "Quiz generation failed."
