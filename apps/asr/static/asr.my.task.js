let refreshInterval;

async function fetchTasks() {
    try {
        const uid = getUidFromUrl();
        const response = await fetch('/asr/my/task', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ uid: uid })
        });

        if (!response.ok) throw new Error(__('common.task_fetch_failed'));

        const data = await response.json();
        const tasks = data.tasks || [];
        renderTasksTable(tasks);
    } catch (error) {
        console.error('Fetch tasks error:', error);
    }
}

function renderTasksTable(tasks) {
    const tableBody = document.querySelector('#tasksTable tbody');
    const emptyState = document.getElementById('emptyState');
    const table = document.querySelector('table');
    const clearBtn = document.getElementById('clearCompletedBtn');

    if (!tasks || tasks.length === 0) {
        table.style.display = 'none';
        emptyState.style.display = 'block';
        clearBtn.style.display = 'none';
        return;
    }

    // 只在有已完成或失败任务时显示清空按钮
    const hasDone = tasks.some(t => t.status === 'completed' || t.status === 'failed');
    clearBtn.style.display = hasDone ? '' : 'none';

    table.style.display = 'table';
    emptyState.style.display = 'none';

    // 保留已有 DOM 做 diff，避免闪烁（只更新变化的部分）
    tasks.forEach((task, index) => {
        const rowId = 'task_row_' + task.task_id;
        let row = document.getElementById(rowId);

        if (!row) {
            row = document.createElement('tr');
            row.id = rowId;
            // 序号
            const idCell = document.createElement('td');
            idCell.style.fontWeight = '600';
            idCell.style.color = '#4b6cb7';
            idCell.textContent = index + 1;
            row.appendChild(idCell);

            // 文件名
            const nameCell = document.createElement('td');
            row.appendChild(nameCell);

            // 创建时间
            const timeCell = document.createElement('td');
            row.appendChild(timeCell);

            // 状态
            const statusCell = document.createElement('td');
            row.appendChild(statusCell);

            // 进度
            const progressCell = document.createElement('td');
            row.appendChild(progressCell);

            // 下载
            const downloadCell = document.createElement('td');
            row.appendChild(downloadCell);

            // 操作
            const actionCell = document.createElement('td');
            row.appendChild(actionCell);

            tableBody.appendChild(row);
        }

        const cells = row.querySelectorAll('td');
        cells[0].textContent = index + 1;

        // 文件名
        cells[1].innerHTML = `<div><strong>${escapeHtml(task.original_filename)}</strong></div>`;

        // 创建时间
        cells[2].textContent = formatDateTime(task.created_at);

        // 状态
        cells[3].innerHTML = buildStatusBadge(task);

        // 进度
        cells[4].innerHTML = buildProgressBar(task);

        // 下载
        cells[5].innerHTML = buildDownloadBtn(task);

        // 操作
        cells[6].innerHTML = buildActionBtn(task);
    });

    // 移除不存在的行
    const existingIds = new Set(tasks.map(t => 'task_row_' + t.task_id));
    tableBody.querySelectorAll('tr').forEach(row => {
        if (!existingIds.has(row.id)) row.remove();
    });
}

function buildStatusBadge(task) {
    const map = {
        'converting': { cls: 'status-converting', key: 'asr.status_converting' },
        'processing': { cls: 'status-processing', key: 'asr.status_sending' },
        'transcribing': { cls: 'status-transcribing', key: 'asr.status_transcribing' },
        'completed': { cls: 'status-completed', key: 'asr.status_completed' },
        'failed': { cls: 'status-failed', key: 'asr.status_failed' },
    };
    const m = map[task.status] || map['processing'];
    return `<span class="status-badge ${m.cls}">${__(m.key)}</span>`;
}

function buildProgressBar(task) {
    // 转录中阶段没有进度可展示，只显示文字
    if (task.status === 'transcribing') {
        return `<span style="color: #1890ff; font-size: 0.85rem;">${__('asr.status_transcribing')}...</span>`;
    }
    const pct = task.progress || 0;
    return `
        <div>${pct}%</div>
        <div class="progress-bar-container">
            <div class="progress-bar-fill" style="width: ${pct}%"></div>
        </div>`;
}

function buildDownloadBtn(task) {
    if (task.status === 'completed') {
        return `
            <a href="/asr/download/${task.task_id}" class="download-link" download>
                <i class="fas fa-download"></i> ${__('asr.col_download')}
            </a>`;
    }
    return '<span style="color: #999;">-</span>';
}

function buildActionBtn(task) {
    return `
        <button class="action-btn action-delete" data-task-id="${task.task_id}" data-filename="${escapeHtml(task.original_filename)}">
            <i class="fas fa-trash"></i> ${__('common.delete')}
        </button>`;
}

function formatDateTime(dateString) {
    if (!dateString) return '';
    try {
        const date = new Date(dateString);
        if (isNaN(date.getTime())) return dateString;
        const y = date.getFullYear();
        const mo = String(date.getMonth() + 1).padStart(2, '0');
        const d = String(date.getDate()).padStart(2, '0');
        const h = String(date.getHours()).padStart(2, '0');
        const mi = String(date.getMinutes()).padStart(2, '0');
        const s = String(date.getSeconds()).padStart(2, '0');
        return `${y}-${mo}-${d} ${h}:${mi}:${s}`;
    } catch (e) {
        return dateString;
    }
}

async function deleteTask(taskId, filename) {
    if (!confirm(__fmt_named('asr.delete_confirm', {name: filename}))) return;

    showLoading();
    try {
        const response = await fetch('/asr/del/task', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ task_id: taskId })
        });

        if (!response.ok) throw new Error(__('common.delete_failed'));
        await fetchTasks();
    } catch (error) {
        console.error('Delete error:', error);
        alert(__('common.delete_failed_retry'));
    } finally {
        hideLoading();
    }
}

async function clearCompletedTasks() {
    if (!confirm(__('asr.clear_completed_confirm'))) return;

    const uid = getUidFromUrl();
    showLoading();
    try {
        const response = await fetch('/api/clear_tasks', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ uid: parseInt(uid) })
        });

        if (!response.ok) throw new Error(__('common.delete_failed'));
        const data = await response.json();
        alert(data.message);
        await fetchTasks();
    } catch (error) {
        console.error('Clear completed error:', error);
        alert(__('common.delete_failed_retry'));
    } finally {
        hideLoading();
    }
}

function showLoading() {
    document.getElementById('loadingOverlay').style.display = 'flex';
}
function hideLoading() {
    document.getElementById('loadingOverlay').style.display = 'none';
}

function startAutoRefresh() {
    refreshInterval = setInterval(fetchTasks, 5000);
    document.getElementById('refreshIndicator').style.display = 'block';
}
function stopAutoRefresh() {
    if (refreshInterval) {
        clearInterval(refreshInterval);
        document.getElementById('refreshIndicator').style.display = 'none';
    }
}

function getUidFromUrl() {
    const urlParams = new URLSearchParams(window.location.search);
    return urlParams.get('uid') || '';
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

document.addEventListener('DOMContentLoaded', () => {
    fetchTasks();
    startAutoRefresh();

    // 委托事件：删除按钮
    document.getElementById('tasksTable').addEventListener('click', (e) => {
        const btn = e.target.closest('.action-delete');
        if (btn) {
            deleteTask(btn.dataset.taskId, btn.dataset.filename);
        }
    });

    // 清空已完成
    document.getElementById('clearCompletedBtn').addEventListener('click', () => {
        clearCompletedTasks();
    });

    document.addEventListener('visibilitychange', function() {
        if (document.hidden) {
            stopAutoRefresh();
        } else {
            fetchTasks();
            startAutoRefresh();
        }
    });
});