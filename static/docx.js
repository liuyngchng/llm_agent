// 当前步骤
let currentStep = 1;
let taskId = null;
let pollInterval = null;
let selectedTemplate = 'system'; // 默认选择系统模板
window.generatedDocUrl = null; // 存储生成的文档URL

 // 初始化进度条
function updateProgressBar() {
    const progressBar = document.getElementById('progressBar');
    const progress = ((currentStep - 1) / 3) * 100;
    progressBar.style.width = `${progress}%`;

    // 更新步骤激活状态
    document.querySelectorAll('.step').forEach((step, index) => {
        if (index < currentStep) {
            step.classList.add('active');
        } else {
            step.classList.remove('active');
        }
    });
}

// 选择模板类型
function selectTemplate(type) {
    selectedTemplate = type;
    document.getElementById('outline_source').value = type;
    // 更新按钮文本
    const confirmBtn = document.getElementById('confirmOutlineBtn');
    if (type === 'custom') {
        confirmBtn.innerHTML = '下一步 <i class="fas fa-arrow-right"></i>';
    } else {
        confirmBtn.innerHTML = '确认并编辑 <i class="fas fa-edit"></i>';
    }
    // 更新UI
    document.getElementById('systemTemplate').classList.toggle('active', type === 'system');
    document.getElementById('customTemplate').classList.toggle('active', type === 'custom');
    document.getElementById('uploadContainer').classList.toggle('active', type === 'custom');

    // 重置目录显示
    const outlineContainer = document.getElementById('outlineContainer');
    // 获取已存储的目录
    const existingOutline = document.getElementById('outlineText').value;
    if (type === 'system') {
        //如果已有生成的目录，则显示它；否则显示提示信息
        if (existingOutline) {
            renderOutline(existingOutline); // 直接渲染已存储的目录
            console.log('line48_confirmBtn_disabled_false')
            confirmBtn.disabled = false;
        } else {
            confirmBtn.disabled = true;
            outlineContainer.innerHTML = `
                <div class="info-message" style="text-align: center; padding: 30px;">
                    <i class="fas fa-robot" style="font-size: 3rem; color: #4b6cb7; margin-bottom: 15px;"></i>
                    <p>已选择系统智能生成模式，点击下方按钮生成目录</p>
                    <button class="btn btn-primary" onclick="generateOutline()" style="margin-top: 20px;">
                    <i class="fas fa-sync-alt"></i> 生成目录
                    </button>
                </div>
            `;
        }
    } else {
        outlineContainer.innerHTML = `
            <div class="info-message" style="text-align: center; padding: 30px;">
                <i class="fas fa-file-upload" style="font-size: 3rem; color: #4b6cb7; margin-bottom: 15px;"></i>
                <p>请上传Word文档模板，系统将自动提取三级目录</p>
            </div>
        `;
    }
}

// 下一步函数
function nextStep(step) {
    // 验证步骤1的输入
    if (step === 1) {
        const docType = document.getElementById('docType').value;
        const docTitle = document.getElementById('docTitle').value;
        if (!docType) {
            alert('请选择文档类型');
            return;
        }
        if (!docTitle.trim()) {
            alert('请输入文档标题');
            return;
        }
    }
    // 隐藏当前步骤
    document.getElementById(`step${currentStep}`).classList.remove('active');
    // 更新当前步骤
    currentStep = step + 1;
    // 显示下一步
    document.getElementById(`step${currentStep}`).classList.add('active');
    // 更新进度条
    updateProgressBar();
    // 如果是第二步，生成目录
    if (currentStep === 2) {
        // 初始化模板选择
        selectTemplate('system');
    }
    // 如果是第三步，填充编辑区域
    if (currentStep === 3) {
        const markdownContent = document.getElementById('outlineText').value;
        const plainText = markdownToPlainText(markdownContent);
        document.getElementById('modifiedOutline').value = plainText;
        // 根据来源设置只读状态
        const outlineSource = document.getElementById('outline_source').value;
        document.getElementById('modifiedOutline').readOnly = (outlineSource === 'custom');
    }
}

// 上一步函数
function prevStep(step) {
    document.getElementById('modifiedOutline').readOnly = false;
    resetGenerateState();
    document.getElementById('progressDisplay').style.display = 'none';
    // 隐藏当前步骤
    document.getElementById(`step${currentStep}`).classList.remove('active');
    // 更新当前步骤
    currentStep = step - 1;
    // 显示上一步
    document.getElementById(`step${currentStep}`).classList.add('active');
    // 更新进度条
    updateProgressBar();
    // 如果回到步骤3，保持只读状态
    if (currentStep === 3) {
      const outlineSource = document.getElementById('outline_source').value;
      document.getElementById('modifiedOutline').readOnly = (outlineSource === 'custom');
    }
}

// 处理文件上传
function handleFileUpload(input) {
    const file = input.files[0];
    if (!file) return;
    // 验证文件类型
    if (!file.name.endsWith('.docx')) {
        alert('请上传 .docx 格式的Word文档');
        return;
    }
    // 显示文件信息
    document.getElementById('fileInfo').style.display = 'block';
    document.getElementById('fileName').textContent = file.name;
    document.getElementById('fileSize').textContent = formatFileSize(file.size);
    // 解析文件并提取目录
    uploadTemplateFile(file);
}

 // 格式化文件大小
function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

// 上传文件到后端
async function uploadTemplateFile(file) {
    const outlineContainer = document.getElementById('outlineContainer');
    const uid = document.getElementById('uid').value;
    outlineContainer.innerHTML = `
        <div class="loading">
            <div class="snake-loader"></div>
            <p>正在解析Word模板，提取目录结构<span class="loading-dots"></span></p>
        </div>
    `;
    const formData = new FormData();
    formData.append('file', file);
    formData.append('uid', uid);
    try {
        const response = await fetch('/docx/upload', {
            method: 'POST',
            body: formData
        });
        if (!response.ok) {
            throw new Error('文件上传失败');
        }
        const data = await response.json();
        // 检查目录是否为空
        if (!data.outline || data.outline.length === 0) {
            throw new Error('请上传含有三级目录的 Word docx模板');
        }
        // 记录上传的文件模板的名称
        document.getElementById('file_name').value = data.file_name;
        // 保存任务ID和目录结构
        document.getElementById('taskId').value = data.task_id;
        document.getElementById('outlineText').value = data.outline;
        // 渲染目录
        renderOutline(data.outline);
        // 启用确认按钮
        document.getElementById('confirmOutlineBtn').disabled = false;
    } catch (error) {
        console.error('上传错误:', error);
        alert(error.message);
        outlineContainer.innerHTML = `
        <div class="error-message" style="color: #e74c3c; text-align: center; padding: 30px;">
            <i class="fas fa-exclamation-triangle" style="font-size: 3rem;"></i>
            <p>文件解析失败: ${error.message}</p>
            <button class="btn btn-secondary" onclick="selectTemplate('custom')" style="margin-top: 20px;">
                重新上传
            </button>
        </div>
        `;
        // 重置文件选择
        document.getElementById('templateFile').value = '';
        document.getElementById('fileInfo').style.display = 'none'
    }
}



// 目录生成
function generateOutline() {
    const docType = document.getElementById('docType').value;
    const docTitle = document.getElementById('docTitle').value;
    const keywords = document.getElementById('keywords').value;
    const uid = document.getElementById('uid').value;
    const token = document.getElementById('t').value;
    // 显示加载状态
    const outlineContainer = document.getElementById('outlineContainer');
    outlineContainer.innerHTML = `
        <div class="loading">
            <div class="snake-loader"></div>
            <p>正在生成文档目录结构<span class="loading-dots"></span></p>
        </div>
    `;
    // 清空之前的Markdown内容
    document.getElementById('outlineText').value = '';
    // 调用后端API
    fetch('/docx/generate/outline', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
            doc_type: docType,
            doc_title: docTitle,
            keywords: keywords,
            uid: uid
        })
    })
    .then(response => {
        if (!response.ok) {
            throw new Error('生成失败，请重试');
        }
        const reader = response.body.getReader();
        const decoder = new TextDecoder('utf-8');
        let markdownContent = '';
        function read() {
            return reader.read().then(({ done, value }) => {
                if (done) {
                    // 流读取完成
                    document.getElementById('confirmOutlineBtn').disabled = false;
                    return;
                }
                // 解码数据块
                const chunk = decoder.decode(value, { stream: true });
                markdownContent += chunk;
                // 更新隐藏的Markdown内容
                document.getElementById('outlineText').value = markdownContent;
                // 将Markdown转换为HTML并实时渲染
                renderOutline(markdownContent);
                // 继续读取下一个数据块
                return read();
            });
        }
        return read();
    })
    .catch(error => {
        console.error('Error:', error);
        outlineContainer.innerHTML = `
        <div class="error" style="text-align: center; padding: 30px; color: #e74c3c;">
            <i class="fas fa-exclamation-triangle" style="font-size: 3rem;"></i>
            <p style="margin-top: 15px; font-size: 1.1rem;">${error.message}</p>
            <button class="btn btn-secondary" onclick="generateOutline()" style="margin-top: 20px;">
              <i class="fas fa-redo"></i> 重新生成
            </button>
         </div>
       `;
    });
}

 // 渲染Markdown目录数据
function renderOutline(markdown) {
    const outlineContainer = document.getElementById('outlineContainer');
    // 使用marked将Markdown转换为HTML
    try {
        const htmlContent = marked.parse(markdown);
        outlineContainer.innerHTML = htmlContent;
        outlineContainer.scrollTop = outlineContainer.scrollHeight;
        // 添加一些基本样式
        const style = document.createElement('style');
        style.textContent = `
            #outlineContainer h1 {
                display: block !important;
                text-align: left !important;
                justify-content: flex-start !important;
                font-size: 1.4rem;  /* 一级目录使用原三级目录大小 */
                margin: 12px 0 8px 0;
                font-weight: 600;
                color: #2c3e50;
            }
            #outlineContainer h2 {
                font-size: 1.3rem;  /* 二级目录缩小 */
                margin: 10px 0 6px 15px;
                font-weight: 500;
                color: #34495e;
            }
            #outlineContainer h3 {
                font-size: 1.2rem;
                margin: 8px 0 5px 30px;
                font-weight: 400;
                color: #4b6cb7;
            }
            #outlineContainer h4 {
                font-size: 1.1rem;
                margin: 6px 0 4px 45px;
                font-weight: 400;
                color: #7e8c8d;
            }
            #outlineContainer h5 {
                font-size: 1.0rem;
                margin: 5px 0 3px 60px;
                font-weight: 400;
                color: #7e8c8d;
            }
            #outlineContainer ul {
                padding-left: 25px;
                margin-bottom: 12px;
            }
            #outlineContainer li {
                margin: 6px 0;
                position: relative;
                font-size: 0.9rem;  /* 列表项同步缩小 */
            }
            #outlineContainer li:before {
                content: "•";
                position: absolute;
                left: -15px;
                color: #4b6cb7;
                font-size: 0.8rem;  /* 列表符号缩小 */
            }
        `;
        outlineContainer.appendChild(style);
    } catch (e) {
        // 错误处理保持不变
    }
}

// 将Markdown转换为缩进文本（用于第三步编辑）
function markdownToPlainText(markdown) {
    const lines = markdown.split('\n');
    let output = '';

    for (const line of lines) {
        if (!line.trim()) continue;

        // 处理标题
        if (line.startsWith('#')) {
            const match = line.match(/^(#+)\s*(.*)/);
            if (match) {
                const level = match[1].length;  // 获取标题等级
                const text = match[2].trim();
                // 设置缩进：一级标题0，二级2，三级4
                const indent = '  '.repeat(level - 1);
                output += indent + text + '\n';
            }
        }
        // 其他内容保持原样
        else {
            output += line + '\n';
        }
    }

    return output;
}


document.addEventListener('DOMContentLoaded', function() {
    updateProgressBar();
    loadKnowledgeBases();
});

async function gen_doc() {
    document.getElementById('modifiedOutline').readOnly = true;
    const uid = document.getElementById('uid').value;
    const token = document.getElementById('t').value;
    const task_id = document.getElementById('taskId').value;
    const doc_outline = document.getElementById('modifiedOutline').value;
    const doc_title = document.getElementById('docTitle').value;
    const doc_type = document.getElementById('docType').value;
    const keywords = document.getElementById('keywords').value;
    const generateBtn = document.getElementById('generateBtn');
    const outlineSource = document.getElementById('outline_source').value;
    const file_name = document.getElementById('file_name').value;

    // 禁用按钮
    generateBtn.disabled = true;
    generateBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> 提交中...';

    let apiUrl, postData;
    if (outlineSource === 'system') {
        apiUrl = '/docx/write/outline';
        postData = {
            uid: uid,
            doc_type: doc_type,
            doc_title: doc_title,
            keywords: keywords,
            doc_outline: doc_outline,
            vbd_id: document.getElementById('knowledgeBase').value
        };
    } else {
        apiUrl = '/docx/write/template';
        postData = {
            uid: uid,
            doc_type: doc_type,
            doc_title: doc_title,
            keywords: keywords,
            task_id: task_id,
            file_name: file_name,
            vbd_id: document.getElementById('knowledgeBase').value
        };
    }

    try {
        const response = await fetch(apiUrl, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify(postData)
        });

        if (!response.ok) throw new Error('文档生成任务提交失败');

        const result = await response.json();
        if (result.status === "started") {
            alert('文档生成任务已提交，可在页面右上角"我的写作任务"中查看写作进度');
            resetForm(); // 重置表单
        } else {
            throw new Error('任务提交失败');
        }
    } catch (error) {
        alert(`错误: ${error.message}`);
        resetGenerateState();
    }
}

// 重置表单
function resetForm() {
    // 重置到第一步
    document.getElementById(`step${currentStep}`).classList.remove('active');
    currentStep = 1;
    document.getElementById(`step${currentStep}`).classList.add('active');
    updateProgressBar();

    // 清空表单数据
    document.getElementById('docType').selectedIndex = 0;
    document.getElementById('docTitle').value = '';
    document.getElementById('keywords').value = '';
    document.getElementById('knowledgeBase').selectedIndex = 0;
    document.getElementById('outlineText').value = '';
    document.getElementById('modifiedOutline').value = '';
    document.getElementById('fileInfo').style.display = 'none';
    document.getElementById('templateFile').value = '';
    document.getElementById('taskId').value = '';
    document.getElementById('file_name').value = '';

    // 重置模板选择
    selectTemplate('system');
    resetGenerateState();
}

// 重置生成状态
function resetGenerateState() {
    const generateBtn = document.getElementById('generateBtn');
    if (generateBtn) {
        generateBtn.disabled = false;
        generateBtn.innerHTML = '提交任务 <i class="fas fa-paper-plane"></i>';
    }
    document.getElementById('modifiedOutline').readOnly = false;
}


// 加载知识库列表
async function loadKnowledgeBases() {
    const selector = document.getElementById('knowledgeBase');
    const uid = document.getElementById('uid').value;
    const token = document.getElementById('t').value;

    try {
        const response = await fetch('/vdb/my/list', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ uid, t })
        });
        if (!response.ok) {
            const errorText = await response.text();
            throw new Error(`API 错误 ${response.status}: ${errorText.slice(0, 100)}...`);
        }

        const result = await response.json();
        // 清空现有选项（除了第一个）
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