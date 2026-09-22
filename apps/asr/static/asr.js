let selectedFiles = [];

document.addEventListener('DOMContentLoaded', function() {
    initEventListeners();
});

function initEventListeners() {
    const uploadBtn = document.getElementById('uploadButton');
    const fileInput = document.getElementById('fileInput');

    uploadBtn.addEventListener('click', () => {
        fileInput.click();
    });

    fileInput.addEventListener('change', (e) => {
        handleFiles(e.target.files);
        fileInput.value = '';
    });
}

function handleFiles(files) {
    for (let file of files) {
        const validExtensions = ['.mp3', '.m4a', '.amr', '.wav', '.flac', '.ogg', '.aac'];
        const ext = '.' + file.name.split('.').pop().toLowerCase();

        if (validExtensions.includes(ext)) {
            selectedFiles.push(file);
        } else {
            showUploadResult(__fmt_named('asr.unsupported_format', {name: file.name}), 'error');
        }
    }

    updateFileList();

    if (selectedFiles.length > 0) {
        uploadAllFiles();
    }
}

function updateFileList() {
    const container = document.getElementById('fileListContainer');
    const fileList = document.getElementById('fileList');
    const badge = document.getElementById('fileCountBadge');

    if (selectedFiles.length === 0) {
        container.style.display = 'none';
        badge.style.display = 'none';
        return;
    }

    container.style.display = 'block';
    badge.style.display = 'flex';
    badge.textContent = selectedFiles.length;

    fileList.innerHTML = '';
    selectedFiles.forEach((file, index) => {
        const fileItem = document.createElement('div');
        fileItem.className = 'file-item';
        fileItem.innerHTML = `
            <div class="file-info">
                <i class="fas fa-file-audio"></i>
                <div class="file-details">
                    <span class="file-name">${escapeHtml(file.name)}</span>
                    <span class="file-size">${formatFileSize(file.size)}</span>
                </div>
            </div>
            <button class="file-remove" onclick="removeFile(${index})">
                <i class="fas fa-times"></i>
            </button>
        `;
        fileList.appendChild(fileItem);
    });
}

function removeFile(index) {
    selectedFiles.splice(index, 1);
    updateFileList();
}

function clearFileList() {
    selectedFiles = [];
    updateFileList();
}

function formatFileSize(bytes) {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

async function uploadAllFiles() {
    setUploadButtonEnabled(false);
    try {
        for (let file of selectedFiles) {
            await uploadFile(file);
        }
        clearFileList();
    } finally {
        setUploadButtonEnabled(true);
    }
}

function setUploadButtonEnabled(enabled) {
    const btn = document.getElementById('uploadButton');
    btn.disabled = !enabled;
    btn.classList.toggle('disabled', !enabled);
}

async function uploadFile(file) {
    showUploadResult(
        __('asr.processing') + ` <i class="fas fa-spinner spin"></i>`,
        'processing'
    );

    const formData = new FormData();
    formData.append('file', file);

    // 从隐藏 input 获取 uid 和 t
    const uid = document.getElementById('uid').value || '0';
    const t = document.getElementById('t').value || '';
    formData.append('uid', uid);

    try {
        const response = await fetch('/api/upload', {
            method: 'POST',
            body: formData
        });

        const data = await response.json();

        if (response.ok) {
            const tasksUrl = `/asr/task?uid=${uid}&app_source=asr&t=${t}`;
            showUploadResult(`
                <div><i class="fas fa-check-circle" style="color: #52c41a; margin-right: 6px;"></i>${__('asr.upload_success')}</div>
                <div style="margin-top: 8px; font-size: 0.9rem; color: #666;">${__('asr.view_tasks_hint')}</div>
                <a href="${tasksUrl}" target="_blank" class="goto-tasks-link">
                    <i class="fas fa-tasks"></i> ${__('asr.my_tasks_btn')}
                </a>
            `, 'success');
        } else {
            showUploadResult(__fmt_named('asr.process_failed', {msg: data.error}), 'error');
        }
    } catch (error) {
        console.error('Upload error:', error);
        showUploadResult(__fmt_named('asr.upload_failed', {msg: error.message}), 'error');
    }
}

function showUploadResult(html, type) {
    const el = document.getElementById('uploadResult');
    el.style.display = 'block';
    el.innerHTML = html;
    el.className = 'upload-result upload-result-' + type;
    el.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}