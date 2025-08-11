var psw_input = document.getElementById("psw");
document.getElementById("login-button").onclick = function () {
    var usr = document.getElementById("usr").value.trim();
    var psw = document.getElementById("psw").value; // 获取原始密码值

    if (usr === '') {
        alert("请输入用户名");
        return;
    }
    if (psw.trim() === '') {
        alert("请输入密码");
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