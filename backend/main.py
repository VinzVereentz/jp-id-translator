import os, shutil, subprocess, tempfile, uuid, json
from pathlib import Path
from typing import List
from dotenv import load_dotenv
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from groq import Groq

load_dotenv()
API_KEY = os.getenv("GROQ_API_KEY")
if not API_KEY:
    raise RuntimeError("GROQ_API_KEY belum diisi. Buat file .env berdasarkan .env.example.")

TRANS_MODEL = os.getenv("GROQ_TRANSCRIPTION_MODEL", "whisper-large-v3-turbo")
TRANSLATE_MODEL = os.getenv("GROQ_TRANSLATION_MODEL", "llama-3.3-70b-versatile")
MAX_MB = int(os.getenv("MAX_UPLOAD_MB", "500"))
client = Groq(api_key=API_KEY)

app = FastAPI(title="JP-ID Subtitle Translator", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])

WORK = Path(tempfile.gettempdir()) / "jp_id_subtitle"
WORK.mkdir(exist_ok=True)

class Segment(BaseModel):
    id: int
    start: float
    end: float
    ja: str
    id_text: str

class TranslateRequest(BaseModel):
    segments: List[Segment]

def ffmpeg_available():
    return shutil.which("ffmpeg") is not None

def fmt_srt_time(sec: float):
    sec = max(0, sec)
    ms = int(round((sec - int(sec))*1000))
    total = int(sec)
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    if ms >= 1000:
        s += 1; ms = 0
        if s >= 60: s = 0; m += 1
        if m >= 60: m = 0; h += 1
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

def fmt_vtt_time(sec: float):
    sec = max(0, sec)
    h = int(sec//3600); m = int((sec%3600)//60); s = sec%60
    return f"{h:02d}:{m:02d}:{s:06.3f}"

def write_srt(segs, path):
    with open(path, "w", encoding="utf-8") as f:
        for i, x in enumerate(segs, 1):
            f.write(f"{i}\n{fmt_srt_time(x['start'])} --> {fmt_srt_time(x['end'])}\n{x['id_text'].strip()}\n\n")

def write_vtt(segs, path):
    with open(path, "w", encoding="utf-8") as f:
        f.write("WEBVTT\n\n")
        for x in segs:
            f.write(f"{fmt_vtt_time(x['start'])} --> {fmt_vtt_time(x['end'])}\n{x['id_text'].strip()}\n\n")

def extract_audio(src, dst):
    if not ffmpeg_available():
        raise HTTPException(500, "FFmpeg tidak ditemukan. Install FFmpeg dan pastikan masuk PATH.")
    p = subprocess.run(["ffmpeg","-y","-i",str(src),"-vn","-ac","1","-ar","16000","-c:a","mp3","-b:a","64k",str(dst)],
                       capture_output=True, text=True)
    if p.returncode != 0:
        raise HTTPException(500, "FFmpeg gagal mengekstrak audio.")

def transcribe(path):
    duration_probe = subprocess.run(["ffprobe","-v","error","-show_entries","format=duration",
                                     "-of","default=noprint_wrappers=1:nokey=1",str(path)],
                                    capture_output=True, text=True)
    try: duration = float(duration_probe.stdout.strip())
    except: duration = 0
    chunk_seconds = 300
    all_segments = []
    tempdir = path.parent / ("chunks_"+uuid.uuid4().hex)
    tempdir.mkdir()
    try:
        if duration > chunk_seconds + 1:
            if not ffmpeg_available(): raise HTTPException(500, "FFmpeg tidak ditemukan.")
            starts = range(0, int(duration)+1, chunk_seconds)
            for idx, start in enumerate(starts):
                out = tempdir / f"c{idx}.mp3"
                subprocess.run(["ffmpeg","-y","-ss",str(start),"-t",str(chunk_seconds),"-i",str(path),
                                "-ac","1","-ar","16000","-c:a","mp3","-b:a","64k",str(out)],
                               capture_output=True)
                if out.exists(): all_segments.extend(transcribe_one(out, offset=start))
        else:
            all_segments = transcribe_one(path, offset=0)
    finally:
        shutil.rmtree(tempdir, ignore_errors=True)
    return all_segments

def transcribe_one(path, offset=0):
    with open(path, "rb") as audio:
        result = client.audio.transcriptions.create(
            file=(path.name, audio.read()), model=TRANS_MODEL, language="ja",
            response_format="verbose_json", timestamp_granularities=["segment"], temperature=0
        )
    out=[]
    for i, seg in enumerate(getattr(result, "segments", []) or []):
        text = (getattr(seg, "text", "") or "").strip()
        if not text: continue
        out.append({"id": i+1, "start": float(seg.start)+offset,
                    "end": float(seg.end)+offset, "ja": text, "id_text": ""})
    return out

def translate_batch(items):
    if not items: return []
    numbered = "\n".join(f"{i}. {x['ja']}" for i,x in enumerate(items,1))
    prompt = """Translate the following Japanese subtitle lines into natural Indonesian.
Rules:
- Preserve the exact numbering.
- Return a JSON object with a single key \"translations\" whose value is an array of strings.
- The array must contain exactly one Indonesian translation per input line.
- Do not add explanations.
- Keep names, honorifics, and context natural.
- Do not merge or split lines.
Input:
""" + numbered
    r = client.chat.completions.create(
        model=TRANSLATE_MODEL, temperature=0.2,
        response_format={"type":"json_object"},
        messages=[{"role":"system","content":"You are a professional Japanese-to-Indonesian subtitle translator."},
                  {"role":"user","content":prompt}]
    )
    data = json.loads(r.choices[0].message.content)
    vals = data.get("translations")
    if not isinstance(vals,list) or len(vals) != len(items):
        raise ValueError("Format terjemahan dari model tidak sesuai.")
    return [str(v).strip() for v in vals]

def translate_all(segs):
    for i in range(0, len(segs), 25):
        batch=segs[i:i+25]
        try:
            vals=translate_batch(batch)
        except Exception:
            vals=[]
            for x in batch:
                r=client.chat.completions.create(
                    model=TRANSLATE_MODEL, temperature=0.2,
                    messages=[{"role":"system","content":"Translate Japanese to natural Indonesian. Return only the translation."},
                              {"role":"user","content":x["ja"]}]
                )
                vals.append(r.choices[0].message.content.strip())
        for x,v in zip(batch,vals): x["id_text"]=v
    return segs

@app.get("/api/health")
def health(): return {"ok": True, "transcription_model": TRANS_MODEL, "translation_model": TRANSLATE_MODEL}

@app.post("/api/translate")
async def translate(file: UploadFile = File(...)):
    if not file.filename: raise HTTPException(400,"File tidak valid.")
    ext=Path(file.filename).suffix.lower()
    allowed={".mp3",".wav",".m4a",".mp4",".mov",".webm",".mkv",".avi",".aac",".flac"}
    if ext not in allowed: raise HTTPException(400,"Format file tidak didukung.")
    job=WORK/uuid.uuid4().hex; job.mkdir()
    src=job/(Path(file.filename).stem+ext)
    with open(src,"wb") as f:
        total=0
        while chunk:=await file.read(1024*1024):
            total+=len(chunk)
            if total>MAX_MB*1024*1024:
                shutil.rmtree(job,ignore_errors=True)
                raise HTTPException(413,f"File terlalu besar. Maksimum {MAX_MB} MB.")
            f.write(chunk)
    audio=src
    if ext not in {".mp3",".wav",".m4a",".aac",".flac"}:
        audio=job/"audio.mp3"; extract_audio(src,audio)
    segs=transcribe(audio)
    if not segs: raise HTTPException(422,"Tidak ada ucapan yang berhasil dikenali.")
    segs=translate_all(segs)
    srt=job/"subtitle.srt"; vtt=job/"subtitle.vtt"
    write_srt(segs,srt); write_vtt(segs,vtt)
    return {"job_id":job.name,"filename":file.filename,"segments":segs,
            "srt_url":f"/api/download/{job.name}/srt","vtt_url":f"/api/download/{job.name}/vtt"}

@app.post("/api/retranslate")
def retranslate(req: TranslateRequest):
    segs=[x.model_dump() for x in req.segments]
    return {"segments":translate_all(segs)}

@app.get("/api/download/{job_id}/{kind}")
def download(job_id:str, kind:str):
    if kind not in {"srt","vtt"}: raise HTTPException(400,"Jenis file tidak valid.")
    p=WORK/job_id/f"subtitle.{kind}"
    if not p.exists(): raise HTTPException(404,"File tidak ditemukan.")
    return FileResponse(p, media_type="text/plain; charset=utf-8", filename=f"subtitle_ja-id.{kind}")
