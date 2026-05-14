"""
FastAPI 主服务 - WebSocket 语音对话
"""
import asyncio
import json
import base64
import uuid
import contextlib
from datetime import datetime
from typing import Dict
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from contextlib import asynccontextmanager

from config import check_config, PORT, HOST
from doubao_client import doubao_client
from ai_parent import AIParent
from evaluator import ConversationEvaluator
from scenarios import list_parent_types, list_scenarios, PARENT_TYPES, SCENARIOS
from screenshot import capture_training_interface, capture_conversation
from storage import storage


# 存储活跃会话
sessions: Dict[str, dict] = {}

ASR_TIMEOUT_SECONDS = 45
AI_RESPONSE_TIMEOUT_SECONDS = 35
EVALUATION_TIMEOUT_SECONDS = 20
TTS_TIMEOUT_SECONDS = 35


async def send_json_safe(websocket: WebSocket, payload: dict) -> bool:
    """安全发送 JSON，避免连接断开时抛异常打断主流程"""
    try:
        await websocket.send_json(payload)
        return True
    except Exception as e:
        print(f"发送消息失败: {e}")
        return False


async def send_parent_audio_safe(websocket: WebSocket, audio_bytes: bytes) -> bool:
    if not audio_bytes:
        return False
    return await send_json_safe(
        websocket,
        {
            "type": "parent_audio",
            "data": base64.b64encode(audio_bytes).decode("utf-8")
        }
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    """服务生命周期管理"""
    # 启动检查
    missing = check_config()
    if missing:
        print(f"⚠️  缺少配置: {', '.join(missing)}")
        print("请复制 .env.example 为 .env 并填写 API Key")
    else:
        print("✅ 配置检查通过")
    
    yield
    
    # 清理
    sessions.clear()


app = FastAPI(title="学大咨询师训练系统", lifespan=lifespan)

# 静态文件服务
app.mount("/static", StaticFiles(directory="../frontend"), name="static")


@app.get("/", response_class=HTMLResponse)
async def get_index():
    """主页面"""
    return """<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>学大咨询师训练系统</title>
    <style>
        body { font-family: -apple-system, sans-serif; max-width: 1180px; margin: 30px auto; padding: 20px; background: #f5f7fb; }
        h1, h3 { color: #333; }
        .layout { display: grid; grid-template-columns: minmax(0, 2fr) minmax(320px, 1fr); gap: 20px; align-items: start; }
        .panel { background: white; border-radius: 12px; box-shadow: 0 8px 24px rgba(15,23,42,0.06); padding: 20px; }
        .status { padding: 15px; border-radius: 8px; margin: 20px 0; }
        .status.ok { background: #d4edda; color: #155724; }
        .status.error { background: #f8d7da; color: #721c24; }
        button { padding: 12px 20px; font-size: 15px; cursor: pointer; border-radius: 8px; border: none; }
        .primary { background: #007bff; color: white; }
        .primary:hover { background: #0056b3; }
        .danger { background: #dc3545; color: white; }
        .danger:hover { background: #c82333; }
        .ghost { background: #eef2ff; color: #334155; }
        #conversation { margin: 20px 0; padding: 20px; background: #f8f9fa; border-radius: 8px; min-height: 260px; max-height: 70vh; overflow: auto; }
        .message { margin: 10px 0; padding: 10px; border-radius: 8px; }
        .consultant { background: #007bff; color: white; text-align: right; }
        .parent { background: #e9ecef; color: #333; }
        #controls { margin: 20px 0; display: flex; gap: 12px; flex-wrap: wrap; }
        .recording { animation: pulse 1s infinite; }
        .session-list { display: flex; flex-direction: column; gap: 10px; margin-top: 12px; }
        .session-item { border: 1px solid #e5e7eb; border-radius: 10px; padding: 12px; cursor: pointer; transition: all .2s ease; }
        .session-item:hover { border-color: #93c5fd; background: #f8fbff; }
        .session-meta { color: #64748b; font-size: 13px; margin-top: 6px; }
        .badge { display: inline-block; padding: 4px 8px; border-radius: 999px; font-size: 12px; background: #eef2ff; color: #3730a3; margin-right: 6px; }
        .score { font-weight: 700; }
        .empty { color: #94a3b8; padding: 10px 0; }
        @keyframes pulse { 0% { opacity: 1; } 50% { opacity: 0.5; } 100% { opacity: 1; } }
        @media (max-width: 900px) { .layout { grid-template-columns: 1fr; } }
    </style>
</head>
<body>
    <h1>🎓 学大咨询师训练系统</h1>
    <div class="layout">
        <div class="panel">
            <div id="status" class="status">正在连接...</div>
            
            <div id="config" style="margin: 20px 0; padding: 20px; background: #f8f9fa; border-radius: 8px;">
                <h3>选择训练配置</h3>
                <div style="margin: 15px 0;">
                    <label>家长类型：</label>
                    <select id="parentType" style="padding: 8px; font-size: 14px;">
                        <option value="anxious">焦虑型 - 急于看到效果</option>
                        <option value="price_sensitive">价格敏感型 - 经常砍价</option>
                        <option value="picky">挑剔型 - 对质量要求高</option>
                        <option value="hesitant">犹豫型 - 难以做决定</option>
                        <option value="confident">自信型 - 积极配合</option>
                        <option value="defensive">防御型 - 担心风险</option>
                    </select>
                </div>
                <div style="margin: 15px 0;">
                    <label>场景模式：</label>
                    <select id="scenario" style="padding: 8px; font-size: 14px;">
                        <option value="first_visit">首访咨询 - 第一次接触</option>
                        <option value="trial_followup">试听后跟进 - 回访转化</option>
                        <option value="renewal">续费沟通 - 老学员续费</option>
                        <option value="referral">转介绍 - 口碑推荐</option>
                        <option value="complaint">投诉处理 - 危机沟通</option>
                        <option value="price_negotiation">价格谈判 - 专门议价</option>
                    </select>
                </div>
            </div>
            
            <div id="controls">
                <button id="startBtn" class="primary" onclick="startTraining()">开始训练</button>
                <button id="recordBtn" class="danger" style="display:none;" 
                        onmousedown="startRecording()" onmouseup="stopRecording()"
                        ontouchstart="startRecording()" ontouchend="stopRecording()">
                    🎤 按住说话
                </button>
                <button id="textModeBtn" class="ghost" style="display:none;" onclick="toggleTextMode()">⌨️ 文字模式</button>
                <button id="endBtn" style="display:none;" onclick="endTraining()">结束通话</button>
                <button class="ghost" onclick="loadSessionList()">刷新历史</button>
            </div>
            <div id="textInput" style="display:none; margin: 10px 0;">
                <input id="textMsg" type="text" placeholder="输入你的回复..." style="width: 75%; padding: 10px; font-size: 14px; border: 1px solid #ddd; border-radius: 8px;" onkeydown="if(event.key==='Enter') sendText()">
                <button class="primary" onclick="sendText()" style="margin-left: 8px;">发送</button>
            </div>
            
            <div id="conversation"></div>
        </div>

        <div class="panel">
            <h3>📚 训练历史</h3>
            <div id="historySummary" class="session-meta">正在加载训练记录...</div>
            <div id="sessionList" class="session-list"></div>
        </div>
    </div>
    
    <script src="/static/app.js"></script>
</body>
</html>"""


@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    """WebSocket 语音对话"""
    await websocket.accept()
    
    # 等待客户端发送配置
    config_msg = await websocket.receive_text()
    config_data = json.loads(config_msg)
    
    # 初始化会话（等待客户端发送配置）
    ai_parent = AIParent()  # 临时实例，会被配置消息替换
    sessions[session_id] = {
        "websocket": websocket,
        "ai_parent": ai_parent,
        "audio_buffer": b"",
        "evaluator": ConversationEvaluator(),  # 每个会话独立评估器
        "created_at": datetime.now().isoformat(),
        "parent_type": "anxious",
        "scenario": "first_visit",
    }
    
    print(f"会话 {session_id} 已连接")
    
    try:
        # 等待配置消息
        config_received = False
        while not config_received:
            message = await websocket.receive_text()
            data = json.loads(message)
            
            if data.get("type") == "config":
                parent_type = data.get("parent_type", "anxious")
                scenario = data.get("scenario", "first_visit")
                
                # 重新初始化 AI 家长
                ai_parent = AIParent(parent_type=parent_type, scenario=scenario)
                sessions[session_id]["ai_parent"] = ai_parent
                sessions[session_id]["parent_type"] = parent_type
                sessions[session_id]["scenario"] = scenario
                
                # 发送开场白
                opening = ai_parent.parent_config["opening_lines"][0]
                await send_json_safe(websocket, {
                    "type": "parent_text",
                    "text": opening
                })
                
                # 合成开场白语音（失败不阻断训练）
                try:
                    opening_audio = await asyncio.wait_for(
                        doubao_client.text_to_speech(opening),
                        timeout=TTS_TIMEOUT_SECONDS
                    )
                    if opening_audio:
                        await send_parent_audio_safe(websocket, opening_audio)
                    else:
                        await send_json_safe(websocket, {
                            "type": "warning",
                            "message": "开场语音暂时不可用，已切换为文字模式继续训练"
                        })
                except asyncio.TimeoutError:
                    await send_json_safe(websocket, {
                        "type": "warning",
                        "message": "开场语音生成超时，已切换为文字模式继续训练"
                    })
                except Exception as e:
                    print(f"开场语音失败: {e}")
                    await send_json_safe(websocket, {
                        "type": "warning",
                        "message": "开场语音生成失败，已切换为文字模式继续训练"
                    })
                
                config_received = True
        
        while True:
            # 接收消息
            message = await websocket.receive_text()
            data = json.loads(message)
            
            msg_type = data.get("type")
            
            if msg_type == "audio":
                # 接收语音数据
                audio_base64 = data.get("data", "")
                try:
                    audio_bytes = base64.b64decode(audio_base64)
                except Exception:
                    await send_json_safe(websocket, {
                        "type": "error",
                        "message": "收到的音频数据损坏，请重新录音"
                    })
                    continue
                sessions[session_id]["audio_buffer"] += audio_bytes
                
            elif msg_type == "text":
                # 文字输入模式（麦克风不可用时的备用）
                consultant_text = data.get("text", "").strip()
                if not consultant_text:
                    continue
                if not await send_json_safe(websocket, {"type": "consultant_text", "text": consultant_text}):
                    break
                # 复用下方 AI 回复逻辑
                try:
                    parent_response = await asyncio.wait_for(
                        sessions[session_id]["ai_parent"].generate_response(consultant_text),
                        timeout=AI_RESPONSE_TIMEOUT_SECONDS
                    )
                except asyncio.TimeoutError:
                    await send_json_safe(websocket, {"type": "error", "message": "AI 回复超时，请重试"})
                    continue
                await send_json_safe(websocket, {"type": "parent_text", "text": parent_response})
                try:
                    parent_audio = await asyncio.wait_for(
                        doubao_client.text_to_speech(parent_response),
                        timeout=TTS_TIMEOUT_SECONDS
                    )
                    await send_parent_audio_safe(websocket, parent_audio)
                except Exception:
                    pass
                try:
                    evaluation = await asyncio.wait_for(
                        sessions[session_id]["evaluator"].evaluate_turn(
                            consultant_text, parent_response,
                            sessions[session_id]["ai_parent"].turn_count,
                            sessions[session_id]["ai_parent"].get_traits()
                        ),
                        timeout=EVALUATION_TIMEOUT_SECONDS
                    )
                    await send_json_safe(websocket, {"type": "evaluation", "data": evaluation})
                    # B: 动态突变 — 根据本轮评分调整家长态度
                    scores = evaluation.get("scores", {})
                    if scores:
                        avg = sum(scores.values()) / len(scores)
                        sessions[session_id]["ai_parent"].update_attitude(avg)
                except Exception:
                    pass

            elif msg_type == "audio_end":
                # 语音结束，开始处理
                audio_data = sessions[session_id]["audio_buffer"]
                sessions[session_id]["audio_buffer"] = b""
                
                if len(audio_data) < 1000:  # 太短忽略
                    continue
                
                # 1. ASR 转文字（前端已将录音转为 WAV）
                try:
                    consultant_text = await asyncio.wait_for(
                        doubao_client.speech_to_text(audio_data, audio_format=data.get("audio_format", "webm")),
                        timeout=ASR_TIMEOUT_SECONDS
                    )
                except asyncio.TimeoutError:
                    consultant_text = None
                    await send_json_safe(websocket, {
                        "type": "error",
                        "message": "语音识别超时，请缩短发言后重试"
                    })
                except Exception as e:
                    consultant_text = None
                    print(f"语音识别异常: {e}")
                    await send_json_safe(websocket, {
                        "type": "error",
                        "message": "语音识别失败，请重试"
                    })
                
                if not consultant_text:
                    continue
                
                # 发送咨询师文字到前端
                if not await send_json_safe(websocket, {
                    "type": "consultant_text",
                    "text": consultant_text
                }):
                    break
                
                # 2. AI 家长生成回复
                try:
                    parent_text = await asyncio.wait_for(
                        ai_parent.generate_response(consultant_text),
                        timeout=AI_RESPONSE_TIMEOUT_SECONDS
                    )
                except asyncio.TimeoutError:
                    parent_text = "不好意思，我这边刚刚没听清，您可以再简短说一次吗？"
                    await send_json_safe(websocket, {
                        "type": "warning",
                        "message": "家长回复生成超时，已使用兜底回复继续训练"
                    })
                except Exception as e:
                    print(f"AI 家长回复失败: {e}")
                    parent_text = "这个我还想再了解一下，您可以换个说法再讲讲吗？"
                    await send_json_safe(websocket, {
                        "type": "warning",
                        "message": "家长回复生成失败，已使用兜底回复继续训练"
                    })
                
                # 发送家长文字到前端
                if not await send_json_safe(websocket, {
                    "type": "parent_text",
                    "text": parent_text
                }):
                    break
                
                # 3. 实时评估（失败不阻断主流程）
                try:
                    turn_eval = await asyncio.wait_for(
                        sessions[session_id]["evaluator"].evaluate_turn(
                            consultant_text,
                            parent_text,
                            ai_parent.turn_count,
                            ai_parent.get_traits()
                        ),
                        timeout=EVALUATION_TIMEOUT_SECONDS
                    )
                    await send_json_safe(websocket, {
                        "type": "evaluation",
                        "data": turn_eval
                    })
                    # B: 动态突变
                    scores = turn_eval.get("scores", {})
                    if scores:
                        avg = sum(scores.values()) / len(scores)
                        ai_parent.update_attitude(avg)
                except asyncio.TimeoutError:
                    await send_json_safe(websocket, {
                        "type": "warning",
                        "message": "本轮评估超时，已跳过，不影响继续训练"
                    })
                except Exception as e:
                    print(f"实时评估失败: {e}")
                    await send_json_safe(websocket, {
                        "type": "warning",
                        "message": "本轮评估失败，已跳过，不影响继续训练"
                    })
                
                # 4. TTS 转语音（失败时保留文字模式继续）
                try:
                    audio_response = await asyncio.wait_for(
                        doubao_client.text_to_speech(parent_text),
                        timeout=TTS_TIMEOUT_SECONDS
                    )
                    if audio_response:
                        await send_parent_audio_safe(websocket, audio_response)
                    else:
                        await send_json_safe(websocket, {
                            "type": "warning",
                            "message": "语音合成失败，已切换为文字模式继续训练"
                        })
                except asyncio.TimeoutError:
                    await send_json_safe(websocket, {
                        "type": "warning",
                        "message": "语音合成超时，已切换为文字模式继续训练"
                    })
                except Exception as e:
                    print(f"TTS 失败: {e}")
                    await send_json_safe(websocket, {
                        "type": "warning",
                        "message": "语音合成失败，已切换为文字模式继续训练"
                    })
                    
            elif msg_type == "text":
                # 文字模式（备用）
                consultant_text = (data.get("text", "") or "").strip()
                if not consultant_text:
                    await send_json_safe(websocket, {
                        "type": "error",
                        "message": "请输入咨询师话术后再发送"
                    })
                    continue

                try:
                    parent_text = await asyncio.wait_for(
                        ai_parent.generate_response(consultant_text),
                        timeout=AI_RESPONSE_TIMEOUT_SECONDS
                    )
                except asyncio.TimeoutError:
                    parent_text = "我这边刚刚有点没跟上，您可以再简短说一次吗？"
                    await send_json_safe(websocket, {
                        "type": "warning",
                        "message": "家长回复生成超时，已使用兜底回复继续训练"
                    })
                except Exception as e:
                    print(f"文字模式回复失败: {e}")
                    parent_text = "这个我还想再想想，您继续说。"
                    await send_json_safe(websocket, {
                        "type": "warning",
                        "message": "家长回复生成失败，已使用兜底回复继续训练"
                    })
                
                if not await send_json_safe(websocket, {
                    "type": "parent_text",
                    "text": parent_text
                }):
                    break
                
                # 同时合成语音
                try:
                    audio_response = await asyncio.wait_for(
                        doubao_client.text_to_speech(parent_text),
                        timeout=TTS_TIMEOUT_SECONDS
                    )
                    if audio_response:
                        await send_parent_audio_safe(websocket, audio_response)
                    else:
                        await send_json_safe(websocket, {
                            "type": "warning",
                            "message": "语音合成失败，已切换为文字模式继续训练"
                        })
                except asyncio.TimeoutError:
                    await send_json_safe(websocket, {
                        "type": "warning",
                        "message": "语音合成超时，已切换为文字模式继续训练"
                    })
                except Exception as e:
                    print(f"文字模式 TTS 失败: {e}")
                    await send_json_safe(websocket, {
                        "type": "warning",
                        "message": "语音合成失败，已切换为文字模式继续训练"
                    })
                    
            elif msg_type == "end":
                # 结束训练，生成报告
                traits = ai_parent.get_traits_summary()
                history = ai_parent.conversation_history
                
                # 生成最终评估报告
                try:
                    final_report = sessions[session_id]["evaluator"].generate_final_report()
                except Exception as e:
                    print(f"生成最终报告失败: {e}")
                    final_report = {
                        "overall_score": 0,
                        "level": "暂未生成",
                        "dimension_scores": {},
                        "dimension_names": {},
                        "total_turns": len(history),
                        "strengths": [],
                        "improvements": ["本次训练报告生成失败，建议稍后重试"],
                        "summary": "本次训练已结束，但报告生成失败。",
                        "recommendations": ["请保留本次对话记录，稍后重新生成报告"]
                    }
                
                session_record = {
                    "session_id": session_id,
                    "created_at": sessions[session_id].get("created_at"),
                    "ended_at": datetime.now().isoformat(),
                    "parent_type": ai_parent.parent_type,
                    "parent_type_name": ai_parent.parent_config["name"],
                    "scenario": ai_parent.scenario,
                    "scenario_name": ai_parent.scenario_config["name"],
                    "traits": ai_parent.get_traits(),
                    "traits_summary": traits,
                    "turns": len(history),
                    "history": history,
                    "turn_evaluations": sessions[session_id]["evaluator"].evaluations,
                    "evaluation": final_report,
                }
                saved_summary = None
                try:
                    saved_summary = storage.save_session(session_record)
                except Exception as e:
                    print(f"保存训练记录失败: {e}")

                await send_json_safe(websocket, {
                    "type": "report",
                    "record_id": saved_summary["record_id"] if saved_summary else None,
                    "saved_at": saved_summary["saved_at"] if saved_summary else None,
                    "traits": traits,
                    "turns": len(history),
                    "history": history,
                    "evaluation": final_report
                })
                break
                
    except WebSocketDisconnect:
        print(f"会话 {session_id} 已断开")
    except Exception as e:
        print(f"会话 {session_id} 错误: {e}")
        with contextlib.suppress(Exception):
            await send_json_safe(websocket, {
                "type": "error",
                "message": "当前训练连接出现异常，请重新开始一轮训练"
            })
    finally:
        if session_id in sessions:
            del sessions[session_id]


@app.get("/health")
async def health_check():
    """健康检查"""
    return {"status": "ok", "sessions": len(sessions)}


@app.get("/api/parent-types")
async def get_parent_types():
    """获取家长类型列表"""
    return list_parent_types()


@app.get("/api/scenarios")
async def get_scenarios():
    """获取场景列表"""
    return list_scenarios()


@app.get("/api/sessions")
async def list_training_sessions(limit: int = 20):
    """获取训练记录列表"""
    return {"items": storage.list_sessions(limit=limit)}


@app.get("/api/sessions/{record_id}")
async def get_training_session(record_id: str):
    """获取单次训练记录详情"""
    session = storage.get_session(record_id)
    if not session:
        return {"error": "记录不存在", "record_id": record_id}
    return session


@app.get("/api/screenshot")
async def get_screenshot(type: str = "interface"):
    """
    获取界面截图
    
    Args:
        type: 截图类型 (interface=配置界面, conversation=对话界面)
    """
    try:
        if type == "interface":
            path = await capture_training_interface()
        elif type == "conversation":
            path = await capture_conversation()
        else:
            from screenshot import capture_screenshot
            path = await capture_screenshot()
        
        from fastapi.responses import FileResponse
        return FileResponse(path, media_type="image/png")
        
    except Exception as e:
        return {"error": f"截图失败: {str(e)}"}


@app.get("/api/admin/stats")
async def admin_stats():
    """主管后台：汇总统计"""
    items = storage.list_sessions(limit=500)
    if not items:
        return {"total": 0, "avg_score": 0, "by_type": {}, "by_scenario": {}, "recent": []}
    scores = [i["overall_score"] for i in items if i.get("overall_score")]
    by_type: dict = {}
    by_scenario: dict = {}
    for item in items:
        t = item.get("parent_type_name") or item.get("parent_type", "未知")
        s = item.get("scenario_name") or item.get("scenario", "未知")
        by_type.setdefault(t, {"count": 0, "score_sum": 0.0})
        by_type[t]["count"] += 1
        by_type[t]["score_sum"] += item.get("overall_score") or 0
        by_scenario.setdefault(s, {"count": 0, "score_sum": 0.0})
        by_scenario[s]["count"] += 1
        by_scenario[s]["score_sum"] += item.get("overall_score") or 0
    return {
        "total": len(items),
        "avg_score": round(sum(scores) / len(scores), 1) if scores else 0,
        "by_type": {k: {"count": v["count"], "avg_score": round(v["score_sum"] / v["count"], 1)} for k, v in by_type.items()},
        "by_scenario": {k: {"count": v["count"], "avg_score": round(v["score_sum"] / v["count"], 1)} for k, v in by_scenario.items()},
        "recent": items[:10],
    }


@app.get("/admin", response_class=HTMLResponse)
async def admin_page():
    """主管后台页面"""
    return """<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>主管后台 - 学大咨询师训练系统</title>
<style>
body{font-family:-apple-system,sans-serif;max-width:960px;margin:30px auto;padding:20px;background:#f5f7fb}
h1,h2{color:#333}.card{background:white;border-radius:12px;padding:20px;margin:20px 0;box-shadow:0 2px 8px rgba(0,0,0,.08)}
table{width:100%;border-collapse:collapse}th,td{padding:10px;text-align:left;border-bottom:1px solid #eee}
th{background:#f8f9fa;font-weight:600}.big{font-size:2em;font-weight:700;color:#007bff}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:20px}
</style></head><body>
<h1>📊 主管后台</h1>
<a href="/">← 返回训练系统</a>
<div id="app">加载中...</div>
<script>
async function load(){
  const d=await fetch('/api/admin/stats').then(r=>r.json());
  const fmt=v=>new Date(v).toLocaleString('zh-CN',{hour12:false});
  document.getElementById('app').innerHTML=`
    <div class="card"><h2>总览</h2>
      <div class="grid">
        <div>总训练次数<br><span class="big">${d.total}</span></div>
        <div>平均评分<br><span class="big">${d.avg_score}</span></div>
      </div></div>
    <div class="grid">
      <div class="card"><h2>按家长类型</h2>
        <table><tr><th>类型</th><th>次数</th><th>均分</th></tr>
        ${Object.entries(d.by_type).map(([k,v])=>`<tr><td>${k}</td><td>${v.count}</td><td>${v.avg_score}</td></tr>`).join('')}
        </table></div>
      <div class="card"><h2>按场景</h2>
        <table><tr><th>场景</th><th>次数</th><th>均分</th></tr>
        ${Object.entries(d.by_scenario).map(([k,v])=>`<tr><td>${k}</td><td>${v.count}</td><td>${v.avg_score}</td></tr>`).join('')}
        </table></div>
    </div>
    <div class="card"><h2>最近10条记录</h2>
      <table><tr><th>时间</th><th>家长类型</th><th>场景</th><th>轮次</th><th>评分</th><th>评级</th></tr>
      ${d.recent.map(i=>`<tr><td>${fmt(i.saved_at)}</td><td>${i.parent_type_name||'-'}</td><td>${i.scenario_name||'-'}</td><td>${i.turns||0}</td><td>${i.overall_score||'-'}</td><td>${i.level||'-'}</td></tr>`).join('')}
      </table></div>`;
}
load();
</script></body></html>"""


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=HOST, port=PORT)