// 聊天元素
const chatContainer = document.getElementById('chat-container');
const queryForm = document.getElementById('query-form');
const queryInput = document.getElementById('query-input');
const sendButton = document.getElementById('send-button');
const stopButton = document.getElementById('stop-button');

// 获取 token
function getToken() {
    return localStorage.getItem('token') || '';
}

// 带认证头的 fetch 封装
function authFetch(url, options) {
    options = options || {};
    options.headers = options.headers || {};
    options.headers['Authorization'] = 'Bearer ' + getToken();
    return fetch(url, options);
}

let isFetching = false;
let abortController = null;
let currentBotMessage = null;

const MAX_MESSAGES = 50;
let messages = [];

// 会话 ID
let sessionId = crypto.randomUUID ? crypto.randomUUID() : Date.now().toString(36) + Math.random().toString(36).slice(2);

// localStorage key
function getStorageKey() {
    var uidEl = document.getElementById('uid');
    var uid = uidEl ? uidEl.value : 'default';
    return 'chat2kb_messages_' + uid;
}

function saveMessages() {
    if (messages.length > MAX_MESSAGES) {
        messages = messages.slice(-MAX_MESSAGES);
    }
    localStorage.setItem(getStorageKey(), JSON.stringify(messages));
}

function loadMessages() {
    try {
        const raw = localStorage.getItem(getStorageKey());
        if (raw) {
            messages = JSON.parse(raw);
            if (messages.length > MAX_MESSAGES) {
                messages = messages.slice(-MAX_MESSAGES);
            }
            // 清理未完成的消息（含 typing-indicator 或被中断的）
            var cleaned = false;
            messages = messages.filter(function(m) {
                if (m.type === 'bot' && m.text.indexOf('typing-indicator') !== -1) {
                    cleaned = true;
                    return false; // 丢掉"思考中..."
                }
                return true;
            });
            if (cleaned) {
                localStorage.setItem(getStorageKey(), JSON.stringify(messages));
            }
        }
    } catch (e) {
        messages = [];
    }
}

function restoreMessages() {
    chatContainer.innerHTML = '';
    messages.forEach(m => addMessageToDOM(m.text, m.type));
}

// 加载可用工作流列表
async function loadWorkflows() {
    try {
        var resp = await authFetch('/api/workflows');
        var json = await resp.json();
        var wfs = json.data || [];
        var sel = document.getElementById('workflow-select');
        if (sel) {
            wfs.forEach(function(w) {
                var opt = document.createElement('option');
                opt.value = w.id;
                opt.textContent = w.name;
                sel.appendChild(opt);
            });
        }
    } catch(e) {
        console.warn('加载工作流列表失败:', e);
    }
}

// 页面加载
window.onload = function() {
    loadMessages();
    if (messages.length > 0) {
        restoreMessages();
    }
    loadWorkflows();
    queryInput.focus();
};

// 表单提交
queryForm.addEventListener('submit', async function(e) {
    e.preventDefault();
    if (isFetching) return;

    const query = queryInput.value.trim();
    if (!query) return;

    // 用户消息
    addMessage(query, 'user');
    queryInput.value = '';
    queryInput.focus();

    try {
        await fetchQueryData(query);
    } catch (error) {
        console.error('请求出错:', error);
        if (currentBotMessage) {
            updateBotMessage('抱歉，生成回复时出错，请重试。');
        }
        resetUI();
    }
});

// 停止按钮
stopButton.addEventListener('click', function() {
    if (abortController) {
        abortController.abort();
    }

    if (currentBotMessage) {
        const messageBubble = currentBotMessage.querySelector('.bot-message-bubble');
        if (messageBubble) {
            const typingIndicator = messageBubble.querySelector('.typing-indicator');
            if (typingIndicator) {
                typingIndicator.remove();
                const stopNotice = document.createElement('div');
                stopNotice.className = 'stop-notice';
                stopNotice.textContent = '已停止生成';
                messageBubble.appendChild(stopNotice);
            }
        }
    }
    resetUI();
});

// 流式请求
async function fetchQueryData(query) {
    isFetching = true;
    sendButton.style.display = 'none';
    stopButton.style.display = 'inline-block';

    abortController = new AbortController();

    // 加载中动画
    currentBotMessage = addMessage('<div class="typing-indicator"><span></span><span></span><span></span> 思考中...</div>', 'bot');

    try {
        const response = await authFetch('/api/chat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Accept': 'text/event-stream'
            },
            body: JSON.stringify({
                msg: query,
                session_id: sessionId,
                workflow_id: parseInt(document.getElementById('workflow-select').value) || 0
            }),
            signal: abortController.signal
        });

        if (!response.ok) {
            throw new Error('网络请求失败');
        }
        if (!response.body) {
            throw new Error('不支持流式响应');
        }

        // 读取 SSE 流
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let accumulatedText = '';

        while (true) {
            const { value, done } = await reader.read();
            if (done) break;

            const chunk = decoder.decode(value, { stream: true });
            const lines = chunk.split('\n');

            for (const line of lines) {
                if (line.startsWith('data: ')) {
                    const data = line.substring(6);
                    if (data === '[DONE]' || data === '') continue;
                    // 处理工作流进度消息
                    if (data.startsWith('[步骤 ')) {
                        // 显示进度为临时状态
                        updateBotMessage(accumulatedText + '\n\n*' + data + '*');
                        continue;
                    }
                    // 处理错误
                    if (data.startsWith('[错误]')) {
                        console.warn('服务端错误:', data);
                        continue;
                    }
                    accumulatedText += data;
                    updateBotMessage(accumulatedText);
                }
            }
        }

        // 添加复制按钮
        addCopyButton(currentBotMessage, accumulatedText);

    } catch (error) {
        if (error.name === 'AbortError') {
            console.log('请求已中止');
        } else {
            console.error('请求出错:', error);
            if (currentBotMessage) {
                updateBotMessage('请求失败，请重试。');
            }
        }
    } finally {
        resetUI();
    }
}

// 更新机器人消息
function updateBotMessage(text) {
    if (!currentBotMessage) return;

    const messageBubble = currentBotMessage.querySelector('.bot-message-bubble');
    if (messageBubble) {
        const sanitizedContent = DOMPurify.sanitize(
            marked.parse(text),
            { ADD_TAGS: ['canvas'], ADD_ATTR: ['id'] }
        );
        messageBubble.innerHTML = sanitizedContent;
        messageBubble.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }

    // 同步更新持久化
    if (messages.length > 0 && messages[messages.length - 1].type === 'bot') {
        messages[messages.length - 1].text = text;
        saveMessages();
    }
}

// 添加消息到 DOM
function addMessageToDOM(text, type) {
    const messageContainer = document.createElement('div');
    messageContainer.classList.add('message-container');

    if (type === 'user') {
        messageContainer.classList.add('user-message-container');
        const sanitized = DOMPurify.sanitize(text);
        messageContainer.innerHTML = '<div class="message-bubble user-message-bubble">' + sanitized + '</div>';
    } else {
        messageContainer.classList.add('bot-message-container');
        const sanitized = DOMPurify.sanitize(
            marked.parse(text),
            { ADD_TAGS: ['canvas'], ADD_ATTR: ['id'] }
        );
        messageContainer.innerHTML =
            '<div class="bot-message-header"><span><i class="fas fa-robot"></i> AI助手</span></div>' +
            '<div class="message-bubble bot-message-bubble">' + sanitized + '</div>';
    }

    chatContainer.appendChild(messageContainer);
    messageContainer.scrollIntoView({ behavior: 'smooth' });
    return messageContainer;
}

// 添加消息（持久化 + DOM）
function addMessage(text, type) {
    messages.push({ text, type });
    saveMessages();
    return addMessageToDOM(text, type);
}

// 复制按钮
function addCopyButton(messageContainer, text) {
    const actionsContainer = document.createElement('div');
    actionsContainer.classList.add('message-actions');

    const copyButton = document.createElement('button');
    copyButton.classList.add('copy-button');
    copyButton.innerHTML = '<i class="fas fa-copy"></i> 复制';
    copyButton.onclick = function() {
        navigator.clipboard.writeText(text).then(() => {
            copyButton.innerHTML = '<i class="fas fa-check"></i> 已复制';
            setTimeout(() => {
                copyButton.innerHTML = '<i class="fas fa-copy"></i> 复制';
            }, 2000);
        });
    };

    actionsContainer.appendChild(copyButton);
    messageContainer.appendChild(actionsContainer);
}

// 新对话
async function newChat() {
    if (isFetching && abortController) {
        abortController.abort();
    }
    try {
        await authFetch('/api/chat/clear', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ session_id: sessionId })
        });
    } catch (e) {
        console.warn('清空上下文失败:', e);
    }
    sessionId = crypto.randomUUID ? crypto.randomUUID() : Date.now().toString(36) + Math.random().toString(36).slice(2);
    messages = [];
    saveMessages();
    chatContainer.innerHTML = '';
    resetUI();
}

// 重置 UI
function resetUI() {
    isFetching = false;
    sendButton.style.display = 'inline-block';
    stopButton.style.display = 'none';
    abortController = null;
}

// 新对话按钮
const newChatBtn = document.getElementById('newChat');
if (newChatBtn) {
    newChatBtn.addEventListener('click', newChat);
}

// 注销
async function logout() {
    try {
        await authFetch('/api/logout', { method: 'POST' });
    } catch (e) {
        // ignore
    }
    window.location.href = '/login';
}

// 修改密码
function showChangePwd() {
    document.getElementById('pwdModal').style.display = 'flex';
    document.getElementById('oldPwd').value = '';
    document.getElementById('newPwd').value = '';
    document.getElementById('pwdError').style.display = 'none';
}
function hideChangePwd() {
    document.getElementById('pwdModal').style.display = 'none';
}
document.getElementById('pwdForm').addEventListener('submit', async function(e) {
    e.preventDefault();
    const oldPwd = document.getElementById('oldPwd').value.trim();
    const newPwd = document.getElementById('newPwd').value.trim();
    const errDiv = document.getElementById('pwdError');
    if (!oldPwd || !newPwd) {
        errDiv.textContent = '密码不能为空';
        errDiv.style.display = 'block';
        return;
    }
    try {
        const resp = await authFetch('/api/user/password', {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ old_pwd: oldPwd, new_pwd: newPwd })
        });
        const data = await resp.json();
        if (data.status === 'ok') {
            hideChangePwd();
            alert('密码修改成功');
        } else {
            errDiv.textContent = data.error || '修改失败';
            errDiv.style.display = 'block';
        }
    } catch (err) {
        errDiv.textContent = '网络错误: ' + err.message;
        errDiv.style.display = 'block';
    }
});

// 键盘快捷键
queryInput.addEventListener('keydown', function(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        queryForm.dispatchEvent(new Event('submit'));
    }
});
