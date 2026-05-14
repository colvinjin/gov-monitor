"""
测试不同的 resource_id
"""
import asyncio
import httpx
import base64
from config import DOUBAO_API_KEY

async def test_with_resource(resource_id):
    """测试指定 resource_id"""
    print(f"\n测试 resource_id: {resource_id}")
    
    endpoint = "https://openspeech.bytedance.com/api/v3/tts/unidirectional/sse"
    headers = {
        "Authorization": f"Bearer;{DOUBAO_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "app_id": "4666302687",
        "resource_id": resource_id,
        "text": "你好，我是学大教育的家长。",
        "voice_type": "BV001_streaming",
        "speed": 1.0
    }
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                endpoint,
                headers=headers,
                json=payload,
                timeout=30.0
            )
            
            content = response.text
            print(f"状态: {response.status_code}")
            
            if "data:" in content:
                for line in content.split('\n'):
                    if line.startswith('data:'):
                        data = line[5:].strip()
                        try:
                            import json
                            json_data = json.loads(data)
                            print(f"响应: {json_data}")
                            
                            if "data" in json_data:
                                print(f"✅ 成功！获取音频 {len(json_data['data'])} bytes")
                                return True
                            elif "message" in json_data:
                                print(f"消息: {json_data.get('message')}")
                        except:
                            pass
                            
    except Exception as e:
        print(f"异常: {e}")
    
    return False

async def main():
    print("=" * 60)
    print("测试不同 resource_id")
    print("=" * 60)
    
    # 测试几个可能的 resource_id
    resources = [
        "volc.service_type.10029",  # 语音合成大模型
        "volc.megatts.concurr",      # 声音复刻
        "BV001_streaming",           # 音色ID直接作为resource_id
        "",                          # 空值
    ]
    
    for res in resources:
        if await test_with_resource(res):
            print(f"\n✅ 找到可用 resource_id: {res}")
            break
    else:
        print("\n❌ 测试的 resource_id 都不可用")
        print("\n建议：")
        print("1. 登录火山引擎控制台")
        print("2. 进入 豆包语音 → 音色管理")
        print("3. 查看已开通音色的 resource_id")

if __name__ == "__main__":
    asyncio.run(main())
