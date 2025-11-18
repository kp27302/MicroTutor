# MicroTutor Setup Script for Windows PowerShell
# This script ensures all dependencies are installed in the virtual environment

Write-Host "🔧 MicroTutor Setup Script" -ForegroundColor Cyan
Write-Host "=========================" -ForegroundColor Cyan
Write-Host ""

# Check if venv exists
if (Test-Path ".venv") {
    Write-Host "✅ Virtual environment found" -ForegroundColor Green
} else {
    Write-Host "❌ Virtual environment not found. Creating one..." -ForegroundColor Yellow
    python -m venv .venv
    Write-Host "✅ Virtual environment created" -ForegroundColor Green
}

# Activate venv
Write-Host ""
Write-Host "🔄 Activating virtual environment..." -ForegroundColor Yellow
& .\.venv\Scripts\Activate.ps1

# Upgrade pip
Write-Host ""
Write-Host "📦 Upgrading pip..." -ForegroundColor Yellow
python -m pip install --upgrade pip --quiet

# Install requirements
Write-Host ""
Write-Host "📚 Installing dependencies from requirements.txt..." -ForegroundColor Yellow
pip install -r requirements.txt

# Check if .env file exists
Write-Host ""
if (Test-Path ".env") {
    Write-Host "✅ .env file found" -ForegroundColor Green
} else {
    Write-Host "⚠️  .env file not found" -ForegroundColor Yellow
    Write-Host "   Please create a .env file with your API keys:" -ForegroundColor Yellow
    Write-Host "   - Copy env_template.txt to .env" -ForegroundColor Yellow
    Write-Host "   - Add your GEMINI_API_KEY (required)" -ForegroundColor Yellow
    Write-Host "   - Add OPENAI_API_KEY and MEM0_API_KEY (optional)" -ForegroundColor Yellow
}

# Verify Python path
Write-Host ""
Write-Host "🐍 Python path:" -ForegroundColor Cyan
python -c "import sys; print(sys.executable)"

# Verify key dependencies
Write-Host ""
Write-Host "🔍 Verifying key dependencies..." -ForegroundColor Cyan
python -c "import gradio; print('✅ gradio:', gradio.__version__)" 2>$null
python -c "import google.genai; print('✅ google-generativeai: installed')" 2>$null
python -c "import fitz; print('✅ pymupdf: installed')" 2>$null

Write-Host ""
Write-Host "✨ Setup complete!" -ForegroundColor Green
Write-Host ""
Write-Host "To run the app:" -ForegroundColor Cyan
Write-Host "  python app.py" -ForegroundColor White
Write-Host ""

