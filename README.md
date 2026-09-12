# JP → ID Subtitle Translator

A ready-to-run Japanese audio/video translator using Groq for transcription and translation.

## Requirements
- Python 3.10+
- Node.js 18+
- FFmpeg installed and available in PATH
- Groq API key

## Backend
```bash
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate
# Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
copy .env.example .env   # Windows
# cp .env.example .env   # Linux/macOS
# edit .env and add GROQ_API_KEY
uvicorn main:app --reload --port 8000
```

## Frontend
```bash
cd frontend
npm install
npm run dev
```
Open http://localhost:5173

## Notes
- Upload: mp3, wav, m4a, mp4, mov, webm, mkv, avi, aac, flac.
- The backend extracts audio from video with FFmpeg.
- Whisper timestamps are preserved and converted to SRT/VTT.
- Long audio is split into chunks to avoid oversized requests.
- Groq API key stays on the backend.

## Deployment architecture
GitHub stores the source code. The React frontend can be deployed to a static host such as Vercel/Netlify, while the FastAPI backend needs a server/container because it runs Python, FFmpeg, and Groq API calls. GitHub Pages alone cannot run this backend.

For a deployed frontend, set `VITE_API_URL` to the public backend URL. Never put `GROQ_API_KEY` in frontend code or GitHub.
