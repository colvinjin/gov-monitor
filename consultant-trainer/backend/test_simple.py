"""
简化测试 - 尝试不同的认证方式
"""
import asyncio
import httpx
import base64
import uuid
import json

APP_ID = "4666302687"
ACCESS_TOKEN = "WjA2KweOU11r-KhqrhofgukUVcBTOmr3"
TTS_RESOURCE_ID = "seed-tts-2.0"

async def test_bearer():
    """测试 Bearer Token 方式"""
    print("=" * 60)
    print("测试 Bearer Token 认证")
    print("=" * 60)
    
    headers = {
        "Authorization": f"Bearer;{ACCESS_TOKEN}",
        "Resource-Id": TTS_RESOURCE_ID,
        "Content-Type": "application/json"
    }
    
    payload = {
        "app": {
            "appid": APP_ID,
            "token": "access_token",
            "cluster": "volcengine"
        },
        "user": {
            "uid": "388808087185088"
        },
        "audio": {
            "voice_type": "BV001_streaming",
            "encoding": "mp3",
            "speed_ratio": 1.0,
            "volume_ratio": 1.0
        },
        "request": {
            "reqid": str(uuid.uuid4()),
            "text": "你好，我是学大教育的家长。",
            "operation": "query"
        }
    }
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://openspeech.bytedance.com/api/v3/tts/unidirectional/sse",
                headers=headers,
                json=payload,
                timeout=30.0
            )
            
            print(f"状态码: {response.status_code}")
            content = response.text
            print(f"响应: {content[:1000]}")
            
    except Exception as e:
        print(f"异常: {e}")

async def test_x_api_key():
    """测试 X-Api-Key 方式"""
    print("\n" + "=" * 60)
    print("测试 X-Api-Key 认证")
    print("=" * 60)
    
    headers = {
        "X-Api-Key": ACCESS_TOKEN,
        "X-Api-Resource-Id": TTS_RESOURCE_ID,
        "X-Api-Request-Id": str(uuid.uuid4()),
        "Content-Type": "application/json"
    }
    
    payload = {
        "app": {
            "appid": APP_ID,
            "token": "access_token",
            "cluster": "volcengine"
        },
        "user": {
            "uid": "388808087185088"
        },
        "audio": {
            "voice_type": "BV001_streaming",
            "encoding": "mp3",
            "speed_ratio": 1.0,
            "volume_ratio": 1.0
        },
        "request": {
            "reqid": str(uuid.uuid4()),
            "text": "你好，我是学大教育的家长。",
            "operation": "query"
        }
    }
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://openspeech.bytedance.com/api/v3/tts/unidirectional/sse",
                headers=headers,
                json=payload,
                timeout=30.0
            )
            
            print(f"状态码: {response.status_code}")
            content = response.text
            print(f"响应: {content[:1000]}")
            
    except Exception as e:
        print(f"异常: {e}")

async def main():
    await test_bearer()
    await test_x_api_key()

if __name__ == "__main__":
    asyncio.run(main())
