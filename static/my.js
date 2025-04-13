<script>
    document.querySelector('.system-settings-link').addEventListener('click', function(e) {
        e.preventDefault();
        const uid = document.getElementById('uid').value;
        fetch('/cfg/idx', {
            method: 'POST',
            headers: {'Content-Type': 'application/x-www-form-urlencoded'},
            body: `uid=${encodeURIComponent(uid)}`
        })
        .then(response => response.text())
        .then(html => {
            const newWindow = window.open();
            newWindow.document.write(html);
        })
        .catch(error => console.error('请求失败:', error));
    });

</script>