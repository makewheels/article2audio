"""对话稿按角色分配音色，并行合成后拼接成单个 mp3。"""
import os
import re
import subprocess
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import dashscope
from dashscope.audio.tts_v2 import SpeechSynthesizer

TURN_LIMIT = 800   # 单次合成的安全字符数
MAX_WORKERS = 3    # cosyvoice 默认并发限制内
GAP_SECONDS = 0.25 # 两轮对话之间的停顿

LINE_RE = re.compile(r"^\s*([AB])\s*[：:]\s*(.*)$")


def _split_long(text: str) -> list[str]:
    parts = []
    while len(text) > TURN_LIMIT:
        cut = max((text.rfind(c, 0, TURN_LIMIT) for c in "。！？；"), default=-1)
        cut = cut + 1 if cut > 0 else TURN_LIMIT
        parts.append(text[:cut])
        text = text[cut:].strip()
    if text:
        parts.append(text)
    return parts


def parse_dialogue(script: str) -> list[tuple[str, str]]:
    """解析成 [(speaker, text)]；没有 A:/B: 标记的稿子整体当 A 单人朗读。"""
    turns: list[tuple[str, str]] = []
    for raw in script.splitlines():
        line = raw.strip()
        if not line:
            continue
        m = LINE_RE.match(line)
        if m and m.group(2).strip():
            sp, txt = m.group(1), m.group(2).strip()
            if turns and turns[-1][0] == sp:
                turns[-1] = (sp, turns[-1][1] + "\n" + txt)
            else:
                turns.append((sp, txt))
        elif turns:
            turns[-1] = (turns[-1][0], turns[-1][1] + "\n" + line)
        else:
            turns.append(("A", line))
    out = []
    for sp, txt in turns:
        out.extend((sp, piece) for piece in _split_long(txt))
    return out


def _synth_one(model: str, voice: str, text: str) -> bytes:
    last_err = None
    for attempt in range(2):
        try:
            audio = SpeechSynthesizer(model=model, voice=voice).call(text)
            if audio:
                return audio
            last_err = RuntimeError("无音频返回")
        except Exception as e:
            last_err = e
        time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"合成失败: {last_err}")


def _concat(parts: list[Path], out_path: Path, tmp: Path):
    rate = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "a:0",
         "-show_entries", "stream=sample_rate", "-of", "default=nw=1:nk=1", str(parts[0])],
        check=True, capture_output=True, text=True,
    ).stdout.strip() or "22050"
    silence = tmp / "silence.mp3"
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", f"anullsrc=r={rate}:cl=mono",
         "-t", str(GAP_SECONDS), "-c:a", "libmp3lame", "-b:a", "64k", str(silence)],
        check=True, capture_output=True,
    )
    concat_list = tmp / "list.txt"
    lines = []
    for i, p in enumerate(parts):
        if i:
            lines.append(f"file '{silence}'\n")
        lines.append(f"file '{p}'\n")
    concat_list.write_text("".join(lines))
    subprocess.run(
        ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_list),
         "-c:a", "libmp3lame", "-q:a", "2", str(out_path)],
        check=True, capture_output=True,
    )


def synthesize_iter(script: str, out_path: Path):
    """并行合成各轮对话，每完成一轮 yield {done, total}，最后写出 mp3。"""
    dashscope.api_key = os.environ["DASHSCOPE_API_KEY"]
    model = os.getenv("TTS_MODEL", "cosyvoice-v2")
    voices = {
        "A": os.getenv("TTS_VOICE_A", "longxiaochun_v2"),
        "B": os.getenv("TTS_VOICE_B", "longcheng_v2"),
    }
    turns = parse_dialogue(script)
    total = len(turns)
    if not total:
        raise RuntimeError("讲稿为空")
    yield {"done": 0, "total": total}

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        parts: list[Path | None] = [None] * total
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
            futs = {
                pool.submit(_synth_one, model, voices[sp], txt): i
                for i, (sp, txt) in enumerate(turns)
            }
            done = 0
            for fut in as_completed(futs):
                i = futs[fut]
                part = tmp / f"part{i:03d}.mp3"
                part.write_bytes(fut.result())
                parts[i] = part
                done += 1
                yield {"done": done, "total": total}

        out_path.parent.mkdir(parents=True, exist_ok=True)
        if total == 1:
            out_path.write_bytes(parts[0].read_bytes())
        else:
            _concat(parts, out_path, tmp)


def safe_filename(title: str) -> str:
    name = re.sub(r'[\\/:*?"<>|\s]+', "_", title).strip("_")
    return name[:60] or "untitled"
