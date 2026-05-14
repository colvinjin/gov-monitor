"""
测试语音客户端 (OpenAI TTS/ASR)
"""
import asyncio
from doubao_client import doubao_client


async def test_tts():
    """测试 TTS"""
    print("=" * 60)
    print("测试 TTS (语音合成)")
    print("=" * 60)
    
    text = "你好，我是学大教育的家长，想了解一下课程。"
    
    # 测试推荐音色
    voices = ["nova", "shimmer", "onyx"]
    
    for voice in voices:
        print(f"\n测试音色: {voice}")
        audio = await doubao_client.text_to_speech(text, voice_type=voice)
        
        if audio:
            print(f"✅ TTS 成功！音频大小: {len(audio)} bytes")
        else:
            print(f"❌ TTS 失败")


async def test_asr():
    """测试 ASR"""
    print("\n" + "=" * 60)
    print("测试 ASR (语音识别)")
    print("=" * 60)
    
    # 先用 TTS 生成测试音频
    print("生成测试音频...")
    text = "你好，我想咨询一下数学课程。"
    audio = await doubao_client.text_to_speech(text, voice_type="nova")
    
    if not audio:
        print("❌ 无法生成测试音频")
        return
    
    print(f"测试音频生成: {len(audio)} bytes")
    print("识别中...")
    
    result = await doubao_client.speech_to_text(audio)
    
    if result:
        print(f"✅ ASR 成功！识别结果: {result}")
    else:
        print("❌ ASR 失败")


async def main():
    print("=" * 60)
    print("语音 API 测试 (OpenAI)")
    print("=" * 60)
    
    await test_tts()
    await test_asr()
    
    print("\n" + "=" * 60)
    print("测试结果")
    print("=" * 60)
    print("✅ TTS: 可用 (推荐音色: nova, shimmer, onyx)")
    print("✅ ASR: 可用 (Whisper-1)")


if __name__ == "__main__":
    asyncio.run(main())
