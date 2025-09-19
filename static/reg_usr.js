var psw_input = document.getElementById("psw");
psw_input.onchange = function () {
    document.getElementById("t").value = CryptoJS.MD5(psw_input.value).toString();
};

document.getElementById("register-button").onclick = function () {
    if (document.getElementById("usr").value.trim() === '') {
        alert("请输入用户名");
        return;
    }
    if (document.getElementById("psw").value.trim() === '') {
        alert("请输入密码");
        return;
    }
    document.getElementById('warning-message').textContent = '';
    document.getElementById("my_form").submit();
}

// 按回车键提交表单
document.addEventListener('keypress', function(e) {
    if (e.key === 'Enter') {
        document.getElementById("register-button").click();
    }
});