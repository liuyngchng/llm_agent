var psw_input = document.getElementById("psw");
document.getElementById("login-button").onclick = function () {
    var usr = document.getElementById("usr").value.trim();
    var psw = document.getElementById("psw").value;
    var captchaCode = document.getElementById("captcha_code").value.trim();
    var captchaToken = document.getElementById("captcha_token").value;

    if (usr === '') {
        alert("请输入用户名");
        return;
    }
    if (psw.trim() === '') {
        alert("请输入密码");
        return;
    }
    if (captchaCode === '') {
        alert("请输入图形验证码");
        return;
    }
    if (captchaCode.length !== 4) {
        alert("图形验证码必须是4位数字");
        return;
    }

    // 提交前实时计算MD5并赋值
    document.getElementById("t").value = CryptoJS.MD5(psw).toString();
    document.getElementById("my_form").submit();
}

// 保留回车提交
document.addEventListener('keypress', function(e) {
    if (e.key === 'Enter') {
        document.getElementById("login-button").click();
    }
});

// 验证码输入框自动跳转
document.getElementById("captcha_code")?.addEventListener('input', function(e) {
    if (this.value.length === 4) {
        document.getElementById("login-button").focus();
    }
});