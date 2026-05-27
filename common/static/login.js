var psw_input = document.getElementById("psw");
document.getElementById("login-button").onclick = function () {
    var usr = document.getElementById("usr").value.trim();
    var psw = document.getElementById("psw").value;
    var captchaCode = document.getElementById("captcha_code").value.trim();
    var captchaToken = document.getElementById("captcha_token").value;

    if (usr === '') {
        alert(__('auth.please_enter_username'));
        return;
    }
    if (psw.trim() === '') {
        alert(__('auth.please_enter_password'));
        return;
    }
    if (captchaCode === '') {
        alert(__('auth.please_enter_captcha'));
        return;
    }
    if (captchaCode.length !== 4) {
        alert(__('auth.captcha_must_be_4_digits'));
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