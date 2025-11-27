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

// 处理评审标准文件上传（支持xlsx和docx）
function handleCriteriaUpload(input) {
    const file = input.files[0];
    if (!file) return;

    // 验证文件类型
    const allowedExtensions = ['.xlsx', '.docx'];
    const fileExtension = file.name.toLowerCase().slice(file.name.lastIndexOf('.'));

    if (!allowedExtensions.includes(fileExtension)) {
        alert('请上传 .xlsx 或 .docx 格式的文件');
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
    }

    // 上传文件到后端
    uploadCriteriaFile(file);
}

// 处理图片上传
function handleImageUpload(input) {
    const files = input.files;
    if (!files || files.length === 0) return;

    // 验证文件类型
    const allowedExtensions = ['.png', '.jpg', '.jpeg'];
    let hasInvalidFile = false;

    for (let file of files) {
        const fileExtension = file.name.toLowerCase().slice(file.name.lastIndexOf('.'));
        if (!allowedExtensions.includes(fileExtension)) {
            hasInvalidFile = true;
            break;
        }
    }

    if (hasInvalidFile) {
        alert('请上传 .png、.jpg 或 .jpeg 格式的图片文件');
        input.value = '';
        return;
    }

    // 显示文件信息
    document.getElementById('imageFileInfo').style.display = 'block';
    document.getElementById('imageFileName').textContent = `${files.length}个图片文件`;
    document.getElementById('imageFileCount').textContent = `${files.length}个文件`;

    // 显示图片预览
    showImagePreviews(files);

    // 上传文件到后端
    uploadImageFiles(files);
}

// 显示图片预览
function showImagePreviews(files) {
    const previewContainer = document.getElementById('imagePreviewContainer');
    const previewsDiv = document.getElementById('imagePreviews');

    previewsDiv.innerHTML = ''; // 清空之前的预览
    previewContainer.style.display = 'block';

    Array.from(files).forEach((file, index) => {
        const reader = new FileReader();

        reader.onload = function(e) {
            const previewDiv = document.createElement('div');
            previewDiv.className = 'image-preview-item';
            previewDiv.innerHTML = `
                <img src="${e.target.result}" alt="${file.name}">
                <div class="image-info">
                    <span class="image-name">${file.name}</span>
                    <span class="image-size">${formatFileSize(file.size)}</span>
                </div>
            `;
            previewsDiv.appendChild(previewDiv);
        };

        reader.readAsDataURL(file);
    });
}

// 上传图片文件到后端
async function uploadImageFiles(files) {
    const uid = document.getElementById('uid').value;
    const uploadedFileNames = [];

    try {
        // 创建所有上传任务的数组
        const uploadPromises = Array.from(files).map(file => {
            const formData = new FormData();
            formData.append('file', file);
            formData.append('uid', uid);
            formData.append('file_type', 'image');

            return fetch('/img/upload', {
                method: 'POST',
                body: formData
            }).then(response => {
                if (!response.ok) {
                    throw new Error(`图片文件 ${file.name} 上传失败`);
                }
                return response.json();
            }).then(data => {
                document.getElementById('taskId').value = data.task_id;
                return data.file_name; // 返回文件名用于后续处理
            });
        });

        // 等待所有上传任务完成
        const fileNames = await Promise.all(uploadPromises);
        uploadedFileNames.push(...fileNames);

        // 保存所有上传的图片文件名称（逗号分隔的字符串）
        document.getElementById('review_image_file_names').value = uploadedFileNames.join(',');

    } catch (error) {
        console.error('上传错误:', error);
        alert('图片文件上传失败: ' + error.message);
        // 重置文件选择
        document.getElementById('reviewImageFile').value = '';
        document.getElementById('imageFileInfo').style.display = 'none';
        document.getElementById('imagePreviewContainer').style.display = 'none';
    }
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
        const uploadUrl = fileExtension === '.xlsx' ? '/xlsx/upload' : '/docx/upload';

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

    } catch (error) {
        console.error('上传错误:', error);
        alert('评审标准文件上传失败: ' + error.message);
        // 重置文件选择
        document.getElementById('reviewCriteria').value = '';
        document.getElementById('criteriaFileInfo').style.display = 'none';
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
    } catch (error) {
        console.error('上传错误:', error);
        alert('评审材料文件上传失败: ' + error.message);
        // 重置文件选择
        document.getElementById('reviewPaperFile').value = '';
        document.getElementById('docxFileInfo').style.display = 'none';
    }
}


async function gen_review_report() {
    const uid = document.getElementById('uid').value;
    const task_id = document.getElementById('taskId').value;
    const review_topic = document.getElementById('reviewTopic').value;
    const review_type = document.getElementById('reviewType').value;
    const review_criteria_file_name = document.getElementById('review_criteria_file_name').value;
    const review_paper_file_name = document.getElementById('review_paper_file_name').value;
    const review_image_file_names = document.getElementById('review_image_file_names').value;
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

    // 验证至少上传了Word文档或图片
    if (!review_paper_file_name && !review_image_file_names) {
        alert('请上传Word文档或图片文件');
        return;
    }

    // 禁用按钮
    generateBtn.disabled = true;
    generateBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> 提交中...';

    const apiUrl = '/review_report/gen';

    // 将逗号分隔的字符串转换为数组
    const imageFileNamesArray = review_image_file_names ? review_image_file_names.split(',') : [];

    const postData = {
        uid: uid,
        review_topic: review_topic,
        review_type: review_type,
        task_id: task_id,
        review_criteria_file_name: review_criteria_file_name,
        review_paper_file_name: review_paper_file_name,
        review_image_file_names: imageFileNamesArray
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
    document.getElementById('reviewType').value = '';
    document.getElementById('reviewCriteria').value = '';
    document.getElementById('reviewPaperFile').value = '';
    document.getElementById('reviewImageFile').value = '';

    document.getElementById('criteriaFileInfo').style.display = 'none';
    document.getElementById('docxFileInfo').style.display = 'none';
    document.getElementById('imageFileInfo').style.display = 'none';
    document.getElementById('imagePreviewContainer').style.display = 'none';

    document.getElementById('taskId').value = '';
    document.getElementById('review_criteria_file_name').value = '';
    document.getElementById('review_paper_file_name').value = '';
    document.getElementById('review_image_file_names').value = '';

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