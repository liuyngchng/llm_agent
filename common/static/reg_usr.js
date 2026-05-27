var psw_input = document.getElementById("psw");
psw_input.onchange = function () {
    document.getElementById("t").value = CryptoJS.MD5(psw_input.value).toString();
};

document.getElementById("register-button").onclick = function () {
    var username = document.getElementById("usr").value.trim();
    var password = document.getElementById("psw").value.trim();
    var captchaCode = document.getElementById("captcha_code").value.trim();
    var captchaToken = document.getElementById("captcha_token").value;
    var warningMessage = document.getElementById('warning-message');

    // 清空之前的警告信息
    warningMessage.textContent = '';
    warningMessage.style.display = 'none';

    if (username === '') {
        alert(__('auth.please_enter_username'));
        return;
    }
    if (password === '') {
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
    document.getElementById("t").value = CryptoJS.MD5(psw_input.value).toString();
    document.getElementById("my_form").submit();
}

// 按回车键提交表单
document.addEventListener('keypress', function(e) {
    if (e.key === 'Enter') {
        document.getElementById("register-button").click();
    }
});