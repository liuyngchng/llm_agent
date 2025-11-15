// 聊天容器和元素
const chatContainer = document.getElementById('chat-container');
const queryForm = document.getElementById('query-form');
const queryInput = document.getElementById('query-input');
const sendButton = document.getElementById('send-button');
const stopButton = document.getElementById('stop-button');
let isFetching = false;
let currentResponse = null;
let abortController = null;
let currentBotMessage = null;

// 文件上传相关元素
const fileUploadButton = document.getElementById('file-upload-button');
const fileInput = document.getElementById('file-input');
const fileList = document.getElementById('file-list');
const fileListContainer = document.getElementById('file-list-container');

// 已选择的文件列表
let selectedFiles = [];

// 页面加载时显示欢迎信息
window.onload = function() {
    loadKnowledgeBases();
    const greetingEl = document.getElementById('greeting');
    if (greetingEl && greetingEl.value) {
        addMessage(greetingEl.value, 'bot');
    }
    queryInput.focus();
    initFileUpload();
};

// 初始化文件上传功能
function initFileUpload() {
    // 点击上传按钮触发文件选择
    fileUploadButton.addEventListener('click', function() {
        fileInput.click();
    });

    // 文件选择处理
    fileInput.addEventListener('change', function(e) {
        handleFiles(e.target.files);
        // 清空input，允许重复选择相同文件
        fileInput.value = '';
    });

    // 拖拽功能
    const inputContainer = document.querySelector('.input-container');

    inputContainer.addEventListener('dragover', function(e) {
        e.preventDefault();
        inputContainer.style.borderColor = '#4b6cb7';
        inputContainer.style.background = '#f0f4ff';
    });

    inputContainer.addEventListener('dragleave', function(e) {
        e.preventDefault();
        inputContainer.style.borderColor = '#ddd';
        inputContainer.style.background = 'white';
    });

    inputContainer.addEventListener('drop', function(e) {
        e.preventDefault();
        inputContainer.style.borderColor = '#ddd';
        inputContainer.style.background = 'white';

        const files = e.dataTransfer.files;
        handleFiles(files);
    });
}

// 处理文件选择
function handleFiles(files) {
    for (let file of files) {
        if (validateFile(file)) {
            addFileToList(file);
        }
    }
    updateFileListVisibility();
}

// 文件验证
function validateFile(file) {
    const validTypes = [
        'application/pdf',
        'application/msword',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'application/vnd.ms-excel',
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        'text/plain',
        'application/vnd.ms-powerpoint',
        'application/vnd.openxmlformats-officedocument.presentationml.presentation',
        'image/jpeg',
        'image/jpg',
        'image/png',
        'application/zip',
        'application/x-rar-compressed'
    ];

    const maxSize = 10 * 1024 * 1024; // 10MB

    if (!validTypes.includes(file.type) && !file.name.match(/\.(pdf|doc|docx|xls|xlsx|txt|ppt|pptx|jpg|jpeg|png|zip|rar)$/i)) {
        alert(`不支持的文件类型: ${file.name}`);
        return false;
    }

    if (file.size > maxSize) {
        alert(`文件大小超过限制 (10MB): ${file.name}`);
        return false;
    }

    return true;
}

// 添加文件到列表
function addFileToList(file) {
    // 检查是否已存在同名文件
    if (selectedFiles.some(f => f.name === file.name && f.size === file.size)) {
        return;
    }

    selectedFiles.push(file);

    const fileItem = document.createElement('div');
    fileItem.className = 'file-item';

    const fileSize = formatFileSize(file.size);
    const fileExtension = getFileExtension(file.name);

    fileItem.innerHTML = `
        <div class="file-info">
            <div class="file-icon">
                <i class="fas fa-file"></i>
            </div>
            <span class="file-name" title="${file.name}">${file.name}</span>
            <span class="file-size">${fileSize}</span>
        </div>
        <button class="remove-file" type="button">
            <i class="fas fa-times"></i>
        </button>
    `;

    // 设置文件图标
    const fileIcon = fileItem.querySelector('.file-icon i');
    setFileIcon(fileIcon, fileExtension);

    // 移除文件
    fileItem.querySelector('.remove-file').addEventListener('click', function() {
        const index = selectedFiles.findIndex(f => f.name === file.name && f.size === file.size);
        if (index > -1) {
            selectedFiles.splice(index, 1);
        }
        fileItem.remove();
        updateFileListVisibility();
    });

    fileList.appendChild(fileItem);
}

// 更新文件列表显示状态
function updateFileListVisibility() {
    if (selectedFiles.length > 0) {
        fileList.classList.add('has-files');
        fileListContainer.classList.add('has-files');
    } else {
        fileList.classList.remove('has-files');
        fileListContainer.classList.remove('has-files');
    }
}

// 格式化文件大小
function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

// 获取文件扩展名
function getFileExtension(filename) {
    return filename.slice((filename.lastIndexOf('.') - 1 >>> 0) + 2).toLowerCase();
}

// 设置文件图标
function setFileIcon(iconElement, extension) {
    const iconMap = {
        'pdf': 'fa-file-pdf',
        'doc': 'fa-file-word',
        'docx': 'fa-file-word',
        'xls': 'fa-file-excel',
        'xlsx': 'fa-file-excel',
        'ppt': 'fa-file-powerpoint',
        'pptx': 'fa-file-powerpoint',
        'txt': 'fa-file-alt',
        'jpg': 'fa-file-image',
        'jpeg': 'fa-file-image',
        'png': 'fa-file-image',
        'zip': 'fa-file-archive',
        'rar': 'fa-file-archive'
    };

    const defaultIcon = 'fa-file';
    const iconClass = iconMap[extension] || defaultIcon;

    // 移除现有的文件类，添加新的
    iconElement.className = 'fas ' + iconClass;
}

// 表单提交事件
queryForm.addEventListener('submit', async function(e) {
    e.preventDefault();
    if (isFetching) return;

    const query = queryInput.value.trim();
    const hasFiles = selectedFiles.length > 0;

    // 修改1: 允许只有文件没有文本的情况
    if (!query && !hasFiles) {
        addMessage("请填写问题或上传文件", 'bot');
        return;
    }

    // 添加用户消息（显示文本和文件信息）
    let userMessage = query;
    let finalQuery = query; // 用于发送到后端的消息

    if (hasFiles) {
        const fileNames = selectedFiles.map(f => f.name).join(', ');
        // 如果只有文件没有文本，显示不同的消息
        userMessage = userMessage || "文件上传评审";
        finalQuery = finalQuery || "请对上传的文件进行评审"; // 优化：为后端提供明确的指令
        userMessage += `\n\n上传文件: ${fileNames}`;
    }
    addMessage(userMessage, 'user');

    // 如果有文件，先上传文件
    let uploadedFileInfos = [];
    if (hasFiles) {
        try {
            uploadedFileInfos = await uploadFiles();
            // 修改2: 文件上传成功后立即清空文件列表
            clearFileList();
        } catch (error) {
            console.error("文件上传失败:", error);
            addMessage("文件上传失败，请重试", 'bot');
            return;
        }
    }

    queryInput.value = '';
    updateFileListVisibility();

    try {
        // 开始获取数据
        await fetchQueryData(finalQuery, uploadedFileInfos);
    } catch (error) {
        console.error("请求出错:", error);
        if (currentBotMessage) {
            updateBotMessage("回答生成中断或出错，请重试");
        }
        resetUI();
    }
});

function clearFileList() {
    selectedFiles = [];
    fileList.innerHTML = '';
    updateFileListVisibility();
}

// 停止按钮事件
stopButton.addEventListener('click', function() {
    if (abortController) {
        abortController.abort();
    }

    if (currentBotMessage) {
        const messageBubble = currentBotMessage.querySelector('.bot-message-bubble');
        if (messageBubble) {
            // 保留现有内容，只移除加载动画
            const typingIndicator = messageBubble.querySelector('.typing-indicator');
            if (typingIndicator) {
                typingIndicator.remove();

                // 添加停止提示（不覆盖已有内容）
                const stopNotice = document.createElement('div');
                stopNotice.className = 'stop-notice';
                stopNotice.textContent = '（生成已停止）';
                messageBubble.appendChild(stopNotice);
            }
        }
    }
    resetUI();
});

// 获取流式数据
async function fetchQueryData(query, fileInfos = []) {
    isFetching = true;
    sendButton.disabled = true;
    stopButton.style.display = 'inline-block';

    // 创建新的中止控制器
    abortController = new AbortController();

    // 添加加载中的消息
    currentBotMessage = addMessage('<div class="typing-indicator"><span></span><span></span><span></span> 思考中...</div>', 'bot');

    try {
        const t = document.getElementById('t').value;
        const appSource = document.getElementById('app_source').value;
        const uid = document.getElementById('uid').value;

        // 构建请求数据
        const requestData = new URLSearchParams();
        requestData.append('msg', query);
        requestData.append('uid', uid);
        requestData.append('t', t);
        requestData.append('app_source', appSource);
        // 添加文件信息（JSON格式）
        if (fileInfos.length > 0) {
            requestData.append('file_infos', JSON.stringify(fileInfos));
        }

        const response = await fetch('/chat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded',
                'Accept': 'text/event-stream'
            },
            body: requestData,
            signal: abortController.signal,
            credentials: 'include'
        });

        // 检查响应是否正常
        if (!response.ok || !response.body) {
            throw new Error('网络响应失败');
        }

        // 设置当前响应对象
        currentResponse = response;

        // 读取流数据
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let accumulatedText = '';

        while (true) {
            const { value, done } = await reader.read();
            if (done) break;

            const chunk = decoder.decode(value, { stream: true });
            accumulatedText += chunk;

            // 更新消息内容
            updateBotMessage(accumulatedText);
        }

        // 添加复制按钮
        addCopyButton(currentBotMessage, accumulatedText);

    } catch (error) {
        if (error.name === 'AbortError') {
            console.log('请求已中止');
        } else {
            console.error('请求出错:', error);
            if (currentBotMessage) {
                updateBotMessage("回答生成出错，请重试");
            }
        }
    } finally {
        resetUI();
    }
}

// 上传多个文件
async function uploadFiles() {
    const uploadedFileInfos = [];
    const uid = document.getElementById('uid').value;
    const t = document.getElementById('t').value;

    // 逐个上传文件
    for (let file of selectedFiles) {
        try {
            const fileInfo = await uploadSingleFile(file, uid, t);
            uploadedFileInfos.push({
                file_id: fileInfo.file_id,
                file_name: fileInfo.file_name,
                original_name: file.name
            });
        } catch (error) {
            console.error(`文件 ${file.name} 上传失败:`, error);
            throw new Error(`文件 ${file.name} 上传失败`);
        }
    }

    return uploadedFileInfos;
}

// 上传单个文件
async function uploadSingleFile(file, uid, t) {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('uid', uid);
    formData.append('t', t);

    const response = await fetch('/upload', {
        method: 'POST',
        body: formData
    });

    if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`上传失败: ${errorText}`);
    }

    return await response.json();
}

// 加载知识库列表
async function loadKnowledgeBases() {
    const selector = document.getElementById('kb_selector');
    if (!selector) return;

    const uid = document.getElementById('uid').value;
    const t = document.getElementById('t').value;

    try {
        const response = await fetch('/vdb/pub/list', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ uid, t })
        });

        // 添加状态码检查
        if (!response.ok) {
            const errorText = await response.text();
            throw new Error(`API 错误 ${response.status}: ${errorText.slice(0, 100)}...`);
        }

        const result = await response.json();
        console.log('vdb_list=', result);

        // 清空选择器（保留第一个选项）
        while (selector.options.length > 1) {
            selector.remove(1);
        }

        // 添加知识库选项
        if (result.kb_list && result.kb_list.length > 0) {
            result.kb_list.forEach(kb => {
                const option = document.createElement('option');
                option.value = kb.id;
                option.textContent = kb.name;
                selector.appendChild(option);
            });
        }
    } catch (error) {
        console.error('加载知识库失败:', error);
    }
}

// 更新机器人消息
function updateBotMessage(text) {
    if (!currentBotMessage) return;

    const messageBubble = currentBotMessage.querySelector('.bot-message-bubble');
    if (messageBubble) {
        // 使用DOMPurify和Marked解析Markdown
        const sanitizedContent = DOMPurify.sanitize(
            marked.parse(text),
            { ADD_TAGS: ['canvas'], ADD_ATTR: ['id'] }
        );
        messageBubble.innerHTML = sanitizedContent;

        // 滚动到底部
        messageBubble.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }
}

// 添加消息到聊天容器
function addMessage(text, type) {
    const messageContainer = document.createElement('div');
    messageContainer.classList.add('message-container');

    let sanitizedContent = '';

    if (type === 'user') {
        messageContainer.classList.add('user-message-container');
        sanitizedContent = DOMPurify.sanitize(text);
        messageContainer.innerHTML = `
            <div class="message-bubble user-message-bubble">${sanitizedContent}</div>
        `;
    } else {
        messageContainer.classList.add('bot-message-container');
        sanitizedContent = DOMPurify.sanitize(
            marked.parse(text),
            { ADD_TAGS: ['canvas'], ADD_ATTR: ['id'] }
        );
        messageContainer.innerHTML = `
            <div class="bot-message-header">
                <img src="/static/bot.png" alt="AI Assistant">
                <span>数字专家</span>
            </div>
            <div class="message-bubble bot-message-bubble">${sanitizedContent}</div>
        `;
    }

    chatContainer.appendChild(messageContainer);
    messageContainer.scrollIntoView({ behavior: 'smooth' });
    return messageContainer;
}

// 添加复制按钮
function addCopyButton(messageContainer, text) {
    const actionsContainer = document.createElement('div');
    actionsContainer.classList.add('message-actions');

    const copyButton = document.createElement('button');
    copyButton.classList.add('copy-button');
    copyButton.innerHTML = '<i class="fas fa-copy"></i> 复制';
    copyButton.onclick = function() {
        navigator.clipboard.writeText(text).then(() => {
            const originalText = copyButton.innerHTML;
            copyButton.innerHTML = '<i class="fas fa-check"></i> 已复制!';
            setTimeout(() => {
                copyButton.innerHTML = originalText;
            }, 2000);
        });
    };

    actionsContainer.appendChild(copyButton);
    messageContainer.appendChild(actionsContainer);
}

// 重置UI状态
function resetUI() {
    isFetching = false;
    sendButton.disabled = false;
    stopButton.style.display = 'none';
    currentResponse = null;
    abortController = null;
}

// 键盘快捷键支持
queryInput.addEventListener('keydown', function(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        queryForm.dispatchEvent(new Event('submit'));
    }
});