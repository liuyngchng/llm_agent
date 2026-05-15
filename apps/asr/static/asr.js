let selectedFiles = [];
let pollingIntervals = {};
let waitStartTime = {};  // taskId → timestamp when progress first hit 100%

// 初始化
document.addEventListener('DOMContentLoaded', function() {
    initEventListeners();
    loadTaskHistory();
});

function initEventListeners() {
    // 上传按钮
    const uploadBtn = document.getElementById('uploadButton');
    const fileInput = document.getElementById('fileInput');

    uploadBtn.addEventListener('click', () => {
        fileInput.click();
    });

    fileInput.addEventListener('change', (e) => {
        handleFiles(e.target.files);
        fileInput.value = ''; // 清空，允许重复选择同一个文件
    });

    // 清空历史按钮
    document.getElementById('clearHistoryBtn').addEventListener('click', () => {
        if (confirm('确定要清空所有历史记录吗？')) {
            clearHistory();
        }
    });
}

function handleFiles(files) {
    for (let file of files) {
        // 检查文件格式
        const validExtensions = ['.mp3', '.m4a', '.amr', '.wav', '.flac', '.ogg', '.aac'];
        const ext = '.' + file.name.split('.').pop().toLowerCase();

        if (validExtensions.includes(ext)) {
            selectedFiles.push(file);
        } else {
            showMessage('系统', `不支持的文件格式: ${file.name}`, 'error');
        }
    }

    updateFileList();

    if (selectedFiles.length > 0) {
        // 自动上传所有选中的文件
        uploadAllFiles();
    }
}

function updateFileList() {
    const container = document.getElementById('fileListContainer');
    const fileList = document.getElementById('fileList');
    const badge = document.getElementById('fileCountBadge');

    if (selectedFiles.length === 0) {
        container.style.display = 'none';
        badge.style.display = 'none';
        return;
    }

    container.style.display = 'block';
    badge.style.display = 'flex';
    badge.textContent = selectedFiles.length;

    fileList.innerHTML = '';
    selectedFiles.forEach((file, index) => {
        const fileItem = document.createElement('div');
        fileItem.className = 'file-item';
        fileItem.innerHTML = `
            <div class="file-info">
                <i class="fas fa-file-audio"></i>
                <div class="file-details">
                    <span class="file-name">${escapeHtml(file.name)}</span>
                    <span class="file-size">${formatFileSize(file.size)}</span>
                </div>
            </div>
            <button class="file-remove" onclick="removeFile(${index})">
                <i class="fas fa-times"></i>
            </button>
        `;
        fileList.appendChild(fileItem);
    });
}

function removeFile(index) {
    selectedFiles.splice(index, 1);
    updateFileList();
}

function clearFileList() {
    selectedFiles = [];
    updateFileList();
}

function formatFileSize(bytes) {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

async function uploadAllFiles() {
    setUploadButtonEnabled(false);
    try {
        for (let file of selectedFiles) {
            await uploadFile(file);
        }
        clearFileList();
    } finally {
        setUploadButtonEnabled(true);
    }
}

function setUploadButtonEnabled(enabled) {
    const btn = document.getElementById('uploadButton');
    btn.disabled = !enabled;
    btn.classList.toggle('disabled', !enabled);
}

async function uploadFile(file) {
    // 显示上传中的消息
    const tempId = 'temp_' + Date.now() + '_' + Math.random();
    showMessage('用户', file.name, 'user', tempId);
    showMessage('系统', `正在处理 ${file.name}... <i class="fas fa-spinner spin"></i>`, 'processing', null, tempId);

    const formData = new FormData();
    formData.append('file', file);

    try {
        const response = await fetch('/api/upload', {
            method: 'POST',
            body: formData
        });

        const data = await response.json();

        if (response.ok) {
            // 替换处理中的消息
            updateMessage(tempId, `文件 ${file.name} 已上传，正在转写中... <i class="fas fa-spinner spin"></i>`);
            // 开始轮询任务状态
            startPolling(data.task_id, tempId, file.name);
        } else {
            updateMessage(tempId, `处理失败: ${data.error}`, 'error');
        }
    } catch (error) {
        console.error('Upload error:', error);
        updateMessage(tempId, `上传失败: ${error.message}`, 'error');
    }
}

function startPolling(taskId, messageId, filename) {
    if (pollingIntervals[taskId]) {
        clearInterval(pollingIntervals[taskId]);
    }

    const poll = async () => {
        try {
            const response = await fetch(`/api/status/${taskId}`);
            const data = await response.json();

            if (data.status === 'completed') {
                // 识别完成
                clearInterval(pollingIntervals[taskId]);
                delete pollingIntervals[taskId];
                delete waitStartTime[taskId];

                const resultHtml = `
                    <div>✅ 转写完成！</div>
                    <div style="margin-top: 10px; padding: 10px; background: #f0f2f5; border-radius: 8px;">
                        ${escapeHtml(data.result_text || '无识别结果')}
                    </div>
                    <button class="download-btn" onclick="downloadResult('${taskId}', '${filename}')">
                        <i class="fas fa-download"></i> 下载结果
                    </button>
                `;
                updateMessage(messageId, resultHtml, 'completed');

                // 添加到历史记录
                addToTaskHistory(taskId, filename, data.result_text);

            } else if (data.status === 'failed') {
                clearInterval(pollingIntervals[taskId]);
                delete pollingIntervals[taskId];
                delete waitStartTime[taskId];
                updateMessage(messageId, `❌ 转写失败: ${data.error}`, 'error');
            } else {
                // 更新状态及进度
                let statusHtml;
                if (data.status === 'converting') {
                    statusHtml = `正在处理 ${filename}: 转换音频格式... <i class="fas fa-spinner spin"></i>`;
                } else if (data.progress !== undefined && data.progress !== null) {
                    const pct = data.progress;
                    if (pct >= 100) {
                        // 数据已全部发送，等待服务端处理
                        if (!waitStartTime[taskId]) {
                            waitStartTime[taskId] = Date.now();
                        }
                        const elapsed = Math.floor((Date.now() - waitStartTime[taskId]) / 1000);
                        const minutes = Math.floor(elapsed / 60);
                        const seconds = elapsed % 60;
                        const elapsedStr = minutes > 0
                            ? `${minutes}分${seconds}秒`
                            : `${seconds}秒`;
                        statusHtml = `正在处理 ${filename}: 数据已发送，等待服务端处理中（${elapsedStr}）<i class="fas fa-spinner spin"></i>`;
                    } else {
                        statusHtml = `正在处理 ${filename}: ${pct}% <i class="fas fa-spinner spin"></i>`;
                        statusHtml += `
                            <div style="margin-top: 8px; background: #e9ecef; border-radius: 6px; height: 8px; overflow: hidden;">
                                <div style="width: ${pct}%; height: 100%; background: linear-gradient(90deg, #4b6cb7, #6c8de0); border-radius: 6px; transition: width 1s ease;"></div>
                            </div>`;
                    }
                } else {
                    statusHtml = `正在处理 ${filename}: 语音识别中... <i class="fas fa-spinner spin"></i>`;
                }
                updateMessage(messageId, statusHtml);
            }
        } catch (error) {
            console.error('Polling error:', error);
        }
    };

    // 立即执行一次
    poll();
    // 每2秒轮询一次
    pollingIntervals[taskId] = setInterval(poll, 2000);
}

async function downloadResult(taskId, filename) {
    try {
        const response = await fetch(`/api/download/${taskId}`);
        if (response.ok) {
            const blob = await response.blob();
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `${filename.replace(/\.[^/.]+$/, '')}_转写结果.txt`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
        } else {
            const error = await response.json();
            alert('下载失败: ' + error.error);
        }
    } catch (error) {
        console.error('Download error:', error);
        alert('下载失败: ' + error.message);
    }
}

function showMessage(sender, content, type = 'text', senderType = 'user', existingId = null) {
    const chatHistory = document.getElementById('chatHistory');
    const messageId = existingId || 'msg_' + Date.now() + '_' + Math.random();

    // 如果是现有消息的更新，找到并更新
    if (existingId) {
        const existingMsg = document.getElementById(existingId);
        if (existingMsg) {
            const contentDiv = existingMsg.querySelector('.message-content');
            if (contentDiv) {
                if (type === 'error') {
                    contentDiv.style.background = '#fee';
                    contentDiv.style.color = '#c33';
                } else if (type === 'completed') {
                    contentDiv.style.background = '#e8f5e9';
                }
                contentDiv.innerHTML = content;
            }
            return existingMsg;
        }
    }

    // 创建新消息
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${senderType === 'user' ? 'user-message' : 'ai-message'}`;
    messageDiv.id = messageId;

    const headerIcon = senderType === 'user' ? 'fa-user' : 'fa-robot';
    const headerText = senderType === 'user' ? '用户' : '系统';

    messageDiv.innerHTML = `
        <div class="message-header">
            <i class="fas ${headerIcon}"></i>
            <span>${escapeHtml(headerText)}</span>
        </div>
        <div class="message-content">
            ${content}
        </div>
    `;

    chatHistory.appendChild(messageDiv);
    messageDiv.scrollIntoView({ behavior: 'smooth', block: 'nearest' });

    return messageDiv;
}

function updateMessage(messageId, content, type = null) {
    const messageDiv = document.getElementById(messageId);
    if (messageDiv) {
        const contentDiv = messageDiv.querySelector('.message-content');
        if (contentDiv) {
            if (type === 'error') {
                contentDiv.style.background = '#fee';
                contentDiv.style.color = '#c33';
            } else if (type === 'completed') {
                contentDiv.style.background = '#e8f5e9';
            }
            contentDiv.innerHTML = content;
        }
    }
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

async function loadTaskHistory() {
    try {
        const response = await fetch('/api/tasks');
        const data = await response.json();

        if (data.tasks && data.tasks.length > 0) {
            // 显示最近的任务
            for (let task of data.tasks.slice(0, 5)) {
                if (task.status === 'completed') {
                    addToTaskHistory(task.task_id, task.original_filename, null);
                }
            }
        }
    } catch (error) {
        console.error('Load history error:', error);
    }
}

function addToTaskHistory(taskId, filename, resultText) {
    const chatHistory = document.getElementById('chatHistory');
    // 检查是否已经存在
    const existing = document.getElementById(`history_${taskId}`);
    if (existing) return;

    const historyDiv = document.createElement('div');
    historyDiv.className = 'message ai-message';
    historyDiv.id = `history_${taskId}`;

    historyDiv.innerHTML = `
        <div class="message-header">
            <i class="fas fa-history"></i>
            <span>历史记录</span>
        </div>
        <div class="message-content">
            <div><strong>📁 ${escapeHtml(filename)}</strong></div>
            <div style="margin-top: 8px;">✅ 已转写完成</div>
            <button class="download-btn" style="margin-top: 8px;" onclick="downloadResult('${taskId}', '${filename}')">
                <i class="fas fa-download"></i> 重新下载
            </button>
        </div>
    `;

    // 插入到欢迎消息之后
    const welcomeMsg = chatHistory.querySelector('.welcome-message');
    if (welcomeMsg && welcomeMsg.nextSibling) {
        chatHistory.insertBefore(historyDiv, welcomeMsg.nextSibling);
    } else {
        chatHistory.appendChild(historyDiv);
    }
}

async function clearHistory() {
    try {
        await fetch('/api/clear_tasks', { method: 'POST' });

        // 清空页面上的历史记录
        const chatHistory = document.getElementById('chatHistory');
        const messages = chatHistory.querySelectorAll('.message:not(.welcome-message)');
        messages.forEach(msg => {
            if (msg.id && msg.id.startsWith('history_')) {
                msg.remove();
            }
        });

        showMessage('系统', '历史记录已清空', 'text');
    } catch (error) {
        console.error('Clear history error:', error);
    }
}