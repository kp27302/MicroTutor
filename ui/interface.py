import json
import re
from pathlib import Path
from typing import List, Tuple, Dict, Optional

import gradio as gr

from core.file_search import FileSearchManager
from core.page_map import build_page_map
from core.tutor import TutorAssistant
from core.flashcards import (
    FlashcardGenerator,
    start_flip,
    flip_action,
)
from core.quiz import QuizGenerator
from core.schedule import ScheduleGenerator
from core.memory import MemoryManager


file_manager = FileSearchManager()
tutor = TutorAssistant()
flashcard_gen = FlashcardGenerator()
quiz_gen = QuizGenerator()
schedule_gen = ScheduleGenerator()
memory = MemoryManager()

UPLOAD_REGISTRY = {}


def _option_list() -> List[str]:
    return [
        f"{data['filename']} | {store_id}"
        for store_id, data in UPLOAD_REGISTRY.items()
    ]


def _parse_selection(selection: str) -> str:
    if not selection:
        return ""
    return selection.split("|")[-1].strip()


def upload_pdfs(files: List[str]) -> Tuple[str, dict]:
    if not files:
        return "No files uploaded.", gr.update(choices=[], value=None)

    logs = []
    for file_path in files:
        try:
            pdf_path = Path(file_path)
            if not pdf_path.exists():
                logs.append(f"❌ File not found: {pdf_path.name}")
                continue
            
            if not pdf_path.suffix.lower() == '.pdf':
                logs.append(f"❌ Skipping non-PDF file: {pdf_path.name}")
                continue
            
            logs.append(f"⏳ Processing {pdf_path.name}...")
            
            # Extract page map first
            try:
                page_map, full_text = build_page_map(str(pdf_path))
            except Exception as e:
                logs.append(f"❌ Failed to extract text from {pdf_path.name}: {str(e)}")
                continue
            
            # Index the PDF
            try:
                record = file_manager.index_pdf(str(pdf_path))
                store_id = record["store_id"]
                UPLOAD_REGISTRY[store_id] = {
                    "filename": record["filename"],
                    "page_map": page_map,
                    "full_text": full_text,
                }
                logs.append(
                    f"✅ Indexed {record['filename']} (store: {store_id[:20]}...)"
                )
                memory.add(f"Uploaded PDF: {record['filename']}", {"store_id": store_id, "action": "upload"})
            except TimeoutError as e:
                logs.append(f"❌ Timeout while indexing {pdf_path.name}: {str(e)}")
            except RuntimeError as e:
                logs.append(f"❌ Indexing error for {pdf_path.name}: {str(e)}")
            except Exception as e:
                logs.append(f"❌ Unexpected error indexing {pdf_path.name}: {str(e)}")
                import traceback
                logs.append(f"   Details: {traceback.format_exc().split(chr(10))[-2]}")
                
        except Exception as e:
            logs.append(f"❌ Error processing {file_path}: {str(e)}")

    options = _option_list()
    return "\n".join(logs), gr.update(
        choices=options,
        value=options[-1] if options else None,
    )


def schedule_handler(selection: str, days: float) -> str:
    if not UPLOAD_REGISTRY:
        return "Please upload at least one PDF first."
    
    days = max(1, int(days))
    
    # Combine all uploaded PDF content
    all_content_parts = []
    file_names = []
    for store_id, data in UPLOAD_REGISTRY.items():
        all_content_parts.append(f"\n\n--- Content from: {data['filename']} ---\n\n{data['full_text']}")
        file_names.append(data['filename'])
    
    combined_text = "\n".join(all_content_parts)
    
    # Use LLM-based schedule generator with all content
    plan = schedule_gen.build_schedule(combined_text, days)
    
    memory.add(f"Created {days}-day intelligent schedule from {len(UPLOAD_REGISTRY)} PDF(s)", {
        "days": days,
        "pdf_count": len(UPLOAD_REGISTRY),
        "pdfs": file_names,
        "action": "schedule",
        "sessions": len(plan)
    })
    
    # Create visual HTML schedule (without key_concepts)
    html = f"""
    <div style="font-family: 'Segoe UI', sans-serif; padding: 20px;">
        <h2 style="color: #2d5aa0; margin-bottom: 25px; border-bottom: 3px solid #4CAF50; padding-bottom: 10px;">📅 Intelligent Study Schedule - {days} Days</h2>
        <p style="color: #666; margin-bottom: 20px;">Generated from {len(UPLOAD_REGISTRY)} uploaded PDF{'' if len(UPLOAD_REGISTRY) == 1 else 's'}: {', '.join(file_names)}</p>
        <div style="display: grid; gap: 20px;">
    """
    for session in plan:
        day = session.get("day", 1)
        title = session.get("title", f"Day {day}")
        summary = session.get("summary", "")
        estimated = session.get("estimated_pages", "")
        
        html += f"""
        <div style="border: 2px solid #4CAF50; border-radius: 12px; padding: 20px; background: linear-gradient(135deg, #e8f5e9 0%, #ffffff 100%); box-shadow: 0 4px 8px rgba(0,0,0,0.1); transition: transform 0.2s;">
            <div style="display: flex; align-items: center; margin-bottom: 15px;">
                <span style="background: #4CAF50; color: white; padding: 8px 16px; border-radius: 50%; font-weight: bold; font-size: 1.1em; margin-right: 15px;">Day {day}</span>
                <h3 style="margin: 0; color: #1976D2; font-size: 1.3em;">{title}</h3>
            </div>
            <p style="margin: 10px 0; color: #333; line-height: 1.7; font-size: 1.05em;">{summary}</p>
        """
        
        if estimated:
            html += f"""
            <div style="margin-top: 12px; padding: 8px 12px; background: rgba(76, 175, 80, 0.1); border-radius: 6px; display: inline-block;">
                <span style="color: #2e7d32; font-size: 0.9em;">📄 {estimated}</span>
            </div>
            """
        
        html += """
        </div>
        """
    
    html += """
        </div>
    </div>
    """
    return html


def tutor_handler(selection: str, question: str) -> str:
    store_id = _parse_selection(selection)
    if not store_id or store_id not in UPLOAD_REGISTRY:
        return "Select an indexed PDF first."
    if not question:
        return "Enter a question."

    data = UPLOAD_REGISTRY[store_id]
    result = tutor.answer(
        question=question,
        store_id=store_id,
        page_map=data["page_map"],
        filename=data["filename"],
    )
    
    # Store in memory with citations
    citations_info = f" (cited pages: {', '.join([c.split('Page ')[-1] for c in result.get('citations', [])])})" if result.get('citations') else " (no citations)"
    memory.add(f"Tutor Q: {question}{citations_info}", {
        "store_id": store_id,
        "answer": result["answer"][:200],
        "citations": result.get("citations", []),
        "action": "tutor_chat"
    })
    
    # Ensure answer always has citations section
    answer_text = result["answer"]
    if "---\n📄 Citations:" not in answer_text and "---\nCitations:" not in answer_text:
        # If citations section is missing, add it
        citations = result.get("citations", [])
        if citations:
            answer_text = f"{answer_text}\n\n---\n📄 Citations:\n" + "\n".join(f"- {c}" for c in citations)
        else:
            answer_text = f"{answer_text}\n\n---\n📄 Citations:\n- No specific page citations found. This answer is based on the uploaded document content."
    
    return answer_text


def flashcard_handler(topic: str):
    if not topic:
        return "Enter a topic.", []
    cards = flashcard_gen.generate(topic)
    memory.add(f"Generated flashcards for: {topic}", {
        "count": len(cards),
        "action": "flashcard_gen"
    })
    return cards


def parse_quiz(raw: str) -> List[Dict]:
    """Parse quiz text into structured questions with improved pattern matching."""
    questions = []
    
    # Try multiple patterns to handle different formats
    # Pattern 1: Q1: ... A) ... B) ... C) ... D) ... Correct: X
    # Pattern 2: Question 1: ... Option A: ... Option B: ...
    
    # Split by question markers
    blocks = re.split(r'(?:Q|Question)\s*(\d+)[:\s]+', raw, flags=re.IGNORECASE)
    
    for i in range(1, len(blocks), 2):
        if i + 1 >= len(blocks):
            break
        
        q_num = int(blocks[i])
        content = blocks[i + 1]
        
        # Extract question text (before options)
        question_match = re.match(r'(.+?)(?:[A-D]\)|Option [A-D]|Correct:)', content, re.DOTALL | re.IGNORECASE)
        if not question_match:
            continue
        
        q_text = question_match.group(1).strip()
        
        # Extract options - handle both A) and Option A: formats
        options = {}
        option_patterns = [
            r'([A-D])\)\s*(.+?)(?=[A-D]\)|Correct:|$)',  # A) format
            r'Option\s+([A-D]):\s*(.+?)(?=Option [A-D]:|Correct:|$)',  # Option A: format
        ]
        
        for pattern in option_patterns:
            opt_matches = re.finditer(pattern, content, re.DOTALL | re.IGNORECASE)
            for opt_match in opt_matches:
                letter = opt_match.group(1).upper()
                text = opt_match.group(2).strip()
                # Clean up text (remove trailing dashes, correct markers, etc.)
                text = re.sub(r'\s*---.*$', '', text).strip()
                text = re.sub(r'\s*Correct:.*$', '', text, flags=re.IGNORECASE).strip()
                if letter and text and len(text) > 2:  # Minimum option length
                    options[letter] = text
        
        # Find correct answer - handle multiple formats
        correct = None
        correct_patterns = [
            r'Correct:\s*([A-D])',
            r'Answer:\s*([A-D])',
            r'Correct\s+answer:\s*([A-D])',
        ]
        
        for pattern in correct_patterns:
            correct_match = re.search(pattern, content, re.IGNORECASE)
            if correct_match:
                correct = correct_match.group(1).upper()
                break
        
        # If we have question, options, and correct answer, add it
        if q_text and options and len(options) >= 2 and correct:
            questions.append({
                "number": q_num,
                "question": q_text,
                "options": options,
                "correct": correct
            })
    
    # If regex splitting failed, try line-by-line parsing
    if not questions:
        lines = raw.split('\n')
        current_q = None
        current_options = {}
        current_correct = None
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Question
            q_match = re.match(r'(?:Q|Question)\s*(\d+):\s*(.+)', line, re.IGNORECASE)
            if q_match:
                # Save previous question
                if current_q and current_options and current_correct:
                    questions.append({
                        "number": int(q_match.group(1)) - 1 if questions else 1,
                        "question": current_q,
                        "options": current_options,
                        "correct": current_correct
                    })
                current_q = q_match.group(2)
                current_options = {}
                current_correct = None
                continue
            
            # Option
            opt_match = re.match(r'([A-D])[\):]\s*(.+)', line, re.IGNORECASE)
            if opt_match:
                letter = opt_match.group(1).upper()
                text = opt_match.group(2).strip()
                if letter and text:
                    current_options[letter] = text
                continue
            
            # Correct answer
            correct_match = re.match(r'Correct:\s*([A-D])', line, re.IGNORECASE)
            if correct_match:
                current_correct = correct_match.group(1).upper()
        
        # Save last question
        if current_q and current_options and current_correct:
            questions.append({
                "number": len(questions) + 1,
                "question": current_q,
                "options": current_options,
                "correct": current_correct
            })
    
    return questions[:10]  # Limit to 10


def quiz_handler(topic: str, selection: str):
    if not topic:
        return None, "Enter a topic or keywords."
    
    if not UPLOAD_REGISTRY:
        return None, "Please upload at least one PDF first. Quiz questions are generated from uploaded files."
    
    # Combine all uploaded PDF content for quiz generation
    all_content_parts = []
    file_names = []
    for store_id, data in UPLOAD_REGISTRY.items():
        all_content_parts.append(f"\n\n--- Content from: {data['filename']} ---\n\n{data['full_text']}")
        file_names.append(data['filename'])
    
    combined_text = "\n".join(all_content_parts)
    
    # Use combined content with topic/keywords
    raw_quiz = quiz_gen.generate(topic, combined_text)
    questions = parse_quiz(raw_quiz)
    memory.add(f"Generated quiz for: {topic} from {len(UPLOAD_REGISTRY)} PDF(s)", {
        "count": len(questions),
        "action": "quiz_gen",
        "pdf_count": len(UPLOAD_REGISTRY),
        "pdfs": file_names,
        "used_pdf_content": True
    })
    return questions, raw_quiz


def quiz_display_html(questions: List[Dict]) -> str:
    """Convert parsed questions to visual HTML quiz."""
    if not questions:
        return "<div style='padding: 20px; text-align: center; color: #666;'><p>No questions available. Generate a quiz first.</p></div>"
    
    html = f"""
    <div style="font-family: 'Segoe UI', sans-serif; padding: 20px; max-width: 900px;">
        <h2 style="color: #2d5aa0; margin-bottom: 25px; border-bottom: 3px solid #2196F3; padding-bottom: 10px;">📝 Quiz - {len(questions)} Questions</h2>
    """
    for q in questions:
        html += f"""
        <div style="border: 2px solid #2196F3; border-radius: 12px; padding: 25px; margin-bottom: 25px; background: linear-gradient(135deg, #f5f9ff 0%, #ffffff 100%); box-shadow: 0 4px 8px rgba(0,0,0,0.1);">
            <h3 style="color: #1976D2; margin-top: 0; display: flex; align-items: center;">
                <span style="background: #2196F3; color: white; padding: 5px 15px; border-radius: 50%; margin-right: 15px; font-size: 1em;">{q['number']}</span>
                {q['question']}
            </h3>
            <div style="display: grid; gap: 12px; margin-top: 15px;">
        """
        for letter in ['A', 'B', 'C', 'D']:
            if letter in q['options']:
                html += f"""
                <div style="padding: 12px 15px; background: white; border-radius: 8px; border: 2px solid #e0e0e0; transition: all 0.2s;">
                    <span style="font-weight: bold; color: #1976D2; margin-right: 10px; font-size: 1.1em;">{letter})</span>
                    <span style="color: #333;">{q['options'][letter]}</span>
                </div>
                """
        html += """
            </div>
        </div>
        """
    html += """
    </div>
    """
    return html


def create_interactive_quiz_html(questions: List[Dict]) -> str:
    """Create HTML quiz with JavaScript for immediate feedback."""
    if not questions:
        return "<div style='padding: 20px; text-align: center; color: #666;'><p>No questions available. Generate a quiz first.</p></div>"
    
    html = f"""
    <div style="font-family: 'Segoe UI', sans-serif; padding: 20px; max-width: 900px; max-height: 80vh; overflow-y: auto;">
        <h2 style="color: #2d5aa0; margin-bottom: 25px; border-bottom: 3px solid #2196F3; padding-bottom: 10px;">📝 Interactive Quiz - {len(questions)} Questions</h2>
        <p style="color: #666; margin-bottom: 20px; font-weight: 500;">💡 Click on any answer button to see immediate feedback!</p>
    """
    for q in questions:
        q_num = q['number']
        html += f"""
        <div id="q{q_num}" style="border: 2px solid #2196F3; border-radius: 12px; padding: 25px; margin-bottom: 25px; background: linear-gradient(135deg, #f5f9ff 0%, #ffffff 100%); box-shadow: 0 4px 8px rgba(0,0,0,0.1);">
            <h3 style="color: #1976D2; margin-top: 0;">
                <span style="background: #2196F3; color: white; padding: 5px 15px; border-radius: 50%; margin-right: 15px;">{q_num}</span>
                {q['question']}
            </h3>
            <div id="feedback{q_num}" style="margin-top: 10px; padding: 10px; border-radius: 5px; display: none; font-weight: 500;"></div>
            <div style="display: grid; gap: 12px; margin-top: 15px;">
        """
        for letter in ['A', 'B', 'C', 'D']:
            if letter in q['options']:
                is_correct = "true" if letter == q['correct'] else "false"
                # Escape single quotes in option text for JavaScript
                option_text = q['options'][letter].replace("'", "\\'").replace('"', '&quot;')
                html += f"""
                <button type="button"
                        id="btn_q{q_num}_{letter}"
                        onclick="handleQuizClick({q_num}, '{letter}', {is_correct}, '{q['correct']}');"
                        style="padding: 15px 20px; background: white; border-radius: 10px; border: 3px solid #e0e0e0; cursor: pointer; transition: all 0.3s; display: flex; align-items: center; width: 100%; text-align: left; font-size: 1em; font-family: inherit; box-shadow: 0 2px 4px rgba(0,0,0,0.1);" 
                        onmouseover="if(!this.hasAttribute('data-selected')){{this.style.borderColor='#2196F3'; this.style.transform='translateY(-2px)'; this.style.boxShadow='0 4px 8px rgba(33,150,243,0.3)';}}" 
                        onmouseout="if(!this.hasAttribute('data-selected')){{this.style.borderColor='#e0e0e0'; this.style.transform='translateY(0)'; this.style.boxShadow='0 2px 4px rgba(0,0,0,0.1)';}}">
                    <input type="radio" name="q{q_num}" value="{letter}" id="q{q_num}_{letter}" style="margin-right: 12px; transform: scale(1.3); cursor: pointer; pointer-events: none;">
                    <span style="font-weight: bold; color: #1976D2; margin-right: 12px; font-size: 1.1em; min-width: 25px;">{letter})</span>
                    <span style="color: #333; flex: 1; line-height: 1.5;">{option_text}</span>
                </button>
                """
        html += """
            </div>
        </div>
        """
    
    html += """
    </div>
    <script>
    function handleQuizClick(qNum, selected, isCorrect, correctAns) {
        var feedback = document.getElementById('feedback' + qNum);
        var questionDiv = document.getElementById('q' + qNum);
        
        // Set all radio buttons for this question
        ['A', 'B', 'C', 'D'].forEach(function(letter) {
            var radio = document.getElementById('q' + qNum + '_' + letter);
            var btn = document.getElementById('btn_q' + qNum + '_' + letter);
            
            if (radio) {
                radio.checked = (letter === selected);
            }
            
            if (btn) {
                // Reset all buttons
                btn.style.background = 'white';
                btn.style.borderColor = '#e0e0e0';
                btn.style.borderWidth = '3px';
                btn.removeAttribute('data-selected');
                btn.onmouseover = function() {
                    if (!this.hasAttribute('data-selected')) {
                        this.style.borderColor = '#2196F3';
                        this.style.transform = 'translateY(-2px)';
                        this.style.boxShadow = '0 4px 8px rgba(33,150,243,0.3)';
                    }
                };
                btn.onmouseout = function() {
                    if (!this.hasAttribute('data-selected')) {
                        this.style.borderColor = '#e0e0e0';
                        this.style.transform = 'translateY(0)';
                        this.style.boxShadow = '0 2px 4px rgba(0,0,0,0.1)';
                    }
                };
                
                if (letter === selected) {
                    btn.setAttribute('data-selected', 'true');
                    // Highlight selected button
                    if (isCorrect === true || isCorrect === 'true') {
                        btn.style.background = '#e8f5e9';
                        btn.style.borderColor = '#4CAF50';
                        btn.style.borderWidth = '3px';
                    } else {
                        btn.style.background = '#ffebee';
                        btn.style.borderColor = '#f44336';
                        btn.style.borderWidth = '3px';
                    }
                }
            }
        });
        
        // Show feedback
        if (feedback && questionDiv) {
            if (isCorrect === true || isCorrect === 'true') {
                feedback.innerHTML = '<span style="color: #4CAF50; font-weight: bold; font-size: 1.1em;">✓ Correct! Well done.</span>';
                feedback.style.background = '#e8f5e9';
                feedback.style.border = '2px solid #4CAF50';
                questionDiv.style.borderColor = '#4CAF50';
            } else {
                feedback.innerHTML = '<span style="color: #f44336; font-weight: bold; font-size: 1.1em;">✗ Wrong. The correct answer is ' + correctAns + '.</span>';
                feedback.style.background = '#ffebee';
                feedback.style.border = '2px solid #f44336';
                questionDiv.style.borderColor = '#f44336';
            }
            feedback.style.display = 'block';
        }
        
        return false;
    }
    </script>
    """
    return html


def submit_quiz(questions: List[Dict], answers: str) -> Tuple[str, int]:
    """Check quiz answers and return score."""
    if not questions:
        return "No quiz available.", 0
    
    if not answers:
        return "Please answer all questions before submitting.", 0
    
    try:
        answer_dict = json.loads(answers) if isinstance(answers, str) else answers
    except:
        return "Invalid answer format.", 0
    
    correct_count = 0
    total = len(questions)
    feedback = []
    
    for q in questions:
        q_num = q['number']
        user_answer = answer_dict.get(f"q{q_num}", "").upper()
        correct_answer = q['correct'].upper()
        
        if user_answer == correct_answer:
            correct_count += 1
            feedback.append(f"✅ Q{q_num}: Correct! ({correct_answer})")
        else:
            feedback.append(f"❌ Q{q_num}: Wrong. You chose {user_answer}, correct is {correct_answer}")
    
    score = int((correct_count / total) * 100)
    result_html = f"""
    <div style="padding: 20px; border-radius: 10px; background: {'#e8f5e9' if score >= 70 else '#fff3e0'}; border: 3px solid {'#4CAF50' if score >= 70 else '#FF9800'};">
        <h2 style="color: {'#2e7d32' if score >= 70 else '#e65100'}; margin-top: 0;">📊 Quiz Results</h2>
        <div style="font-size: 2em; font-weight: bold; color: {'#4CAF50' if score >= 70 else '#FF9800'}; margin: 20px 0;">
            Score: {score}%
        </div>
        <p style="font-size: 1.2em; margin: 10px 0;">
            {correct_count} out of {total} correct
        </p>
        <div style="margin-top: 20px;">
            <h3>Feedback:</h3>
            <ul style="list-style: none; padding: 0;">
                {''.join(f'<li style="padding: 5px 0;">{f}</li>' for f in feedback)}
            </ul>
        </div>
    </div>
    """
    
    memory.add(f"Quiz completed: {correct_count}/{total} correct ({score}%)", {
        "score": score,
        "correct": correct_count,
        "total": total,
        "action": "quiz_submit"
    })
    
    return result_html, score


def flip_card_display(cards: List[Dict], idx: int, show: bool) -> str:
    """Create visual flip card HTML without mirroring text."""
    if not cards or idx >= len(cards):
        return """
        <div style="text-align: center; padding: 100px; font-size: 1.5em; color: #999;">
            No flashcards available. Generate flashcards first.
        </div>
        """
    
    card = cards[idx]
    content = card["a"] if show else card["q"]
    label = "Answer" if show else "Question"
    
    # Use simple show/hide instead of 3D flip to avoid text mirroring
    html = f"""
    <div style="font-family: 'Segoe UI', sans-serif;">
        <div style="width: 500px; height: 350px; margin: 20px auto; position: relative; transition: all 0.3s ease;">
            <div style="width: 100%; height: 100%; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); border-radius: 20px; box-shadow: 0 10px 30px rgba(0,0,0,0.3); display: flex; flex-direction: column; justify-content: center; align-items: center; padding: 30px; color: white; text-align: center; transform: scale(1);">
                <div style="position: absolute; top: 15px; left: 20px; background: rgba(255,255,255,0.2); padding: 5px 15px; border-radius: 20px; font-size: 0.9em; backdrop-filter: blur(10px);">
                    {label}
                </div>
                <div style="font-size: 1.5em; line-height: 1.6; font-weight: 500; word-wrap: break-word; max-width: 100%;">
                    {content}
                </div>
                <div style="position: absolute; bottom: 15px; right: 20px; background: rgba(255,255,255,0.2); padding: 5px 15px; border-radius: 20px; font-size: 0.9em; backdrop-filter: blur(10px);">
                    Card {idx + 1} of {len(cards)}
                </div>
            </div>
        </div>
    </div>
    """
    return html




def flip_prev_handler(cards: List[Dict], idx: int, show: bool):
    result = flip_action(cards, idx, show, "prev")
    display = flip_card_display(cards, result[1], result[2])
    memory.add(f"Navigated flashcard {result[1]}", {"action": "flashcard_nav"})
    return display, result[1], result[2]


def flip_next_handler(cards: List[Dict], idx: int, show: bool):
    result = flip_action(cards, idx, show, "next")
    display = flip_card_display(cards, result[1], result[2])
    memory.add(f"Navigated flashcard {result[1]}", {"action": "flashcard_nav"})
    return display, result[1], result[2]


def flip_toggle_handler(cards: List[Dict], idx: int, show: bool):
    result = flip_action(cards, idx, show, "flip")
    display = flip_card_display(cards, result[1], result[2])
    return display, result[1], result[2]


def build_interface():
    with gr.Blocks(title="MicroTutor", theme=gr.themes.Soft()) as app:
        gr.Markdown(
            """
            # 📘 MicroTutor
            """
        )
        
        with gr.Tab("📄 Upload & Index PDFs"):
            gr.Markdown("### Upload your course PDFs to get started")
            file_input = gr.File(label="Upload PDFs", file_count="multiple", type="filepath")
            upload_log = gr.Textbox(label="Status", lines=8, interactive=False)
            store_selector = gr.Dropdown(label="Indexed PDFs", choices=[], interactive=True)
            file_input.upload(upload_pdfs, file_input, [upload_log, store_selector])

        with gr.Tab("📅 Create Schedule"):
            gr.Markdown("### Visual Study Schedule Generator")
            gr.Markdown("Generates a schedule from all uploaded PDFs.")
            with gr.Row():
                days_input = gr.Number(label="Number of days", value=5, precision=0, minimum=1, maximum=30)
            schedule_output = gr.HTML(label="Study Schedule")
            gr.Button("Generate Schedule", variant="primary").click(
                schedule_handler,
                [gr.State(""), days_input],  # No longer needs selection
                schedule_output,
            )

        with gr.Tab("🎓 Tutor Chat (RAG)"):
            gr.Markdown("### Ask questions about your PDF content")
            question_box = gr.Textbox(label="Ask a question", lines=3, placeholder="e.g., What is the main topic discussed in chapter 3?")
            answer_box = gr.Textbox(label="Answer with Page Citations", lines=15, max_lines=30, interactive=False, show_copy_button=True)
            gr.Button("Ask Tutor", variant="primary").click(
                tutor_handler,
                [store_selector, question_box],
                answer_box,
            )

        with gr.Tab("🃏 Flashcards"):
            gr.Markdown("### Generate and Review Flashcards")
            cards_state = gr.State([])
            flip_index = gr.State(0)
            flip_show = gr.State(False)
            
            with gr.Row():
                with gr.Column(scale=1):
                    topic_input = gr.Textbox(label="Topic for Flashcards", lines=2, placeholder="e.g., Neural Networks, Calculus Basics")
                    generate_flashcard_btn = gr.Button("Generate Flashcards", variant="primary")
                
                with gr.Column(scale=2):
                    flip_view = gr.HTML(label="Flip Card", value="<div style='padding: 100px; text-align: center; color: #999; font-size: 1.2em;'>Generate flashcards to get started.</div>")
                    with gr.Row():
                        flip_prev_btn = gr.Button("⬅️ Previous", variant="secondary")
                        flip_btn = gr.Button("🔄 Flip", variant="primary")
                        flip_next_btn = gr.Button("Next ➡️", variant="secondary")
            
            def generate_flashcards_wrapper(topic):
                if not topic:
                    return [], 0, False, gr.update(value="<div style='padding: 40px; text-align: center; color: #999;'>Enter a topic first.</div>")
                cards = flashcard_handler(topic)
                if not cards:
                    return [], 0, False, gr.update(value="<div style='padding: 40px; text-align: center; color: #999;'>Failed to generate flashcards. Try again.</div>")
                display = flip_card_display(cards, 0, False)
                return cards, 0, False, gr.update(value=display)
            
            generate_flashcard_btn.click(
                generate_flashcards_wrapper,
                topic_input,
                [cards_state, flip_index, flip_show, flip_view],
            )
            
            flip_prev_btn.click(
                flip_prev_handler,
                [cards_state, flip_index, flip_show],
                [flip_view, flip_index, flip_show],
            )
            flip_btn.click(
                flip_toggle_handler,
                [cards_state, flip_index, flip_show],
                [flip_view, flip_index, flip_show],
            )
            flip_next_btn.click(
                flip_next_handler,
                [cards_state, flip_index, flip_show],
                [flip_view, flip_index, flip_show],
            )

        with gr.Tab("📝 Quiz"):
            gr.Markdown("### Interactive Multiple Choice Quiz with Feedback")
            quiz_questions_state = gr.State([])
            
            with gr.Row():
                with gr.Column(scale=1):
                    quiz_topic = gr.Textbox(label="Topic/Keywords for Quiz", lines=2, placeholder="e.g., Machine Learning Fundamentals, Neural Networks")
                    generate_quiz_btn = gr.Button("Generate Quiz", variant="primary")
                    submit_quiz_btn = gr.Button("Submit Quiz", variant="primary", visible=False)
                
                with gr.Column(scale=2):
                    quiz_status = gr.Markdown("Enter a topic and click 'Generate Quiz' to get started.", visible=True)
                    
                    # Pre-create 10 Radio components (will be hidden initially)
                    quiz_radios = []
                    for i in range(10):
                        radio = gr.Radio(
                            choices=[],
                            label=f"Question {i+1}",
                            visible=False,
                            interactive=True
                        )
                        quiz_radios.append(radio)
                    
                    quiz_result_display = gr.Markdown(visible=False)
                    quiz_feedback_display = gr.Textbox(label="📊 Performance Feedback", lines=12, visible=False, interactive=False)
            
            def generate_interactive_quiz(topic):
                if not topic or not topic.strip():
                    updates = [gr.update(visible=False) for _ in range(10)]  # Hide all radios
                    return tuple([
                        gr.update(value="Enter a topic/keywords first.", visible=True),
                        []
                    ] + updates + [
                        gr.update(visible=False),
                        gr.update(visible=False),
                        gr.update(visible=False)
                    ])
                
                try:
                    questions, raw_quiz = quiz_handler(topic.strip(), "")
                    
                    if not questions or questions == []:
                        error_msg = raw_quiz if isinstance(raw_quiz, str) else "Failed to generate quiz. Please upload PDFs and try again."
                        updates = [gr.update(visible=False) for _ in range(10)]
                        return tuple([
                            gr.update(value=f"❌ {error_msg}", visible=True),
                            []
                        ] + updates + [
                            gr.update(visible=False),
                            gr.update(visible=False),
                            gr.update(visible=False)
                        ])
                    
                    # Create updates for Radio components
                    updates = []
                    for i in range(10):
                        if i < len(questions):
                            q = questions[i]
                            q_num = q['number']
                            options_list = []
                            for letter in ['A', 'B', 'C', 'D']:
                                if letter in q['options']:
                                    options_list.append(f"{letter}) {q['options'][letter]}")
                            
                            updates.append(gr.update(
                                choices=options_list,
                                label=f"Q{q_num}: {q['question']}",
                                value=None,
                                visible=True,
                                interactive=True
                            ))
                        else:
                            updates.append(gr.update(visible=False))
                    
                    feedback_msg = f"✅ **Quiz generated with {len(questions)} questions!**\n\nSelect your answers below, then click 'Submit Quiz' to see your results."
                    
                    return tuple([
                        gr.update(value=feedback_msg, visible=True),  # quiz_status
                        questions,  # quiz_questions_state
                    ] + updates + [  # quiz_radios updates (unpacked)
                        gr.update(visible=True),  # submit_quiz_btn
                        gr.update(visible=False),  # quiz_result_display
                        gr.update(visible=False)  # quiz_feedback_display
                    ])
                
                except Exception as e:
                    error_msg = f"Error generating quiz: {str(e)}. Please try again."
                    updates = [gr.update(visible=False) for _ in range(10)]
                    import traceback
                    print(f"Quiz generation error: {traceback.format_exc()}")
                    return tuple([
                        gr.update(value=f"❌ {error_msg}", visible=True),
                        []
                    ] + updates + [
                        gr.update(visible=False),
                        gr.update(visible=False),
                        gr.update(visible=False)
                    ])
            
            def submit_quiz_handler(questions, *answers):
                if not questions:
                    return gr.update(visible=False), gr.update(visible=False)
                
                correct_count = 0
                total = len(questions)
                feedback_lines = []
                
                for i, q in enumerate(questions):
                    q_num = q['number']
                    if i < len(answers) and answers[i]:
                        # Radio component returns string like "A) option text"
                        user_answer_str = answers[i] if isinstance(answers[i], str) else ""
                        # Extract the letter (A, B, C, or D) from the string
                        user_answer = user_answer_str[0].upper() if user_answer_str and len(user_answer_str) > 0 else ""
                        correct_answer = q['correct'].upper()
                        
                        if user_answer == correct_answer:
                            correct_count += 1
                            feedback_lines.append(f"✅ **Q{q_num}:** Correct! ({correct_answer})")
                        else:
                            feedback_lines.append(f"❌ **Q{q_num}:** Wrong. You chose {user_answer}, correct is **{correct_answer}**) {q['options'][correct_answer]}")
                    else:
                        correct_answer = q['correct'].upper()
                        feedback_lines.append(f"⚠️ **Q{q_num}:** Not answered. Correct answer is **{correct_answer}**) {q['options'][correct_answer]}")
                
                score = int((correct_count / total) * 100)
                result_text = f"""
### 📊 Quiz Results

**Score: {score}%**

{correct_count} out of {total} correct

---

### Question Feedback:

{chr(10).join(feedback_lines)}
"""
                
                # Generate detailed feedback
                wrong_qs = []
                for i, q in enumerate(questions):
                    if i >= len(answers) or not answers[i]:
                        wrong_qs.append({"question": q['question'], "correct": q['correct']})
                    else:
                        user_answer_str = answers[i] if isinstance(answers[i], str) else ""
                        user_answer = user_answer_str[0].upper() if user_answer_str and len(user_answer_str) > 0 else ""
                        if user_answer != q['correct'].upper():
                            wrong_qs.append({"question": q['question'], "correct": q['correct']})
                wrong_qs = wrong_qs[:5]
                
                store_id = list(UPLOAD_REGISTRY.keys())[0] if UPLOAD_REGISTRY else ""
                selection_value = f"{UPLOAD_REGISTRY[store_id]['filename']} | {store_id}" if store_id else ""
                
                detailed_feedback = f"""Quiz Score: {score}%

You answered {correct_count} out of {total} questions correctly.

Review the question feedback above to see which answers were correct and incorrect.
"""
                
                memory.add(f"Quiz completed: {correct_count}/{total} correct ({score}%)", {
                    "score": score,
                    "correct": correct_count,
                    "total": total,
                    "action": "quiz_submit"
                })
                
                return gr.update(visible=True, value=result_text), gr.update(visible=True, value=detailed_feedback)
            
            generate_quiz_btn.click(
                generate_interactive_quiz,
                [quiz_topic],
                [quiz_status, quiz_questions_state] + quiz_radios + [submit_quiz_btn, quiz_result_display, quiz_feedback_display],
            )
            
            submit_quiz_btn.click(
                submit_quiz_handler,
                [quiz_questions_state] + quiz_radios,
                [quiz_result_display, quiz_feedback_display]
            )

        with gr.Tab("📊 Performance Review"):
            gr.Markdown("### Learning Analytics & Performance Insights")
            gr.Markdown("Review your learning progress, quiz performance, and study patterns.")
            
            refresh_btn = gr.Button("🔄 Refresh Analytics", variant="primary")
            performance_display = gr.Markdown(visible=True, value="Click 'Refresh Analytics' to see your learning performance and insights.")
            
            def generate_performance_review():
                """Generate comprehensive performance review from memory data."""
                try:
                    # Get all memory entries
                    all_memories = memory.dump()
                    
                    # If no memories, show message
                    if not all_memories or len(all_memories) == 0:
                        return gr.update(value="### 📊 Performance Review\n\n**No data available yet.**\n\nStart using MicroTutor to see your learning analytics:\n- Upload PDFs\n- Generate quizzes\n- Ask tutor questions\n- Create study schedules\n- Study flashcards\n\nYour activities will be tracked here.", visible=True)
                    
                    # Parse memories to extract analytics
                    pdf_uploads = []
                    quiz_scores = []
                    tutor_questions = []
                    flashcards_generated = []
                    schedules_created = []
                    
                    for entry in all_memories:
                        content = entry.get("content", "")
                        metadata = entry.get("metadata", {})
                        action = metadata.get("action", "")
                        
                        if action == "upload":
                            pdf_uploads.append({
                                "filename": metadata.get("store_id", "Unknown"),
                                "timestamp": metadata.get("timestamp", "")
                            })
                        elif action == "quiz_submit":
                            score = metadata.get("score", 0)
                            correct = metadata.get("correct", 0)
                            total = metadata.get("total", 0)
                            quiz_scores.append({
                                "score": score,
                                "correct": correct,
                                "total": total,
                                "date": metadata.get("timestamp", "")
                            })
                        elif action == "tutor_chat":
                            tutor_questions.append({
                                "question": content[:100] + "..." if len(content) > 100 else content,
                                "store_id": metadata.get("store_id", ""),
                                "citations": len(metadata.get("citations", []))
                            })
                        elif action == "flashcard_gen":
                            flashcards_generated.append({
                                "topic": content.replace("Generated flashcards for: ", ""),
                                "count": metadata.get("count", 0)
                            })
                        elif action == "schedule":
                            schedules_created.append({
                                "days": metadata.get("days", 0),
                                "sessions": metadata.get("sessions", 0),
                                "pdf_count": metadata.get("pdf_count", 0)
                            })
                    
                    # Calculate statistics
                    total_uploads = len(pdf_uploads)
                    total_quizzes = len(quiz_scores)
                    total_questions = len(tutor_questions)
                    total_flashcards = len(flashcards_generated)
                    total_schedules = len(schedules_created)
                    
                    # Quiz performance
                    avg_score = sum(q["score"] for q in quiz_scores) / len(quiz_scores) if quiz_scores else 0
                    best_score = max(q["score"] for q in quiz_scores) if quiz_scores else 0
                    worst_score = min(q["score"] for q in quiz_scores) if quiz_scores else 0
                    
                    # Build performance report
                    report = f"""
### 📊 Performance Review & Learning Analytics

---

#### 📈 **Overview Statistics**

- **📄 PDFs Uploaded:** {total_uploads}
- **📝 Quizzes Completed:** {total_quizzes}
- **🎓 Tutor Questions Asked:** {total_questions}
- **🃏 Flashcard Sets Generated:** {total_flashcards}
- **📅 Study Schedules Created:** {total_schedules}

---

#### 📊 **Quiz Performance**

"""
                    
                    if quiz_scores:
                        report += f"""
- **Average Score:** {avg_score:.1f}%
- **Best Score:** {best_score}%
- **Lowest Score:** {worst_score}%
- **Total Questions Answered:** {sum(q["total"] for q in quiz_scores)}
- **Total Correct Answers:** {sum(q["correct"] for q in quiz_scores)}

**Recent Quiz Scores:**
"""
                        for i, quiz in enumerate(quiz_scores[-5:], 1):  # Show last 5
                            report += f"- Quiz {i}: {quiz['correct']}/{quiz['total']} correct ({quiz['score']}%)\n"
                    else:
                        report += "No quiz data available yet. Complete some quizzes to see your performance!\n"
                    
                    report += "\n---\n\n"
                    
                    report += f"""
#### 🎓 **Tutor Chat Activity**

- **Total Questions:** {total_questions}
- **Average Citations per Answer:** {sum(q["citations"] for q in tutor_questions) / len(tutor_questions) if tutor_questions else 0:.1f}

"""
                    
                    if tutor_questions:
                        report += "**Recent Questions:**\n"
                        for i, q in enumerate(tutor_questions[-5:], 1):  # Show last 5
                            report += f"- {i}. {q['question']}\n"
                    else:
                        report += "No tutor questions yet. Ask some questions to get help with your PDFs!\n"
                    
                    report += "\n---\n\n"
                    
                    report += f"""
#### 🃏 **Flashcard Activity**

- **Flashcard Sets Created:** {total_flashcards}

"""
                    
                    if flashcards_generated:
                        report += "**Topics Studied:**\n"
                        for i, fc in enumerate(flashcards_generated[-5:], 1):  # Show last 5
                            report += f"- {i}. {fc['topic']} ({fc['count']} cards)\n"
                    else:
                        report += "No flashcards generated yet. Create flashcards to study topics!\n"
                    
                    report += "\n---\n\n"
                    
                    report += f"""
#### 📅 **Study Planning**

- **Study Schedules Created:** {total_schedules}

"""
                    
                    if schedules_created:
                        report += "**Recent Schedules:**\n"
                        for i, sched in enumerate(schedules_created[-5:], 1):  # Show last 5
                            report += f"- {i}. {sched['days']}-day schedule with {sched['sessions']} sessions ({sched['pdf_count']} PDF(s))\n"
                    else:
                        report += "No study schedules created yet. Generate a schedule to plan your learning!\n"
                    
                    report += "\n---\n\n"
                    
                    # Performance insights
                    report += "### 💡 **Performance Insights**\n\n"
                    
                    if quiz_scores:
                        if avg_score >= 80:
                            report += "✅ **Excellent Performance!** You're scoring well on quizzes. Keep up the great work!\n\n"
                        elif avg_score >= 70:
                            report += "👍 **Good Performance!** You're doing well. Consider reviewing topics where you scored lower.\n\n"
                        elif avg_score >= 60:
                            report += "📚 **Improving!** Your scores show you're learning. Focus on areas that need more practice.\n\n"
                        else:
                            report += "🎯 **Keep Practicing!** Review the material and try more quizzes to improve your understanding.\n\n"
                    
                    if total_questions > 0:
                        report += f"💬 **Active Learner:** You've asked {total_questions} tutor questions, showing good engagement with the material.\n\n"
                    
                    if total_flashcards > 0:
                        report += f"🃏 **Flashcard Learner:** You've created {total_flashcards} flashcard sets - great for active recall practice!\n\n"
                    
                    if total_schedules > 0:
                        report += f"📅 **Planned Learning:** You've created {total_schedules} study schedule(s), showing organized learning approach.\n\n"
                    
                    if total_uploads == 0:
                        report += "⚠️ **Get Started:** Upload some PDFs to begin your learning journey!\n\n"
                    
                    report += "\n---\n\n"
                    report += "*Last updated: " + str(len(all_memories)) + " activities tracked*"
                    
                    return gr.update(value=report, visible=True)
                
                except Exception as e:
                    import traceback
                    error_msg = f"Error generating performance review: {str(e)}\n\n{traceback.format_exc()}"
                    return gr.update(value=f"### ❌ Error\n\n{error_msg}", visible=True)
            
            refresh_btn.click(
                generate_performance_review,
                [],
                [performance_display]
            )

    return app
