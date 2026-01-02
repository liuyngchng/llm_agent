let currentDocEditor = null;
let currentDocument = null;

// 页面加载完成
document.addEventListener('DOMContentLoaded', function() {
    console.log('文档审阅系统已加载');

    // 检查OnlyOffice API是否可用
    if (typeof DocsAPI === 'undefined') {
        console.error('OnlyOffice API未加载，请检查Document Server是否运行');
    } else {
        console.log('OnlyOffice API已就绪');
    }

    // 绑定文件输入事件
    const fileInput = document.getElementById('fileInput');
    fileInput.addEventListener('change', handleFileSelect);

    // 添加上传按钮点击事件 - 改为直接触发文件选择
    const uploadButton = document.getElementById('uploadButton');
    uploadButton.addEventListener('click', function() {
        fileInput.click();
    });
});

// 文件选择处理
function handleFileSelect(e) {
    if (e.target.files.length > 0) {
        const file = e.target.files[0];
        handleFiles(file);
    }
}

// 处理上传
async function handleFiles(file) {
    const statusDiv = document.getElementById('uploadStatus');

    // 清空之前的消息
    statusDiv.innerHTML = '';

    // 显示上传状态
    const statusMessage = document.createElement('div');
    statusMessage.className = 'status-message';
    statusMessage.innerHTML = `<span class="loading"></span> 正在上传 ${file.name}...`;
    statusDiv.appendChild(statusMessage);

    try {
        // 创建FormData
        const formData = new FormData();
        formData.append('file', file);

        // 发送上传请求
        const response = await fetch('/api/documents/upload', {
            method: 'POST',
            body: formData
        });

        const result = await response.json();

        if (result.success) {
            // 上传成功
            statusMessage.className = 'status-message status-success';
            statusMessage.innerHTML = `✅ 上传成功: ${result.document.original_filename}`;

            // 3秒后自动隐藏成功消息
            setTimeout(() => {
                statusMessage.style.opacity = '0';
                setTimeout(() => {
                    if (statusMessage.parentNode === statusDiv) {
                        statusDiv.removeChild(statusMessage);
                    }
                }, 500);
            }, 3000);

            // 保存文档信息
            currentDocument = result.document;

            // 初始化OnlyOffice编辑器
            if (result.onlyoffice_config) {
                initDocumentEditor(result.onlyoffice_config);
            } else {
                // 如果没有返回配置，使用旧方式
                initDocumentEditorLegacy(result.document.url, result.document.key);
            }

        } else {
            // 上传失败
            statusMessage.className = 'status-message status-error';
            statusMessage.innerHTML = `❌ 上传失败: ${result.error || '未知错误'}`;
        }

    } catch (error) {
        statusMessage.className = 'status-message status-error';
        statusMessage.innerHTML = `❌ 上传出错: ${error.message}`;
        console.error('上传错误:', error);
    }
}

function initDocumentEditorLegacy(documentUrl, documentKey) {
    // 清空原来的编辑器
    const editorContainer = document.getElementById('editorContainer');
    editorContainer.innerHTML = '';

    // 直接使用API生成令牌
    const config = {
        token: generateLocalJWT(documentKey, documentUrl),
        document: {
            fileType: "docx",
            key: documentKey,
            title: currentDocument.original_filename,
            url: documentUrl,
            permissions: {
                edit: true,
                comment: true,
                download: true,
                print: true,
                review: true
            }
        },
        documentType: "word",
        editorConfig: {
            mode: "edit",
            lang: "zh-CN",
            callbackUrl: "http://localhost:19000/callback",
            customization: {
                autosave: true,
                autosaveInterval: 60,
                comments: true,
                compactHeader: true,
                feedback: false,
                help: false,
                hideRightMenu: false,
                toolbarNoTabs: false,
                zoom: 100
            },
            user: {
                id: "user-" + Date.now(),
                name: "审阅者"
            }
        }
    };

    console.log("使用备选配置:", config);
    currentDocEditor = new DocsAPI.DocEditor("editorContainer", config);
}

// 初始化OnlyOffice编辑器 - 简化版
function initDocumentEditor(onlyofficeConfig) {
    // 清空原来的编辑器
    const editorContainer = document.getElementById('editorContainer');
    editorContainer.innerHTML = '';

    console.log("收到的OnlyOffice配置:", onlyofficeConfig);

    // 直接使用后端返回的完整配置
    const config = onlyofficeConfig;

    // 添加事件监听
    config.events = {
        onDocumentReady: function() {
            console.log("文档已加载完成");
            analyzeDocument();
        },
        onError: function(event) {
            console.error("编辑器错误:", event.data);
            showError("文档加载失败: " + (event.data.errorDescription || event.data));
        }
    };

    console.log("最终配置:", config);

    // 检查token是否存在
    if (!config.token) {
        showError("JWT令牌缺失，请检查服务器配置");
        return;
    }

    try {
        currentDocEditor = new DocsAPI.DocEditor("editorContainer", config);
    } catch (error) {
        console.error("初始化编辑器失败:", error);
        showError("初始化编辑器失败: " + error.message);
    }
}


function generateLocalJWT(key, url) {
    try {
        // 这是一个简单的JWT生成示例
        // 注意：在生产环境中，JWT应该在后端生成
        const header = {
            "alg": "HS256",
            "typ": "JWT"
        };

        const payload = {
            "document": {
                "fileType": "docx",
                "key": key,
                "title": currentDocument.original_filename,
                "url": url
            },
            "iss": "FlaskApp",
            "iat": Math.floor(Date.now() / 1000)
        };

        // 将header和payload转为base64
        const encodedHeader = btoa(JSON.stringify(header)).replace(/=/g, '');
        const encodedPayload = btoa(JSON.stringify(payload)).replace(/=/g, '');

        // 模拟签名（实际应该在后端用secret签名）
        const signature = "simulated_signature";

        return `${encodedHeader}.${encodedPayload}.${signature}`;
    } catch (error) {
        console.error("生成JWT失败:", error);
        return "";
    }
}

// 保存文档
async function saveDocument(data) {
    try {
        // 这里可以处理文档保存逻辑
        console.log("保存文档数据:", data);

        // 如果是OnlyOffice回调的保存
        if (data.url) {
            // 可以下载最新版本
            const response = await fetch(data.url);
            // 处理下载的文件...
        }

    } catch (error) {
        console.error("保存文档失败:", error);
    }
}

// AI分析文档
async function analyzeDocument() {
    const suggestionsList = document.getElementById('suggestionsList');
    suggestionsList.innerHTML = `
        <div style="text-align: center; padding: 40px;">
            <div class="loading" style="margin: 0 auto 20px;"></div>
            <p>AI正在分析文档...</p>
        </div>
    `;

    try {
        // 模拟AI分析延迟
        await new Promise(resolve => setTimeout(resolve, 2000));

        // 模拟AI返回的数据
        const mockSuggestions = [
            {
                id: 1,
                originalText: "本项目",
                suggestion: "建议改为'本项目旨在'，使表达更完整",
                reason: "语言不够规范",
                position: "第1段",
                severity: "低"
            },
            {
                id: 2,
                originalText: "非常重大",
                suggestion: "建议改为'至关重要'或'极为重要'",
                reason: "用词可以更专业",
                position: "第2段",
                severity: "中"
            },
            {
                id: 3,
                originalText: "等等",
                suggestion: "建议列举具体项目，或删除'等等'",
                reason: "避免使用模糊词汇",
                position: "列举部分",
                severity: "低"
            },
            {
                id: 4,
                originalText: "尽快完成",
                suggestion: "建议明确具体时间，如'在本月底前完成'",
                reason: "时间要求不够明确",
                position: "时间安排部分",
                severity: "高"
            }
        ];

        // 显示AI意见
        displaySuggestions(mockSuggestions);

    } catch (error) {
        console.error("AI分析失败:", error);
        suggestionsList.innerHTML = `
            <div class="status-message status-error">
                ❌ AI分析失败: ${error.message}
            </div>
        `;
    }
}

// 显示AI意见
function displaySuggestions(suggestions) {
    const suggestionsList = document.getElementById('suggestionsList');

    if (suggestions.length === 0) {
        suggestionsList.innerHTML = `
            <div class="empty-state">
                <div style="font-size: 48px; margin-bottom: 20px;">✅</div>
                <h3>文档质量良好</h3>
                <p>AI未发现需要修改的问题</p>
            </div>
        `;
        return;
    }

    suggestionsList.innerHTML = suggestions.map(suggestion => `
        <div class="ai-suggestion" data-id="${suggestion.id}">
            <div class="suggestion-title">
                ${getSeverityIcon(suggestion.severity)}
                问题 ${suggestion.id}: ${suggestion.position}
            </div>
            <div class="suggestion-text">
                <strong>原文：</strong>${suggestion.originalText}
            </div>
            <div class="suggestion-text">
                <strong>建议：</strong>${suggestion.suggestion}
            </div>
            <div class="suggestion-text">
                <strong>原因：</strong>${suggestion.reason}
            </div>
            <div class="action-buttons">
                <button class="accept-btn" onclick="acceptSuggestion(${suggestion.id})">
                    接受建议
                </button>
                <button class="skip-btn" onclick="skipSuggestion(${suggestion.id})">
                    忽略
                </button>
            </div>
        </div>
    `).join('');
}

// 获取严重性图标
function getSeverityIcon(severity) {
    const icons = {
        '高': '🔴',
        '中': '🟡',
        '低': '🟢'
    };
    return icons[severity] || '⚪';
}

// 接受建议
function acceptSuggestion(suggestionId) {
    const suggestionElement = document.querySelector(`[data-id="${suggestionId}"]`);
    suggestionElement.style.opacity = '0.5';

    // 这里应该调用API应用修改到文档
    console.log(`接受建议 ${suggestionId}`);

    // 模拟修改文档
    if (currentDocEditor) {
        // 在实际应用中，这里应该调用OnlyOffice API修改文档
        alert(`建议 ${suggestionId} 已接受，将在文档中应用修改`);
    }
}

// 忽略建议
function skipSuggestion(suggestionId) {
    const suggestionElement = document.querySelector(`[data-id="${suggestionId}"]`);
    suggestionElement.style.display = 'none';
    console.log(`忽略建议 ${suggestionId}`);
}

// 显示错误消息
function showError(message) {
    const statusDiv = document.getElementById('uploadStatus');
    const errorMessage = document.createElement('div');
    errorMessage.className = 'status-message status-error';
    errorMessage.innerHTML = `❌ ${message}`;
    statusDiv.appendChild(errorMessage);

    // 5秒后自动隐藏
    setTimeout(() => {
        errorMessage.style.opacity = '0';
        setTimeout(() => {
            if (errorMessage.parentNode === statusDiv) {
                statusDiv.removeChild(errorMessage);
            }
        }, 500);
    }, 5000);
}