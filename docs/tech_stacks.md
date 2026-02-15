# Tech Stack & Coding Guidelines (Vue + Flask Edition)

## Architecture
- **Pattern**: Client-Server Decoupled (前后端分离).
- **Frontend**: Vue 3 + Vite (Single Page Application).
- **Backend**: Python Flask API.

## Frontend Stack (Must Use)
- **Framework**: Vue 3 (Composition API) with `<script setup lang="ts">`.
- **Build Tool**: Vite.
- **Styling**: Tailwind CSS (Utility-first).
- **State Management**: Pinia (用于管理 PDF 缩放、当前页、AI 侧边栏状态).
- **PDF Rendering**: `vue-pdf-embed` (https://github.com/hgn/vue-pdf-embed).
- **UI Components**: `shadcn-vue` (推荐) OR `Element Plus` (如果需要更快的开发速度).
- **Networking**: Axios.

## Backend Stack (Python)
- **Framework**: Flask.
- **PDF Processing**: `PyMuPDF` (aka `fitz`) - 用于提取文本和坐标(bounding box).
- **AI/LLM**: `openai` or `langchain` library.

## Directory Structure Rules
### Frontend (/frontend)
- `/components/pdf`: PDF viewer components.
- `/components/ai-panel`: Right sidebar components.
- `/stores`: Pinia stores.
- `/composables`: Reusable logic (hooks).

### Backend (/backend)
- `app.py`: Entry point.
- `/services/pdf_service.py`: Logic to parse PDF and extract text coordinates.
- `/services/ai_service.py`: Logic to call LLMs.

### OpenAPI
openapi/
├── openapi.yaml                 # 👑 主入口文件 (总指挥)
├── paths/                       # 存放具体的 API 路径定义
│   ├── pdf.yaml                 # 所有 /pdf/* 相关的接口
│   ├── chat.yaml                # 所有 /chatbox/* 相关的接口
│   ├── highlight.yaml           # /highlight/*
│   ├── notes.yaml               # /notes/*
│   ├── translate.yaml           # /translate/*
│   ├── smartref.yaml            # /smartref/*
│   └── system.yaml              # /health
└── components/                  # 存放组件 (Schema, Security)
    ├── security.yaml            # 认证定义 (UserIdHeader)
    └── schemas/                 # 数据模型
        ├── common.yaml          # 通用的 (比如 Error)
        ├── pdf.yaml             # UploadResponse, PDFInfoResponse...
        ├── chat.yaml            # ChatResponse, MessageRequest...
        ├── highlight.yaml
        ├── notes.yaml
        └── smartref.yaml