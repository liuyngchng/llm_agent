// 全局变量
let refreshInterval;

// 获取任务数据
async function fetchTasks() {
    try {
        const token = localStorage.getItem('token') || '';
        const uid = getUidFromUrl();

        const response = await fetch('/mt_report/my/task', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify({ uid: uid })
        });

        if (!response.ok) throw new Error('任务获取失败');

        const tasksData = await response.json();
        const tasks = Array.isArray(tasksData) ? tasksData : [tasksData];

        // 按创建时间排序（新任务在前）
        tasks.sort((a, b) => {
            return new Date(b.create_time) - new Date(a.create_time);
        });

        // 直接重新渲染整个表格
        renderTasksTable(tasks);
    } catch (error) {
        console.error('获取任务失败:', error);
    }
}

// 渲染任务表格
function renderTasksTable(tasks) {
    const tableBody = document.querySelector('#tasksTable tbody');
    const emptyState = document.getElementById('emptyState');

    if (!tasks || tasks.length === 0) {
        document.querySelector('table').style.display = 'none';
        emptyState.style.display = 'block';
        return;
    }

    tableBody.innerHTML = '';
    const uid = getUidFromUrl();
    tasks.forEach((task, index) => {
        const row = document.createElement('tr');

        // 序号
        const idCell = document.createElement('td');
        idCell.textContent = index + 1;
        idCell.style.fontWeight = '600';
        idCell.style.color = '#4b6cb7';

        // 文档标题
        const infoCell = document.createElement('td');
        infoCell.innerHTML = `
            <div><strong>${task.doc_title || '无标题'}</strong></div>
            <div style="color: #666; font-size: 0.9rem;">${task.doc_type || '未知类型'}</div>
        `;

        // 创建时间
        const createTimeCell = document.createElement('td');
        createTimeCell.textContent = formatDateTime(task.create_time);

        // 处理信息
        const timeCell = document.createElement('td');
        timeCell.textContent = task.process_info || '未知时间';

        // 处理进度
        const statusCell = document.createElement('td');
        statusCell.innerHTML = `
            <div>${task.percent || 0}%</div>
            <div class="progress-bar-container">
                <div class="progress-bar-fill" style="width: ${task.percent || 0}%"></div>
            </div>
        `;

        // 文档下载
        const downloadCell = document.createElement('td');
        downloadCell.innerHTML = `
            <a href="/docx/download/task/${task.task_id}?uid=${uid}" class="action-btn action-download">
                <i class="fas fa-download"></i> 全文下载
            </a>
        `;

        // 操作 （刷新/重试/完成）
        const actionCell = document.createElement('td');
        actionCell.style.display = 'flex';
        actionCell.style.gap = '8px';
        actionCell.style.flexWrap = 'wrap';

        let statusButton = '';
        if (task.status === 'in-progress' || task.status === 'pending') {
            statusButton = `
                <button class="action-btn action-refresh" onclick="refreshTask('${task.id}')">
                    <i class="fas fa-sync-alt"></i> 刷新
                </button>
            `;
        } else if (task.status === 'failed') {
            statusButton = `
                <button class="action-btn action-refresh" onclick="retryTask('${task.id}')">
                    <i class="fas fa-redo"></i> 重试
                </button>
            `;
        } else {
            statusButton = `
                <button class="action-btn" disabled>
                    <i class="fas fa-check"></i> 完成
                </button>
            `;
        }

        // 删除按钮
        const deleteButton = `
            <button class="action-btn action-delete" onclick="deleteTask('${task.task_id}', '${task.doc_title || '无标题'}')">
                <i class="fas fa-trash"></i> 删除
            </button>
        `;
        actionCell.innerHTML = statusButton + deleteButton;

        row.appendChild(idCell);
        row.appendChild(infoCell);
        row.appendChild(createTimeCell);
        row.appendChild(timeCell);
        row.appendChild(statusCell);
        row.appendChild(downloadCell);
        row.appendChild(actionCell);
        tableBody.appendChild(row);
    });

    document.querySelector('table').style.display = 'table';
    emptyState.style.display = 'none';
}

// 格式化日期时间，确保月份、日期、小时、分钟、秒都是两位数
function formatDateTime(dateString, useLocalTime = true) {
    if (!dateString) return '未知时间';

    try {
        const date = new Date(dateString);

        if (isNaN(date.getTime())) {
            return '未知时间';
        }

        let year, month, day, hours, minutes, seconds;

        if (useLocalTime) {
            // 使用本地时区
            year = date.getFullYear();
            month = String(date.getMonth() + 1).padStart(2, '0');
            day = String(date.getDate()).padStart(2, '0');
            hours = String(date.getHours()).padStart(2, '0');
            minutes = String(date.getMinutes()).padStart(2, '0');
            seconds = String(date.getSeconds()).padStart(2, '0');
        } else {
            // 使用 UTC 时间
            year = date.getUTCFullYear();
            month = String(date.getUTCMonth() + 1).padStart(2, '0');
            day = String(date.getUTCDate()).padStart(2, '0');
            hours = String(date.getUTCHours()).padStart(2, '0');
            minutes = String(date.getUTCMinutes()).padStart(2, '0');
            seconds = String(date.getUTCSeconds()).padStart(2, '0');
        }

        return `${year}-${month}-${day} ${hours}:${minutes}:${seconds}`;
    } catch (error) {
        console.error('日期格式化错误:', error);
        return '未知时间';
    }
}

// 刷新单个任务状态
async function refreshTask(taskId) {
    showLoading();
    try {
        const token = localStorage.getItem('token') || '';
        const uid = localStorage.getItem('uid') || '';

        const response = await fetch('/docx/my/task/refresh', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify({
                uid: uid,
                task_id: taskId
            })
        });

        if (!response.ok) throw new Error('刷新失败');
        await fetchTasks();
    } catch (error) {
        console.error('刷新失败:', error);
        alert('刷新失败，请重试');
    } finally {
        hideLoading();
    }
}

// 重试任务
async function retryTask(taskId) {
    showLoading();
    try {
        const token = localStorage.getItem('token') || '';
        const uid = localStorage.getItem('uid') || '';

        const response = await fetch('/docx/my/task/retry', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify({
                uid: uid,
                task_id: taskId
            })
        });

        if (!response.ok) throw new Error('重试失败');
        await fetchTasks();
        alert(`任务 ${taskId} 已重新提交`);
    } catch (error) {
        console.error('重试失败:', error);
        alert('重试失败，请重试');
    } finally {
        hideLoading();
    }
}

// 删除任务
async function deleteTask(taskId, docTitle) {
    if (!confirm(`确定要删除任务 "${docTitle}" 吗？此操作将删除任务记录和生成的文档，且不可恢复。`)) {
        return;
    }

    showLoading();
    try {
        const token = localStorage.getItem('token') || '';

        const response = await fetch(`/docx/del/task/${taskId}`, {
            method: 'GET',
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });

        if (!response.ok) throw new Error('删除失败');

        const result = await response.json();
        alert(result.msg || '删除成功');

        // 刷新任务列表
        await fetchTasks();
    } catch (error) {
        console.error('删除失败:', error);
        alert('删除失败，请重试');
    } finally {
        hideLoading();
    }
}

// 显示/隐藏加载状态
function showLoading() {
    document.getElementById('loadingOverlay').style.display = 'flex';
}
function hideLoading() {
    document.getElementById('loadingOverlay').style.display = 'none';
}

// 自动刷新控制
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

// 从URL获取UID
function getUidFromUrl() {
    const urlParams = new URLSearchParams(window.location.search);
    return urlParams.get('uid');
}

// 初始化页面
document.addEventListener('DOMContentLoaded', () => {
    fetchTasks();
    startAutoRefresh();

    // 页面可见性控制
    document.addEventListener('visibilitychange', function() {
        if (document.hidden) {
            stopAutoRefresh();
        } else {
            startAutoRefresh();
        }
    });
});