"""最小请求测试当前 key 对哪些 DashScope TTS 模型有权限。"""
import os
from pathlib import Path

import dashscope
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")
dashscope.api_key = os.environ["DASHSCOPE_API_KEY"]

TEXT = "你好，这是一条语音合成权限测试。"


def try_qwen_tts(model: str, voice: str = "Cherry"):
    from dashscope.audio.qwen_tts import SpeechSynthesizer
    resp = SpeechSynthesizer.call(model=model, text=TEXT, voice=voice)
    if resp.status_code == 200 and resp.output and resp.output.audio:
        return True, f"audio url: {resp.output.audio['url'][:60]}..."
    return False, f"{resp.status_code} {getattr(resp, 'code', '')} {getattr(resp, 'message', '')}"


def try_cosyvoice(model: str, voice: str = "longxiaochun_v2"):
    from dashscope.audio.tts_v2 import SpeechSynthesizer
    syn = SpeechSynthesizer(model=model, voice=voice)
    audio = syn.call(TEXT)
    if audio:
        return True, f"got {len(audio)} bytes"
    return False, "no audio returned"


for name, fn in [
    ("qwen3-tts-flash", lambda: try_qwen_tts("qwen3-tts-flash")),
    ("qwen-tts", lambda: try_qwen_tts("qwen-tts")),
    ("cosyvoice-v2", lambda: try_cosyvoice("cosyvoice-v2")),
]:
    try:
        ok, msg = fn()
    except Exception as e:
        ok, msg = False, f"{type(e).__name__}: {e}"
    print(f"{'✓' if ok else '✗'} {name}: {msg}")
