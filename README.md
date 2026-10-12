# 🎓 AI Lecture Recorder

**Transform YouTube lectures into an intelligent, searchable knowledge base with AI-powered Q&A.**

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                    AI LECTURE RECORDER — PIPELINE                    │
├─────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  🎬 YouTube URL                                                       │
│       │                                                               │
│       ▼  [yt-dlp]                                                     │
│  🎧 MP3 Audio File                                                    │
│       │                                                               │
│       ▼  [Librosa]                                                    │
│  📈 Waveform Visualization                                            │
│       │                                                               │
│       ▼  [OpenAI Whisper]                                             │
│  📝 Text Transcript                                                   │
│       │                                                               │
│       ▼  [LangChain / Custom]                                         │
│  ✂️  Data Chunks (512 tokens, 64 overlap)                            │
│       │                                                               │
│       ▼  [sentence-transformers]                                      │
│  🔢 Vector Embeddings (384-dim)                                       │
│       │                                                               │
│       ▼  [FAISS]                                                      │
│  🗄️ Vector Store / Index                                             │
│       │                                                               │
│  ┌────┴──────────────────────────────────────────────────────────┐   │
│  │          🔍 ML SEARCH BLOCK — COSINE SIMILARITY               │   │
│  │                                                                │   │
│  │   User Query → Embed → cos(θ) = (A·B)/(‖A‖×‖B‖) → Top-K    │   │
│  └────────────────────────────────────────────────────────────────┘   │
│       │                                                               │
│       ▼  [PyTorch LSTM]                                               │
│  🧠 LSTM Context Memory                                               │
│       │  ├── Forget Gate: what to discard                            │
│       │  ├── Input Gate: what new info to store                      │
│       │  └── Output Gate: what to pass forward                       │
│       │                                                               │
│  ┌────┴──────────────────────────────────────────────────────────┐   │
│  │              🖥️ STREAMLIT UI                                   │   │
│  │   ┌─────────────────┐    ┌─────────────────────────────────┐  │   │
│  │   │  👤 User Auth   │    │     💬 Chat Interface           │  │   │
│  │   │  - Login        │    │     - Ask questions             │  │   │
│  │   │  - Register     │    │     - LSTM multi-turn memory    │  │   │
│  │   └─────────────────┘    └─────────────────────────────────┘  │   │
│  └────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 🚀 Quick Start

### 1. Clone & Install

```bash
git clone <repo-url>
cd ai_lecture_recorder
pip install -r requirements.txt
```

> **FFmpeg required:** `brew install ffmpeg` (Mac) | `sudo apt install ffmpeg` (Linux)

### 2. Run the App

```bash
streamlit run app.py
```

### 3. Use the App

1. Register/Login at the login screen
2. Go to **Process Video** → paste a YouTube URL
3. Wait for the pipeline to complete
4. Go to **AI Chat** → ask questions about the lecture!

---

## 📁 Project Structure

```
ai_lecture_recorder/
│
├── app.py                    # Main Streamlit application
│
├── utils/
│   ├── audio_processor.py    # YouTube → MP3 → Waveform → Transcript
│   └── vector_store.py       # Chunks → Embeddings → FAISS → Cosine Search
│
├── models/
│   └── lstm_chat.py          # LSTM context-aware chat manager
│
├── assets/                   # Static files (images, icons)
├── pages/                    # Additional Streamlit pages
├── components/               # Reusable UI components
│
├── requirements.txt
└── README.md
```

---

## 🔬 Key ML Concepts Used

### Cosine Similarity
```
cos(θ) = (A · B) / (‖A‖ × ‖B‖)

- Score = 1.0  →  Identical meaning
- Score = 0.0  →  Unrelated
- Score = -1.0 →  Opposite meaning
```

### LSTM Gating (Long Short-Term Memory)
```
Forget Gate:  f_t = σ(Wf · [h_{t-1}, x_t] + bf)
Input Gate:   i_t = σ(Wi · [h_{t-1}, x_t] + bi)
Cell Update:  c_t = f_t ⊙ c_{t-1} + i_t ⊙ tanh(Wc · [h_{t-1}, x_t] + bc)
Output Gate:  h_t = σ(Wo · [h_{t-1}, x_t] + bo) ⊙ tanh(c_t)
```

---

## 🛠️ Tech Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| Download | yt-dlp | YouTube audio extraction |
| Audio | FFmpeg + Librosa | MP3 + waveform analysis |
| STT | OpenAI Whisper | Speech → Text |
| Chunking | LangChain | Split transcript |
| Embeddings | sentence-transformers | Text → Vectors |
| Vector DB | FAISS | Fast similarity search |
| Search | Cosine Similarity | Semantic retrieval |
| Chat Memory | PyTorch LSTM | Context management |
| UI | Streamlit | Web interface |

---

## 📝 License

MIT License — Free to use and modify.

---

*Built with ❤️ using Streamlit, Whisper, FAISS, and PyTorch*
