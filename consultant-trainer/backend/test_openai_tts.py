"""
测试 OpenAI TTS API
"""
import asyncio
from openai_tts_client import openai_tts_client


async def test_tts():
    """测试 TTS"""
    print("=" * 60)
    print("测试 OpenAI TTS (语音合成)")
    print("=" * 60)
    
    text = "你好，我是学大教育的家长，想了解一下课程。"
    
    # 测试不同音色
    voices = ["alloy", "echo", "fable", "onyx", "nova", "shimmer"]
    
    for voice in voices:
        print(f"\n测试音色: {voice}")
        audio = await openai_tts_client.text_to_speech(text, voice=voice)
        
        if audio:
            print(f"✅ TTS 成功！音频大小: {len(audio)} bytes")
            # 保存测试文件
            filename = f"/tmp/test_tts_{voice}.mp3"
            with open(filename, "wb") as f:
                f.write(audio)
            print(f"✅ 音频已保存到 {filename}")
        else:
            print(f"❌ TTS 失败")


async def test_asr():
    """测试 ASR"""
    print("\n" + "=" * 60)
    print("测试 OpenAI ASR (语音识别)")
    print("=" * 60)
    
    # 先用 TTS 生成测试音频
    print("生成测试音频...")
    text = "你好，我想咨询一下数学课程。"
    audio = await openai_tts_client.text_to_speech(text, voice="nova")
    
    if not audio:
        print("❌ 无法生成测试音频")
        return
    
    print(f"测试音频生成: {len(audio)} bytes")
    print("识别中...")
    
    result = await openai_tts_client.speech_to_text(audio)
    
    if result:
        print(f"✅ ASR 成功！识别结果: {result}")
    else:
        print("❌ ASR 失败")


async def main():
    print("=" * 60)
    print("OpenAI TTS/ASR API 测试")
    print("=" * 60)
    
    await test_tts()
    await test_asr()
    
    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
