"""把文章正文改编成双人播客对话稿。"""
import os

from openai import OpenAI

SYSTEM_PROMPT = """你是一档中文播客的编剧，要把一篇文章改编成两位主播的对话节目稿。

角色设定：
- A：女主播，节目主持人。负责开场、引导话题、替听众提问、追问、总结，语气好奇、有亲和力
- B：男主播，懂行的朋友。负责把文章内容讲清楚，爱举例子、打比方，语气松弛，像聊天不像念稿

要求：
- 输出格式：每句对话单独一行，以"A："或"B："开头，除对话外不要任何内容（不要标题、旁白、舞台说明、markdown）
- 对话要有来有回：接话、反问、恍然大悟、口头语（"诶""嗯""对对对""等会儿"），不要一人一大段轮流念稿
- 单轮别太长，一般不超过三四句话，长解释拆成多轮你来我往
- 英文术语、产品名、人名保留英文，其余用中文（英文文章也改成中文对话）
- 忽略文章里的链接、代码、广告推广、作者简介
- 关键事实、数字、观点忠于原文，不编造不夸大
- 长度跟原文信息量成比例，一般 2000～3500 字；A 开场一两句引入主题，结尾简短收束，不要喊口号"""

MAX_INPUT_CHARS = 30000


def stream_script(title: str, text: str):
    """流式生成对话稿，逐段 yield 文本增量。"""
    client = OpenAI(
        api_key=os.environ["DASHSCOPE_API_KEY"],
        base_url=os.getenv("LLM_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
    )
    stream = client.chat.completions.create(
        model=os.getenv("LLM_MODEL", "qwen3.7-plus"),
        temperature=0.8,
        stream=True,
        extra_body={"enable_thinking": False},  # 思考阶段不出字，前端会像卡死
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"文章标题：{title}\n\n文章正文：\n{text[:MAX_INPUT_CHARS]}"},
        ],
    )
    for chunk in stream:
        if chunk.choices and chunk.choices[0].delta.content:
            yield chunk.choices[0].delta.content
