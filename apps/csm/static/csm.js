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

const MAX_MESSAGES = 50;
let messages = [];

// 会话 ID — 标识一次连续对话，用于后端管理 LLM 上下文
let sessionId = generateSessionId();

function generateSessionId() {
    return crypto.randomUUID ? crypto.randomUUID() : Date.now().toString(36) + Math.random().toString(36).slice(2);
}

// localStorage key 按 uid 隔离，防止不同用户串数据
function getStorageKey() {
    const uidEl = document.getElementById('uid');
    const uid = uidEl ? uidEl.value : 'default';
    return `chat2kb_messages_${uid}`;
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
        }
    } catch (e) {
        messages = [];
    }
}

function restoreMessages() {
    chatContainer.innerHTML = '';
    messages.forEach(m => addMessageToDOM(m.text, m.type));
}

// 页面加载时恢复历史消息
window.onload = function() {
    loadMessages();
    if (messages.length > 0) {
        restoreMessages();
    }
    queryInput.focus();
};

// 表单提交事件
queryForm.addEventListener('submit', async function(e) {
    e.preventDefault();
    if (isFetching) return;

    const query = queryInput.value.trim();
    if (!query) {
        addMessage(__('csm.question_required'), 'bot');
        return;
    }

    // 添加用户消息
    addMessage(query, 'user');
    queryInput.value = '';
    queryInput.focus();

    try {
        // 开始获取数据
        await fetchQueryData(query);
    } catch (error) {
        console.error("请求出错:", error);
        if (currentBotMessage) {
            updateBotMessage(__('csm.generation_error'));
        }
        resetUI();
    }
});

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
                stopNotice.textContent = __('csm.stopped_note');
                messageBubble.appendChild(stopNotice);
            }
        }
    }
    resetUI();
});

// 获取流式数据
async function fetchQueryData(query) {
    isFetching = true;
    sendButton.disabled = true;
    stopButton.style.display = 'inline-block';

    // 创建新的中止控制器
    abortController = new AbortController();

    // 添加加载中的消息
    currentBotMessage = addMessage(`<div class="typing-indicator"><span></span><span></span><span></span> ${__('csm.thinking')}</div>`, 'bot');

    try {
        const t = document.getElementById('t').value;
        const appSource = document.getElementById('app_source').value;
        const uid = document.getElementById('uid').value;

        const response = await fetch('/chat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded',
                'Accept': 'text/event-stream'
            },
            body: `msg=${encodeURIComponent(query)}&uid=${encodeURIComponent(uid)}&t=${t}&app_source=${appSource}&session_id=${encodeURIComponent(sessionId)}`,
            signal: abortController.signal,
            credentials: 'include'
        });

        // 检查响应是否正常
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
            throw new Error(__('csm.network_failed'));
        }
        if (!response.body) {
            throw new Error(__('csm.network_failed'));
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
                updateBotMessage(__('csm.generation_retry'));
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

    // 同步更新持久化的最后一条 bot 消息
    if (messages.length > 0 && messages[messages.length - 1].type === 'bot') {
        messages[messages.length - 1].text = text;
        saveMessages();
    }
}

// 添加消息到聊天容器（仅 DOM，不涉及持久化）
function addMessageToDOM(text, type) {
    const messageContainer = document.createElement('div');
    messageContainer.classList.add('message-container');

    if (type === 'user') {
        messageContainer.classList.add('user-message-container');
        const sanitizedContent = DOMPurify.sanitize(text);
        messageContainer.innerHTML = `
            <div class="message-bubble user-message-bubble">${sanitizedContent}</div>
        `;
    } else {
        messageContainer.classList.add('bot-message-container');
        const sanitizedContent = DOMPurify.sanitize(
            marked.parse(text),
            { ADD_TAGS: ['canvas'], ADD_ATTR: ['id'] }
        );
        messageContainer.innerHTML = `
            <div class="bot-message-header">
                <img src="/static/bot.png" alt="AI Assistant">
                <span>${__('csm.ai_assistant')}</span>
            </div>
            <div class="message-bubble bot-message-bubble">${sanitizedContent}</div>
        `;
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

// 添加复制按钮
function addCopyButton(messageContainer, text) {
    const actionsContainer = document.createElement('div');
    actionsContainer.classList.add('message-actions');

    const copyButton = document.createElement('button');
    copyButton.classList.add('copy-button');
    copyButton.innerHTML = `<i class="fas fa-copy"></i> ${__('common.copy')}`;
    copyButton.onclick = function() {
        navigator.clipboard.writeText(text).then(() => {
            const originalText = copyButton.innerHTML;
            copyButton.innerHTML = `<i class="fas fa-check"></i> ${__('csm.copied_state')}`;
            setTimeout(() => {
                copyButton.innerHTML = originalText;
            }, 2000);
        });
    };

    actionsContainer.appendChild(copyButton);
    messageContainer.appendChild(actionsContainer);
}

// 开启新对话 — 清空前端存储 + 清空后端 LLM 上下文
async function newChat() {
    if (isFetching && abortController) {
        abortController.abort();
    }
    // 通知后端清空当前会话上下文
    const uid = document.getElementById('uid').value;
    try {
        await fetch('/chat/clear', {
            method: 'POST',
            headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
            body: `session_id=${encodeURIComponent(sessionId)}&uid=${encodeURIComponent(uid)}`
        });
    } catch (e) {
        console.warn('清空后端上下文失败:', e);
    }
    // 生成新会话 ID
    sessionId = generateSessionId();
    // 清空前端
    messages = [];
    saveMessages();
    chatContainer.innerHTML = '';
    resetUI();
}

// 重置UI状态
function resetUI() {
    isFetching = false;
    sendButton.disabled = false;
    stopButton.style.display = 'none';
    currentResponse = null;
    abortController = null;
}

// 开启新对话按钮
const newChatBtn = document.getElementById('newChat');
if (newChatBtn) {
    newChatBtn.addEventListener('click', newChat);
}

// 键盘快捷键支持
queryInput.addEventListener('keydown', function(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        queryForm.dispatchEvent(new Event('submit'));
    }
});