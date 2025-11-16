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

// 处理xlsx文件上传
function handleXlsxUpload(input) {
    const file = input.files[0];
    if (!file) return;

    // 验证文件类型
    if (!file.name.endsWith('.xlsx')) {
        alert('请上传 .xlsx 格式的 Excel 文档');
        return;
    }

    // 显示文件信息
    document.getElementById('xlsxFileInfo').style.display = 'block';
    document.getElementById('xlsxFileName').textContent = file.name;
    document.getElementById('xlsxFileSize').textContent = formatFileSize(file.size);

    // 上传文件到后端
    uploadXlsxFile(file);
}

// 处理docx文件上传
function handleDocxUpload(input) {
    const file = input.files[0];
    if (!file) return;

    // 验证文件类型
    if (!file.name.endsWith('.docx')) {
        alert('请上传 .docx 格式的 Word 文档');
        return;
    }

    // 显示文件信息
    document.getElementById('docxFileInfo').style.display = 'block';
    document.getElementById('docxFileName').textContent = file.name;
    document.getElementById('docxFileSize').textContent = formatFileSize(file.size);

    // 上传文件到后端
    uploadDocxFile(file);
}

// 格式化文件大小
function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

// 上传xlsx文件到后端
async function uploadXlsxFile(file) {
    const uid = document.getElementById('uid').value;

    const formData = new FormData();
    formData.append('file', file);
    formData.append('uid', uid);

    try {
        const response = await fetch('/xlsx/upload', {
            method: 'POST',
            body: formData
        });
        if (!response.ok) {
            throw new Error('评审标准文件上传失败');
        }
        const data = await response.json();

        // 记录上传的评审标准文件名称
        document.getElementById('review_criteria_file_name').value = data.file_name;
        // 保存任务ID
        document.getElementById('taskId').value = data.task_id;
    } catch (error) {
        console.error('上传错误:', error);
        alert('评审标准文件上传失败: ' + error.message);
        // 重置文件选择
        document.getElementById('reviewCriteria').value = '';
        document.getElementById('xlsxFileInfo').style.display = 'none';
    }
}

// 上传docx文件到后端
async function uploadDocxFile(file) {
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
            throw new Error('评审材料文件上传失败');
        }
        const data = await response.json();

        // 记录上传的评审材料文件名称
        document.getElementById('review_paper_file_name').value = data.file_name;
        // 保存任务ID
        document.getElementById('taskId').value = data.task_id;
    } catch (error) {
        console.error('上传错误:', error);
        alert('评审材料文件上传失败: ' + error.message);
        // 重置文件选择
        document.getElementById('reviewPaperFile').value = '';
        document.getElementById('docxFileInfo').style.display = 'none';
    }
}

// 生成评审报告
async function gen_review_report() {
    const uid = document.getElementById('uid').value;
    const task_id = document.getElementById('taskId').value;
    const doc_title = document.getElementById('reviewTopic').value;
    const review_criteria_file_name = document.getElementById('review_criteria_file_name').value;
    const review_paper_file_name = document.getElementById('review_paper_file_name').value;
    const generateBtn = document.getElementById('generateBtn');

    // 验证输入
    if (!doc_title.trim()) {
        alert('请输入评审主题');
        return;
    }

    if (!review_criteria_file_name) {
        alert('请上传评审标准文件');
        return;
    }

    if (!review_paper_file_name) {
        alert('请上传评审材料文件');
        return;
    }

    // 禁用按钮
    generateBtn.disabled = true;
    generateBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> 提交中...';

    const apiUrl = '/review_report/gen';
    const postData = {
        uid: uid,
        doc_title: doc_title,
        task_id: task_id,
        review_criteria_file_name: review_criteria_file_name,
        review_paper_file_name: review_paper_file_name
    };

    try {
        const response = await fetch(apiUrl, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(postData)
        });

        if (!response.ok) throw new Error('评审报告生成任务提交失败');

        const result = await response.json();
        if (result.status === "started") {
            alert('评审报告生成任务已提交，可在页面右上角"我的任务"中查看进度');
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
    document.getElementById('reviewTopic').value = '';
    document.getElementById('reviewCriteria').value = '';
    document.getElementById('reviewPaperFile').value = '';
    document.getElementById('xlsxFileInfo').style.display = 'none';
    document.getElementById('docxFileInfo').style.display = 'none';
    document.getElementById('taskId').value = '';
    document.getElementById('review_criteria_file_name').value = '';
    document.getElementById('review_paper_file_name').value = '';

    resetGenerateState();
}

// 重置生成状态
function resetGenerateState() {
    const generateBtn = document.getElementById('generateBtn');
    if (generateBtn) {
        generateBtn.disabled = false;
        generateBtn.innerHTML = '生成评审报告 <i class="fas fa-file-contract"></i>';
    }
}

// 页面加载完成后的初始化
document.addEventListener('DOMContentLoaded', function() {
    updateProgressBar();
});