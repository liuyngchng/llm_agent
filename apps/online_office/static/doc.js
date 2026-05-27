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
    statusMessage.innerHTML = `<span class="loading"></span> ${__('online_office.uploading_file')}${file.name}...`;
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
            statusMessage.innerHTML = `✅ ${__('online_office.upload_success')}${result.document.original_filename}`;

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
            statusMessage.innerHTML = `❌ ${__('online_office.upload_failed_prefix')}${result.error || __('common.unknown_error')}`;
        }

    } catch (error) {
        statusMessage.className = 'status-message status-error';
        statusMessage.innerHTML = `❌ ${__('online_office.upload_error')}${error.message}`;
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
                name: __('online_office.reviewer_name')
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
            showError(__('online_office.doc_load_failed') + (event.data.errorDescription || event.data));
        }
    };

    console.log("最终配置:", config);

    // 检查token是否存在
    if (!config.token) {
        showError(__('online_office.jwt_missing'));
        return;
    }

    try {
        currentDocEditor = new DocsAPI.DocEditor("editorContainer", config);
    } catch (error) {
        console.error("初始化编辑器失败:", error);
        showError(__('online_office.init_editor_failed') + error.message);
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
        <div class="empty-state">
            <div class="loading" style="width: 40px; height: 40px; margin: 0 auto 20px;"></div>
            <h3>${__('online_office.ai_analyzing')}</h3>
            <p>${__('online_office.ai_analyzing_desc')}</p>
        </div>
    `;

    try {
        if (!currentDocument || !currentDocument.id) {
            throw new Error(__('online_office.no_doc_to_analyze'));
        }

        // 调用后端AI分析接口
        const response = await fetch('/api/documents/analyze', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                doc_id: currentDocument.id
            })
        });

        const result = await response.json();

        if (result.success && result.suggestions) {
            // 转换格式为前端所需
            const suggestions = result.suggestions.map(suggestion => ({
                id: suggestion.id,
                category: suggestion.category,
                severity: suggestion.severity,
                position: suggestion.position,
                description: suggestion.description,
                suggestion: suggestion.suggestion
            }));
            
            displaySuggestions(suggestions);
            
            // 显示分析完成消息
            showStatusMessage(`✅ ${__fmt_named('online_office.analysis_complete', {n: suggestions.length})}`, 'success');
        } else {
            throw new Error(result.error || __('online_office.analysis_failed'));
        }

    } catch (error) {
        console.error("AI分析失败:", error);
        suggestionsList.innerHTML = `
            <div class="empty-state">
                <div style="font-size: 48px; margin-bottom: 20px;">⚠️</div>
                <h3>${__('online_office.ai_unavailable')}</h3>
                <p>${error.message}</p>
                <p class="file-types">${__('online_office.ai_unavailable_desc')}</p>
            </div>
        `;
        showStatusMessage(`⚠️ ${__fmt_named('online_office.ai_analysis_failed', {msg: error.message})}`, 'warning');
    }
}

// 显示AI意见
function displaySuggestions(suggestions) {
    const suggestionsList = document.getElementById('suggestionsList');

    if (suggestions.length === 0) {
        suggestionsList.innerHTML = `
            <div class="empty-state">
                <div style="font-size: 48px; margin-bottom: 20px;">✅</div>
                <h3>${__('online_office.doc_good_quality')}</h3>
                <p>${__('online_office.doc_good_desc')}</p>
                <p class="file-types">${__('online_office.doc_good_info')}</p>
            </div>
        `;
        return;
    }

    suggestionsList.innerHTML = suggestions.map(suggestion => `
        <div class="ai-suggestion" data-id="${suggestion.id}" data-severity="${suggestion.severity}">
            <div class="suggestion-header">
                <div class="suggestion-category">${suggestion.category}</div>
                <div class="suggestion-severity ${suggestion.severity.toLowerCase()}">
                    ${getSeverityIcon(suggestion.severity)} ${suggestion.severity}
                </div>
            </div>
            <div class="suggestion-title">
                ${__('online_office.problem_label_small')} ${suggestion.id}: ${suggestion.position}
            </div>
            <div class="suggestion-content">
                <div class="suggestion-item">
                    <span class="label">${__('online_office.problem_description')}</span>
                    <span class="value">${suggestion.description}</span>
                </div>
                <div class="suggestion-item">
                    <span class="label">${__('online_office.suggestion')}</span>
                    <span class="value">${suggestion.suggestion}</span>
                </div>
            </div>
            <div class="action-buttons">
                <button class="accept-btn" onclick="acceptSuggestion(${suggestion.id})">
                    <i class="fas fa-check"></i> ${__('online_office.accept_suggestion')}
                </button>
                <button class="ignore-btn" onclick="ignoreSuggestion(${suggestion.id})">
                    <i class="fas fa-times"></i> ${__('online_office.ignore')}
                </button>
                <button class="info-btn" onclick="showSuggestionDetails(${suggestion.id})">
                    <i class="fas fa-info-circle"></i> ${__('online_office.details')}
                </button>
            </div>
        </div>
    `).join('');
}

// 获取严重性图标
function getSeverityIcon(severity) {
    const icons = {
        [__('online_office.severity_high')]: '🔴',
        [__('online_office.severity_medium')]: '🟡',
        [__('online_office.severity_low')]: '🟢'
    };
    return icons[severity] || '⚪';
}

// 接受建议
function acceptSuggestion(suggestionId) {
    const suggestionElement = document.querySelector(`[data-id="${suggestionId}"]`);
    if (!suggestionElement) return;
    
    // 标记为已接受
    suggestionElement.classList.add('accepted');
    suggestionElement.querySelector('.accept-btn').disabled = true;
    suggestionElement.querySelector('.accept-btn').innerHTML = `<i class="fas fa-check-circle"></i> ${__('online_office.accepted')}`;
    
    // 显示成功消息
    const position = suggestionElement.querySelector('.suggestion-title').textContent;
    showStatusMessage(`✅ ${__fmt_named('online_office.accept_success', {pos: position})}`, 'success');
    
    // 在实际应用中，这里应该调用后端API应用修改
    applySuggestionToDocument(suggestionId);
}

// 忽略建议
function ignoreSuggestion(suggestionId) {
    const suggestionElement = document.querySelector(`[data-id="${suggestionId}"]`);
    if (!suggestionElement) return;
    
    // 添加淡出动画
    suggestionElement.style.opacity = '0.5';
    suggestionElement.style.transform = 'translateX(-10px)';
    
    setTimeout(() => {
        suggestionElement.style.display = 'none';
        showStatusMessage(`📝 ${__('online_office.ignored_one')}`, 'info');
    }, 300);
}

// 显示建议详情
function showSuggestionDetails(suggestionId) {
    const suggestionElement = document.querySelector(`[data-id="${suggestionId}"]`);
    if (!suggestionElement) return;
    
    const category = suggestionElement.querySelector('.suggestion-category').textContent;
    const severity = suggestionElement.querySelector('.suggestion-severity').textContent;
    const title = suggestionElement.querySelector('.suggestion-title').textContent;
    const description = suggestionElement.querySelector('.suggestion-item:nth-child(1) .value').textContent;
    const suggestion = suggestionElement.querySelector('.suggestion-item:nth-child(2) .value').textContent;
    
    const details = `
        <div class="suggestion-details">
            <h4>${title}</h4>
            <div class="details-meta">
                <span class="meta-item"><strong>${__('online_office.category_label')}</strong> ${category}</span>
                <span class="meta-item"><strong>${__('online_office.severity_label')}</strong> ${severity}</span>
            </div>
            <div class="details-content">
                <p><strong>${__('online_office.problem_label_small')}</strong> ${description}</p>
                <p><strong>${__('online_office.suggestion_label_small')}</strong> ${suggestion}</p>
            </div>
            <div class="details-actions">
                <button onclick="acceptSuggestion(${suggestionId})" class="accept-btn">
                    <i class="fas fa-check"></i> ${__('online_office.accept_suggestion_btn')}
                </button>
                <button onclick="closeDetails()" class="close-btn">
                    ${__('online_office.close_btn')}
                </button>
            </div>
        </div>
    `;
    
    // 创建详情模态框
    const modal = document.createElement('div');
    modal.className = 'modal-overlay';
    modal.innerHTML = `
        <div class="modal-content">
            ${details}
        </div>
    `;
    
    document.body.appendChild(modal);
    
    // 点击外部关闭
    modal.addEventListener('click', function(e) {
        if (e.target === modal) {
            closeDetails();
        }
    });
}

function closeDetails() {
    const modal = document.querySelector('.modal-overlay');
    if (modal) {
        modal.remove();
    }
}

// 应用建议到文档
async function applySuggestionToDocument(suggestionId) {
    try {
        // 在实际应用中，这里应该调用后端API处理文档修改
        // 目前只是记录日志
        console.log(`应用建议 ${suggestionId} 到文档`);
        
        // 模拟API调用
        // const response = await fetch('/api/documents/apply-suggestion', {
        //     method: 'POST',
        //     headers: {
        //         'Content-Type': 'application/json',
        //     },
        //     body: JSON.stringify({
        //         doc_id: currentDocument.id,
        //         suggestion_id: suggestionId
        //     })
        // });
        
    } catch (error) {
        console.error('应用建议失败:', error);
    }
}

// 显示状态消息
function showStatusMessage(message, type = 'info') {
    const statusDiv = document.getElementById('uploadStatus');
    
    // 移除旧消息
    const oldMessages = statusDiv.querySelectorAll('.status-message');
    oldMessages.forEach(msg => {
        msg.style.opacity = '0';
        setTimeout(() => {
            if (msg.parentNode === statusDiv) {
                statusDiv.removeChild(msg);
            }
        }, 300);
    });
    
    // 添加新消息
    const messageDiv = document.createElement('div');
    messageDiv.className = `status-message status-${type}`;
    messageDiv.innerHTML = message;
    
    statusDiv.appendChild(messageDiv);
    
    // 自动隐藏（成功消息3秒，错误消息5秒）
    const timeout = type === 'error' ? 5000 : 3000;
    setTimeout(() => {
        messageDiv.style.opacity = '0';
        setTimeout(() => {
            if (messageDiv.parentNode === statusDiv) {
                statusDiv.removeChild(messageDiv);
            }
        }, 300);
    }, timeout);
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