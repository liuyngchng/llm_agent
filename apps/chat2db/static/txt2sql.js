const outputEl = document.getElementById('stream_output');
const startBtn = document.getElementById('startBtn');
let eventSource = null;
let currentQuery = '';
const chartRules = [
    {pattern: /(趋势|变化|增长|下降)/, type: 'line'},
    {pattern: /(对比|比较|差异|不同|排名|排序)/, type: 'bar'},
    {pattern: /(占比|比例|分布)/, type: 'pie'}
];

function detectChartType(query) {
    return chartRules.find(rule => rule.pattern.test(query))?.type || 'pie';
}

startBtn.addEventListener('click', () => {
    if (eventSource) eventSource.close();
    outputEl.innerHTML = '<div class="empty-state"><p>正在处理您的查询，请稍候...</p></div>';
    currentQuery = document.getElementById('dialog').value;
    const query = encodeURIComponent(currentQuery);
    const uid = encodeURIComponent(document.getElementById('uid').value);

    eventSource = new EventSource(`/stream?t=${Date.now()}&q=${query}&uid=${uid}`);
    eventSource.onmessage = (event) => {
        const lastChild = outputEl.lastElementChild;
        if (lastChild && (lastChild.textContent || '').includes('...')) {
            outputEl.removeChild(lastChild);
        }
        try {
            const { data_type, data } = JSON.parse(event.data);
            console.log("switch_case, data_type="+ data_type + ", data=" + data)
            switch(data_type) {
                case 'txt':
                handleTxtData(data);
                break;
            case 'html':
                handleHtmlData(data);
                break;
            case 'chart_js':
                handleChartData(data, currentQuery);
                break;
            case 'msg':
                console.log("switch_msg, data_type="+ data_type + ", data=" + data)
                handleMsgData(data);
                break;
            default:
                console.warn('未知数据类型:', data_type);
            }
        } catch (e) {
            console.error('数据解析失败', e);
            const fallback = document.createElement('div');
            fallback.className = 'response-card';
            fallback.innerHTML = `<div class="warning-message">数据解析错误: ${e.message}</div>`;
            outputEl.appendChild(fallback);
        }
    };
    eventSource.onerror = handleSSEError;
});

function handleTxtData(data) {
    const pre = document.createElement('pre');
    pre.style.whiteSpace = 'pre-wrap';
    pre.textContent = data;
    outputEl.appendChild(pre);
}

function handleHtmlData(data) {
    const html_container = document.createElement('div');
    html_container.className = 'response-card';
    html_container.innerHTML = data;
    outputEl.appendChild(html_container);
}

function handleChartData(data, query) {
    const chart_container = document.createElement('div');
    chart_container.className = 'chart-container';
    outputEl.appendChild(chart_container);
    const canvas = document.createElement('canvas');
    chart_container.appendChild(canvas);
    const chartType = detectChartType(query);

    const chartConfig = {
        type: chartType,
        data: {
            labels: data.chart.labels,
            datasets: [{
                label: data.chart.title || '数据',
                data: data.chart.values,
                backgroundColor: [
                    'rgba(75, 108, 183, 0.7)',
                    'rgba(46, 204, 113, 0.7)',
                    'rgba(155, 89, 182, 0.7)',
                    'rgba(241, 196, 15, 0.7)',
                    'rgba(230, 126, 34, 0.7)'
                ],
                borderColor: 'white',
                borderWidth: 2,
                ...(chartType === 'line' && {
                    fill: false,
                    tension: 0.4,
                    borderColor: '#4b6cb7'
                })
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: chartType === 'pie' ? 'right' : 'top'
                },
                title: {
                    display: true,
                    text: data.chart.title,
                    font: { size: 18 }
                }
            },
            ...(chartType !== 'pie' && {
                scales: {
                    x: {
                        title: {
                            display: true,
                            text: '类别'
                        }
                    },
                    y: {
                        title: {
                            display: true,
                            text: data.chart.unit ? `数值 (${data.chart.unit})` : '数值'
                        },
                        beginAtZero: true
                    }
                }
            })
        }
    };

    new Chart(canvas, chartConfig);
}

function handleMsgData(data) {
    if (data.cur_page !== undefined) {
        document.getElementById('cur_page').value = data.cur_page;
    }
    if (data.total_page !== undefined) {
        document.getElementById('total_page').value = data.total_page;
    }
    if (data.total_count !== undefined) {
        document.getElementById('total_count').value = data.total_count;
    }
}

window.loadNextPage = function(e) {
    e.preventDefault();
    const curPage = parseInt(document.getElementById('cur_page').value || '0');
    const totalPage = parseInt(document.getElementById('total_page').value || '0');
    if (curPage >= totalPage) {
        alert("已经是最后一页了");
        return;
    }
    const nextPage = curPage + 1;
    const query = encodeURIComponent(document.getElementById('dialog').value);
    const uid = encodeURIComponent(document.getElementById('uid').value);
    if (eventSource) eventSource.close();
    outputEl.innerHTML = `<pre style="white-space: pre-wrap;">${currentQuery}, 翻页到第 ${nextPage}页/总共 ${totalPage} 页</pre>`;
    uri = `/stream?t=${Date.now()}&uid=${uid}&page=${nextPage}`
    eventSource = new EventSource(uri);
    console.log("new_event_source_uri=" + uri)
    eventSource.onmessage = handleSSEMessage;
    eventSource.onerror = handleSSEError;
};

function handleSSEError(event) {
    console.error("EventSource error:", event);
    if (eventSource) {
        eventSource.close();
        eventSource = null;
    }
}

// 在现有 txt2sql.js 文件末尾添加以下代码

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
        document.getElementById('dialog').disabled = true;
        clearInterval(timer);

        // 创建波形条
        document.getElementById('voice-effect').innerHTML =
            Array(20).fill('<div class="wave-bar"></div>').join('');
        document.querySelectorAll('.wave-bar').forEach((bar, i) => {
            bar.style.animationDelay = `${i * 50}ms`;
        });

        try {
            countdown = 10;
            document.getElementById('dialog').value = '';
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
            console.error('麦克风访问失败:', error);
            showStatus('❌ 麦克风不可用');
            clearState();
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
    if (mediaRecorder && mediaRecorder.state !== 'inactive') {
        mediaRecorder.stop();
    }
    if (mediaStream) {
        mediaStream.getTracks().forEach(track => {
            track.stop();
        });
    }
    clearTimeout(timeoutId);
}

async function processAudio() {
    try {
        voiceBtn.disabled = true;
        startBtn.disabled = true;
        const audioBlob = new Blob(audioChunks, { type: 'audio/webm' });
        const formData = new FormData();
        formData.append('audio', audioBlob, 'recording.webm');

        const response = await fetch('/trans/audio', { method: 'POST', body: formData });
        const { text } = await response.json();

        if (text) {
            document.getElementById('dialog').value = text;
            showStatus('✅ 识别成功', 1500);
        }
    } catch (error) {
        console.error('语音识别失败:', error);
        showStatus('❌ 识别失败', 2000);
    } finally {
        voiceBtn.disabled = false;
        startBtn.disabled = false;
        clearState();
    }
}

function clearState() {
    document.getElementById('dialog').disabled = false;
    if (mediaStream) {
        mediaStream.getTracks().forEach(track => track.stop());
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
    if (!isRecording) return;

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