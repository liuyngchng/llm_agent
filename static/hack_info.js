function validateForm() {
    const fields = [
        {id: 'user_list', msg: '请选择用户名'},
        {id: 'hack_user_config', msg: '请输入提问配置'},
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


function showStatus(text, duration=1500) {
    const indicator = document.createElement('div');
    indicator.className = 'status-indicator';
    indicator.textContent = text;
    document.body.appendChild(indicator);
    setTimeout(() => indicator.remove(), duration);
}