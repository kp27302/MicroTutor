# Quick run script for MicroTutor
# Ensures venv is activated and runs the app

# Activate venv if it exists
if (Test-Path ".venv\Scripts\Activate.ps1") {
    Write-Host "🔄 Activating virtual environment..." -ForegroundColor Yellow
    & .\.venv\Scripts\Activate.ps1
} else {
    Write-Host "⚠️  Virtual environment not found. Run setup.ps1 first!" -ForegroundColor Red
    exit 1
}

# Check if dependencies are installed
try {
    python -c "import gradio" 2>$null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "❌ Dependencies not installed. Running setup..." -ForegroundColor Yellow
        & .\setup.ps1
    }
} catch {
    Write-Host "❌ Dependencies not installed. Run setup.ps1 first!" -ForegroundColor Red
    exit 1
}

# Check if .env exists
if (-not (Test-Path ".env")) {
    Write-Host "⚠️  .env file not found. Please create one from env_template.txt" -ForegroundColor Yellow
    Write-Host "   Or set environment variables manually." -ForegroundColor Yellow
}

# Run the app
Write-Host ""
Write-Host "🚀 Starting MicroTutor..." -ForegroundColor Green
Write-Host ""
python app.py

