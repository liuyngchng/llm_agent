marked.setOptions({
    breaks: true, // 转换 \n 为 <br>
    gfm: true,    // 启用 GitHub Flavored Markdown
    smartLists: true,
    smartypants: true
});

function renderMarkdown(content) {
    if (!content) return '';
    try {
        return DOMPurify.sanitize(marked.parse(content));
    } catch (e) {
        console.error('Markdown渲染失败:', e);
        return content; // 渲染失败时返回原始内容
    }
}

let abortController = null;

function submitQuestion() {
    const question = document.getElementById('question-input').value.trim();
    const resultArea = document.getElementById('result-area');
    const loading = document.getElementById('loading');
    const loadingOverlay = document.getElementById('loading-overlay');
    const submitBtn = document.getElementById('submit-btn');
    const streamToggle = document.getElementById('stream-toggle').checked;

    if (!question) {
        resultArea.innerHTML = '<div class="error">请输入问题</div>';
        return;
    }

    // 清除之前的结果
    resultArea.innerHTML = '';

    // 显示加载动画和遮罩
    loading.style.display = 'block';
    loadingOverlay.style.display = 'block';
    submitBtn.disabled = true;

    // 如果已有进行中的请求，取消它
    if (abortController) {
        abortController.abort();
    }
    abortController = new AbortController();

    if (streamToggle) {
        // 使用流式响应
        useStreamResponse(question, resultArea, loading, loadingOverlay, submitBtn, abortController.signal);
    } else {
        // 使用普通响应
        useNormalResponse(question, resultArea, loading, loadingOverlay, submitBtn);
    }
}

function useStreamResponse(question, resultArea, loading, loadingOverlay, submitBtn, signal) {
    // 使用fetch API发送POST请求
    fetch('/api/query', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            question: question,
            stream: true
        }),
        signal: signal
    })
    .then(response => {
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        // 创建读取器来处理流式响应
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        // 递归读取流
        function read() {
            return reader.read().then(({ value, done }) => {
                if (done) {
                    // 隐藏加载动画和遮罩
                    loading.style.display = 'none';
                    loadingOverlay.style.display = 'none';
                    submitBtn.disabled = false;
                    return;
                }

                // 解码并处理数据
                buffer += decoder.decode(value, { stream: true });

                // 按行分割数据
                const lines = buffer.split('\n');
                buffer = lines.pop(); // 保存最后一行（可能不完整）

                for (const line of lines) {
                    if (line.startsWith('data: ')) {
                        const data = line.substring(6); // 去掉 "data: " 前缀

                        if (data === '[DONE]') {
                            // 隐藏加载动画和遮罩
                            loading.style.display = 'none';
                            loadingOverlay.style.display = 'none';
                            submitBtn.disabled = false;
                            return;
                        }

                        try {
                            const parsedData = JSON.parse(data);
                            switch(parsedData.type) {
                                case 'status':
                                    resultArea.innerHTML += `<div class="status-message">${renderMarkdown(parsedData.content)}</div>`;
                                    break;
                                case 'tool_call':
                                    resultArea.innerHTML += `<div class="tool-call">${renderMarkdown(parsedData.content)}</div>`;
                                    break;
                                case 'tool_start':
                                    resultArea.innerHTML += `<div class="tool-call">${renderMarkdown(parsedData.content)}...</div>`;
                                    break;
                                case 'tool_result':
                                    resultArea.innerHTML += `<div class="tool-result">${renderMarkdown(parsedData.content)}: ${renderMarkdown(parsedData.result)}</div>`;
                                    break;
                                case 'final':
                                    resultArea.innerHTML += `<div class="final-result">${renderMarkdown(parsedData.content)}</div>`;
                                    break;
                                case 'error':
                                    resultArea.innerHTML += `<div class="error">${renderMarkdown(parsedData.content)}</div>`;
                                    break;
                            }


                            // 滚动到底部
                            resultArea.scrollTop = resultArea.scrollHeight;
                        } catch (e) {
                            console.error('解析数据失败:', e, '原始数据:', data);
                        }
                    }
                }

                // 继续读取
                return read();
            });
        }

        return read();
    })
    .catch(error => {
        if (error.name === 'AbortError') {
            console.log('请求已被取消');
        } else {
            console.error('请求失败:', error);
            resultArea.innerHTML += `<div class="error">请求失败: ${error.message}</div>`;
        }

        // 隐藏加载动画和遮罩
        loading.style.display = 'none';
        loadingOverlay.style.display = 'none';
        submitBtn.disabled = false;
    });
}

function useNormalResponse(question, resultArea, loading, loadingOverlay, submitBtn) {
    // 发送请求到后端
    fetch('/api/query', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            question: question,
            stream: false
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            resultArea.innerHTML = `<h3>问题: ${data.question}</h3>
                <hr>
                <div class="final-result">${renderMarkdown(data.answer)}</div>
            `;
        } else {
            resultArea.innerHTML = `<div class="error">
                    <strong>错误:</strong> ${renderMarkdown(data.error || '未知错误')}        </div>
            `;
        }
    })
    .catch(error => {
        resultArea.innerHTML = `
            <div class="error">
                <strong>请求失败:</strong> ${error.message}
            </div>
        `;
    })
    .finally(() => {
        // 隐藏加载动画和遮罩
        loading.style.display = 'none';
        loadingOverlay.style.display = 'none';
        submitBtn.disabled = false;
    });
}

// 支持按回车键提交
document.getElementById('question-input').addEventListener('keypress', function(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        submitQuestion();
    }
});

// 添加取消按钮功能
document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape' && abortController) {
        abortController.abort();
        document.getElementById('loading').style.display = 'none';
        document.getElementById('loading-overlay').style.display = 'none';
        document.getElementById('submit-btn').disabled = false;
    }
});