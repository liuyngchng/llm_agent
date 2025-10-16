// 页面加载完成后执行
document.addEventListener('DOMContentLoaded', function() {
    loadMarkdown();
});

// 加载Markdown内容
function loadMarkdown(md_name) {
    // 显示加载状态，隐藏其他内容
    document.getElementById('loading').style.display = 'block';
    document.getElementById('error').style.display = 'none';
    document.getElementById('markdown-content').style.display = 'none';

    // 调用API获取Markdown内容
    fetch("/md/${md_name}.md")
        .then(response => {
            if (!response.ok) {
                throw new Error('网络响应不正常: ' + response.status);
            }
            return response.text();
        })
        .then(markdownText => {
            // 使用marked.js将Markdown转换为HTML
            const htmlContent = marked.parse(markdownText);

            // 显示渲染后的内容
            document.getElementById('markdown-content').innerHTML = htmlContent;
            document.getElementById('loading').style.display = 'none';
            document.getElementById('markdown-content').style.display = 'block';
        })
        .catch(error => {
            // 显示错误信息
            console.error('获取Markdown内容失败:', error);
            document.getElementById('error-message').textContent = error.message || '无法获取Markdown内容，请稍后重试。';
            document.getElementById('loading').style.display = 'none';
            document.getElementById('error').style.display = 'block';
        });
}