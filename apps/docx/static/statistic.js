
// 获取任务数据
async function fetchTasks() {
    try {
        const token = localStorage.getItem('token') || '';
        const uid = getUidFromUrl();

        const response = await fetch('/docx/statistic/report', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify({ uid: uid })
        });

        if (!response.ok) throw new Error('任务获取失败');

        const statisticData = await response.json();
        const tasks = Array.isArray(statisticData) ? statisticData : [statisticData];

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
//    data sample  {'uid': 332987902, 'nickname': 'avata', 'date': '2025-10-24', 'access_count': 19, 'input_token': 21718, 'output_token': 33697},
    tasks.forEach((task, index) => {
        const row = document.createElement('tr');
        // 序号
        const idCell = document.createElement('td');
        idCell.textContent = index + 1;
        idCell.style.fontWeight = '600';
        idCell.style.color = '#4b6cb7';
        // 用户 ID
        const uidCell = document.createElement('td');
        uidCell.innerHTML = `<div><strong>${task.uid || '-'}</strong></div>`;
        // 用户名
        const nicknameCell = document.createElement('td');
        nicknameCell.innerHTML = `<div><strong>${task.nickname || '-'}</strong></div>`;
        // 日期
        const dateCell = document.createElement('td');
        dateCell.textContent = task.date || '-';
        // 访问量
        const accessCountCell = document.createElement('td');
        accessCountCell.innerHTML = `<div>${task.access_count || 0}</div>`;
        // 输入 tokens
        const inputTokenCell = document.createElement('td');
        inputTokenCell.innerHTML = `<div>${task.input_token || 0}</div>`;
        // 输出 tokens
        const outputTokenCell = document.createElement('td');
        outputTokenCell.innerHTML = `<div>${task.output_token || 0}</div>`;

        row.appendChild(idCell);
        row.appendChild(uidCell);
        row.appendChild(nicknameCell);
        row.appendChild(dateCell);
        row.appendChild(accessCountCell);
        row.appendChild(inputTokenCell);
        row.appendChild(outputTokenCell);
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




// 从URL获取UID
function getUidFromUrl() {
    const urlParams = new URLSearchParams(window.location.search);
    return urlParams.get('uid');
}

// 初始化页面
document.addEventListener('DOMContentLoaded', () => {
    fetchTasks();
});