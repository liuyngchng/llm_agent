function validateForm() {
    const fields = [
        {id: 'db_type', msg: '请选择数据库类型'},
        {id: 'db_name', msg: '请输入数据库名称'},
        {id: 'db_host', msg: '请输入数据库主机地址'},
        {id: 'db_usr', msg: '请输入数据库用户名'}
    ];

    return fields.every(({id, msg}) => {
        if (!document.getElementById(id).value.trim()) {
            showStatus(msg, 2000);
            return false;
        }
        return true;
    });
}

document.getElementById("save_button").onclick = function(e) {
    e.preventDefault();
    if (validateForm()) document.forms[0].submit();
}

document.getElementById("delete_button").addEventListener("click", async function(e) {
    e.preventDefault();
    const uid = document.getElementById("uid").value;
    document.getElementById("warning_info").textContent = ""

    if (!confirm('确定要删除当前配置吗？此操作不可恢复！')) return;

    try {
        const response = await fetch('/cfg/delete', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ uid })
        });

        const result = await response.json();
        if (result.success) {
            document.getElementById("warning_info").textContent = "配置已删除";
            document.getElementById("warning_info").className = "warning-message";
            setTimeout(() => window.location.reload(), 1500);
        } else {
            document.getElementById("warning_info").textContent = '删除失败: ' + (result.message || '');
            document.getElementById("warning_info").className = "warning-message";
        }
    } catch (error) {
        console.error('Error:', error);
        document.getElementById("warning_info").textContent = '请求失败';
        document.getElementById("warning_info").className = "warning-message";
    }
});

function showStatus(text, duration=1500) {
    const indicator = document.createElement('div');
    indicator.className = 'status-indicator';
    indicator.textContent = text;
    document.body.appendChild(indicator);
    setTimeout(() => indicator.remove(), duration);
}