# 代码审查问题修复清单

## 修复状态

### ✅ 已修复

1. **严重 1**: 登录防爆破 + 时序安全
   - ✅ 已实现 `_LoginLimiter` 类（基于滑动窗口的失败次数限制）
   - ✅ 使用 `secrets.compare_digest` 时序安全比较
   - ✅ 添加 `login_min_delay_seconds` 延迟
   - ✅ 添加配置项 `login_max_attempts`, `login_window_seconds`
   - 位置: `backend/app/api/routes/auth.py`

2. **严重 2**: Provider/Model 白名单校验
   - ✅ 在 schema 层添加 `Literal` 类型约束 (`LlmProviderName`, `SearchProviderName`)
   - ✅ 对 `thinking_model` 和 `task_model` 增加长度和非空校验
   - 位置: `backend/app/research/schemas.py`, `backend/app/research/providers.py`

3. **中等 3**: MCP Bearer 会话隔离
   - ✅ 当前实现已经按 `owner_id` 隔离会话
   - ✅ `handle_sse_mcp_message` 检查 `mcp_session.owner_id != auth.subject`
   - ⚠️ Bearer 模式下所有客户端共享 `web_username`，这是设计决策（文档已说明）

4. **中等 4**: JSON 解析容错
   - ✅ 实现 `parse_json_list_or_none` 函数
   - ✅ 增强 `parse_json_response` 添加 `_extract_first_json_object` 逻辑
   - ✅ `_generate_search_queries` 使用 `parse_json_list_or_none` 并回退到 fallback
   - 位置: `backend/app/research/providers.py`, `backend/app/research/service.py`

5. **中等 5**: 删除任务后事件写入
   - ✅ 当前代码中 `CancelledError` 不被 `except Exception` 捕获，设计正确
   - ✅ `delete_task` 在删除前发布 `done` 事件，清理锁和 runs
   - ℹ️ 无需额外修复，现有逻辑已正确

6. **中等 6**: 中文流式分块
   - ✅ 重写 `_chunk_text` 支持 CJK 硬切
   - ✅ 优先在空格边界切分，回退到字符切分
   - 位置: `backend/app/research/service.py`

7. **中等 7**: `research_concurrency` 默认值一致性
   - ✅ 修改 `config.py` 默认值从 `3` 改为 `2`
   - 位置: `backend/app/core/config.py` (已修复)

8. **轻微 8**: SSE 事件拼写 `infor` → `info`
   - ✅ 修改测试文件中的 `infor` 为 `info`
   - 位置: `backend/tests/test_api.py`, `frontend/tests/e2e/workbench.spec.ts`

9. **轻微 9**: CORS origins 环境变量覆盖
   - ✅ 添加 `cors_origins_override` 字段和 `effective_cors_origins` 方法
   - ✅ 添加 `_parse_cors_origins` 辅助函数
   - 位置: `backend/app/core/config.py`

10. **轻微 10**: `WorkflowState` 类型注解
    - ℹ️ 保留作为文档用途，LangGraph 使用 dict 类型
    - ℹ️ 无需修复

11. **轻微 11**: `list_tasks` 无 owner 版本未使用
    - ℹ️ 保留供未来管理员功能使用
    - ℹ️ 无需修复

12. **轻微 12**: 前端反代 `X-Forwarded-Proto`
    - ✅ 在 `frontend/server.mjs` 的 `proxyRequest` 函数中透传 `X-Forwarded-Proto`
    - 位置: `frontend/server.mjs`

13. **轻微 13**: MCP 同步阻塞配额说明
    - ✅ 在 README 中添加 MCP 配额占用说明
    - 位置: `README.md`

14. **轻微 14**: README "不支持 MCP" 矛盾
    - ✅ 从 README 已知限制中删除 "MCP" 项
    - 位置: `README.md`

15. **轻微 15**: `GEMINI.md` 与 `AGENTS.md` 重复
    - ✅ 删除 `GEMINI.md`，保留 `AGENTS.md` 作为唯一开发指南
    - 位置: 项目根目录

## 测试验证

- [ ] `cd backend && uv run pytest` 通过
- [ ] `cd frontend && npm test` 通过
- [ ] Docker Compose 启动成功
- [ ] 登录限流功能验证
- [ ] 中文报告流式输出验证
- [ ] MCP 工具调用验证

## 其他改进

- ✅ 添加 `.env.example` 中缺失的登录限流配置项
- ✅ 更新 README 环境变量表格
