# Online Office 文档审阅系统

基于 OnlyOffice 和 AI 的智能文档审阅系统，支持在线编辑和 AI 分析。

## 功能特性

### 🚀 核心功能
- **在线文档编辑**: 集成 OnlyOffice，支持 Word、Excel、PPT、PDF 等格式
- **AI 智能审阅**: 自动分析文档并提供修改建议
- **多格式支持**: docx, doc, pdf, xlsx, pptx, txt
- **文档管理**: 上传、下载、删除、版本管理
- **实时协作**: 支持多人在线协作编辑

### 🧠 AI 分析能力
- **结构分析**: 检查文档结构合理性
- **格式建议**: 标题、段落、排版建议
- **语法检查**: 拼写、语法错误检测
- **可读性优化**: 段落分割、表达优化
- **内容质量**: 内容完整性检查

### 🛡️ 系统特性
- **数据库支持**: SQLite 数据持久化
- **用户反馈**: 实时状态提示和错误处理
- **健康检查**: 系统状态监控
- **响应式设计**: 支持移动端和桌面端

## 快速开始

### 1. 环境要求
- Python 3.8+
- OnlyOffice Document Server (可选，用于在线编辑)
- 500MB 磁盘空间

### 2. 安装依赖
```bash
pip install -r requirements.txt
```

### 3. 配置 OnlyOffice (可选)
如果您需要在线编辑功能，需要部署 OnlyOffice Document Server：

```bash
# 使用 Docker 运行 OnlyOffice
docker run -i -t -d -p 8080:80 onlyoffice/documentserver
```

### 4. 启动服务
```bash
cd /home/rd/workspace/llm_agent
PYTHONPATH=./:${PYTHONPATH} ./apps/online_office/app.py
```

服务将在 `http://localhost:19000` 启动。

### 5. 健康检查
访问 `http://localhost:19000/health` 检查系统状态。

## API 文档

### 文档管理
- `GET /api/documents/list` - 获取文档列表
- `POST /api/documents/upload` - 上传文档
- `GET /api/documents/<doc_id>` - 获取文档信息
- `DELETE /api/documents/delete/<doc_id>` - 删除文档
- `GET /api/documents/download/<doc_id>` - 下载文档

### AI 分析
- `POST /api/documents/analyze` - 分析文档内容
- `POST /api/documents/update-suggestion` - 更新建议状态

### 系统信息
- `GET /health` - 健康检查
- `GET /api/documents/stats` - 文档统计

## 项目结构

```
apps/online_office/
├── app.py              # 主应用
├── office_util.py      # OnlyOffice 工具函数
├── documents.db        # SQLite 数据库
├── documents/          # 文档存储目录
│   ├── uploads/        # 上传文档
│   ├── preview/        # 预览文档
│   └── temp/           # 临时文件
├── static/
│   ├── doc.js          # 前端逻辑
│   └── doc.css         # 样式文件
├── templates/
│   ├── index.html      # 主页面
│   └── error.html      # 错误页面
├── requirements.txt    # Python 依赖
└── logging.conf        # 日志配置
```

## 数据库设计

### documents 表
存储文档基本信息：
- id: 文档唯一标识
- original_filename: 原始文件名
- filename: 存储文件名
- file_type: 文件类型
- file_ext: 文件扩展名
- size: 文件大小
- upload_time: 上传时间
- status: 文档状态 (active/deleted)

### document_analysis 表
存储 AI 分析结果：
- doc_id: 关联文档ID
- category: 建议类别
- severity: 严重程度 (高/中/低)
- position: 问题位置
- description: 问题描述
- suggestion: 修改建议
- status: 建议状态 (pending/accepted/ignored)

## 配置说明

### cfg.yml (如果需要)
创建 `cfg.yml` 文件进行高级配置：

```yaml
server:
  host: 0.0.0.0
  port: 19000
  debug: false

onlyoffice:
  api_url: "http://localhost:8080"
  jwt_secret: "your_secret_key"
  jwt_enabled: true

storage:
  max_file_size: 52428800  # 50MB
  upload_folder: "./documents/uploads"
  preview_folder: "./documents/preview"

ai:
  enabled: true
  max_suggestions: 10
  analyze_timeout: 30
```

## 故障排除

### 常见问题

1. **OnlyOffice 无法加载**
   - 检查 OnlyOffice Document Server 是否运行: `curl http://localhost:8080/health`
   - 确认防火墙未阻止端口 8080

2. **上传失败**
   - 检查磁盘空间: `df -h`
   - 确认上传文件夹权限: `ls -la documents/`
   - 检查文件大小是否超过限制 (50MB)

3. **AI 分析失败**
   - 检查依赖是否安装: `python -c "import docx, pandas"`
   - 确认文档格式是否正确
   - 查看日志: `tail -f logs/online_office.log`

4. **数据库错误**
   - 检查数据库文件权限: `ls -la documents.db`
   - 重建数据库: 删除 documents.db 文件重启应用

### 日志查看
应用日志位于项目根目录的 `logs/` 文件夹下：
```bash
tail -f logs/online_office.log
```

## 开发指南

### 扩展 AI 分析功能
1. 在 `analyze_word_document()` 函数中添加新的分析规则
2. 在 `analyze_excel_document()` 函数中添加 Excel 分析逻辑
3. 集成第三方 NLP 库进行更深入的分析

### 添加新文件格式支持
1. 在 `ALLOWED_DOC_EXTENSIONS` 中添加新的扩展名
2. 实现对应的分析函数: `analyze_newformat_document()`
3. 更新前端的上传过滤器

### 性能优化
- 使用缓存减少重复分析
- 异步处理大型文档
- 数据库索引优化

## 许可证

MIT License

## 贡献指南

1. Fork 项目
2. 创建功能分支
3. 提交更改
4. 推送到分支
5. 创建 Pull Request

## 联系方式

如有问题或建议，请通过以下方式联系：
- GitHub Issues: [项目 Issues](https://github.com/liuyngchng/llm_agent/issues)
- 邮箱: liuyngchng@hotmail.com