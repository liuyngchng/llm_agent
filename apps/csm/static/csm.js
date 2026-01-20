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

// 在 csm.js 中添加以下代码
document.addEventListener('DOMContentLoaded', function() {
    // 监听表单提交事件
    document.addEventListener('submit', function(e) {
        const form = e.target;

        // 只处理上门服务表单
        if (form.id === 'doorSrvReqForm') {
            e.preventDefault(); // 阻止默认提交

            // 表单验证
            if (!validateDoorServiceForm(form)) {
                return;
            }

            // 收集表单数据
            const formData = new FormData(form);
            const data = Object.fromEntries(formData.entries());

            // 显示加载状态
            const submitBtn = form.querySelector('.submit-btn');
            const originalText = submitBtn.textContent;
            submitBtn.textContent = '提交中...';
            submitBtn.disabled = true;

            // 发送 AJAX 请求
            fetch('/door/srv', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(data)
            })
            .then(response => response.json())
            .then(result => {
                if (result.success) {
                    // 显示成功消息
                    alert('预约成功！我们会尽快与您联系。');

                    // 可以在这里将表单提交的消息发送到聊天
                    // 例如：sendMessage('我已经提交了上门服务预约');

                    // 重置表单
                    form.reset();
                } else {
                    alert('提交失败：' + (result.message || '请稍后重试'));
                }
            })
            .catch(error => {
                console.error('提交错误:', error);
                alert('网络错误，请稍后重试');
            })
            .finally(() => {
                // 恢复按钮状态
                submitBtn.textContent = originalText;
                submitBtn.disabled = false;
            });
        }
    });

    // 表单验证函数
    function validateDoorServiceForm(form) {
        const requiredFields = form.querySelectorAll('[required]');
        let isValid = true;

        requiredFields.forEach(field => {
            if (!field.value.trim()) {
                isValid = false;
                field.style.borderColor = 'red';

                // 添加错误提示
                let errorMsg = field.nextElementSibling;
                if (!errorMsg || !errorMsg.classList.contains('error-msg')) {
                    errorMsg = document.createElement('div');
                    errorMsg.className = 'error-msg';
                    errorMsg.style.color = 'red';
                    errorMsg.style.fontSize = '12px';
                    errorMsg.style.marginTop = '5px';
                    errorMsg.textContent = '此字段不能为空';
                    field.parentNode.appendChild(errorMsg);
                }
            } else {
                field.style.borderColor = '';

                // 移除错误提示
                const errorMsg = field.nextElementSibling;
                if (errorMsg && errorMsg.classList.contains('error-msg')) {
                    errorMsg.remove();
                }
            }
        });

        // 验证电话号码格式（可选）
        const phoneField = form.querySelector('#contactNumber');
        if (phoneField.value && !/^1[3-9]\d{9}$/.test(phoneField.value)) {
            alert('请输入正确的手机号码');
            return false;
        }

        // 验证日期（不能是过去的时间）
        const dateField = form.querySelector('#preferredDate');
        if (dateField.value) {
            const selectedDate = new Date(dateField.value);
            const today = new Date();
            today.setHours(0, 0, 0, 0);

            if (selectedDate < today) {
                alert('预约日期不能是过去的时间');
                return false;
            }
        }

        return isValid;
    }
});