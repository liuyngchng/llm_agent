// 当前步骤
let currentStep = 1;


// 处理评审标准文件上传（支持xlsx和docx）
function handleCriteriaUpload(input) {
    const file = input.files[0];
    if (!file) return;

    // 验证文件类型
    const allowedExtensions = ['.xlsx', '.docx', '.md'];
    const fileExtension = file.name.toLowerCase().slice(file.name.lastIndexOf('.'));

    if (!allowedExtensions.includes(fileExtension)) {
        alert('请上传 .xlsx、.docx 或 .md 格式的文件');
        return;
    }

    // 显示文件信息
    document.getElementById('criteriaFileInfo').style.display = 'block';
    document.getElementById('criteriaFileName').textContent = file.name;
    document.getElementById('criteriaFileSize').textContent = formatFileSize(file.size);

    // 设置文件图标
    const fileIcon = document.getElementById('criteriaFileIcon');
    if (fileExtension === '.xlsx') {
        fileIcon.className = 'fas fa-file-excel';
    } else if (fileExtension === '.docx') {
        fileIcon.className = 'fas fa-file-word';
    } else if (fileExtension === '.md') {
        fileIcon.className = 'fas fa-file-code';
    }

    // 上传文件到后端
    uploadCriteriaFile(file);
}

// 处理评审材料文件上传
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

// 上传评审标准文件到后端（支持xlsx和docx）
async function uploadCriteriaFile(file) {
    const uid = document.getElementById('uid').value;

    const formData = new FormData();
    formData.append('file', file);
    formData.append('uid', uid);
    formData.append('file_type', 'criteria');

    try {
        // 根据文件类型选择上传接口
        const fileExtension = file.name.toLowerCase().slice(file.name.lastIndexOf('.'));
        let uploadUrl;
        if (fileExtension === '.xlsx' || fileExtension === '.xls') {
            uploadUrl = '/xlsx/upload';
        } else if (fileExtension === '.docx' || fileExtension === '.doc') {
            uploadUrl = '/docx/upload';
        } else if (fileExtension === '.md') {
            uploadUrl = '/md/upload';
        } else {
            alert('不支持的文件格式');
            return;
        }

        const response = await fetch(uploadUrl, {
            method: 'POST',
            body: formData
        });

        if (!response.ok) {
            throw new Error('评审标准文件上传失败');
        }

        const data = await response.json();

        // 记录上传的评审标准文件名称
        document.getElementById('review_criteria_file_name').value = data.file_name;

        // 设置预览链接
        const criteriaPreviewLink = document.getElementById('criteriaPreviewLink');
        const criteriaPreviewAction = document.getElementById('criteriaPreviewAction');

        // 如果有 task_id，则设置预览链接
        if (data.task_id) {
            criteriaPreviewLink.href = `/paper_review/preview/file/${data.file_name}?uid=${uid}`;
            criteriaPreviewAction.style.display = 'block';
        } else {
            // 如果没有 task_id，可以隐藏预览按钮或使用其他预览方式
            criteriaPreviewAction.style.display = 'none';
        }
    } catch (error) {
        console.error('上传错误:', error);
        alert('评审标准文件上传失败: ' + error.message);
        // 重置文件选择
        document.getElementById('reviewCriteria').value = '';
        document.getElementById('criteriaFileInfo').style.display = 'none';
        document.getElementById('criteriaPreviewAction').style.display = 'none';
    }
}

// 上传评审材料文件到后端
async function uploadDocxFile(file) {
    const uid = document.getElementById('uid').value;

    const formData = new FormData();
    formData.append('file', file);
    formData.append('uid', uid);
    formData.append('file_type', 'paper');
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

        // 设置预览链接
        const docxPreviewLink = document.getElementById('docxPreviewLink');
        const docxPreviewAction = document.getElementById('docxPreviewAction');

        // 设置预览链接
        if (data.task_id) {
            docxPreviewLink.href = `/paper_review/preview/file/${data.file_name}?uid=${uid}`;
            docxPreviewAction.style.display = 'block';
        } else {
            docxPreviewAction.style.display = 'none';
        }
    } catch (error) {
        console.error('上传错误:', error);
        alert('评审材料文件上传失败: ' + error.message);
        // 重置文件选择
        document.getElementById('reviewPaperFile').value = '';
        document.getElementById('docxFileInfo').style.display = 'none';
        document.getElementById('docxPreviewAction').style.display = 'none';
    }
}

// 生成评审报告
async function gen_review_report() {
    const uid = document.getElementById('uid').value;
    const task_id = document.getElementById('taskId').value;
    const review_topic = document.getElementById('reviewTopic').value;
    const review_type = document.getElementById('reviewType').value;
    const review_criteria_file_name = document.getElementById('review_criteria_file_name').value;
    const review_paper_file_name = document.getElementById('review_paper_file_name').value;
    const generateBtn = document.getElementById('generateBtn');

    // 验证输入
    if (!review_topic.trim()) {
        alert('请输入评审主题');
        return;
    }
    if (!review_type.trim()) {
        alert('请输入评审类别');
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
        review_topic: review_topic,
        review_type: review_type,
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

// 加载知识库列表
async function loadKnowledgeBases() {
    console.log('loadKnowledgeBases triggered')
    const selector = document.getElementById('kb_selector');
    const uid = document.getElementById('uid').value;
    const t = document.getElementById('t').value;

    try {
        const response = await fetch('/vdb/pub/list', {
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
        }
    } catch (error) {
        console.error('加载知识库失败:', error);
    }
}

// 重置表单
function resetForm() {
    // 清空表单数据
    document.getElementById('reviewTopic').value = '';
    document.getElementById('reviewCriteria').value = '';
    document.getElementById('reviewPaperFile').value = '';
    document.getElementById('criteriaFileInfo').style.display = 'none';
    document.getElementById('docxFileInfo').style.display = 'none';

    document.getElementById('criteriaPreviewAction').style.display = 'none';
    document.getElementById('docxPreviewAction').style.display = 'none';

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
    loadKnowledgeBases();
});