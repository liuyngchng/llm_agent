// 全局变量
let chatHistory = [];
let currentStream = null;
let uploadedFiles = [];
let currentStreamController = null; // 用于停止流式响应
let isStreaming = false; // 是否正在流式传输

const CHAT_STORAGE_KEY = 'chat_messages';
const MAX_MESSAGES = 19;  // 与 common/const.py:MAX_HISTORY_SIZE 保持一致
let displayMessages = [];

function saveChatHistory() {
    if (displayMessages.length > MAX_MESSAGES) {
        displayMessages = displayMessages.slice(-MAX_MESSAGES);
    }
    localStorage.setItem(CHAT_STORAGE_KEY, JSON.stringify(displayMessages));
}

function loadChatHistory() {
    try {
        const raw = localStorage.getItem(CHAT_STORAGE_KEY);
        if (raw) {
            displayMessages = JSON.parse(raw);
            if (displayMessages.length > MAX_MESSAGES) {
                displayMessages = displayMessages.slice(-MAX_MESSAGES);
            }
        }
    } catch (e) {
        displayMessages = [];
    }
}

function restoreChatHistory() {
    const welcomeMsg = document.querySelector('.welcome-message');
    chatHistoryEl.innerHTML = '';
    displayMessages.forEach(msg => {
        const id = msg.messageId || undefined;
        addMessageToUI(msg.role, msg.content, id);
        chatHistory.push({ role: msg.role, content: msg.content, messageId: id });
    });
    if (welcomeMsg && displayMessages.length === 0) {
        chatHistoryEl.appendChild(welcomeMsg);
    }
    scrollToBottom();
}

// 配置 marked.js
marked.setOptions({
    highlight: function(code, lang) {
        if (lang && hljs.getLanguage(lang)) {
            try {
                return hljs.highlight(code, { language: lang }).value;
            } catch (e) {
                console.warn('代码高亮失败:', e);
            }
        }
        return code;
    },
    breaks: true, // 转换换行符为 <br>
    gfm: true, // 使用 GitHub Flavored Markdown
    headerIds: false, // 不自动生成 header id
});

// DOM 元素
const messageInput = document.getElementById('messageInput');
const sendButton = document.getElementById('sendButton');
const uploadButton = document.getElementById('uploadButton');
const chatHistoryEl = document.getElementById('chatHistory');
const clearChatBtn = document.getElementById('clearChat');
const modelNameEl = document.getElementById('modelName');
const currentModelEl = document.getElementById('currentModel');
const fileInput = document.getElementById('fileInput');
const fileList = document.getElementById('fileList');
const fileListContainer = document.getElementById('fileListContainer');
const fileCountBadge = document.getElementById('fileCountBadge');
const uid = document.getElementById('uid');
const t = document.getElementById('t');

// 初始化
document.addEventListener('DOMContentLoaded', function() {
    setTimeout(() => {
        loadConfig();
        setupEventListeners();
        loadChatHistory();
        if (displayMessages.length > 0) {
            restoreChatHistory();
        }
        messageInput.focus();
    }, 100);
});

// 加载配置
async function loadConfig() {
    try {
        const response = await fetch('/config');
        const config = await response.json();

        // 检查元素是否存在
        if (modelNameEl) {
            modelNameEl.textContent = `模型: ${config.model}`;
        }
        if (currentModelEl) {
            currentModelEl.textContent = config.model;
        }

        if (!config.has_api_key) {
            showError(__('doc_forge.no_api_key'));
        }
    } catch (error) {
        console.error('加载配置失败:', error);
    }
}

// 设置事件监听器
function setupEventListeners() {
    // 检查元素是否存在
    if (!sendButton || !clearChatBtn || !uploadButton || !messageInput) {
        console.error('DOM 元素未找到，重试中...');
        setTimeout(setupEventListeners, 100);
        return;
    }

    sendButton.addEventListener('click', sendMessage);
    clearChatBtn.addEventListener('click', clearChat);
    uploadButton.addEventListener('click', () => fileInput.click());

    // 文件选择事件
    fileInput.addEventListener('change', handleFileSelect);

    // 输入框键盘事件
    messageInput.addEventListener('keydown', function(event) {
        if (event.key === 'Enter' && !event.shiftKey) {
            event.preventDefault();
            sendMessage();
        }
    });

    // 输入框自动调整高度
    messageInput.addEventListener('input', function() {
        this.style.height = 'auto';
        this.style.height = (this.scrollHeight) + 'px';
    });
}

// 处理文件选择
function handleFileSelect(e) {
    const files = e.target.files;
    processFiles(files);
}

// 处理文件
function processFiles(files) {
    const maxSize = 10 * 1024 * 1024; // 10MB
    const allowedTypes = [
        'image/jpeg', 'image/png', 'image/gif',
        'application/pdf',
        'text/plain', 'text/markdown', 'text/html',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        'application/vnd.openxmlformats-officedocument.presentationml.presentation'
    ];

    let addedFiles = 0;

    for (let i = 0; i < files.length; i++) {
        const file = files[i];

        // 检查文件大小
        if (file.size > maxSize) {
            showError(__fmt_named('doc_forge.file_too_large', {name: file.name}));
            continue;
        }

        // 检查文件类型
        if (!allowedTypes.includes(file.type) && !file.name.match(/\.(txt|md|pdf|xlsx|docx|ppt|pptx|jpg|jpeg|png|gif)$/i)) {
            showError(__fmt_named('doc_forge.error_unsupported_file', {name: file.name}));
            continue;
        }

        // 检查是否已存在同名文件
        const existingFile = uploadedFiles.find(f => f.name === file.name && f.size === file.size);
        if (existingFile) {
            showError(__fmt_named('doc_forge.file_already_added', {name: file.name}));
            continue;
        }

        // 添加到上传列表
        addFileToList(file);
        uploadedFiles.push(file);
        addedFiles++;
    }

    if (addedFiles > 0) {
        updateFileListDisplay();
        showSuccess(__fmt_named('doc_forge.files_added', {n: addedFiles}));
    }

    fileInput.value = ''; // 重置input以便重新选择相同文件
}

// 添加文件到列表
function addFileToList(file) {
    const fileId = 'file-' + Date.now() + '-' + Math.random().toString(36).substr(2, 9);
    file.fileId = fileId;

    const fileItem = document.createElement('div');
    fileItem.className = 'file-item';
    fileItem.id = fileId;
    fileItem.innerHTML = `
        <div class="file-info">
            <i class="fas ${getFileIcon(file.type, file.name)}"></i>
            <div class="file-details">
                <span class="file-name">${file.name}</span>
                <span class="file-size">${formatFileSize(file.size)}</span>
            </div>
        </div>
        <button class="file-remove" onclick="removeFile('${fileId}')">
            <i class="fas fa-times"></i>
        </button>
    `;

    fileList.appendChild(fileItem);
}

// 获取文件图标
function getFileIcon(type, name) {
    if (type.startsWith('image/')) return 'fa-image';
    if (type === 'application/pdf') return 'fa-file-pdf';
    if (type.startsWith('text/')) return 'fa-file-alt';
    if (name.match(/\.docx?$/i)) return 'fa-file-word';
    if (name.match(/\.xlsx?$/i)) return 'fa-file-excel';
    if (name.match(/\.pptx?$/i)) return 'fa-file-powerpoint';
    return 'fa-file';
}

// 格式化文件大小
function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

// 移除文件
function removeFile(fileId) {
    // 从界面移除
    const fileElement = document.getElementById(fileId);
    if (fileElement) {
        fileElement.remove();
    }

    // 从数组移除
    uploadedFiles = uploadedFiles.filter(file => file.fileId !== fileId);
    updateFileListDisplay();
}

// 更新文件列表显示
function updateFileListDisplay() {
    if (uploadedFiles.length > 0) {
        fileListContainer.style.display = 'block';
        fileCountBadge.textContent = uploadedFiles.length;
        fileCountBadge.style.display = 'block';
    } else {
        fileListContainer.style.display = 'none';
        fileCountBadge.style.display = 'none';
    }

    // 调整文本区域边距
    if (uploadedFiles.length > 0) {
        messageInput.style.marginBottom = '10px';
    } else {
        messageInput.style.marginBottom = '0';
    }
}

// 清空文件列表
function clearFileList(silent = false) {
    if (uploadedFiles.length > 0) {
        // 如果是静默模式（发送时自动清理），不弹确认框
        if (!silent) {
            if (!confirm(__fmt_named('doc_forge.remove_files_confirm', {n: uploadedFiles.length}))) {
                return;
            }
        }

        fileList.innerHTML = '';
        uploadedFiles = [];
        updateFileListDisplay();

        // 如果不是静默模式，显示成功消息
        if (!silent) {
            showSuccess(__('doc_forge.files_removed'));
        }
    }
}

// 停止流式响应
function stopStream() {
    if (currentStreamController) {
        currentStreamController.abort();
        currentStreamController = null;
        isStreaming = false;
        showSuccess(__('doc_forge.generation_stopped'));
    }
}

// 发送消息
async function sendMessage() {
    // 如果正在流式传输，则停止
    if (isStreaming) {
        stopStream();
        return;
    }

    const message = messageInput.value.trim();

    // 如果没有消息和文件，直接返回
    if (!message && uploadedFiles.length === 0) {
        showError(__('doc_forge.need_message_or_file'));
        return;
    }

    // 设置流式传输状态
    isStreaming = true;

    // 禁用输入和上传按钮
    messageInput.disabled = true;
    uploadButton.disabled = true;

    // 设置发送按钮为停止按钮
    sendButton.disabled = false; // 允许点击停止
    sendButton.innerHTML = '<i class="fas fa-stop"></i> ' + __('doc_forge.stop');
    sendButton.classList.add('btn-stop'); // 添加停止按钮样式

    // 如果有文件，先上传文件
    let fileContents = [];
    if (uploadedFiles.length > 0) {
        try {
            fileContents = await uploadFiles();
        } catch (error) {
            console.error('上传文件失败:', error);
            showError(__('doc_forge.file_upload_failed'));
            resetInputState();
            return;
        }
    }

    // 构建完整消息 - 发送给API的消息包含文件内容
    let fullMessage = message;
    if (fileContents.length > 0) {
        fullMessage += '\n\n上传的文件内容:\n' + fileContents.join('\n\n---\n\n');
    }

    let displayMessage = message;
    if (uploadedFiles.length > 0) {
        // 如果用户有输入消息，先添加一个换行
        if (message.trim().length > 0) {
            displayMessage += '\n\n'; // 添加两个换行符，形成段落间距
        }

        const fileCount = uploadedFiles.length;
        const fileEmoji = fileCount === 1 ? '📎' : '📁';

        // 添加Markdown格式的文件清单
        displayMessage += `${fileEmoji} **${fileCount}个文件**\n\n`;

        // 添加文件列表
        uploadedFiles.forEach((file, index) => {
            const fileIcon = getFileEmoji(file.type, file.name);
            displayMessage += `${fileIcon} **${file.name}** (${formatFileSize(file.size)})\n`;
        });
    }

    // 添加用户消息到界面
    addMessageToUI('user', displayMessage);
    displayMessages.push({ role: 'user', content: displayMessage });
    saveChatHistory();

    // 清空输入框和文件列表
    messageInput.value = '';
    messageInput.style.height = 'auto';
    clearFileList(true);

    // 添加AI消息占位符
    const aiMessageId = 'ai-' + Date.now();
    addMessageToUI('ai', '', aiMessageId);

    // 发送请求
    try {
        await streamAIResponse(fullMessage, aiMessageId);
    } catch (error) {
        // 只在不是AbortError的情况下显示错误
        if (error.name !== 'AbortError') {
            console.error('发送消息失败:', error);
            updateAIMessage(aiMessageId, `<span class="error">${__('common.request_failed')} ${error.message}</span>`);
        } else {
            // AbortError是用户主动停止的，不显示为错误
            console.log('用户主动停止了请求');
        }
    } finally {
        resetInputState();
        isStreaming = false;
    }
}

// 获取文件对应的emoji图标（用于Markdown）
function getFileEmoji(type, name) {
    if (type.startsWith('image/')) return '🖼️';
    if (type === 'application/pdf') return '📄';
    if (type.startsWith('text/')) return '📝';
    if (name.match(/\.docx?$/i)) return '📋';
    if (name.match(/\.xlsx?$/i)) return '📊';
    if (name.match(/\.pptx?$/i)) return '📽️';
    return '📎';
}

// 上传文件到服务器
async function uploadFiles() {
    const fileContents = [];
    const savedFilenames = [];

    for (let i = 0; i < uploadedFiles.length; i++) {
        const file = uploadedFiles[i];
        const formData = new FormData();
        formData.append('file', file);
        formData.append('uid', uid.value);

        const response = await fetch('/upload', {
            method: 'POST',
            body: formData
        });

        if (!response.ok) {
            throw new Error(`文件 ${file.name} 上传失败`);
        }

        const result = await response.json();
        if (result.success) {
            fileContents.push(`文件: ${file.name}\n路径: upload_doc/${result.saved_filename}\n${result.content}`);
            savedFilenames.push(result.saved_filename);
        }

        // 更新进度提示
        showProgress(`正在处理文件 (${i + 1}/${uploadedFiles.length})...`);
    }

    return fileContents;
}

// 重置输入状态
function resetInputState() {
    messageInput.disabled = false;
    sendButton.disabled = false;
    uploadButton.disabled = false;
    sendButton.innerHTML = '<i class="fas fa-paper-plane"></i> ' + __('doc_forge.send');
    sendButton.classList.remove('btn-stop'); // 移除停止按钮样式
    messageInput.focus();
}

// 流式获取AI响应
async function streamAIResponse(userMessage, messageId) {
    // 添加用户消息到历史
    chatHistory.push({ role: 'user', content: userMessage });

    // 创建AbortController用于停止请求
    currentStreamController = new AbortController();

    // 发起流式请求
    const response = await fetch('/doc_forge', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            uid: uid.value,
            t: t.value,
            message: userMessage,
            history: chatHistory.slice(-10) // 发送最近10条历史

        }),
        signal: currentStreamController.signal
    });

    if (!response.ok) {
        if (response.status === 401) {
            try {
                const errData = await response.json();
                if (errData.error === 'auth_expired' && errData.redirect) {
                    window.location.href = errData.redirect;
                    return;
                }
            } catch (e) { /* fall through */ }
        }
        throw new Error(`HTTP错误: ${response.status}`);
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let aiResponse = '';

    // 创建消息对象来存储原始Markdown内容
    const messageObject = {
        id: messageId,
        rawMarkdown: '', // 存储原始Markdown内容
        renderedHTML: '',
        timestamp: Date.now()
    };

    // 将消息对象存储在全局
    window.messageMap = window.messageMap || {};
    window.messageMap[messageId] = messageObject;

    // 读取流数据
    while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value);
        const lines = chunk.split('\n');

        for (const line of lines) {
            if (line.startsWith('data: ')) {
                const data = line.substring(6);

                if (data === '[DONE]') {
                    // 流式传输完成
                    const completedMessage = {
                        role: 'assistant',
                        content: aiResponse,
                        messageId: messageId
                    };
                    chatHistory.push(completedMessage);
                    displayMessages.push({ role: 'assistant', content: aiResponse, messageId: messageId });
                    saveChatHistory();

                    // 更新消息对象的完整内容
                    messageObject.rawMarkdown = aiResponse;

                    return;
                }

                try {
                    const parsed = JSON.parse(data);

                    if (parsed.error) {
                        throw new Error(parsed.error);
                    }

                    if (parsed.content) {
                        aiResponse += parsed.content;
                        // 累积原始Markdown内容
                        messageObject.rawMarkdown += parsed.content;

                        // 使用新函数渲染 Markdown
                        renderAIMessage(messageId, aiResponse);
                    }
                } catch (e) {
                    console.error('解析流数据失败:', e);
                }
            }
        }
    }
}

// 添加消息到界面
function addMessageToUI(role, content, messageId = null) {
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${role}-message`;

    if (messageId) {
        messageDiv.id = messageId;
    }

    let displayContent = content;

    if (role === 'ai') {
        // AI消息：包含操作按钮和内容
        messageDiv.innerHTML = `
            <div class="message-content markdown-content">${displayContent}</div>
            <div class="message-actions">
                <div class="action-buttons">
                    <button class="action-btn copy-btn" title="${__('doc_forge.copy')}">
                        <i class="fas fa-copy"></i>
                    </button>
                    <button class="action-btn refresh-btn" title="${__('doc_forge.regenerate')}">
                        <i class="fas fa-redo"></i>
                    </button>
                    <button class="action-btn like-btn" title="${__('doc_forge.like')}">
                        <i class="fas fa-thumbs-up"></i>
                    </button>
                    <button class="action-btn dislike-btn" title="${__('doc_forge.dislike')}">
                        <i class="fas fa-thumbs-down"></i>
                    </button>
                    <button class="action-btn download-btn" title="${__('common.download')}">
                        <i class="fas fa-download"></i>
                    </button>
                </div>
            </div>
        `;
    } else {
        // 用户消息：保持原有结构
        messageDiv.innerHTML = `
            <div class="message-avatar">
                <i class="fas fa-user"></i>
            </div>
            <div class="message-content">${displayContent}</div>
        `;
    }

    chatHistoryEl.appendChild(messageDiv);

    // 如果是AI消息并且有内容，渲染Markdown
    if (role === 'ai' && content) {
        renderAIMessage(messageId, content);
    }

    // 为AI消息添加事件监听器
    if (role === 'ai') {
        setTimeout(() => setupMessageActions(messageDiv, messageId), 100);
    }

    scrollToBottom();
}

// 设置消息操作按钮事件
function setupMessageActions(messageDiv, messageId) {
    const contentDiv = messageDiv.querySelector('.message-content');
    const copyBtn = messageDiv.querySelector('.copy-btn');
    const refreshBtn = messageDiv.querySelector('.refresh-btn');
    const likeBtn = messageDiv.querySelector('.like-btn');
    const dislikeBtn = messageDiv.querySelector('.dislike-btn');
    const downloadBtn = messageDiv.querySelector('.download-btn');

    // 复制功能
    copyBtn.addEventListener('click', async () => {
        const textToCopy = contentDiv.textContent;
        try {
            await navigator.clipboard.writeText(textToCopy);
            showSuccess(__('doc_forge.copied'));
            copyBtn.innerHTML = '<i class="fas fa-check"></i>';
            setTimeout(() => {
                copyBtn.innerHTML = '<i class="fas fa-copy"></i>';
            }, 2000);
        } catch (err) {
            console.error('复制失败:', err);
            showError(__('doc_forge.copy_failed'));
        }
    });

    // 重新生成功能
    refreshBtn.addEventListener('click', () => {
        if (confirm(__('doc_forge.regenerate_confirm'))) {
            // 移除当前消息
            messageDiv.remove();

            // 从历史记录中移除
            const aiIndex = chatHistory.findIndex(msg => msg.role === 'assistant');
            if (aiIndex !== -1) {
                chatHistory.splice(aiIndex, 1);
            }

            // 重新发送最后一条用户消息
            const lastUserMessage = chatHistory.findLast(msg => msg.role === 'user');
            if (lastUserMessage) {
                sendMessageFromHistory(lastUserMessage.content);
            }
        }
    });

    // 点赞功能
    likeBtn.addEventListener('click', () => {
        likeBtn.classList.toggle('active');
        if (likeBtn.classList.contains('active')) {
            likeBtn.innerHTML = '<i class="fas fa-thumbs-up" style="color: #4b6cb7;"></i>';
            dislikeBtn.classList.remove('active');
            dislikeBtn.innerHTML = '<i class="fas fa-thumbs-down"></i>';
            console.log(`点赞消息: ${messageId}`);
            showSuccess(__('doc_forge.liked'));
        } else {
            likeBtn.innerHTML = '<i class="fas fa-thumbs-up"></i>';
        }
    });

    // 点踩功能
    dislikeBtn.addEventListener('click', () => {
        dislikeBtn.classList.toggle('active');
        if (dislikeBtn.classList.contains('active')) {
            dislikeBtn.innerHTML = '<i class="fas fa-thumbs-down" style="color: #e74c3c;"></i>';
            likeBtn.classList.remove('active');
            likeBtn.innerHTML = '<i class="fas fa-thumbs-up"></i>';
            console.log(`点踩消息: ${messageId}`);
            showSuccess(__('doc_forge.disliked'));
        } else {
            dislikeBtn.innerHTML = '<i class="fas fa-thumbs-down"></i>';
        }
    });

    // 下载功能
    downloadBtn.addEventListener('click', () => {
        // 从全局消息映射中获取原始Markdown内容
        let markdownContent = '';

        if (window.messageMap && window.messageMap[messageId]) {
            markdownContent = window.messageMap[messageId].rawMarkdown;
        }

        // 如果消息映射中没有，尝试从聊天历史中查找
        if (!markdownContent) {
            for (let i = chatHistory.length - 1; i >= 0; i--) {
                const msg = chatHistory[i];
                if (msg.messageId === messageId) {
                    markdownContent = msg.content;
                    break;
                }
            }
        }

        // 如果还是没找到，使用当前显示的内容
        if (!markdownContent) {
            // 获取文本内容（虽然没有格式，但总比没有好）
            markdownContent = contentDiv.textContent;
        }

        // 创建Markdown文件
        const blob = new Blob([markdownContent], {
            type: 'text/markdown;charset=utf-8'
        });

        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;

        // 生成文件名，包含时间戳
        const now = new Date();
        const dateStr = now.toISOString().slice(0, 10); // YYYY-MM-DD
        const timeStr = now.toTimeString().slice(0, 8).replace(/:/g, '-'); // HH-MM-SS

        a.download = `AI_Response_${dateStr}_${timeStr}.md`;

        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);

        showSuccess(__('doc_forge.download_md'));
    });
}

// 从历史记录发送消息
async function sendMessageFromHistory(messageContent) {
    messageInput.value = messageContent;
    messageInput.style.height = 'auto';
    messageInput.style.height = (messageInput.scrollHeight) + 'px';

    // 直接调用发送消息函数
    await sendMessage();
}

// 渲染AI消息的Markdown
function renderAIMessage(messageId, content) {
    const messageDiv = document.getElementById(messageId);
    if (messageDiv) {
        const contentDiv = messageDiv.querySelector('.message-content');
        try {
            // 使用 marked 渲染 Markdown
            const rendered = marked.parse(content);
            contentDiv.innerHTML = rendered;

            // 应用代码高亮
            contentDiv.querySelectorAll('pre code').forEach((block) => {
                hljs.highlightElement(block);
            });

            // 添加Markdown内容的特殊样式
            contentDiv.classList.add('markdown-rendered');

            // 为表格添加样式
            contentDiv.querySelectorAll('table').forEach((table) => {
                table.classList.add('markdown-table');
            });

            // 增强下载链接：新标签页打开 + 样式
            contentDiv.querySelectorAll('a[href^="/download/"]').forEach((link) => {
                link.setAttribute('target', '_blank');
                link.classList.add('download-link');
                // 添加下载图标
                if (!link.querySelector('.fa-download')) {
                    const icon = document.createElement('i');
                    icon.className = 'fas fa-download';
                    icon.style.marginRight = '4px';
                    link.prepend(icon);
                }
            });
        } catch (e) {
            console.error('Markdown渲染失败:', e);
            // 如果渲染失败，回退到纯文本
            contentDiv.innerHTML = content.replace(/\n/g, '<br>');
        }
        scrollToBottom();
    }
}

// 旧函数保留兼容性（直接调用新函数）
function updateAIMessage(messageId, content) {
    renderAIMessage(messageId, content);
}

// 清空聊天
function clearChat() {
    if (confirm(__('doc_forge.clear_chat_confirm'))) {
        // 中止当前流
        if (isStreaming) {
            stopStream();
        }

        // 清空历史
        chatHistory = [];
        displayMessages = [];
        saveChatHistory();
        clearFileList();

        // 清空界面（保留欢迎消息）
        const welcomeMessage = document.querySelector('.welcome-message');
        chatHistoryEl.innerHTML = '';
        if (welcomeMessage) {
            chatHistoryEl.appendChild(welcomeMessage);
        }

        scrollToBottom();
    }
}

// 显示错误
function showError(message) {
    const errorDiv = document.createElement('div');
    errorDiv.className = 'error-message';
    errorDiv.innerHTML = `<i class="fas fa-exclamation-triangle"></i> ${message}`;
    chatHistoryEl.appendChild(errorDiv);
    setTimeout(() => errorDiv.remove(), 5000);
}

// 显示成功消息
function showSuccess(message) {
    const successDiv = document.createElement('div');
    successDiv.className = 'success-message';
    successDiv.innerHTML = `<i class="fas fa-check-circle"></i> ${message}`;
    chatHistoryEl.appendChild(successDiv);
    setTimeout(() => successDiv.remove(), 3000);
}

// 显示进度消息
function showProgress(message) {
    // 如果有旧的进度消息，先移除
    const oldProgress = document.querySelector('.progress-message');
    if (oldProgress) oldProgress.remove();

    const progressDiv = document.createElement('div');
    progressDiv.className = 'progress-message';
    progressDiv.innerHTML = `<i class="fas fa-spinner fa-spin"></i> ${message}`;
    chatHistoryEl.appendChild(progressDiv);
    scrollToBottom();

    // 5秒后自动移除
    setTimeout(() => {
        if (progressDiv.parentNode) {
            progressDiv.remove();
        }
    }, 5000);
}

// 滚动到底部
function scrollToBottom() {
    chatHistoryEl.scrollTop = chatHistoryEl.scrollHeight;
}

function handleKeyPress(event) {
    if (event.key === 'Enter' && !event.shiftKey) {
        event.preventDefault();
        sendMessage();
    }
}

window.handleKeyPress = handleKeyPress;
window.removeFile = removeFile;
window.clearFileList = clearFileList;