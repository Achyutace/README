readme/
├── backend/
│   ├── core/               
│   │   ├── config.py               # 读取 config.yaml, 管理 API Keys
│   │   ├── database.py             # 数据库初始化连接: PostgreSQL(主库), Qdrant(向量库)
│   │   ├── security.py             # JWT 校验 & 用户鉴权
│   │   ├── exceptions.py           # 自定义异常，发送给前端
│   │   └── logging.py              # 统一日志配置
│   |
│   ├── api/                # 路由层：接发请求
│   |   ├── dependencies.py # FastAPI的依赖注入
│   |   ├── v1/ 
│   │   |   ├── chat_box.py     # 聊天框相关路由：聊天记录添加、获取、删除；信息发送，获取回答
│   │   |   ├── highlight.py    # 高亮路由：添加，删除，改颜色         
│   │   |   ├── notes.py        # 笔记相关路由：添加，删除  
│   │   |   ├── link.py         # 引用相关路由：请求引用相关内容                                         
│   │   |   ├── translate.py    # 翻译相关路由：段落翻译+划词翻译
│   │   |   ├── upload.py       # pdf上传路由  
│   │   |   ├── library.py      # 文献管理路由：上传，删除，分组
│   │   |   ├── user.py         # 用户管理相关路由
│   │   |   ├── keyword.py      # 关键词相关路由
│   │   |   ├── roadmap.py      # 知识图谱相关路由：获取结点，添加节点，删除节点  
│   │   └── routers.py              # 统一注册所有路由
│   ├── model/                      # 模型层：定义数据长什么样
│   │   ├── db/                     # SQLAlchemy ORM 模型 (对应数据库表)
│   │   │   ├── base.py             # Declarative Base
│   │   │   ├── user_models.py      # User
│   │   │   ├── doc_models.py       # Paper, Note, Highlight, Image
│   │   │   └── graph_models.py     # RoadmapJSON, Node, Edge
│   │   └── schemas.py                # Pydantic 模型 (对应 API 输入输出 & 工具结构)
│   ├── repository/                 # 数据层：直接操作数据库，提供接口给上层
│   │   ├── sql_repo.py             # PostgreSQL 操作封装 
│   │   └── vector_repo.py          # Qdrant 操作封装
│   │   └── object_repo.py          # 对象数据库存储
│   ├── service/                    # 业务层
│   │   ├── paper_service.py        # 启动异步处理新的论文；对接数据库，返回段落和图表信息；增删段落翻译信息
│   │   ├── library_service.py      # 文献库管理：上传，删除，分组，获取论文条目和笔记
│   │   ├── rag_service.py          # 用户全文献库rag服务   
│   │   ├── chat_service.py         # 聊天框管理服务：获取、增删聊天记录
│   │   ├── roadmap_service.py      # 知识图谱服务：增删结点、关系；获取结点及相应数据
│   │   ├── note_service.py         # 笔记服务：添加笔记，删除笔记，修改笔记
│   │   ├── translate_service.py    # 翻译服务：llm请求
│   │   └── user_service.py         # 用户管理服务：登录，注册等
│   ├── tasks/                      # 异步任务
│   │   ├── pdf_tasks.py            # pdf段落+图片解析+向量化的异步处理
│   │   └── chat_task.py            # 聊天框的异步任务：标题异步生成
│   ├── agent/                      # Agent服务层：过于重了，单独列出来 
│   │   ├── state.py                # 定义 AgentState (Messages, Context, Keys)
│   │   ├── nodes/                  # LangGraph节点
│   │   │   ├── router.py           # 路由节点        
│   │   │   ├── paper_expert.py     # 单论文细读节点：RAG补充上下文      
│   │   │   └── search_expert.py    # 外部检索路由节点：检索用户关联的文献库+联网搜索                
│   |   └── main_graph.py           # 构建 Workflow, 编译 StateGraph
│   ├── utils/                      # 纯工具箱： 无业务状态、纯函数，从原来的service模块中提取
│   │   ├── pdf_engine.py           # PDF 解析 (PyPDF), 文本清洗
│   │   ├── image_processor.py      # 图片处理 (OCR等)
│   │   ├── embedding_utils.py      # 向量化封装 (OpenAI 等 API 调用)
│   │   ├── search_utils.py         # 联网搜索封装 (搜索 API 请求与清洗)
│   │   ├── text_splitter.py        # 文本切片 (RecursiveCharacterTextSplitter)
│   │   ├── graph_algo.py           # NetworkX 纯算法 (roadmap可能用到的一些算法)
│   │   └── ...
└── config.yaml             # 所有的配置都在这里

