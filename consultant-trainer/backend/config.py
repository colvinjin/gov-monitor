import os
from dotenv import load_dotenv

load_dotenv()

# 豆包 API
DOUBAO_API_KEY = os.getenv("DOUBAO_API_KEY", "")
DOUBAO_TTS_ENDPOINT = os.getenv("DOUBAO_TTS_ENDPOINT", "")
DOUBAO_ASR_ENDPOINT = os.getenv("DOUBAO_ASR_ENDPOINT", "")

# Claude API (通过 Antigravity 或直连)
CLAUDE_API_KEY = os.getenv("CLAUDE_API_KEY", "")
CLAUDE_API_URL = os.getenv("CLAUDE_API_URL", "https://api.anthropic.com/v1/messages")

# 火山方舟 API
ARK_API_KEY = os.getenv("ARK_API_KEY", "")
ARK_TTS_ENDPOINT = os.getenv("ARK_TTS_ENDPOINT", "https://ark.cn-beijing.volces.com/api/v3/prediction/tts")
ARK_ASR_ENDPOINT = os.getenv("ARK_ASR_ENDPOINT", "https://ark.cn-beijing.volces.com/api/v3/prediction/asr")

# 豆包语音 V3 API
DOUBAO_APP_ID = os.getenv("DOUBAO_APP_ID", "4666302687")
DOUBAO_ACCESS_TOKEN = os.getenv("DOUBAO_ACCESS_TOKEN", "")
DOUBAO_SECRET_KEY = os.getenv("DOUBAO_SECRET_KEY", "")

# OpenAI API
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

# 服务配置
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))

# 验证配置
def check_config():
    missing = []
    if not DOUBAO_API_KEY:
        missing.append("DOUBAO_API_KEY")
    if not CLAUDE_API_KEY:
        missing.append("CLAUDE_API_KEY")
    return missing