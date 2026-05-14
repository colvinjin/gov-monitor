"""
OpenAI TTS 客户端
使用 OpenAI 的文本转语音 API
"""
import httpx
from typing import Optional
from config import OPENAI_API_KEY


class OpenAITTSClient:
    def __init__(self):
        self.api_key = OPENAI_API_KEY
        self.base_url = "https://api.openai.com/v1"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
    
    async def text_to_speech(
        self,
        text: str,
        voice: str = "nova",
        model: str = "tts-1",
        speed: float = 1.0
    ) -> Optional[bytes]:
        """
        文字转语音 (OpenAI TTS API)
        
        Args:
            text: 要合成的文本
            voice: 音色 (alloy, echo, fable, onyx, nova, shimmer)
            model: 模型 (tts-1, tts-1-hd)
            speed: 语速 (0.25 - 4.0)
        """
        try:
            payload = {
                "model": model,
                "input": text,
                "voice": voice,
                "speed": speed,
                "response_format": "mp3"
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/audio/speech",
                    headers=self.headers,
                    json=payload,
                    timeout=60.0
                )
                response.raise_for_status()
                
                return response.content
                    
        except Exception as e:
            print(f"OpenAI TTS error: {e}")
            return None
    
    async def speech_to_text(self, audio_bytes: bytes, model: str = "whisper-1") -> Optional[str]:
        """
        语音转文字 (OpenAI Whisper API)
        
        Args:
            audio_bytes: 音频数据
            model: 模型 (whisper-1)
        """
        try:
            import io
            
            async with httpx.AsyncClient() as client:
                files = {
                    "file": ("audio.mp3", io.BytesIO(audio_bytes), "audio/mpeg")
                }
                data = {
                    "model": model,
                    "language": "zh"
                }
                
                # 注意：文件上传需要特殊处理 headers
                headers = {
                    "Authorization": f"Bearer {self.api_key}"
                }
                
                response = await client.post(
                    f"{self.base_url}/audio/transcriptions",
                    headers=headers,
                    files=files,
                    data=data,
                    timeout=60.0
                )
                response.raise_for_status()
                
                result = response.json()
                return result.get("text")
                    
        except Exception as e:
            print(f"OpenAI ASR error: {e}")
            return None


# 单例实例
openai_tts_client = OpenAITTSClient()
