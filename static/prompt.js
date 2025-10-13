function validateForm() {
    const fields = [
        {id: 'refine_q_msg', msg: '请输入问题优化提示词配置'},
        {id: 'sql_gen_msg', msg: '请输入SQL生成提示词配置'},
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
    const saveButton = this;
    if (validateForm()) {
        // 禁用按钮
        saveButton.disabled = true;
        saveButton.innerHTML = '<i class="fas fa-spinner fa-spin"></i> 保存中...';

        // 提交表单
        document.forms[0].submit();

        // 3秒后重新启用按钮（防止重复提交）
        setTimeout(() => {
            saveButton.disabled = false;
            saveButton.innerHTML = '<i class="fas fa-save"></i> 保存配置';
        }, 3000);
    }
}