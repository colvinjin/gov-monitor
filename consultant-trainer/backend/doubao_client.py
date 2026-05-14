"""
语音客户端 - TTS + ASR
使用 OpenAI TTS/Whisper API（豆包语音备用）
"""
import httpx
import io
from typing import Optional, Tuple
from config import OPENAI_API_KEY


class DoubaoClient:
    """语音客户端（使用 OpenAI API）"""
    
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
        voice_type: str = "nova",
        speed: float = 1.0
    ) -> Optional[bytes]:
        """
        文字转语音 (OpenAI TTS API)
        
        Args:
            text: 要合成的文本
            voice_type: 音色 (alloy, echo, fable, onyx, nova, shimmer)
            speed: 语速 (0.25 - 4.0)
        
        Returns:
            MP3 格式的音频数据
        """
        try:
            payload = {
                "model": "tts-1",
                "input": text,
                "voice": voice_type,
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
            print(f"TTS error: {e}")
            return None
    
    async def speech_to_text(
        self,
        audio_bytes: bytes,
        audio_format: str = "webm"
    ) -> Optional[str]:
        """
        语音转文字 (OpenAI Whisper API)
        
        Args:
            audio_bytes: 音频数据 (支持 mp3, mp4, mpeg, mpga, m4a, wav, webm)
            audio_format: 音频格式标识（如 webm / wav / mp3）
        
        Returns:
            识别出的文本
        """
        try:
            # 文件上传需要特殊处理 headers（去掉 Content-Type）
            headers = {
                "Authorization": f"Bearer {self.api_key}"
            }
            
            filename, content_type = self._resolve_audio_meta(audio_format)
            files = {
                "file": (filename, io.BytesIO(audio_bytes), content_type)
            }
            data = {
                "model": "whisper-1",
                "language": "zh"
            }
            
            async with httpx.AsyncClient() as client:
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
            print(f"ASR error: {e}")
            return None

    def _resolve_audio_meta(self, audio_format: str) -> Tuple[str, str]:
        fmt = (audio_format or "webm").lower()
        mapping = {
            "webm": ("audio.webm", "audio/webm"),
            "wav": ("audio.wav", "audio/wav"),
            "mp3": ("audio.mp3", "audio/mpeg"),
            "m4a": ("audio.m4a", "audio/mp4"),
        }
        return mapping.get(fmt, (f"audio.{fmt}", "application/octet-stream"))


# 单例实例
doubao_client = DoubaoClient()
