# Learn Sphere AI

**An AI-powered learning platform that transforms YouTube lectures into searchable learning material with AI-powered Q&A.**

## Overview

Learn Sphere AI helps learners work with educational video content and access AI-assisted learning features.

## Architecture

The original project documentation describes this lecture-processing pipeline:

1. **YouTube audio extraction** using `yt-dlp`
2. **Audio processing** using FFmpeg and Librosa
3. **Speech transcription** using OpenAI Whisper
4. **Transcript chunking** for retrieval
5. **Text embeddings** using `sentence-transformers`
6. **Vector search** for finding relevant lecture content
7. **AI-assisted question answering** through a Streamlit interface

The exact implementation and technologies used by the current code should be verified against the source files.

## Quick Start

### 1. Clone the repository

```bash
git clone https://github.com/SumuCodes/Learn-Sphere-AI.git
cd Learn-Sphere-AI
```

### 2. Create a virtual environment

```bash
python -m venv venv
```

Activate it on Windows:

```powershell
.\venv\Scripts\Activate.ps1
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

FFmpeg may also be required for audio-processing features. Install it using the appropriate method for your operating system.

### 4. Run the application

```bash
streamlit run app.py
```

You can also check `run_app.bat` for the project's Windows launch instructions.

## Project Structure

```text
Learn-Sphere-AI/
├── app.py
├── app_pages/
├── assets/
├── components/
├── models/
├── styles/
├── utils/
├── config.py
├── requirements.txt
├── run_app.bat
└── README.md
```

## Technologies

The project source and original documentation reference technologies including:

- Python
- Streamlit
- `yt-dlp`
- FFmpeg and Librosa
- OpenAI-compatible API integrations
- Transcript processing and vector retrieval

See `requirements.txt` and the implementation files for the project's dependencies and details.

## API Keys and Privacy

Configure API keys through the application's supported settings rather than committing credentials to the repository.

**Never commit API keys, passwords, private keys, local user databases, or personal data.**

## License

No license has been specified in this repository yet. Add a license file if you intend to define the terms under which others may use or modify the project.