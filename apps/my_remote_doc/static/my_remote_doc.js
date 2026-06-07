// DOM 元素
const workspaceBtn = document.getElementById('workspaceBtn');
const openWorkspaceBtn = document.getElementById('openWorkspaceBtn');
const workspaceModal = document.getElementById('workspaceModal');
const workspaceModalClose = document.getElementById('workspaceModalClose');

// 初始化
document.addEventListener('DOMContentLoaded', function() {
    setupEventListeners();
});

function setupEventListeners() {
    // 打开工作空间模态框
    function openModal() {
        workspaceModal.style.display = 'flex';
        loadWorkspaceFiles();
    }

    if (workspaceBtn && workspaceModal) {
        workspaceBtn.addEventListener('click', openModal);
    }
    if (openWorkspaceBtn && workspaceModal) {
        openWorkspaceBtn.addEventListener('click', openModal);
    }
    if (workspaceModalClose) {
        workspaceModalClose.addEventListener('click', () => {
            workspaceModal.style.display = 'none';
        });
    }
    if (workspaceModal) {
        workspaceModal.addEventListener('click', (e) => {
            if (e.target === workspaceModal) {
                workspaceModal.style.display = 'none';
            }
        });
    }
}

// 加载工作空间文件列表
async function loadWorkspaceFiles() {
    const fileListEl = document.getElementById('workspaceFileList');
    if (!fileListEl) return;

    fileListEl.innerHTML = '<div class="workspace-loading"><i class="fas fa-spinner fa-spin"></i> ' + __('my_remote_doc.loading') + '</div>';

    try {
        const response = await fetch('/workspace-files');
        const data = await response.json();

        if (data.success) {
            if (data.files.length === 0) {
                fileListEl.innerHTML = '<div class="workspace-empty"><i class="fas fa-folder-open"></i> ' + __('my_remote_doc.empty_workspace') + '</div>';
                return;
            }

            fileListEl.innerHTML = '';
            data.files.forEach(file => {
                const item = document.createElement('div');
                item.className = 'workspace-file-item';
                const icon = getWorkspaceFileIcon(file.ext);
                const sizeStr = formatWorkspaceFileSize(file.size);
                const dateStr = new Date(file.mtime * 1000).toLocaleString();

                item.innerHTML = `
                    <div class="workspace-file-icon"><i class="${icon}"></i></div>
                    <div class="workspace-file-info">
                        <div class="workspace-file-name">${escapeHtml(file.name)}</div>
                        <div class="workspace-file-meta">${sizeStr} - ${dateStr}</div>
                    </div>
                    <div class="workspace-file-actions">
                        <button class="workspace-file-action-btn download" title="${__('my_remote_doc.download')}">
                            <i class="fas fa-download"></i>
                        </button>
                        <button class="workspace-file-action-btn delete" title="${__('my_remote_doc.delete')}">
                            <i class="fas fa-trash-alt"></i>
                        </button>
                    </div>
                `;

                // 点击文件名/图标下载
                item.querySelector('.workspace-file-icon').addEventListener('click', () => {
                    downloadWorkspaceFile(file.name);
                });
                item.querySelector('.workspace-file-info').addEventListener('click', () => {
                    downloadWorkspaceFile(file.name);
                });
                item.querySelector('.workspace-file-action-btn.download').addEventListener('click', (e) => {
                    e.stopPropagation();
                    downloadWorkspaceFile(file.name);
                });
                item.querySelector('.workspace-file-action-btn.delete').addEventListener('click', (e) => {
                    e.stopPropagation();
                    deleteWorkspaceFile(file.name, item);
                });

                fileListEl.appendChild(item);
            });
        } else {
            fileListEl.innerHTML = '<div class="workspace-error"><i class="fas fa-exclamation-triangle"></i> ' + __('my_remote_doc.load_failed') + ': ' + escapeHtml(data.error || '') + '</div>';
        }
    } catch (error) {
        fileListEl.innerHTML = '<div class="workspace-error"><i class="fas fa-exclamation-triangle"></i> ' + __('my_remote_doc.load_failed') + ': ' + escapeHtml(error.message) + '</div>';
    }
}

function downloadWorkspaceFile(filename) {
    const a = document.createElement('a');
    a.href = '/download/workspace/' + encodeURIComponent(filename);
    a.download = filename;
    a.style.display = 'none';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
}

async function deleteWorkspaceFile(filename, itemElement) {
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
            setTimeout(() => itemElement.remove(), 300);
        } else {
            alert(__('my_remote_doc.delete_failed') + ': ' + (data.error || ''));
        }
    } catch (error) {
        alert(__('my_remote_doc.delete_failed') + ': ' + error.message);
    }
}

function getWorkspaceFileIcon(ext) {
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

function formatWorkspaceFileSize(bytes) {
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
