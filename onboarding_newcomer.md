# 新人上手指南（Auto_prd_test_expert）

## 1. 代码库整体结构

- `ui/`：Streamlit 前端页面与交互编排。
  - `ui/main.py`：应用入口，负责“上传资料 -> RAG 检索 -> 生成/微调用例 -> 评估”的主流程。
  - `ui/sidebar.py`：侧边栏配置（API Key、模型选择、清空状态）。
  - `ui/components.py`：结果预览和导出（CSV/JSON/YAML/Markdown）。
- `core/`：核心能力层。
  - `core/rag_engine.py`：向量库、文档切片、多模态解析、入库/检索。
  - `core/llm_client.py`：Gemini 调用封装、模型列表、JSON 提取。
  - `core/evaluator.py`：质量评估器（打分、漏测点、建议）。
- `config/`：配置与 Prompt 中心。
  - `config/prompts.py`：生成、评估、RAG 过滤、多模态解析等 Prompt 模板。
  - `config/settings.py`：代理设置、配置读写（含 `data/user_config.json`）。
- `data/`：本地数据目录（配置、向量库、原始文档），由 Docker volume 持久化。
- `test_prd/`：演示/测试用 PRD 与参考素材。
- `Dockerfile` 与 `docker-compose.yml`：容器化部署入口。

## 2. 你需要优先理解的关键链路

### 2.1 主业务链路（最重要）
1. 在侧边栏录入 API Key、选择模型。  
2. 在主页面上传 PRD/PDF/图片等材料。  
3. `RAGEngine` 检索历史案例与规范，得到上下文。  
4. 调用 LLM 生成测试用例；`split_text_and_json` 把“说明文字”与“JSON 数据”分离。  
5. 右侧预览并可编辑 JSON；支持导出与归档。  
6. 进入“智能评估”Tab，由 `Evaluator` 输出分数与改进建议。  

### 2.2 三个最常改的模块
- 改生成质量：先看 `config/prompts.py`（生成规则、输出结构）。
- 改知识库效果：看 `core/rag_engine.py`（切片策略、检索数量、过滤逻辑）。
- 改页面体验：看 `ui/main.py` + `ui/components.py`（布局、交互、展示）。

## 3. 新人容易踩坑的点

- **状态管理**：Streamlit 依赖 `st.session_state`，字段名改动会影响多处逻辑。
- **JSON 健壮性**：模型输出可能夹杂自然语言，需始终通过 `extract_json_from_text` 容错解析。
- **代理与网络**：若在国内环境，`HTTP_PROXY/HTTPS_PROXY` 是否正确直接决定 Gemini 调用是否成功。
- **向量库污染**：上传文档质量会直接影响召回；噪音文档会拉低生成质量。

## 4. 推荐学习路径（1~2 周）

### 第 1 阶段（第 1~2 天）
- 跑通项目（Docker 或本地）。
- 完整走一遍“上传 -> 生成 -> 导出 -> 评估”。
- 阅读 `readme.md` 中的产品定位与部署说明。

### 第 2 阶段（第 3~5 天）
- 精读 `ui/main.py`：理解每个 session_state 字段用途。
- 对照 `core/rag_engine.py`：看文档如何入库、检索、拼接上下文。
- 调整一个小 Prompt（如摘要或评估），观察输出差异。

### 第 3 阶段（第 6~10 天）
- 选择一个微改任务（示例）：
  - 增加新的导出格式；
  - 调整检索 Top-K；
  - 在评估报告中新增维度展示。
- 改完后做一次端到端自测并记录观察结论。

## 5. 后续进阶建议

- 把“Prompt 调参”与“RAG 数据治理”分开做 A/B 对比，避免变量混淆。
- 为关键流程补最小化自动化测试（JSON 解析、切片边界、评估报告字段校验）。
- 如果计划工程化落地，优先做：
  - 配置管理（环境变量优先级、密钥托管）；
  - 观测性（调用耗时、失败率、Token 成本）；
  - 规范化数据集（高质量历史案例入库流程）。
