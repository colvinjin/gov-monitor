# 学大咨询师训练系统

AI 语音仿真训练平台，帮助学大咨询师提升电话沟通和成交能力。

## 功能特性

- 🎤 语音对话：实时语音交互，模拟真实电话场景
- 🤖 AI 家长：基于大模型的智能家长角色，性格动态变化
- 📊 能力评估：多维度评分，针对性提升建议
- 🎯 盲盒训练：隐藏家长类型，真实还原咨询场景

## 技术栈

- 后端：Python + FastAPI + WebSocket
- 前端：原生 JavaScript + WebRTC
- 语音：豆包 TTS + ASR
- AI：Claude (家长对话推理)

## 快速开始

### 1. 配置环境

```bash
cd backend
cp .env.example .env
# 编辑 .env，填写 API Key
```

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 启动服务

```bash
python main.py
```

服务将在 http://localhost:8000 启动

### 4. 开始训练

浏览器打开 http://localhost:8000，点击"开始训练"

## 项目结构

```
consultant-trainer/
├── backend/
│   ├── main.py           # FastAPI 主服务
│   ├── doubao_client.py  # 豆包语音客户端
│   ├── ai_parent.py      # AI 家长逻辑
│   ├── config.py         # 配置管理
│   └── requirements.txt
├── frontend/
│   ├── app.js            # 前端交互逻辑
│   └── style.css         # 样式（内联在 HTML 中）
├── data/                 # 本地数据存储
└── README.md
```

## 配置说明

`.env` 文件需要配置：

- `DOUBAO_API_KEY`: 豆包 API Key
- `DOUBAO_TTS_ENDPOINT`: 豆包 TTS 接口地址
- `DOUBAO_ASR_ENDPOINT`: 豆包 ASR 接口地址
- `CLAUDE_API_KEY`: Claude API Key

## 开发计划

### 第一阶段（当前）
- [x] 基础架构搭建
- [x] 豆包语音对接
- [x] AI 家长对话
- [ ] 语音格式优化
- [ ] 测试验证

### 第二阶段
- [ ] 家长性格动态突变
- [ ] 多维度评估体系
- [ ] 训练报告生成
- [ ] 历史记录存储

### 第三阶段
- [ ] 主管后台
- [ ] 团队数据看板
- [ ] 真实录音对比
- [ ] 部署上线

## License

内部项目，学大教育集团版权所有。