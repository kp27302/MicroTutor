# 📘 MicroTutor

An intelligent learning system powered by Google Gemini File Search API that provides RAG-based tutoring, flashcards, quizzes, and study schedules from your PDF documents.

## 🚀 Quick Start

### Prerequisites
- Python 3.8+
- Virtual environment (venv)
- API Keys:
  - **GEMINI_API_KEY** (Required) - Get from [Google AI Studio](https://makersuite.google.com/app/apikey)
  - OPENAI_API_KEY (Optional) - For mem0 memory features
  - MEM0_API_KEY (Optional) - For mem0 memory features

### Setup (Windows PowerShell)

1. **Activate your virtual environment:**
   ```powershell
   .\.venv\Scripts\Activate.ps1
   ```

2. **Run the setup script:**
   ```powershell
   .\setup.ps1
   ```
   
   Or manually install dependencies:
   ```powershell
   pip install -r requirements.txt
   ```

3. **Configure API keys:**
   
   Create a `.env` file in the project root:
   ```env
   GEMINI_API_KEY=your_gemini_api_key_here
   OPENAI_API_KEY=your_openai_api_key_here  # Optional
   MEM0_API_KEY=your_mem0_api_key_here      # Optional
   ```
   
   Or use `env_template.txt` as a template.

4. **Run the application:**
   ```powershell
   python app.py
   ```

5. **Access the UI:**
   - The Gradio interface will open in your browser automatically
   - Or visit the URL shown in the terminal (usually `http://127.0.0.1:7860`)

## 📋 Features

- **📄 PDF Upload & Indexing**: Upload multiple PDFs and index them using Gemini File Search
- **🤖 RAG Tutor Chat**: Ask questions and get answers with page citations
- **📅 Intelligent Study Schedule**: Generate personalized study schedules from your PDFs
- **🃏 Flashcards**: Generate interactive flashcards for any topic
- **📝 Interactive Quiz**: Create and take quizzes with immediate feedback
- **🧠 Learning Memory**: Track your progress with mem0 (optional)

## 🏗️ Architecture

```
MicroTutor
├── app.py                    # Entry point
├── core/
│   ├── file_search.py       # Gemini File Search integration
│   ├── page_map.py          # PDF page mapping
│   ├── tutor.py             # RAG tutor assistant
│   ├── schedule.py          # Study schedule generator
│   ├── flashcards.py        # Flashcard generator
│   ├── quiz.py              # Quiz generator
│   └── memory.py            # Memory manager (mem0)
└── ui/
    └── interface.py         # Gradio UI
```

## 🔧 Troubleshooting

### ModuleNotFoundError
If you get `ModuleNotFoundError`:
1. Ensure your virtual environment is activated (check for `(.venv)` in your prompt)
2. Run `pip install -r requirements.txt` inside the venv
3. Or run `.\setup.ps1` to automate setup

### API Key Errors
- Ensure `.env` file exists in the project root
- Check that `GEMINI_API_KEY` is set correctly
- Verify API keys are valid and have proper permissions

### Import Errors
- Make sure you're using the Python from your venv:
  ```powershell
  python -c "import sys; print(sys.executable)"
  ```
- Should show path to `.venv\Scripts\python.exe`

## 📝 Requirements

See `requirements.txt` for full dependency list:
- `google-generativeai` - Gemini API client
- `gradio` - Web UI framework
- `pymupdf` - PDF processing
- `mem0ai` - Memory/persistence (optional)
- `python-dotenv` - Environment variable management

## 📄 License

MIT License

