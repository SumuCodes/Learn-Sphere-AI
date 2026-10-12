@echo off
title Learn Sphere AI Launcher

echo ========================================
echo   Learn Sphere AI – Setup & Launch
echo ========================================

:: 1. Set virtual environment folder name
set VENV_DIR=venv

:: 2. Create virtual environment if it doesn't exist
if not exist %VENV_DIR% (
    echo Creating new virtual environment...
    python -m venv %VENV_DIR%
    if errorlevel 1 (
        echo ❌ Failed to create virtual environment.
        echo Make sure Python is installed and in your PATH.
        pause
        exit /b
    )
    echo ✅ Virtual environment created.
) else (
    echo ✅ Virtual environment already exists.
)

:: 3. Activate the virtual environment
echo Activating virtual environment...
call %VENV_DIR%\Scripts\activate.bat
if errorlevel 1 (
    echo ❌ Activation failed.
    pause
    exit /b
)

:: 4. Upgrade pip
echo Upgrading pip...
python -m pip install --upgrade pip

:: 5. Install required packages
echo Installing dependencies...
pip install streamlit openai yt-dlp chromadb sentence-transformers langchain-text-splitters torch pandas plotly numpy bcrypt sumy nltk librosa openai-whisper
if errorlevel 1 (
    echo ❌ Installation failed. Check your internet connection.
    pause
    exit /b
)

:: 6. Download NLTK data (punkt)
echo Downloading NLTK punkt tokenizer...
python -c "import nltk; nltk.download('punkt')"
python -c "import nltk; nltk.download('punkt_tab')"

:: 7. Launch the Streamlit app
echo ========================================
echo Launching Streamlit app...
streamlit run app.py

:: Keep the window open after app closes
pause