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

document.getElementById("user_list").addEventListener("change", function() {
    txt_area =document.getElementById("hack_user_config");
    txt_area.value = '';
    const uid = this.value;
    fetch(`/${uid}/my/hack/info`)
        .then(response => response.json())
        .then(data => {
            txt_area.value = data.data || '';
        })
        .catch(error => console.error('获取配置失败:', error));
});

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