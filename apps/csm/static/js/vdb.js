// 知识库管理页 JS

// 获取 token
function getToken() {
    return localStorage.getItem('token') || '';
}

// 带认证头的 fetch 封装
function authFetch(url, options) {
    options = options || {};
    options.headers = options.headers || {};
    options.headers['Authorization'] = 'Bearer ' + getToken();
    return fetch(url, options);
}

let currentKbId = null;
let selectedFiles = [];
let refreshInterval = null;

// ============================================================
// 知识库列表
// ============================================================

async function refreshKbList() {
    const sel = document.getElementById('kb_selector');
    const refreshBtn = document.getElementById('kbRefreshBtn');
    refreshBtn.disabled = true;

    try {
        const resp = await authFetch('/api/vdb');
        const data = await resp.json();

        sel.innerHTML = '<option value="">请选择知识库</option>';
        if (data.data) {
            data.data.forEach(kb => {
                const opt = document.createElement('option');
                opt.value = kb.id;
                opt.textContent = kb.name + (kb.is_default ? ' ★' : '');
                sel.appendChild(opt);
            });
        }
    } catch (e) {
        console.error('获取知识库列表失败:', e);
    }

    refreshBtn.disabled = false;
}

// KB 选择事件
document.getElementById('kb_selector').addEventListener('change', function() {
    const id = this.value;
    selectKb(id);
});

// 选中知识库的核心逻辑（页面加载恢复时也复用）
function selectKb(id) {
    currentKbId = id ? parseInt(id) : null;

    clearInterval(refreshInterval);
    refreshInterval = null;

    const deleteBtn = document.getElementById('deleteBtn');
    const starBtn = document.getElementById('setDefaultBtn');
    const fileListContainer = document.getElementById('fileListContainer');
    const fileListHint = document.getElementById('fileListHint');
    const sel = document.getElementById('kb_selector');

    if (id) {
        // 同步更新下拉框选中项
        sel.value = id;

        // 更新 URL hash，使刷新后能恢复选择
        window.location.hash = 'kb=' + id;

        deleteBtn.style.display = 'flex';
        starBtn.style.display = 'flex';
        loadFileList(parseInt(id));
        document.getElementById('vdb_status_desc').textContent = document.getElementById('kb_selector').options[sel.selectedIndex]?.textContent.replace(' ★', '') || '';
        fileListHint.textContent = '';
        document.getElementById('public_badge').style.display = 'inline-block';
        document.getElementById('default_badge').style.display = sel.options[sel.selectedIndex]?.textContent.includes('★') ? 'inline-block' : 'none';
        refreshInterval = setInterval(() => loadFileList(parseInt(id)), 5000);
    } else {
        // 清除 hash
        history.replaceState(null, '', window.location.pathname);

        deleteBtn.style.display = 'none';
        starBtn.style.display = 'none';
        fileListContainer.style.display = 'none';
        fileListHint.textContent = '请先选择知识库';
        document.getElementById('vdb_status_desc').textContent = '未选择';
        document.getElementById('public_badge').style.display = 'none';
        document.getElementById('default_badge').style.display = 'none';
    }
}

// 刷新按钮
document.getElementById('kbRefreshBtn').addEventListener('click', refreshKbList);

// 创建知识库
document.getElementById('createKB').addEventListener('click', async function() {
    const name = document.getElementById('kb_name').value.trim();
    if (!name) {
        alert('请输入知识库名称');
        return;
    }

    const isPublic = document.getElementById('public_checkbox').checked;

    try {
        const resp = await authFetch('/api/vdb', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name: name, is_public: isPublic })
        });
        const data = await resp.json();
        if (data.status === 'ok') {
            document.getElementById('kb_name').value = '';
            document.getElementById('public_checkbox').checked = false;
            refreshKbList();
            showStatus('知识库创建成功！');
        } else {
            alert(data.error || '创建失败');
        }
    } catch (e) {
        console.error('创建知识库失败:', e);
    }
});

// 删除知识库
document.getElementById('deleteBtn').addEventListener('click', async function() {
    if (!currentKbId || !confirm('确定要删除该知识库吗？此操作不可恢复。')) return;

    try {
        const resp = await authFetch('/api/vdb/' + currentKbId, { method: 'DELETE' });
        const data = await resp.json();
        if (data.status === 'ok') {
            currentKbId = null;
            history.replaceState(null, '', window.location.pathname);
            refreshKbList();
            document.getElementById('fileListContainer').style.display = 'none';
            document.getElementById('fileListHint').textContent = '请先选择知识库';
            document.getElementById('vdb_status_desc').textContent = '未选择';
            document.getElementById('public_badge').style.display = 'none';
            document.getElementById('default_badge').style.display = 'none';
            document.getElementById('deleteBtn').style.display = 'none';
            document.getElementById('setDefaultBtn').style.display = 'none';
            clearInterval(refreshInterval);
            refreshInterval = null;
            showStatus('知识库已删除');
        } else {
            alert(data.error || '删除失败');
        }
    } catch (e) {
        console.error('删除知识库失败:', e);
    }
});

// 设为默认
document.getElementById('setDefaultBtn').addEventListener('click', async function() {
    if (!currentKbId) return;

    try {
        const resp = await authFetch('/api/vdb/' + currentKbId + '/default', { method: 'PUT' });
        const data = await resp.json();
        if (data.status === 'ok') {
            refreshKbList();
            showStatus('已设为默认知识库');
        } else {
            alert(data.error || '设置失败');
        }
    } catch (e) {
        console.error('设置默认失败:', e);
    }
});

// ============================================================
// 文件列表
// ============================================================

async function loadFileList(vdbId) {
    try {
        const resp = await authFetch('/api/vdb/' + vdbId + '/files');
        const data = await resp.json();
        renderFileList(data.data || []);
        document.getElementById('fileListContainer').style.display = 'block';
        document.getElementById('fileListHint').textContent = (data.data || []).length + ' 个文件';
    } catch (e) {
        console.error('获取文件列表失败:', e);
    }
}

function renderFileList(files) {
    const tbody = document.querySelector('#fileListTable tbody');
    tbody.innerHTML = '';

    if (files.length === 0) {
        tbody.innerHTML = '<tr><td colspan="6" style="text-align:center;color:#aaa;padding:40px;">暂无文件，请上传文档</td></tr>';
        return;
    }

    files.forEach((f, i) => {
        const tr = document.createElement('tr');
        const progressPct = Math.round(f.percent || 0);
        const statusClass = progressPct === 100 ? 'color:#2e7d32;font-weight:600' : '';
        tr.innerHTML =
            '<td>' + (i + 1) + '</td>' +
            '<td title="' + escapeHtml(f.name) + '">' + escapeHtml(f.name) + '</td>' +
            '<td>' + formatTime(f.create_time) + '</td>' +
            '<td style="' + statusClass + '">' + progressPct + '%</td>' +
            '<td style="font-size:0.82rem;color:#888;">' + escapeHtml(f.process_info || '') + '</td>' +
            '<td><button class="kb-action-btn btn-delete" style="width:auto;padding:4px 10px;font-size:0.8rem;" onclick="deleteFile(' + f.id + ')" title="删除"><i class="fas fa-trash-alt"></i></button></td>';
        tbody.appendChild(tr);
    });
}

async function deleteFile(fileId) {
    if (!confirm('确定要删除该文件吗？')) return;

    try {
        const resp = await authFetch('/api/vdb/file/' + fileId, { method: 'DELETE' });
        const data = await resp.json();
        if (data.status === 'ok' && currentKbId) {
            loadFileList(currentKbId);
        }
    } catch (e) {
        console.error('删除文件失败:', e);
    }
}

// ============================================================
// 文件上传
// ============================================================

const dropzone = document.getElementById('uploadDropzone');
const fileInput = document.getElementById('fileInput');
const fileListDiv = document.getElementById('fileList');
const fileItemsDiv = document.getElementById('fileItems');
const fileCountSpan = document.getElementById('fileCount');
const clearFilesBtn = document.getElementById('clearFilesBtn');
const startBtn = document.getElementById('startBtn');

// Dropzone click → 打开文件选择
dropzone.addEventListener('click', function(e) {
    if (e.target === fileInput) return;
    fileInput.click();
});

// 拖拽事件
dropzone.addEventListener('dragover', function(e) {
    e.preventDefault();
    dropzone.classList.add('drag-over');
});
dropzone.addEventListener('dragleave', function() {
    dropzone.classList.remove('drag-over');
});
dropzone.addEventListener('drop', function(e) {
    e.preventDefault();
    dropzone.classList.remove('drag-over');
    if (e.dataTransfer.files.length > 0) {
        updateFileSelection(Array.from(e.dataTransfer.files));
    }
});

// 文件选择
fileInput.addEventListener('change', function() {
    updateFileSelection(Array.from(this.files));
});

function updateFileSelection(files) {
    selectedFiles = files;
    fileCountSpan.textContent = files.length;
    fileItemsDiv.innerHTML = files.map(f => '<div><i class="fas fa-file" style="margin-right:6px;color:#4b6cb7;"></i>' + escapeHtml(f.name) + '</div>').join('');
    fileListDiv.style.display = files.length > 0 ? 'block' : 'none';
}

// 清空
clearFilesBtn.addEventListener('click', function() {
    selectedFiles = [];
    fileInput.value = '';
    fileCountSpan.textContent = '0';
    fileItemsDiv.innerHTML = '';
    fileListDiv.style.display = 'none';
});

// 上传
startBtn.addEventListener('click', async function() {
    if (!currentKbId) {
        alert('请先选择知识库');
        return;
    }
    if (selectedFiles.length === 0) {
        alert('请先选择文件');
        return;
    }

    const progressDiv = document.getElementById('uploadProgress');
    const progressFill = document.getElementById('overallProgressFill');
    const progressText = document.getElementById('progressText');
    const progressPercent = document.getElementById('progressPercent');
    const resultSpan = document.getElementById('fileUploadResult');

    progressDiv.style.display = 'block';

    for (let i = 0; i < selectedFiles.length; i++) {
        const file = selectedFiles[i];
        const fd = new FormData();
        fd.append('file', file);

        try {
            const resp = await authFetch('/api/vdb/' + currentKbId + '/upload', {
                method: 'POST',
                body: fd
            });
            const data = await resp.json();
            if (data.status !== 'ok') {
                resultSpan.textContent = '上传失败: ' + (data.error || '未知错误');
            } else {
                resultSpan.textContent = '上传成功';
            }
        } catch (e) {
            console.error('上传失败:', e);
            resultSpan.textContent = '上传失败';
        }

        const pct = Math.round((i + 1) / selectedFiles.length * 100);
        progressFill.style.width = pct + '%';
        progressText.textContent = '已上传 ' + (i + 1) + '/' + selectedFiles.length;
        progressPercent.textContent = pct + '%';
    }

    // 刷新文件列表
    loadFileList(currentKbId);
    if (!refreshInterval && currentKbId) {
        refreshInterval = setInterval(() => loadFileList(currentKbId), 5000);
    }

    // 上传完成，1.5 秒后隐藏进度条
    setTimeout(() => {
        progressDiv.style.display = 'none';
        progressFill.style.width = '0';
    }, 1500);

    // 清空已选
    selectedFiles = [];
    fileInput.value = '';
    fileCountSpan.textContent = '0';
    fileItemsDiv.innerHTML = '';
    fileListDiv.style.display = 'none';
});

// ============================================================
// 辅助函数
// ============================================================

function showStatus(msg) {
    const el = document.getElementById('kb_status');
    el.innerHTML = '<i class="fas fa-check-circle"></i> ' + escapeHtml(msg);
    el.style.display = 'inline-block';
    el.style.animation = 'none';
    el.offsetHeight;
    el.style.animation = 'toastFade 3s ease-out forwards';
    setTimeout(() => { el.style.display = 'none'; }, 3000);
}

function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function formatTime(ts) {
    if (!ts) return '';
    const d = new Date(ts);
    return d.toLocaleString('zh-CN');
}

// 页面初始化
refreshKbList().then(() => {
    // 从 URL hash 恢复知识库选择
    const hash = window.location.hash;
    const match = hash.match(/^#kb=(\d+)$/);
    if (match) {
        const kbId = match[1];
        const sel = document.getElementById('kb_selector');
        // 检查该 KB 是否在下拉列表中
        if (sel.querySelector('option[value="' + kbId + '"]')) {
            selectKb(kbId);
        }
    }
});

// 页面离开时清理定时器
window.addEventListener('beforeunload', () => clearInterval(refreshInterval));
