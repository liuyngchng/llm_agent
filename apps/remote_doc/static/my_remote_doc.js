const PROTECTED_FILES = ['AGENTS.md', 'HEARTBEAT.md', 'IDENTITY.md', 'SOUL.md', 'TOOLS.md', 'USER.md', 'memory'];

// 初始化 — 页面加载时直接获取文件列表
document.addEventListener('DOMContentLoaded', function() {
    loadFiles();

    const refreshBtn = document.getElementById('refreshBtn');
    if (refreshBtn) {
        refreshBtn.addEventListener('click', loadFiles);
    }

    const uploadBtn = document.getElementById('uploadBtn');
    const fileInput = document.getElementById('fileInput');
    if (uploadBtn && fileInput) {
        uploadBtn.addEventListener('click', () => fileInput.click());
        fileInput.addEventListener('change', handleUpload);
    }
});

async function handleUpload(e) {
    const files = e.target.files;
    if (!files.length) return;

    const statusEl = document.getElementById('uploadStatus');
    const uploadBtn = document.getElementById('uploadBtn');

    uploadBtn.disabled = true;

    for (let i = 0; i < files.length; i++) {
        const file = files[i];
        statusEl.style.display = 'block';
        statusEl.innerHTML = '<i class="fas fa-spinner fa-spin"></i> 正在上传: ' + escapeHtml(file.name) + ' (' + (i + 1) + '/' + files.length + ')';

        const formData = new FormData();
        formData.append('file', file);

        try {
            const response = await fetch('/upload', { method: 'POST', body: formData });
            const data = await response.json();
            if (!data.success) {
                statusEl.innerHTML = '<i class="fas fa-exclamation-triangle"></i> 上传失败: ' + escapeHtml(file.name) + ' - ' + (data.error || '');
                setTimeout(() => { statusEl.style.display = 'none'; }, 3000);
                break;
            }
        } catch (error) {
            statusEl.innerHTML = '<i class="fas fa-exclamation-triangle"></i> 上传失败: ' + escapeHtml(error.message);
            setTimeout(() => { statusEl.style.display = 'none'; }, 3000);
            break;
        }
    }

    if (files.length > 1) {
        statusEl.innerHTML = '<i class="fas fa-check-circle"></i> 全部上传完成 (' + files.length + ' 个文件)';
    } else {
        statusEl.innerHTML = '<i class="fas fa-check-circle"></i> 上传完成';
    }
    setTimeout(() => { statusEl.style.display = 'none'; }, 2000);

    uploadBtn.disabled = false;
    fileInput.value = '';
    loadFiles();
}

async function loadFiles() {
    const fileListEl = document.getElementById('fileList');
    if (!fileListEl) return;

    fileListEl.innerHTML = '<div class="loading"><i class="fas fa-spinner fa-spin"></i> ' + __('my_remote_doc.loading') + '</div>';

    try {
        const response = await fetch('/workspace-files');
        const data = await response.json();

        if (data.success) {
            if (data.files.length === 0) {
                fileListEl.innerHTML = '<div class="empty"><i class="fas fa-folder-open"></i> ' + __('my_remote_doc.empty_workspace') + '</div>';
                return;
            }

            fileListEl.innerHTML = '';
            data.files.forEach(file => {
                const item = document.createElement('div');
                item.className = 'file-item';
                const icon = getFileIcon(file.ext);
                const sizeStr = formatFileSize(file.size);
                const dateStr = new Date(file.mtime * 1000).toLocaleString();

                const isProtected = PROTECTED_FILES.includes(file.name);
                item.innerHTML = `
                    <div class="file-icon"><i class="${icon}"></i></div>
                    <div class="file-info">
                        <div class="file-name">${escapeHtml(file.name)}</div>
                        <div class="file-meta">${sizeStr} - ${dateStr}</div>
                    </div>
                    <div class="file-actions">
                        <button class="file-action-btn download" title="${__('my_remote_doc.download')}">
                            <i class="fas fa-download"></i>
                        </button>
                        ${isProtected ? '' : `
                        <button class="file-action-btn delete" title="${__('my_remote_doc.delete')}">
                            <i class="fas fa-trash-alt"></i>
                        </button>`}
                    </div>
                `;

                item.querySelector('.file-icon').addEventListener('click', () => downloadFile(file.name));
                item.querySelector('.file-info').addEventListener('click', () => downloadFile(file.name));
                item.querySelector('.file-action-btn.download').addEventListener('click', (e) => {
                    e.stopPropagation();
                    downloadFile(file.name);
                });
                if (!isProtected) {
                    item.querySelector('.file-action-btn.delete').addEventListener('click', (e) => {
                        e.stopPropagation();
                        deleteFile(file.name, item);
                    });
                }

                fileListEl.appendChild(item);
            });
        } else {
            fileListEl.innerHTML = '<div class="error"><i class="fas fa-exclamation-triangle"></i> ' + __('my_remote_doc.load_failed') + ': ' + escapeHtml(data.error || '') + '</div>';
        }
    } catch (error) {
        fileListEl.innerHTML = '<div class="error"><i class="fas fa-exclamation-triangle"></i> ' + __('my_remote_doc.load_failed') + ': ' + escapeHtml(error.message) + '</div>';
    }
}

function downloadFile(filename) {
    const a = document.createElement('a');
    a.href = '/download/workspace/' + encodeURIComponent(filename);
    a.download = filename;
    a.style.display = 'none';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
}

async function deleteFile(filename, itemElement) {
    const confirmMsg = __('my_remote_doc.delete_confirm');
    const msg = confirmMsg.replace('{name}', filename);
    if (!confirm(msg)) {
        return;
    }
    try {
        const response = await fetch('/workspace-files/' + encodeURIComponent(filename), {
            method: 'DELETE',
        });
        const data = await response.json();
        if (data.success) {
            itemElement.style.transition = 'all 0.3s ease';
            itemElement.style.opacity = '0';
            itemElement.style.transform = 'translateX(30px)';
            setTimeout(() => {
                itemElement.remove();
                // 如果列表已空，显示空状态
                const fileListEl = document.getElementById('fileList');
                if (fileListEl && fileListEl.querySelectorAll('.file-item').length === 0) {
                    fileListEl.innerHTML = '<div class="empty"><i class="fas fa-folder-open"></i> ' + __('my_remote_doc.empty_workspace') + '</div>';
                }
            }, 300);
        } else {
            alert(__('my_remote_doc.delete_failed') + ': ' + (data.error || ''));
        }
    } catch (error) {
        alert(__('my_remote_doc.delete_failed') + ': ' + error.message);
    }
}

function getFileIcon(ext) {
    const iconMap = {
        '.doc': 'fas fa-file-word', '.docx': 'fas fa-file-word',
        '.xls': 'fas fa-file-excel', '.xlsx': 'fas fa-file-excel',
        '.ppt': 'fas fa-file-powerpoint', '.pptx': 'fas fa-file-powerpoint',
        '.pdf': 'fas fa-file-pdf',
        '.txt': 'fas fa-file-alt', '.md': 'fas fa-file-alt',
        '.csv': 'fas fa-file-csv',
        '.py': 'fas fa-file-code', '.js': 'fas fa-file-code', '.html': 'fas fa-file-code', '.css': 'fas fa-file-code', '.json': 'fas fa-file-code',
        '.png': 'fas fa-file-image', '.jpg': 'fas fa-file-image', '.jpeg': 'fas fa-file-image', '.gif': 'fas fa-file-image',
        '.zip': 'fas fa-file-archive', '.rar': 'fas fa-file-archive', '.7z': 'fas fa-file-archive',
    };
    return iconMap[ext] || 'fas fa-file';
}

function formatFileSize(bytes) {
    if (bytes === 0) return '0 B';
    const units = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(1024));
    return (bytes / Math.pow(1024, i)).toFixed(i > 0 ? 1 : 0) + ' ' + units[i];
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}
