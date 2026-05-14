"""
端到端测试 - 完整语音对话流程
测试: 语音输入 → ASR → 大模型 → TTS → 语音输出
"""
import asyncio
import base64
from doubao_client import doubao_client
from ai_parent import AIParent


async def test_e2e_voice_conversation():
    """测试完整语音对话流程"""
    print("=" * 70)
    print("🎓 学大咨询师训练系统 - 端到端测试")
    print("=" * 70)
    
    # 初始化 AI 家长
    ai_parent = AIParent()
    
    # 模拟咨询师语音输入
    consultant_messages = [
        "您好，我是学大教育的课程顾问，请问您孩子几年级了？",
        "初三数学确实关键，我们有很多成功案例，您孩子现在成绩怎么样？",
        "70分还有很大提升空间，我们有一对一和班课两种形式，您倾向哪种？"
    ]
    
    print(f"\n【家长性格】{ai_parent.get_traits_summary()}")
    print(f"【对话轮次】{len(consultant_messages)} 轮\n")
    
    for i, consultant_text in enumerate(consultant_messages, 1):
        print(f"\n{'='*70}")
        print(f"第 {i} 轮对话")
        print(f"{'='*70}")
        
        # 1. 模拟咨询师语音（用 TTS 生成音频）
        print(f"\n👨‍💼 咨询师: {consultant_text}")
        print("🎤 合成咨询师语音...")
        consultant_audio = await doubao_client.text_to_speech(
            consultant_text, 
            voice_type="onyx"
        )
        
        if consultant_audio:
            print(f"✅ 咨询师语音合成成功 ({len(consultant_audio)} bytes)")
        else:
            print("❌ 咨询师语音合成失败")
            continue
        
        # 2. ASR 识别（实际场景中是从麦克风接收）
        # 这里为了测试，我们直接用文字，但模拟 ASR 流程
        print("📝 ASR 识别...")
        recognized_text = await doubao_client.speech_to_text(consultant_audio)
        
        if recognized_text:
            print(f"✅ ASR 识别结果: {recognized_text}")
        else:
            print("❌ ASR 识别失败，使用原文")
            recognized_text = consultant_text
        
        # 3. AI 家长生成回复
        print("🤖 AI 家长思考中...")
        parent_response = await ai_parent.generate_response(recognized_text)
        print(f"👤 家长回复: {parent_response}")
        
        # 4. TTS 合成家长语音
        print("🔊 合成家长语音...")
        parent_audio = await doubao_client.text_to_speech(
            parent_response,
            voice_type="nova"  # 女性声音，像家长
        )
        
        if parent_audio:
            print(f"✅ 家长语音合成成功 ({len(parent_audio)} bytes)")
            # 保存测试音频
            filename = f"/tmp/test_e2e_round_{i}_parent.mp3"
            with open(filename, "wb") as f:
                f.write(parent_audio)
            print(f"💾 音频已保存: {filename}")
        else:
            print("❌ 家长语音合成失败")
    
    # 生成报告
    print(f"\n{'='*70}")
    print("📊 训练报告")
    print(f"{'='*70}")
    print(f"总对话轮次: {ai_parent.turn_count}")
    print(f"家长最终性格: {ai_parent.get_traits_summary()}")
    print(f"\n对话历史:")
    for turn in ai_parent.conversation_history:
        print(f"  咨询师: {turn['consultant']}")
        print(f"  家长:   {turn['parent']}")
        print()
    
    print("=" * 70)
    print("✅ 端到端测试完成！")
    print("=" * 70)


async def test_e2e_with_real_audio():
    """使用真实音频文件测试（如果有录音文件）"""
    print("\n" + "=" * 70)
    print("🎤 真实音频测试")
    print("=" * 70)
    
    # 先用 TTS 生成一个测试音频
    test_text = "你好，我想了解一下学大教育的数学课程。"
    print(f"\n生成测试音频: {test_text}")
    
    audio = await doubao_client.text_to_speech(test_text, voice_type="nova")
    if not audio:
        print("❌ 音频生成失败")
        return
    
    print(f"✅ 音频生成成功: {len(audio)} bytes")
    
    # ASR 识别
    print("\nASR 识别中...")
    recognized = await doubao_client.speech_to_text(audio)
    
    if recognized:
        print(f"✅ 识别结果: {recognized}")
        
        # AI 回复
        ai_parent = AIParent()
        response = await ai_parent.generate_response(recognized)
        print(f"🤖 AI 回复: {response}")
        
        # TTS 合成
        response_audio = await doubao_client.text_to_speech(response, voice_type="shimmer")
        if response_audio:
            print(f"✅ 回复语音合成成功: {len(response_audio)} bytes")
            with open("/tmp/test_real_audio_response.mp3", "wb") as f:
                f.write(response_audio)
            print("💾 已保存到 /tmp/test_real_audio_response.mp3")
    else:
        print("❌ ASR 识别失败")


async def main():
    """主测试函数"""
    print("\n" + "=" * 70)
    print("🚀 开始端到端测试")
    print("=" * 70)
    
    # 测试 1: 模拟对话流程
    await test_e2e_voice_conversation()
    
    # 测试 2: 真实音频流程
    await test_e2e_with_real_audio()
    
    print("\n" + "=" * 70)
    print("🎉 所有测试完成！")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
