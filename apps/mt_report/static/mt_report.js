// 当前步骤
let currentStep = 1;

// 初始化进度条
function updateProgressBar() {
    const progressBar = document.getElementById('progressBar');
    const progress = ((currentStep - 1) / 1) * 100; // 只有2步，所以除以1
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

    // 上传文件到后端
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
    const uid = document.getElementById('uid').value;

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

        // 记录上传的文件模板的名称
        document.getElementById('file_name').value = data.file_name;
        // 保存任务ID
        document.getElementById('taskId').value = data.task_id;

        alert('文件上传成功！');

    } catch (error) {
        console.error('上传错误:', error);
        alert('文件上传失败: ' + error.message);
        // 重置文件选择
        document.getElementById('templateFile').value = '';
        document.getElementById('fileInfo').style.display = 'none';
    }
}

// 生成会议纪要
async function gen_mt_report() {
    const uid = document.getElementById('uid').value;
    const token = document.getElementById('t').value;
    const task_id = document.getElementById('taskId').value;
    const doc_title = document.getElementById('docTitle').value;
    const keywords = document.getElementById('keywords').value;
    const file_name = document.getElementById('file_name').value;
    const generateBtn = document.getElementById('generateBtn');

    // 验证输入
    if (!doc_title.trim()) {
        alert('请输入会议纪要标题');
        return;
    }

    if (!keywords.trim()) {
        alert('请输入会议内容要点');
        return;
    }

    // 禁用按钮
    generateBtn.disabled = true;
    generateBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> 提交中...';

    let apiUrl, postData;

    apiUrl = '/mt_report/gen';
    postData = {
        uid: uid,
        doc_title: doc_title,
        keywords: keywords,
        task_id: task_id,
        file_name: file_name
    };

    try {
        const response = await fetch(apiUrl, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify(postData)
        });

        if (!response.ok) throw new Error('会议纪要生成任务提交失败');

        const result = await response.json();
        if (result.status === "started") {
            alert('会议纪要生成任务已提交，可在页面右上角"写作任务"中查看进度');
            resetForm();
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
    // 清空表单数据
    document.getElementById('docTitle').value = '';
    document.getElementById('keywords').value = '';
    document.getElementById('fileInfo').style.display = 'none';
    document.getElementById('templateFile').value = '';
    document.getElementById('taskId').value = '';
    document.getElementById('file_name').value = '';

    resetGenerateState();
}

// 重置生成状态
function resetGenerateState() {
    const generateBtn = document.getElementById('generateBtn');
    if (generateBtn) {
        generateBtn.disabled = false;
        generateBtn.innerHTML = '提交任务 <i class="fas fa-file-word"></i>';
    }
}

// 页面加载完成后的初始化
document.addEventListener('DOMContentLoaded', function() {
    updateProgressBar();
});