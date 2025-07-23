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

// 页面加载时显示欢迎信息
window.onload = function() {
    loadKnowledgeBases();
    const greetingEl = document.getElementById('greeting');
    if (greetingEl && greetingEl.value) {
        addMessage(greetingEl.value, 'bot');
    }
    queryInput.focus();
};

// 表单提交事件
queryForm.addEventListener('submit', async function(e) {
    e.preventDefault();
    if (isFetching) return;

    const query = queryInput.value.trim();
    if (!query) {
        addMessage("请填写您想问的问题", 'bot');
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
            updateBotMessage("回答生成中断或出错，请重试");
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
        updateBotMessage("回答生成已停止");
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
    currentBotMessage = addMessage('<div class="typing-indicator"><span></span><span></span><span></span> 思考中...</div>', 'bot');

    try {
        const t = document.getElementById('t').value;
        const appSource = document.getElementById('app_source').value;
        const uid = document.getElementById('uid').value;
        const kbId = document.getElementById('kb_selector').value || '';
        const modelId = document.getElementById('model_selector').value || '';
        const response = await fetch('/chat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded',
                'Accept': 'text/event-stream'
            },
            body: `msg=${encodeURIComponent(query)}&uid=${encodeURIComponent(uid)}&t=${t}&app_source=${appSource}&kb_id=${kbId}&model_id=${modelId}`,
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

// 加载知识库列表
async function loadKnowledgeBases() {
    const selector = document.getElementById('kb_selector');
    const uid = document.getElementById('uid').value;
    const t = document.getElementById('t').value;

    try {
        const response = await fetch('/vdb/list', {
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
                <span>智能助手</span>
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
    currentBotMessage = null;
}

// 键盘快捷键支持
queryInput.addEventListener('keydown', function(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        queryForm.dispatchEvent(new Event('submit'));
    }
});