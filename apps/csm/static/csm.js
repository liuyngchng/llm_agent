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

const CHAT_STORAGE_KEY = 'chat2kb_messages';
const MAX_MESSAGES = 19;  // 与 common/const.py:MAX_HISTORY_SIZE 保持一致
let messages = [];

function saveMessages() {
    if (messages.length > MAX_MESSAGES) {
        messages = messages.slice(-MAX_MESSAGES);
    }
    localStorage.setItem(CHAT_STORAGE_KEY, JSON.stringify(messages));
}

function loadMessages() {
    try {
        const raw = localStorage.getItem(CHAT_STORAGE_KEY);
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
    loadKnowledgeBases();
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
        const kbId = document.getElementById('kb_selector').value || '';
        // 构建历史消息（排除当前用户消息和"思考中"占位）
        const historyMessages = messages.slice(0, -2).slice(-10);
        const history = historyMessages.map(m => {
            const role = m.type === 'user' ? __('csm.user_role') : __('csm.assistant_role');
            return `${role}：${m.text}`;
        }).join('\n');

        const response = await fetch('/chat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded',
                'Accept': 'text/event-stream'
            },
            body: `msg=${encodeURIComponent(query)}&uid=${encodeURIComponent(uid)}&t=${t}&app_source=${appSource}&kb_id=${kbId}&history=${encodeURIComponent(history)}`,
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

// 加载知识库列表
async function loadKnowledgeBases() {
    const selector = document.getElementById('kb_selector');
    const refreshBtn = document.getElementById('kbRefreshBtn');
    const refreshIcon = document.getElementById('refreshIcon');
    const uid = document.getElementById('uid').value;
    const t = document.getElementById('t').value;

    // 添加加载状态
    refreshBtn.disabled = true;
    refreshIcon.classList.add('fa-spin'); // 添加旋转动画

    try {
        const response = await fetch('/vdb/pub/list', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ uid, t })
        });

        if (!response.ok) {
            const errorText = await response.text();
            throw new Error(`API error ${response.status}: ${errorText.slice(0, 100)}...`);
        }

        const result = await response.json();
        console.log('vdb_list=' + result);

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

            // 显示成功提示（可选）
            showNotification(__('csm.kb_refreshed'), 'success');
        } else {
            // 显示空提示
            showNotification(__('csm.no_kb'), 'info');
        }

    } catch (error) {
        console.error('Load KB failed:', error);
        showNotification(__('csm.refresh_kb_failed') + error.message, 'error');
    } finally {
        // 移除加载状态
        refreshBtn.disabled = false;
        refreshIcon.classList.remove('fa-spin');
    }
}

function showNotification(message, type = 'info') {
    // 创建通知元素
    const notification = document.createElement('div');
    notification.className = `notification notification-${type}`;
    notification.textContent = message;

    // 添加样式
    notification.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        padding: 12px 20px;
        border-radius: 6px;
        background: ${type === 'success' ? '#4CAF50' : type === 'error' ? '#f44336' : '#2196F3'};
        color: white;
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        z-index: 1000;
        animation: slideIn 0.3s ease;
    `;

    // 添加动画
    const style = document.createElement('style');
    style.textContent = `
        @keyframes slideIn {
            from { transform: translateX(100%); opacity: 0; }
            to { transform: translateX(0); opacity: 1; }
        }
        .notification {
            transition: all 0.3s;
        }
    `;
    document.head.appendChild(style);

    // 添加到页面
    document.body.appendChild(notification);

    // 3秒后自动移除
    setTimeout(() => {
        notification.style.opacity = '0';
        notification.style.transform = 'translateX(100%)';
        setTimeout(() => {
            if (notification.parentNode) {
                notification.parentNode.removeChild(notification);
            }
            if (style.parentNode) {
                style.parentNode.removeChild(style);
            }
        }, 300);
    }, 3000);
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

// 清空聊天
function clearChat() {
    if (isFetching && abortController) {
        abortController.abort();
    }
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

// 清空聊天按钮
const clearChatBtn = document.getElementById('clearChat');
if (clearChatBtn) {
    clearChatBtn.addEventListener('click', clearChat);
}

// 键盘快捷键支持
queryInput.addEventListener('keydown', function(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        queryForm.dispatchEvent(new Event('submit'));
    }
});