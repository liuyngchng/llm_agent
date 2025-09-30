// 全局变量
let currentTaskId = null;
let progressInterval = null;
let currentKB = null;
const spinnerChars = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏'];
let spinCounter = 0;
let refreshInterval = null;
let selectedFiles = []; // 存储选中的文件列表

// 页面加载时初始化知识库管理
document.addEventListener('DOMContentLoaded', async () => {
    const step2 = document.getElementById('step2');
    const statusDesc = document.getElementById('vdb_status_desc');
    const deleteBtn = document.getElementById('deleteBtn');
    const setDefaultBtn = document.getElementById('setDefaultBtn');
    const kbSelector = document.getElementById('kb_selector');
    const createKB = document.getElementById('createKB');
    const selectBtn = document.getElementById('selectBtn');
    const clearFilesBtn = document.getElementById('clearFilesBtn');

    // 修改自动刷新逻辑 - 添加对selector.value的检查
    refreshInterval = setInterval(() => {
        const selector = document.getElementById('kb_selector');
        // 三重检查：currentKB存在、selector有值、且两者一致
        if (currentKB && selector.value && selector.value === currentKB) {
            loadFileList(currentKB);
        }
    }, 5000);

    // 加载知识库列表
    await loadKnowledgeBases();

    // 知识库选择器事件
    kbSelector.addEventListener('change', function() {
        if (this.value) {
            currentKB = this.value;
            const kbName = this.options[this.selectedIndex].text;
            statusDesc.textContent = `已选择: ${this.options[this.selectedIndex].text}`;
            const isDefault = kbName.includes('(默认)');
            deleteBtn.style.display = 'block';
            setDefaultBtn.style.display = isDefault ? 'none' : 'block';
            step2.classList.remove('hidden');
            loadFileList(currentKB);
        } else {
            // 彻底清理状态
            currentKB = null;
            step2.classList.add('hidden');
            deleteBtn.style.display = 'none';
            setDefaultBtn.style.display = 'none';
            statusDesc.textContent = '未选择知识库';
            document.getElementById('fileListContainer').style.display = 'none';
        }
    });

    // 创建知识库事件
    createKB.addEventListener('click', async function() {
        const kbName = document.getElementById('kb_name').value.trim();
        if (!kbName) {
            alert('请输入知识库名称');
            return;
        }
        // 创建知识库请求
        const uid = document.getElementById('uid').value;
        const t = document.getElementById('t').value;
        const isPublic = document.getElementById('public_checkbox').checked;
        try {
            const response = await fetch('/vdb/create', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ kb_name: kbName, uid, is_public:isPublic, t })
            });
            const result = await response.json();
            if (result.success) {
                const kbStatus = document.getElementById('kb_status');
                kbStatus.style.display = 'block';
                kbStatus.querySelector('span').textContent = `知识库 "${kbName}" 创建成功`;

                // 重新加载知识库列表
                await loadKnowledgeBases();
                // 清空输入框
                document.getElementById('kb_name').value = '';
            } else {
                throw new Error(result.message || '创建失败');
            }
        } catch (error) {
            console.error('创建失败:', error);
            alert(`创建失败: ${error.message}`);
        }
    });

    // 文件选择处理 - 多文件
    selectBtn.addEventListener('click', () => {
        document.getElementById('fileInput').click();
    });

    document.getElementById('fileInput').addEventListener('change', function(e) {
        const files = Array.from(e.target.files);

        if (files.length === 0) {
            clearFileList();
            return;
        }

        // 文件类型验证
        const allowedTypes = ['.pdf', '.docx', '.txt'];
        const invalidFiles = files.filter(file => {
            const fileName = file.name.toLowerCase();
            return !allowedTypes.some(ext => fileName.endsWith(ext));
        });

        if (invalidFiles.length > 0) {
            const invalidNames = invalidFiles.map(f => f.name).join(', ');
            alert(`以下文件类型不支持：${invalidNames}\n\n仅支持 PDF、DOCX、TXT 文件`);
            // 移除不支持的文件
            const validFiles = files.filter(file => {
                const fileName = file.name.toLowerCase();
                return allowedTypes.some(ext => fileName.endsWith(ext));
            });

            if (validFiles.length === 0) {
                clearFileList();
                return;
            }

            // 更新文件输入
            const dataTransfer = new DataTransfer();
            validFiles.forEach(file => dataTransfer.items.add(file));
            this.files = dataTransfer.files;

            updateFileList(validFiles);
            return;
        }

        // 文件数量限制
        const MAX_FILES = 20;
        if (files.length > MAX_FILES) {
            alert(`最多只能选择 ${MAX_FILES} 个文件，已自动选择前 ${MAX_FILES} 个文件`);
            const limitedFiles = files.slice(0, MAX_FILES);

            // 更新文件输入
            const dataTransfer = new DataTransfer();
            limitedFiles.forEach(file => dataTransfer.items.add(file));
            this.files = dataTransfer.files;

            updateFileList(limitedFiles);
            return;
        }

        updateFileList(files);
    });

    // 清空文件列表
    clearFilesBtn.addEventListener('click', clearFileList);

    // 批量上传文档处理
    document.getElementById('startBtn').addEventListener('click', async () => {
        if (!currentKB) {
            alert('请先选择知识库');
            return;
        }
        if (selectedFiles.length === 0) {
            alert('请先选择 Word/PDF/TXT 文档');
            return;
        }

        // 禁用上传按钮防止重复点击
        const startBtn = document.getElementById('startBtn');
        const originalBtnText = startBtn.innerHTML;
        startBtn.disabled = true;
        startBtn.innerHTML = '<div class="spinner"></div> 上传中...';

        // 重置界面
        document.getElementById('fileUploadResult').textContent = "开始批量处理...";
        const uploadProgress = document.getElementById('uploadProgress');
        uploadProgress.style.display = 'block';

        const uid = document.getElementById('uid').value;

        try {
            await uploadFilesSequentially(selectedFiles, currentKB, uid);
        } catch (error) {
            console.error('批量上传失败:', error);
            document.getElementById('fileUploadResult').textContent = "批量上传失败";
            // 恢复按钮状态
            startBtn.disabled = false;
            startBtn.innerHTML = originalBtnText;
        }
    });

    // 删除知识库功能
    document.getElementById('deleteBtn').addEventListener('click', async () => {
        if (!confirm('确定要删除整个知识库吗？此操作不可恢复！')) return;
        const deleteBtn = document.getElementById('deleteBtn');
        const statusDesc = document.getElementById('vdb_status_desc');
        const selector = document.getElementById('kb_selector');
        const originalText = deleteBtn.innerHTML;
        const uid = document.getElementById('uid').value;
        const t = document.getElementById('t').value;

        try {
            // 禁用按钮并显示加载状态
            deleteBtn.disabled = true;
            deleteBtn.innerHTML = '<div class="spinner"></div> 删除中...';

            const response = await fetch('/vdb/delete', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ uid, t, kb_id: currentKB })
            });

            const result = await response.json();

            if (result.success) {
                // 更新UI
                statusDesc.textContent = "无知识库";
                deleteBtn.style.display = 'none';
                document.getElementById('step2').classList.add('hidden');

                // 从选择器中移除
                for (let i = 0; i < selector.options.length; i++) {
                    if (selector.options[i].value === currentKB) {
                        selector.remove(i);
                        break;
                    }
                }
                selector.value = "";
                currentKB = null;

                alert('知识库已成功删除！');
            } else {
                throw new Error(result.message || '删除失败');
            }
        } catch (error) {
            console.error('删除失败:', error);
            alert(`删除失败: ${error.message}`);
        } finally {
            // 恢复按钮状态
            deleteBtn.disabled = false;
            deleteBtn.innerHTML = originalText;
        }
    });

    // 设置为默认知识库功能
    document.getElementById('setDefaultBtn').addEventListener('click', async () => {
        if (!currentKB) {
            alert('请先选择知识库');
            return;
        }

        const setDefaultBtn = document.getElementById('setDefaultBtn');
        const originalText = setDefaultBtn.innerHTML;
        const uid = document.getElementById('uid').value;
        const t = document.getElementById('t').value;

        try {
            // 禁用按钮并显示加载状态
            setDefaultBtn.disabled = true;
            setDefaultBtn.innerHTML = '<div class="spinner"></div> 设置中...';

            const response = await fetch('/vdb/set/default', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ uid, t, kb_id: currentKB })
            });

            const result = await response.json();

            if (result.success) {
                alert('已设置为默认知识库！');
                // 更新状态显示
                document.getElementById('vdb_status_desc').textContent =
                    `${result.kb_name} (默认)`;
                // 刷新知识库下拉菜单
                await loadKnowledgeBases();
                // 重新选中当前知识库
                const selector = document.getElementById('kb_selector');
                selector.value = currentKB;

                // 触发change事件更新界面状态
                const event = new Event('change');
                selector.dispatchEvent(event);
            } else {
                throw new Error(result.message || '设置失败');
            }
        } catch (error) {
            console.error('设置默认知识库失败:', error);
            alert(`设置失败: ${error.message}`);
        } finally {
            // 恢复按钮状态
            setDefaultBtn.disabled = false;
            setDefaultBtn.innerHTML = originalText;
        }
    });

    // 加载知识库列表
    loadKnowledgeBases();

    // 加载文件列表
    loadFileList(currentKB);
});

// 更新文件列表显示
function updateFileList(files) {
    selectedFiles = files;
    const fileItems = document.getElementById('fileItems');
    const fileCount = document.getElementById('fileCount');

    fileItems.innerHTML = '';
    fileCount.textContent = files.length;

    files.forEach((file, index) => {
        const fileItem = document.createElement('div');
        fileItem.className = 'file-item';
        fileItem.innerHTML = `
            <span class="file-name">${file.name}</span>
            <span class="file-size">(${formatFileSize(file.size)})</span>
            <button type="button" class="btn-remove" data-index="${index}">×</button>
        `;
        fileItems.appendChild(fileItem);
    });

    // 添加删除单个文件的事件监听
    document.querySelectorAll('.btn-remove').forEach(btn => {
        btn.addEventListener('click', function() {
            const index = parseInt(this.getAttribute('data-index'));
            removeFile(index);
        });
    });

    // 显示文件列表容器
    document.getElementById('fileList').style.display = 'block';
}

// 移除单个文件
function removeFile(index) {
    selectedFiles.splice(index, 1);
    updateFileList(selectedFiles);
}

// 清空文件列表
function clearFileList() {
    selectedFiles = [];
    document.getElementById('fileInput').value = '';
    document.getElementById('fileList').style.display = 'none';
    document.getElementById('fileCount').textContent = '0';
    document.getElementById('fileItems').innerHTML = '';
}

// 顺序上传文件
async function uploadFilesSequentially(files, kbId, uid) {
    const totalFiles = files.length;
    let completedCount = 0;
    let successCount = 0;
    let failCount = 0;

    // 更新进度显示
    const updateProgress = () => {
        const percent = Math.round((completedCount / totalFiles) * 100);
        document.getElementById('overallProgressFill').style.width = `${percent}%`;
        document.getElementById('progressText').textContent =
            `上传中: ${completedCount}/${totalFiles} (成功: ${successCount}, 失败: ${failCount})`;
        document.getElementById('progressPercent').textContent = `${percent}%`;
    };

    // 重置进度
    completedCount = 0;
    successCount = 0;
    failCount = 0;
    updateProgress();

    const failedFiles = []; // 记录失败的文件

    for (let i = 0; i < files.length; i++) {
        const file = files[i];

        try {
            // 上传单个文件
            const formData = new FormData();
            formData.append('file', file);
            formData.append('kb_id', kbId);
            formData.append('uid', uid);

            const uploadRes = await fetch('/vdb/upload', {
                method: 'POST',
                body: formData
            });

            const responseData = await uploadRes.json();

            if (uploadRes.ok) {
                successCount++;
                console.log(`文件 "${file.name}" 上传成功:`, responseData.message);
            } else {
                failCount++;
                failedFiles.push({
                    name: file.name,
                    error: responseData.message || '未知错误'
                });
                console.error(`文件 "${file.name}" 上传失败:`, responseData.message);
            }
        } catch (error) {
            failCount++;
            failedFiles.push({
                name: file.name,
                error: error.message || '网络错误'
            });
            console.error(`文件 "${file.name}" 上传异常:`, error);
        } finally {
            completedCount++;
            updateProgress();
        }
    }

    // 上传完成
    let resultMessage = `批量上传完成！成功: ${successCount}, 失败: ${failCount}`;
    if (failedFiles.length > 0) {
        resultMessage += `\n失败文件: ${failedFiles.map(f => f.name).join(', ')}`;
    }

    document.getElementById('fileUploadResult').textContent = resultMessage;

    // 恢复按钮状态
    const startBtn = document.getElementById('startBtn');
    startBtn.disabled = false;
    startBtn.innerHTML = '<i class="fas fa-cloud-upload-alt"></i> 批量上传';

    // 清空文件列表
    clearFileList();

    // 隐藏进度条
    document.getElementById('uploadProgress').style.display = 'none';

    // 刷新文件列表显示
    if (currentKB) {
        await loadFileList(currentKB);
    }

    // 如果有失败的文件，显示详细信息
    if (failedFiles.length > 0) {
        setTimeout(() => {
            const failedDetails = failedFiles.map(f => `${f.name}: ${f.error}`).join('\n');
            if (failedFiles.length <= 3) {
                alert(`以下文件上传失败：\n\n${failedDetails}`);
            } else {
                console.log('失败文件详情:', failedDetails);
            }
        }, 500);
    }
}

// 加载知识库列表
async function loadKnowledgeBases() {
    const selector = document.getElementById('kb_selector');
    const uid = document.getElementById('uid').value;
    const t = document.getElementById('t').value;

    try {
        const response = await fetch('/vdb/my/list', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ uid, t })
        });
        // 添加状态码检查
        if (!response.ok) {
            const errorText = await response.text();
            throw new Error(`API 错误 ${response.status}: ${errorText.slice(0, 100)}...`);
        }
        const result = await response.json();

        // 清空选择器（保留第一个选项）
        while (selector.options.length > 1) {
            selector.remove(1);
        }

        // 添加知识库选项
        if (result.kb_list && result.kb_list.length > 0) {
            result.kb_list.forEach(kb => {
                const option = document.createElement('option');
                option.value = kb.id;
                option.textContent = kb.name;
                selector.appendChild(option);
            });
        }
    } catch (error) {
        console.error('加载知识库失败:', error);
    }
}

// 获取进度
async function fetchProgress() {
    if (!currentTaskId) return;

    try {
        const res = await fetch('/vdb/process/info', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ task_id: currentTaskId })
        });

        const data = await res.json();

        // 更新文本进度
        document.getElementById('fileUploadResult').textContent =
            spinnerChars[spinCounter % spinnerChars.length] + ' ' + data.progress;
        spinCounter++;

        // 更新进度条
        if (data.percent) {
            document.getElementById('progressFill').style.width = `${data.percent}%`;
        }

        // 完成检测
        if (data.progress.includes("完成") || data.progress.includes("成功")) {
            clearInterval(progressInterval);
            document.getElementById('fileUploadResult').textContent = "知识库构建完成!";
            document.getElementById('progressFill').style.width = '100%';
            document.getElementById('stream_output').innerHTML =
                `<div class="status-container"><i class="fas fa-check-circle"></i> ${data.progress}</div>`;
            await loadFileList(currentKB);
        }

        if (data.progress.includes("失败") || data.progress.includes("错误")) {
            clearInterval(progressInterval);
            document.getElementById('stream_output').innerHTML =
                `<div class="error-container">${data.progress}</div>`;
        }
    } catch (error) {
        console.error('进度获取失败:', error);
        document.getElementById('fileUploadResult').textContent = "进度获取失败";
    }
}

// 格式化文件大小
function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

// 加载文件列表
async function loadFileList(kb_id) {
    const container = document.getElementById('fileListContainer');
    const tbody = document.querySelector('#fileListTable tbody');
    const uid = document.getElementById('uid').value;
    const t = document.getElementById('t').value;

    try {
        const response = await fetch('/vdb/file/list', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                vdb_id: kb_id,
                uid: uid,
                t: t
            })
        });

        if (!response.ok) {
            throw new Error(`HTTP错误 ${response.status}: ${response.statusText}`);
        }
        const result = await response.json();
        if (!result.files) {
            throw new Error('返回数据格式错误，缺少 files 属性');
        }
        const files = result.files;
        tbody.innerHTML = '';

        if (files.length === 0) {
            container.style.display = 'none';
            return;
        }

        // 填充文件列表
        files.forEach((file, index)  => {
            const row = document.createElement('tr');
            const displayName = truncateFileName(file.name, 25); // 25个字符长度
            const sequenceNumber = formatSequenceNumber(index, files.length);

            row.innerHTML = `
                <td>${sequenceNumber}</td>
                <td class="filename-cell">
                    ${displayName}
                    ${file.name.length > 25 ? `<div class="filename-tooltip">${file.name}</div>` : ''}
                </td>
                <td>${file.percent}%</td>
                <td>${file.process_info}</td>
                <td>
                    <button class="btn btn-danger delete-file-btn"
                            data-file-id="${file.id}">
                        <i class="fas fa-trash"></i> 删除
                    </button>
                </td>
            `;
            tbody.appendChild(row);
        });

        container.style.display = 'block';

        // 添加删除事件监听
        document.querySelectorAll('.delete-file-btn').forEach(btn => {
            btn.addEventListener('click', handleFileDelete);
        });

    } catch (error) {
        console.error('加载文件列表失败:', error);
        container.style.display = 'none';
    }
}

function formatSequenceNumber(index, total) {
    const digits = total.toString().length;
    return (index + 1).toString().padStart(digits, ' ');
}

// 文件名截断函数
function truncateFileName(filename, maxLength) {
    if (filename.length <= maxLength) {
        return filename;
    }
    // 确保截断后总长度不超过maxLength
    return filename.substring(0, maxLength - 3) + '...';
}

// 处理文件删除
async function handleFileDelete(e) {
    const fileId = e.target.closest('button').dataset.fileId;
    if (!confirm(`确定要删除这个文件吗？此操作不可恢复！`)) return;

    const uid = document.getElementById('uid').value;
    const t = document.getElementById('t').value;
    const btn = e.target.closest('button');
    const originalHTML = btn.innerHTML;

    try {
        // 显示加载状态
        btn.innerHTML = '<div class="spinner"></div> 删除中...';
        btn.disabled = true;

        const response = await fetch('/vdb/file/delete', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                uid,
                vdb_id: currentKB,
                file_id: fileId,
                t
            })
        });

        const result = await response.json();
        if (!result.success) throw new Error(result.message || '删除失败');

        // 刷新文件列表
        await loadFileList(currentKB);
        alert('文件已成功删除！');

    } catch (error) {
        console.error('文件删除失败:', error);
        alert(`删除失败: ${error.message}`);
    } finally {
        // 恢复按钮状态
        btn.disabled = false;
        btn.innerHTML = originalHTML;
    }
}

window.addEventListener('beforeunload', () => {
    if (refreshInterval) {
        clearInterval(refreshInterval);
    }
});