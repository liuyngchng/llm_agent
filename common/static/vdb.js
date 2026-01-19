// 全局变量
let currentTaskId = null;
let progressInterval = null;
let currentKB = null;
const spinnerChars = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏'];
let spinCounter = 0;
let refreshInterval = null;
let selectedFiles = []; // 存储选中的文件列表

let currentKbInfo = null;  // 存储当前知识库的完整信息

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
            const selectedOption = this.options[this.selectedIndex];
            const kbName = selectedOption.text;

            // 提取知识库信息
            currentKbInfo = {
                id: this.value,
                name: kbName.replace(' (默认)', ''), // 移除默认标记
                isDefault: kbName.includes('(默认)'),
                isPublic: selectedOption.dataset.public === 'true'
            };

            // 更新状态显示
            statusDesc.textContent = currentKbInfo.name;

            // 显示/隐藏操作按钮
            deleteBtn.style.display = 'block';
            setDefaultBtn.style.display = currentKbInfo.isDefault ? 'none' : 'block';

            // 更新徽章状态
            updateKbBadges();

            // 显示第二步
            step2.classList.remove('hidden');
            loadFileList(currentKB);
        } else {
            resetKbSelection();
        }
    });

    // 刷新按钮事件
    document.getElementById('kbRefreshBtn').addEventListener('click', async function() {
        const btn = this;
        const icon = btn.querySelector('i');

        // 添加旋转动画
        icon.classList.add('fa-spin');
        btn.disabled = true;

        try {
            await loadKnowledgeBases();
            showNotification('知识库列表已刷新', 'success');
        } catch (error) {
            console.error('刷新失败:', error);
            showNotification('刷新失败: ' + error.message, 'error');
        } finally {
            // 移除旋转动画
            setTimeout(() => {
                icon.classList.remove('fa-spin');
                btn.disabled = false;
            }, 500);
        }
    });

    // 创建知识库事件
    createKB.addEventListener('click', async function() {
        const kbName = document.getElementById('kb_name').value.trim();
        if (!kbName) {
            showNotification('请输入知识库名称', 'error');
            return;
        }

        // 检查知识库名称长度
        if (kbName.length > 50) {
            showNotification('知识库名称不能超过50个字符', 'error');
            return;
        }

        const btn = this;
        const originalText = btn.innerHTML;
        const uid = document.getElementById('uid').value;
        const t = document.getElementById('t').value;
        const isPublic = document.getElementById('public_checkbox').checked;

        try {
            // 禁用按钮并显示加载状态
            btn.disabled = true;
            btn.innerHTML = '<div class="spinner"></div> 创建中...';

            const response = await fetch('/vdb/create', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    kb_name: kbName,
                    uid,
                    is_public: isPublic,
                    t
                })
            });

            const result = await response.json();
            if (result.success) {
                // 显示成功消息
                showNotification(`知识库 "${kbName}" 创建成功`, 'success');

                // 重新加载知识库列表
                await loadKnowledgeBases();

                // 自动选择新创建的知识库
                const selector = document.getElementById('kb_selector');
                for (let option of selector.options) {
                    if (option.text.includes(kbName)) {
                        selector.value = option.value;
                        selector.dispatchEvent(new Event('change'));
                        break;
                    }
                }

                // 清空输入框
                document.getElementById('kb_name').value = '';
                document.getElementById('public_checkbox').checked = false;

                // 显示成功状态
                const kbStatus = document.getElementById('kb_status');
                kbStatus.style.display = 'block';
                setTimeout(() => {
                    kbStatus.style.display = 'none';
                }, 3000);
            } else {
                throw new Error(result.message || '创建失败');
            }
        } catch (error) {
            console.error('创建失败:', error);
            showNotification(`创建失败: ${error.message}`, 'error');
        } finally {
            // 恢复按钮状态
            btn.disabled = false;
            btn.innerHTML = originalText;
        }
    });

    // 文件选择处理 - 多文件
    selectBtn.addEventListener('click', () => {
        document.getElementById('fileInput').click();
    });

    // 修改文件选择处理 - 多文件（追加模式）
    document.getElementById('fileInput').addEventListener('change', function(e) {
        let newFiles = Array.from(e.target.files);
        if (newFiles.length === 0) {
            return;
        }
        // 文件类型验证
        const allowedTypes = ['.pdf', '.docx', '.txt'];
        const invalidFiles = newFiles.filter(file => {
            const fileName = file.name.toLowerCase();
            return !allowedTypes.some(ext => fileName.endsWith(ext));
        });

        if (invalidFiles.length > 0) {
            const invalidNames = invalidFiles.map(f => f.name).join(', ');
            alert(`以下文件类型不支持：${invalidNames}\n\n仅支持 PDF、DOCX、TXT 文件`);
            // 移除不支持的文件
            const validNewFiles = newFiles.filter(file => {
                const fileName = file.name.toLowerCase();
                return allowedTypes.some(ext => fileName.endsWith(ext));
            });

            if (validNewFiles.length === 0) {
                // 清空文件输入，避免重复触发
                this.value = '';
                return;
            }

            newFiles = validNewFiles;
        }

        // 合并新文件到已选文件列表中，避免重复
        const existingFileNames = selectedFiles.map(f => f.name);
        const uniqueNewFiles = newFiles.filter(file => !existingFileNames.includes(file.name));

        // 如果有重复文件，提示用户
        const duplicateFiles = newFiles.filter(file => existingFileNames.includes(file.name));
        if (duplicateFiles.length > 0) {
            const duplicateNames = duplicateFiles.map(f => f.name).join(', ');
            alert(`以下文件已存在，将跳过添加：${duplicateNames}`);
        }

        // 添加新文件到选中列表
        selectedFiles = [...selectedFiles, ...uniqueNewFiles];
        // 文件数量限制
        const MAX_FILES = 20;
        if (selectedFiles.length > MAX_FILES) {
            alert(`最多只能选择 ${MAX_FILES} 个文件，已自动忽略超出的部分`);
            selectedFiles = selectedFiles.slice(0, MAX_FILES);
        }
        updateFileList(selectedFiles);
        // 清空文件输入，避免重复触发
        this.value = '';
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
        if (!currentKbInfo) return;

        const kbName = currentKbInfo.name;
        const confirmMsg = `确定要删除知识库 "${kbName}" 吗？\n\n此操作将删除所有关联文件，且不可恢复！`;

        if (!confirm(confirmMsg)) return;

        const deleteBtn = document.getElementById('deleteBtn');
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
                showNotification(`知识库 "${kbName}" 已删除`, 'success');

                // 重置选择状态
                resetKbSelection();

                // 重新加载知识库列表
                await loadKnowledgeBases();

                // 重置选择器
                document.getElementById('kb_selector').value = "";
            } else {
                throw new Error(result.message || '删除失败');
            }
        } catch (error) {
            console.error('删除失败:', error);
            showNotification(`删除失败: ${error.message}`, 'error');
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

    // 添加键盘快捷键
    document.addEventListener('keydown', function(e) {
        // Ctrl+Enter 创建知识库
        if (e.ctrlKey && e.key === 'Enter') {
            const kbName = document.getElementById('kb_name').value.trim();
            if (kbName) {
                document.getElementById('createKB').click();
                e.preventDefault();
            }
        }

        // F5 刷新列表
        if (e.key === 'F5') {
            document.getElementById('kbRefreshBtn').click();
            e.preventDefault();
        }
    });

    // 加载知识库列表
    loadKnowledgeBases();

    // 加载文件列表
    if (currentKB) {
        loadFileList(currentKB);
    }


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
    startBtn.innerHTML = '<i class="fas fa-cloud-upload-alt"></i> 上传';

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

        if (!response.ok) {
            const errorText = await response.text();
            throw new Error(`API 错误 ${response.status}: ${errorText.slice(0, 100)}...`);
        }

        const result = await response.json();

        // 保存当前选中的值
        const currentValue = selector.value;

        // 清空选择器（保留第一个选项）
        while (selector.options.length > 1) {
            selector.remove(1);
        }

        // 添加知识库选项
        if (result.kb_list && result.kb_list.length > 0) {
            result.kb_list.forEach(kb => {
                const option = document.createElement('option');
                option.value = kb.id;
                option.textContent = kb.name + (kb.is_default ? ' (默认)' : '');
                option.dataset.public = kb.is_public || false;
                option.dataset.default = kb.is_default || false;
                selector.appendChild(option);
            });

            // 恢复之前的选择
            if (currentValue) {
                selector.value = currentValue;
            }
        }
        // 在成功加载后，如果有当前选中的知识库，更新状态
        if (currentKB && selector.value === currentKB) {
            // 触发 change 事件以更新界面状态
            selector.dispatchEvent(new Event('change'));
        }
    } catch (error) {
        console.error('加载知识库失败:', error);
        showNotification('加载知识库失败: ' + error.message, 'error');
    }
}

function resetKbSelection() {
    currentKB = null;
    currentKbInfo = null;
    document.getElementById('step2').classList.add('hidden');
    document.getElementById('deleteBtn').style.display = 'none';
    document.getElementById('setDefaultBtn').style.display = 'none';
    document.getElementById('vdb_status_desc').textContent = '未选择知识库';
    document.getElementById('fileListContainer').style.display = 'none';

    // 隐藏所有徽章
    document.getElementById('public_badge').style.display = 'none';
    document.getElementById('default_badge').style.display = 'none';
}

// 新增函数：更新知识库徽章
function updateKbBadges() {
    const publicBadge = document.getElementById('public_badge');
    const defaultBadge = document.getElementById('default_badge');

    if (currentKbInfo) {
        // 更新公开徽章
        if (currentKbInfo.isPublic) {
            publicBadge.style.display = 'flex';
        } else {
            publicBadge.style.display = 'none';
        }

        // 更新默认徽章
        if (currentKbInfo.isDefault) {
            defaultBadge.style.display = 'flex';
            document.getElementById('setDefaultBtn').style.display = 'none';
        } else {
            defaultBadge.style.display = 'none';
            document.getElementById('setDefaultBtn').style.display = 'block';
        }
    }
}

// 新增函数：显示通知
function showNotification(message, type = 'info') {
    // 创建通知元素
    const notification = document.createElement('div');
    notification.className = `notification notification-${type}`;
    notification.innerHTML = `
        <i class="fas fa-${type === 'success' ? 'check-circle' : type === 'error' ? 'exclamation-circle' : 'info-circle'}"></i>
        <span>${message}</span>
    `;

    // 添加样式
    notification.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        padding: 12px 20px;
        border-radius: 6px;
        background: ${type === 'success' ? '#4CAF50' : type === 'error' ? '#f44336' : '#2196F3'};
        color: white;
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        z-index: 1000;
        animation: slideIn 0.3s ease;
        display: flex;
        align-items: center;
        gap: 10px;
        font-weight: 500;
    `;

    // 添加到页面
    document.body.appendChild(notification);

    // 3秒后自动移除
    setTimeout(() => {
        notification.style.opacity = '0';
        notification.style.transform = 'translateX(100%)';
        setTimeout(() => {
            if (notification.parentNode) {
                notification.parentNode.removeChild(notification);
            }
        }, 300);
    }, 3000);
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

            // 处理创建时间
            let createTime = '未知时间';
            if (file.create_time) {
                try {
                    createTime = new Date(file.create_time).toLocaleString('zh-CN').replace(/\//g, '-');
                } catch (e) {
                    console.warn('时间格式转换错误:', file.create_time, e);
                    createTime = file.create_time; // 使用原始字符串
                }
            }

            row.innerHTML = `
                <td>${sequenceNumber}</td>
                <td class="filename-cell">
                    ${displayName}
                    ${file.name.length > 25 ? `<div class="filename-tooltip">${file.name}</div>` : ''}
                </td>
                <td class="create-time-cell">${createTime}</td>
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