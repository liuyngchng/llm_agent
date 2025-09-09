DOMPurify.addHook('uponSanitizeElement', (node, data) => {
    if (data.tagName === 'canvas') {
        node.setAttribute('id', data.attr.id);
    }
});
// 聊天容器
const chatContainer = document.getElementById('chat-container');
const queryForm = document.getElementById('query-form');
const queryInput = document.getElementById('query-input');   //查询输入框
const dbUriInput = document.getElementById('db-uri-input');
const sendButton = document.querySelector('.send-button');  // 发送按钮
let isFetching = false;                                     //是否正在请求数据

window.onload = function() {
    const greetingEl = document.getElementById('greeting');
    if (greetingEl && greetingEl.value) {
        addMessage(greetingEl.value, 'bot'); // 改为2个参数
    }
};
// 表单提交
queryForm.addEventListener('submit', function(e) {
    e.preventDefault();
    const query = queryInput.value.trim();
    if (!query) {
        addMessage("请填写您想问的问题", 'bot');
        return;
    }

    addMessage(query, 'user');
    queryInput.value = '';

    fetchQueryData(query).then(({response, data}) => {
        if (!response.ok) {
            // 添加错误消息定义
            let errorMessage = '查询失败，请稍后再试';
            switch(response.status) {
                case 400: errorMessage = '请求参数错误'; break;
                case 401: errorMessage = '未授权，请重新登录'; break;
                case 404: errorMessage = '请求的资源不存在'; break;
                case 500: errorMessage = '服务器内部错误'; break;
                case 503: errorMessage = '服务暂时不可用'; break;
            }
            addMessage(errorMessage, 'bot');
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        console.log('response=' + response +', data=' + data)

        addMessage(data || '暂无数据', 'bot');
    }).catch(error => {
        console.log("error_occurred", error.message);
    });
});



async function fetchQueryData(query) {
    let loadingMsg;
    try {
        sendButton.disabled = true;
        isFetching = true;
        loadingMsg = addMessage('<div class="loading-dots">处理中</div>', 'bot');
        const controller = new AbortController();
        setTimeout(() => controller.abort(), 300000);

        const response = await fetch('/usr/ask', {
            method: 'POST',
            headers: {'Content-Type': 'application/x-www-form-urlencoded'},
            body: `msg=${encodeURIComponent(query)}&uid=${encodeURIComponent(document.getElementById('uid').value)}&page=${document.getElementById('next_page').value}`,
            signal: controller.signal
        });

        if (loadingMsg && chatContainer.contains(loadingMsg)) {
            chatContainer.removeChild(loadingMsg);
        }
        sendButton.disabled = false;
        isFetching = false;

        if (!response.ok) throw new Error('网络响应失败');

        // 根据Content-Type决定如何解析响应
        const contentType = response.headers.get('content-type');
        let data;

        if (contentType && contentType.includes('application/json')) {
            data = await response.json();
        } else if (contentType && contentType.includes('text/html')) {
            data = await response.text(); // 获取HTML文本
        } else {
            data = await response.text();
        }

        return {
            response: response,
            data: data
        };
    } catch (error) {
        if (loadingMsg && chatContainer.contains(loadingMsg)) {
            chatContainer.removeChild(loadingMsg);
        }
        sendButton.disabled = false;
        isFetching = false;
        throw error;
    }
}

// 添加消息到聊天
function addMessage(content, type) {
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${type}-message`;

    // 根据消息类型决定如何处理内容
    if (type === 'bot') {
        // 检查内容是否是 HTML（包含标签）
        if (/<[a-z][\s\S]*>/i.test(content)) {
            messageDiv.innerHTML = DOMPurify.sanitize(content);
        } else {
            // 否则按 Markdown 处理
            messageDiv.innerHTML = DOMPurify.sanitize(marked.parse(content));
        }
    } else {
        // 用户消息直接显示文本
        messageDiv.textContent = content;
    }

    chatContainer.appendChild(messageDiv);
    chatContainer.scrollTop = chatContainer.scrollHeight;
}


// 语音识别功能
const voiceBtn = document.getElementById('voice-btn');
let isRecording = false;
let mediaRecorder, mediaStream, timeoutId, timer;
let audioChunks = [];
let countdown = 10;
// 点击切换录音状态
voiceBtn.addEventListener('click', toggleRecording);

async function toggleRecording() {
    if (isRecording) {
        clearTimeout(timeoutId);
        clearInterval(timer);
        mediaRecorder.stop();
        mediaStream.getTracks().forEach(track => track.stop());
        clearState();
        showStatus('🛑 已手动停止', 1500);
    } else {
        document.getElementById('voice-effect').style.display = 'flex';
        queryInput.disabled = true;
        clearInterval(timer);
        document.getElementById('voice-effect').innerHTML =
            Array(20).fill('<div class="wave-bar"></div>').join('');
        document.querySelectorAll('.wave-bar').forEach((bar, i) => {
            bar.style.animationDelay = `${i * 50}ms`; // 交错动画
        });
        try {
            countdown = 10;
            queryInput.value = '';
            mediaStream = await navigator.mediaDevices.getUserMedia({ audio: true });
            mediaRecorder = new MediaRecorder(mediaStream);
            const audioContext = new AudioContext();
            const analyser = audioContext.createAnalyser();
            const source = audioContext.createMediaStreamSource(mediaStream);
            source.connect(analyser);
            setupRecorder();

            mediaRecorder.start();
            updateWaveBars(analyser);
            isRecording = true;
            voiceBtn.classList.add('recording');
            showStatus(`🎤 录音中 (剩余${countdown}秒)...`);
            timer = setInterval(() => {
                countdown--;
                showStatus(`🎤 录音中 (剩余${countdown}秒)...`);
                if(countdown <= 0) clearInterval(timer);
            }, 1000);

            // 10秒自动停止
            timeoutId = setTimeout(autoStopRecording, 10000);
        } catch (error) {
            showStatus('❌ 麦克风不可用');
        }
    }
}

function setupRecorder() {
    audioChunks = [];
    mediaRecorder.ondataavailable = e => audioChunks.push(e.data);
    mediaRecorder.onstop = processAudio;
}

function autoStopRecording() {
    if (isRecording) {
        mediaRecorder.stop();
        showStatus('⏱️ 已达到10秒最长录音时间');
        voiceBtn.disabled = false;
    }
    clearState();
}

function stopRecording() {
    mediaRecorder.stop();
    mediaStream.getTracks().forEach(track => {
        track.stop();  // 停止轨道
        mediaStream.removeTrack(track); // 从流中移除轨道
    });
    mediaStream = null;
    clearTimeout(timeoutId);
}

async function processAudio() {
    try {
        voiceBtn.disabled = true;
        sendButton.disabled = true;
        const audioBlob = new Blob(audioChunks, { type: 'audio/webm' });
        const formData = new FormData();
        formData.append('audio', audioBlob, 'recording.webm');

        const response = await fetch('/trans/audio', { method: 'POST', body: formData });
        const { text } = await response.json();

        if (text) {
            queryInput.value = text;
            showStatus('✅ 识别成功', 1500);
        }
    } catch (error) {
        showStatus('❌ 识别失败', 2000);
    } finally {
        voiceBtn.disabled = false;
        sendButton.disabled = false;
        clearState();
    }
}

function clearState() {
    queryInput.disabled = false;
    if (mediaStream) {
        mediaStream.getTracks().forEach(track => track.stop());
        mediaRecorder.stream = null;
    }
    isRecording = false;
    clearInterval(timer);
    voiceBtn.classList.remove('recording');
    document.getElementById('voice-effect').style.display = 'none';
}

function showStatus(text, duration) {
    const indicator = document.getElementById('status-indicator');
    indicator.textContent = text;
    indicator.style.display = 'block';
    if (duration) setTimeout(() => indicator.style.display = 'none', duration);
}
function updateWaveBars(analyser) {
    const dataArray = new Uint8Array(analyser.frequencyBinCount);
    analyser.getByteFrequencyData(dataArray);
    const avg = dataArray.reduce((a,b) => a + b) / dataArray.length;

    document.querySelectorAll('.wave-bar').forEach(bar => {
        bar.style.transform = avg > 10 ?
            `scaleY(${0.3 + (avg/50)}) rotate(${Math.sin(Date.now()/100)*2}deg)`
            : 'scaleY(0.3)';
    });
    requestAnimationFrame(() => updateWaveBars(analyser));
}