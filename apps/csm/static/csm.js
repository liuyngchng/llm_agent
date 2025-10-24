let fetchInterval = null;
marked.setOptions({
  breaks: true,
  gfm: true
});

const chatContainer = document.getElementById('chat-container');
const queryForm = document.getElementById('query-form');
const queryInput = document.getElementById('query-input');

window.onload = function() {
    const greeting = window.initialGreeting; // 从全局变量获取
    addMessage(greeting, 'bot');
    startMsgPolling();
};

queryForm.addEventListener('submit', function(e) {
    e.preventDefault();
    const query = queryInput.value.trim();
    if (!query) {
        addMessage("请输入您的问题", 'bot');
        return;
    }

    addMessage(query, 'user');
    queryInput.value = '';

    sendMsg(query)
        .then(({data, contentType})  => {
            addMessage(data, 'bot', contentType);
        })
        .catch(error => {
            addMessage(`请求失败：${error.message}`, 'bot');
        });
});

async function sendMsg(query) {
    const sendButton = document.querySelector('.send-button');
    let loadingMsg = null;
    try {
        sendButton.disabled = true;
        loadingMsg = addMessage('<div class="loading-dots">正在处理您的请求</div>', 'bot');

        const response = await fetch('/usr/ask', {
            method: 'POST',
            headers: {'Content-Type': 'application/x-www-form-urlencoded'},
            body: `msg=${encodeURIComponent(query)}&uid=${encodeURIComponent(document.getElementById('uid').value)}`,
            signal: AbortSignal.timeout(300000)
        });

        if (loadingMsg && chatContainer.contains(loadingMsg)) {
            chatContainer.removeChild(loadingMsg);
        }

        const contentType = response.headers.get('Content-Type');
        const data = await response.text();

        if (!response.ok) throw new Error('网络响应失败');
        return {data, contentType};
    } catch (error) {
        if (loadingMsg && chatContainer.contains(loadingMsg)) {
            chatContainer.removeChild(loadingMsg);
        }
        throw error;
    } finally {
        sendButton.disabled = false;
        startMsgPolling();
    }
}

function addMessage(text, type, contentType) {
    if (!text || text.trim() === '') return null;

    const messageContainer = document.createElement('div');
    messageContainer.classList.add('message-container');
    messageContainer.classList.add(`${type}-message-container`);

    const sanitizedContent = DOMPurify.sanitize(
        contentType?.includes('markdown') ? marked.parse(text) : text,
        {
            ALLOWED_TAGS: ['div','h1','form','label','select','option','input','textarea','button','p','br','span','a','strong','em','img', 'meta', 'style', 'svg','path','circle','rect','line','table','thead','tbody','tr','th','td'],
            ALLOWED_ATTR: ['id','class','for','name','required','type','value','target', 'href','placeholder','src','method', 'action', 'style','charset', 'colspan', 'rowspan', 'viewBox','d','cx','cy','r','x','y','stroke','fill',]
        }
    );

    if (type === 'user') {
        messageContainer.innerHTML = `
            <div class="message-bubble">${sanitizedContent}</div>
        `;
    } else {
        messageContainer.innerHTML = `
            <div style="display: flex; align-items: flex-start; gap: 10px;">
                <i class="fas fa-robot" style="color: #4b6cb7; font-size: 1.2rem; margin-top: 3px;"></i>
                <div class="message-bubble">${sanitizedContent}</div>
            </div>
        `;
    }

    chatContainer.appendChild(messageContainer);
    chatContainer.scrollTop = chatContainer.scrollHeight;
    return messageContainer;
}

// 原有的事件监听器保持不变
document.getElementById('chat-container').addEventListener('submit', async function(e) {
    if (e.target.id === 'doorSrvReqForm') {
        e.preventDefault();
        // ...原有代码
    }
});

function startMsgPolling() {
    fetchInterval = setInterval(async () => {
        try {
            const uid = document.getElementById('uid').value;
            const response = await fetch(`/msg/box/${encodeURIComponent(uid)}`);
            if (response.ok) {
                const msg = (await response.text()).trim();
                if (msg) {
                    addMessage(msg, 'bot', 'text/markdown');
                }
            }
        } catch(e) {
            console.error("消息轮询错误:", e)
        }
    }, 2000);
}