"""
测试 volc.service_type 格式的 resource_id
"""
import asyncio
import httpx
import base64
import uuid
import json

APP_ID = "4666302687"
ACCESS_TOKEN = "WjA2KweOU11r-KhqrhofgukUVcBTOmr3"

# 测试不同的 resource_id
RESOURCE_IDS = [
    "volc.service_type.10029",  # 豆包语音 1.0
    "volc.service_type.10048",  # 豆包语音 1.0 并发版
    "volc.service_type.10050",  # 播客语音合成
]

async def test_resource(resource_id):
    """测试指定 resource_id"""
    print(f"\n{'='*60}")
    print(f"测试 resource_id: {resource_id}")
    print(f"{'='*60}")
    
    headers = {
        "Authorization": f"Bearer;{ACCESS_TOKEN}",
        "Resource-Id": resource_id,
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
            
            if "data:" in content:
                for line in content.split('\n'):
                    if line.startswith('data:'):
                        data = line[5:].strip()
                        try:
                            json_data = json.loads(data)
                            print(f"响应: {json_data}")
                            
                            if "data" in json_data and json_data["data"]:
                                print(f"✅ 成功！音频长度: {len(json_data['data'])} bytes")
                                return True
                            elif "code" in json_data:
                                print(f"错误码: {json_data['code']}, 消息: {json_data.get('message')}")
                        except:
                            pass
            else:
                print(f"响应: {content[:500]}")
                            
    except Exception as e:
        print(f"异常: {e}")
    
    return False

async def main():
    print("=" * 60)
    print("测试不同的 resource_id")
    print("=" * 60)
    
    for resource_id in RESOURCE_IDS:
        success = await test_resource(resource_id)
        if success:
            print(f"\n🎉 找到可用的 resource_id: {resource_id}")
            break

if __name__ == "__main__":
    asyncio.run(main())
