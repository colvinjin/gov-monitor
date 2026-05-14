/**
 * 学大咨询师训练系统 - 前端
 */

let ws = null;
let sessionId = null;
let mediaRecorder = null;
let audioChunks = [];
let isRecording = false;
let sessionHistory = [];
let currentReport = null;

// 音频上下文
let audioContext = null;

// 初始化
async function init() {
    updateStatus('正在检查系统...', 'ok');
    
    // 检查浏览器支持
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        updateStatus('您的浏览器不支持录音功能，请使用 Chrome/Edge/Safari', 'error');
        return;
    }
    
    await loadSessionList();
    updateStatus('系统就绪，点击"开始训练"', 'ok');
}

// 更新状态显示
function updateStatus(message, type) {
    const statusEl = document.getElementById('status');
    statusEl.textContent = message;
    statusEl.className = 'status ' + type;
}

// 开始训练
async function startTraining() {
    sessionId = generateSessionId();
    
    // 获取配置
    const parentType = document.getElementById('parentType').value;
    const scenario = document.getElementById('scenario').value;
    
    // 隐藏配置面板
    document.getElementById('config').style.display = 'none';
    
    // 连接 WebSocket
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws/${sessionId}`;
    
    ws = new WebSocket(wsUrl);
    
    ws.onopen = async () => {
        console.log('WebSocket 已连接');
        updateStatus('已连接，等待家长接听...', 'ok');
        
        // 发送配置
        ws.send(JSON.stringify({
            type: 'config',
            parent_type: parentType,
            scenario: scenario
        }));
        
        // 显示控制按钮
        document.getElementById('startBtn').style.display = 'none';
        document.getElementById('recordBtn').style.display = 'inline-block';
        document.getElementById('textModeBtn').style.display = 'inline-block';
        document.getElementById('endBtn').style.display = 'inline-block';
        
        // 初始化音频
        await initAudio();
    };
    
    ws.onmessage = async (event) => {
        const data = JSON.parse(event.data);
        handleMessage(data);
    };
    
    ws.onerror = (error) => {
        console.error('WebSocket 错误:', error);
        updateStatus('连接错误，请刷新重试', 'error');
    };
    
    ws.onclose = () => {
        console.log('WebSocket 已关闭');
        updateStatus('连接已断开', 'error');
    };
}

// 初始化音频
async function initAudio() {
    try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        
        mediaRecorder = new MediaRecorder(stream, {
            mimeType: 'audio/webm;codecs=opus'
        });
        
        mediaRecorder.ondataavailable = (event) => {
            if (event.data.size > 0) {
                audioChunks.push(event.data);
            }
        };
        
        mediaRecorder.onstop = async () => {
            const audioBlob = new Blob(audioChunks, { type: 'audio/webm' });
            audioChunks = [];
            
            const wavBuffer = await convertToWav(audioBlob);
            const base64Audio = arrayBufferToBase64(wavBuffer);
            
            if (ws && ws.readyState === WebSocket.OPEN) {
                ws.send(JSON.stringify({
                    type: 'audio',
                    data: base64Audio
                }));
                ws.send(JSON.stringify({
                    type: 'audio_end',
                    audio_format: 'wav'
                }));
            }
        };
        
    } catch (err) {
        console.error('初始化录音失败:', err);
        updateStatus('无法访问麦克风，请检查权限', 'error');
    }
}

// 开始录音
function startRecording() {
    if (!mediaRecorder || isRecording) return;
    
    isRecording = true;
    audioChunks = [];
    mediaRecorder.start(100); // 每100ms收集一次数据
    
    const btn = document.getElementById('recordBtn');
    btn.classList.add('recording');
    btn.textContent = '🎤 录音中...';
    
    updateStatus('正在录音，松开发送', 'ok');
}

// 停止录音
function stopRecording() {
    if (!mediaRecorder || !isRecording) return;
    
    isRecording = false;
    mediaRecorder.stop();
    
    const btn = document.getElementById('recordBtn');
    btn.classList.remove('recording');
    btn.textContent = '🎤 按住说话';
    
    updateStatus('正在处理...', 'ok');
}

// 处理 WebSocket 消息
async function handleMessage(data) {
    switch (data.type) {
        case 'consultant_text':
            // 显示咨询师语音识别结果
            addMessage('consultant', data.text);
            break;
            
        case 'parent_text':
            // 显示家长文字
            addMessage('parent', data.text);
            break;
            
        case 'parent_audio':
            // 播放家长语音
            await playAudio(data.data);
            updateStatus('请回复', 'ok');
            break;
            
        case 'evaluation':
            // 显示实时评估
            showEvaluation(data.data);
            break;
            
        case 'error':
            updateStatus('错误: ' + data.message, 'error');
            break;
            
        case 'report':
            showReport(data);
            break;
    }
}

// 添加消息到对话区
function addMessage(role, text) {
    const conversation = document.getElementById('conversation');
    const div = document.createElement('div');
    div.className = 'message ' + role;
    div.innerHTML = `<strong>${role === 'consultant' ? '咨询师' : '家长'}:</strong> ${text}`;
    conversation.appendChild(div);
    conversation.scrollTop = conversation.scrollHeight;
}

// 播放音频
async function playAudio(base64Data) {
    try {
        if (!audioContext) {
            audioContext = new (window.AudioContext || window.webkitAudioContext)();
        }
        
        const audioData = base64ToArrayBuffer(base64Data);
        const audioBuffer = await audioContext.decodeAudioData(audioData);
        
        const source = audioContext.createBufferSource();
        source.buffer = audioBuffer;
        source.connect(audioContext.destination);
        source.start();
        
    } catch (err) {
        console.error('播放音频失败:', err);
    }
}

// 文字模式切换
let textMode = false;
function toggleTextMode() {
    textMode = !textMode;
    document.getElementById('textInput').style.display = textMode ? 'block' : 'none';
    document.getElementById('recordBtn').style.display = textMode ? 'none' : 'inline-block';
    document.getElementById('textModeBtn').textContent = textMode ? '🎤 语音模式' : '⌨️ 文字模式';
    if (textMode) document.getElementById('textMsg').focus();
}

// 发送文字
function sendText() {
    const input = document.getElementById('textMsg');
    const text = input.value.trim();
    if (!text || !ws || ws.readyState !== WebSocket.OPEN) return;
    ws.send(JSON.stringify({ type: 'text', text }));
    input.value = '';
    updateStatus('正在处理...', 'ok');
}

// 结束训练
function endTraining() {
    if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: 'end' }));
    }
    
    document.getElementById('recordBtn').style.display = 'none';
    document.getElementById('endBtn').style.display = 'none';
    document.getElementById('startBtn').style.display = 'inline-block';
    document.getElementById('startBtn').textContent = '重新开始';
}

// 显示实时评估
function showEvaluation(data) {
    const conversation = document.getElementById('conversation');
    
    // 计算平均分
    const scores = data.scores || {};
    const avgScore = Object.values(scores).reduce((a, b) => a + b, 0) / Object.values(scores).length;
    
    // 找出最高分维度
    let bestDim = '';
    let bestScore = 0;
    const dimNames = {
        'rapport': '信任建立',
        'needs_analysis': '需求挖掘',
        'product_intro': '产品介绍',
        'objection_handling': '异议处理',
        'closing': '成交引导'
    };
    
    for (const [dim, score] of Object.entries(scores)) {
        if (score > bestScore) {
            bestScore = score;
            bestDim = dimNames[dim] || dim;
        }
    }
    
    const evalDiv = document.createElement('div');
    evalDiv.className = 'evaluation';
    evalDiv.style.cssText = 'margin: 10px 0; padding: 12px; background: #e3f2fd; border-radius: 8px; font-size: 14px;';
    evalDiv.innerHTML = `
        <div style="display: flex; justify-content: space-between; align-items: center;">
            <strong>🎯 第${data.turn}轮评估</strong>
            <span style="font-size: 18px; font-weight: bold; color: ${avgScore >= 8 ? '#4caf50' : avgScore >= 6 ? '#ff9800' : '#f44336'};">
                ${avgScore.toFixed(1)}分
            </span>
        </div>
        <div style="margin-top: 8px; color: #666;">
            💡 ${data.key_insight || '表现良好'}
        </div>
    `;
    
    conversation.appendChild(evalDiv);
    conversation.scrollTop = conversation.scrollHeight;
}

// 显示报告
function showReport(data) {
    currentReport = data;
    const conversation = document.getElementById('conversation');
    conversation.innerHTML += renderReportHtml(data);
    conversation.scrollTop = conversation.scrollHeight;
    updateStatus('训练结束', 'ok');
    loadSessionList();
}

function renderReportHtml(data) {
    const history = data.history || [];
    let historyHtml = '';
    history.forEach((turn, i) => {
        historyHtml += `<p><strong>第${i + 1}轮:</strong><br>`;
        historyHtml += `咨询师: ${turn.consultant}<br>`;
        historyHtml += `家长: ${turn.parent}</p>`;
    });

    let evalHtml = '';
    if (data.evaluation) {
        const evalData = data.evaluation;
        const dimNames = evalData.dimension_names || {};
        let scoresHtml = '';

        for (const [dim, score] of Object.entries(evalData.dimension_scores || {})) {
            const name = dimNames[dim] || dim;
            const color = score >= 8 ? '#4caf50' : score >= 6 ? '#ff9800' : '#f44336';
            scoresHtml += `
                <div style="margin: 5px 0;">
                    <span>${name}:</span>
                    <span style="color: ${color}; font-weight: bold;">${score}分</span>
                    <div style="background: #e0e0e0; height: 8px; border-radius: 4px; margin-top: 2px;">
                        <div style="background: ${color}; width: ${score * 10}%; height: 100%; border-radius: 4px;"></div>
                    </div>
                </div>
            `;
        }

        evalHtml = `
            <div style="margin-top: 15px; padding: 15px; background: #f5f5f5; border-radius: 8px;">
                <h4>📊 综合评估</h4>
                <div style="text-align: center; margin: 15px 0;">
                    <div style="font-size: 48px; font-weight: bold; color: ${evalData.overall_score >= 8 ? '#4caf50' : evalData.overall_score >= 6 ? '#ff9800' : '#f44336'};">
                        ${evalData.overall_score ?? '-'}
                    </div>
                    <div style="font-size: 18px; color: #666;">${evalData.level || '未评级'}</div>
                </div>
                <div style="margin: 15px 0;">${scoresHtml}</div>
                <div style="margin-top: 15px;">
                    <strong>👍 优点:</strong>
                    <ul style="margin: 5px 0; padding-left: 20px;">
                        ${(evalData.strengths || []).map(s => `<li>${s}</li>`).join('')}
                    </ul>
                </div>
                <div style="margin-top: 10px;">
                    <strong>💡 改进建议:</strong>
                    <ul style="margin: 5px 0; padding-left: 20px;">
                        ${(evalData.improvements || []).map(i => `<li>${i}</li>`).join('')}
                    </ul>
                </div>
                <div style="margin-top: 10px; padding: 10px; background: #fff3e0; border-radius: 4px;">
                    <strong>🎯 训练建议:</strong>
                    <ul style="margin: 5px 0; padding-left: 20px;">
                        ${(evalData.recommendations || []).map(r => `<li>${r}</li>`).join('')}
                    </ul>
                </div>
            </div>
        `;
    }

    const parentTypeText = data.parent_type_name || data.traits || '未记录';
    const scenarioText = data.scenario_name || data.scenario || '未记录';
    const recordMeta = data.record_id ? `<p><strong>记录ID:</strong> ${data.record_id}</p>` : '';
    const savedMeta = data.saved_at ? `<p><strong>保存时间:</strong> ${formatTime(data.saved_at)}</p>` : '';

    return `
        <div style="margin-top: 20px; padding: 20px; background: #d4edda; border-radius: 8px;">
            <h3>📝 训练报告</h3>
            ${recordMeta}
            ${savedMeta}
            <p><strong>家长类型:</strong> ${parentTypeText}</p>
            <p><strong>训练场景:</strong> ${scenarioText}</p>
            <p><strong>对话轮次:</strong> ${data.turns || history.length}</p>
            ${evalHtml}
            <hr>
            <h4>对话记录:</h4>
            ${historyHtml || '<p>暂无对话记录</p>'}
        </div>
    `;
}

async function loadSessionList() {
    const listEl = document.getElementById('sessionList');
    const summaryEl = document.getElementById('historySummary');
    if (!listEl || !summaryEl) return;

    summaryEl.textContent = '正在加载训练记录...';
    try {
        const resp = await fetch('/api/sessions?limit=20');
        const data = await resp.json();
        sessionHistory = data.items || [];
        renderSessionList();
    } catch (err) {
        console.error('加载训练记录失败:', err);
        summaryEl.textContent = '训练记录加载失败';
        listEl.innerHTML = '<div class="empty">暂时无法读取训练记录</div>';
    }
}

function renderSessionList() {
    const listEl = document.getElementById('sessionList');
    const summaryEl = document.getElementById('historySummary');
    if (!listEl || !summaryEl) return;

    if (!sessionHistory.length) {
        summaryEl.textContent = '还没有训练记录';
        listEl.innerHTML = '<div class="empty">完成一次训练后，这里会显示历史报告。</div>';
        return;
    }

    summaryEl.textContent = `共 ${sessionHistory.length} 条最近训练记录`;
    listEl.innerHTML = sessionHistory.map(item => {
        const score = item.overall_score ?? '-';
        return `
            <div class="session-item" onclick="viewSessionDetail('${item.record_id}')">
                <div>
                    <span class="badge">${item.parent_type_name || item.parent_type || '未知家长'}</span>
                    <span class="badge">${item.scenario_name || item.scenario || '未知场景'}</span>
                </div>
                <div style="margin-top: 8px; font-weight: 600;">${item.level || '未评级'} · <span class="score">${score}</span> 分</div>
                <div class="session-meta">${formatTime(item.saved_at)} · ${item.turns || 0} 轮对话</div>
            </div>
        `;
    }).join('');
}

async function viewSessionDetail(recordId) {
    if (!recordId) return;
    updateStatus('正在加载历史报告...', 'ok');
    try {
        const resp = await fetch(`/api/sessions/${recordId}`);
        const data = await resp.json();
        if (data.error) {
            updateStatus(data.error, 'error');
            return;
        }
        const conversation = document.getElementById('conversation');
        conversation.innerHTML = renderReportHtml({ ...data, saved_at: data.saved_at || data.ended_at });
        conversation.scrollTop = 0;
        updateStatus('已打开历史报告', 'ok');
    } catch (err) {
        console.error('读取历史报告失败:', err);
        updateStatus('读取历史报告失败', 'error');
    }
}

function formatTime(value) {
    if (!value) return '未知时间';
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return value;
    return date.toLocaleString('zh-CN', { hour12: false });
}

// 辅助函数
function generateSessionId() {
    return Date.now().toString(36) + Math.random().toString(36).substr(2);
}

function arrayBufferToBase64(buffer) {
    const bytes = new Uint8Array(buffer);
    let binary = '';
    for (let i = 0; i < bytes.byteLength; i++) {
        binary += String.fromCharCode(bytes[i]);
    }
    return window.btoa(binary);
}

function base64ToArrayBuffer(base64) {
    const binary = window.atob(base64);
    const bytes = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i++) {
        bytes[i] = binary.charCodeAt(i);
    }
    return bytes.buffer;
}

async function convertToWav(webmBlob) {
    if (!audioContext) {
        audioContext = new (window.AudioContext || window.webkitAudioContext)();
    }
    const arrayBuffer = await webmBlob.arrayBuffer();
    const audioBuffer = await audioContext.decodeAudioData(arrayBuffer);
    return encodeWav(audioBuffer);
}

function encodeWav(audioBuffer) {
    const numChannels = 1;
    const sampleRate = audioBuffer.sampleRate;
    const samples = audioBuffer.getChannelData(0);
    const pcm = new Int16Array(samples.length);
    for (let i = 0; i < samples.length; i++) {
        pcm[i] = Math.max(-32768, Math.min(32767, Math.round(samples[i] * 32767)));
    }
    const dataLen = pcm.length * 2;
    const buf = new ArrayBuffer(44 + dataLen);
    const view = new DataView(buf);
    const w = (off, str) => { for (let i = 0; i < str.length; i++) view.setUint8(off + i, str.charCodeAt(i)); };
    w(0, 'RIFF'); view.setUint32(4, 36 + dataLen, true);
    w(8, 'WAVE'); w(12, 'fmt '); view.setUint32(16, 16, true);
    view.setUint16(20, 1, true); view.setUint16(22, numChannels, true);
    view.setUint32(24, sampleRate, true); view.setUint32(28, sampleRate * 2, true);
    view.setUint16(32, 2, true); view.setUint16(34, 16, true);
    w(36, 'data'); view.setUint32(40, dataLen, true);
    const out = new Int16Array(buf, 44);
    out.set(pcm);
    return buf;
}

// 页面加载时初始化
window.onload = init;