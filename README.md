# article2audio 🎙️

贴一个文章 URL，两位 AI 主播把文章聊给你听——自建版"豆包播客"。

网页正文提取（trafilatura）→ Qwen 改编成双人对话稿（流式打字机展示）→ CosyVoice 双音色并行合成 + ffmpeg 拼接成一个 mp3。约 200 行 Python，无 LangChain。

## 本地运行

需要 [uv](https://docs.astral.sh/uv/) 和 ffmpeg（`brew install ffmpeg`）。

```bash
cp .env.example .env   # 填入 DASHSCOPE_API_KEY（阿里云百炼）
uv sync
uv run src/server.py   # 打开 http://localhost:8770
```

`.env` 可调模型与音色：

```
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1  # 任何 OpenAI 兼容接口均可
LLM_MODEL=qwen3.7-plus          # 对话稿模型
TTS_MODEL=cosyvoice-v2
TTS_VOICE_A=longxiaochun_v2     # 女主播
TTS_VOICE_B=longcheng_v2        # 男主播
```

提取失败的网站（反爬/需登录）可在页面上直接粘贴正文。生成的 mp3 和对话稿存 `out/`。

## Docker 部署

```bash
docker build -t article2audio .
docker run -d --name article2audio \
  -p 8770:8770 --env-file .env \
  -v $(pwd)/out:/app/out \
  --restart unless-stopped article2audio
```

注意：服务无鉴权，公网部署请挂反向代理加访问控制（否则任何人都能烧你的 API 额度），或只绑内网/用 SSH 隧道访问。

## 成本

按 DashScope 计费：一篇文章的对话稿改写约几分钱，语音合成（CosyVoice 约 2 元/万字符）一篇约 0.5～1 元。

## 测试 TTS 权限

换 key 后可先跑 `uv run src/test_tts_access.py` 确认对哪些 TTS 模型有权限。
