"""文章 URL → 语音讲解，本地网页服务。

用法:
  uv run server.py          # 打开 http://localhost:8770
"""
import os
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

import json

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from extract import fetch_article
from script_gen import stream_script
from tts import safe_filename, synthesize_iter

ROOT = Path(__file__).parent
OUT = ROOT / "out"
OUT.mkdir(exist_ok=True)

app = FastAPI()


class ExtractReq(BaseModel):
    url: str


class ScriptReq(BaseModel):
    title: str
    text: str


class TtsReq(BaseModel):
    title: str
    script: str


@app.post("/api/extract")
def api_extract(req: ExtractReq):
    try:
        return fetch_article(req.url.strip())
    except Exception as e:
        raise HTTPException(422, detail=str(e))


@app.post("/api/script")
def api_script(req: ScriptReq):
    if len(req.text.strip()) < 50:
        raise HTTPException(422, detail="正文太短")
    return StreamingResponse(
        stream_script(req.title, req.text), media_type="text/plain; charset=utf-8"
    )


@app.post("/api/tts")
def api_tts(req: TtsReq):
    stem = f"{datetime.now():%Y%m%d}-{safe_filename(req.title)}"
    mp3 = OUT / f"{stem}.mp3"

    def gen():
        try:
            for evt in synthesize_iter(req.script, mp3):
                yield json.dumps(evt) + "\n"
            (OUT / f"{stem}.md").write_text(f"# {req.title}\n\n{req.script}", encoding="utf-8")
            yield json.dumps({"audio_url": f"/audio/{mp3.name}", "file": mp3.name}) + "\n"
        except Exception as e:
            yield json.dumps({"error": str(e)}, ensure_ascii=False) + "\n"

    return StreamingResponse(gen(), media_type="application/x-ndjson")


@app.get("/api/history")
def api_history():
    files = sorted(OUT.glob("*.mp3"), key=lambda p: p.stat().st_mtime, reverse=True)
    return [
        {"file": p.name, "audio_url": f"/audio/{p.name}",
         "size_mb": round(p.stat().st_size / 1048576, 1),
         "date": datetime.fromtimestamp(p.stat().st_mtime).strftime("%Y-%m-%d %H:%M")}
        for p in files
    ]


@app.get("/")
def index():
    return FileResponse(ROOT / "static" / "index.html")


app.mount("/audio", StaticFiles(directory=OUT), name="audio")

if __name__ == "__main__":
    uvicorn.run(app, host=os.getenv("HOST", "127.0.0.1"), port=int(os.getenv("PORT", "8770")))
