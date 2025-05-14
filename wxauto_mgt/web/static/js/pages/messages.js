/**
 * 消息监控页面JavaScript
 */

// 当前选中的监听对象
let currentListener = null;
// 最后一条消息的时间戳
let lastMessageTimestamp = 0;
// 最后一条日志的时间戳
let lastLogTimestamp = 0;

document.addEventListener('DOMContentLoaded', function() {
    // 初始化页面
    initMessagesPage();

    // 绑定刷新按钮事件
    document.getElementById('refresh-listeners').addEventListener('click', loadListeners);
    document.getElementById('refresh-messages').addEventListener('click', function() {
        if (currentListener) {
            loadMessages(currentListener.instance_id, currentListener.chat_name, true);
        }
    });
    document.getElementById('refresh-logs').addEventListener('click', function() {
        loadLogs(true);
    });

    // 绑定添加监听对象按钮事件
    document.getElementById('add-listener').addEventListener('click', showAddListenerModal);

    // 绑定删除监听对象按钮事件
    document.getElementById('delete-listener').addEventListener('click', deleteListener);

    // 绑定保存监听对象按钮事件
    document.getElementById('save-listener').addEventListener('click', saveListener);
});

/**
 * 初始化消息监控页面
 */
function initMessagesPage() {
    // 加载监听对象列表
    loadListeners();

    // 加载日志
    loadLogs();

    // 加载实例列表（用于添加监听对象表单）
    loadInstances();

    // 设置轮询刷新
    pollingManager.addTask('listeners', loadListeners, 5000);  // 更频繁地刷新监听对象列表
    pollingManager.addTask('messages', function() {
        if (currentListener) {
            loadMessages(currentListener.instance_id, currentListener.chat_name);
        }
    }, 2000);  // 更频繁地刷新消息
    pollingManager.addTask('logs', loadLogs, 2000);  // 更频繁地刷新日志
}

/**
 * 加载监听对象列表
 * @param {boolean} forceRefresh - 是否强制刷新（不使用缓存）
 */
async function loadListeners(forceRefresh = false) {
    try {
        const listenersContainer = document.getElementById('listeners-list');

        // 获取监听对象列表（添加时间戳参数避免缓存）
        const timestamp = new Date().getTime();
        const url = forceRefresh ? `/api/listeners?t=${timestamp}` : '/api/listeners';
        const listeners = await fetchAPI(url);

        // 清空容器
        listenersContainer.innerHTML = '';

        if (listeners.length === 0) {
            listenersContainer.innerHTML = `
                <div class="empty-state">
                    <i class="fas fa-headset"></i>
                    <p>暂无监听对象</p>
                </div>
            `;
            return;
        }

        // 添加监听对象
        listeners.forEach(listener => {
            const listenerItem = document.createElement('div');
            listenerItem.className = 'listener-item';
            if (currentListener &&
                currentListener.instance_id === listener.instance_id &&
                currentListener.chat_name === listener.chat_name) {
                listenerItem.classList.add('active');
                // 更新当前选中的监听对象信息
                currentListener = listener;
            }

            // 获取状态标签
            const statusLabel = listener.status === 'active' ?
                '<span class="badge bg-success">活跃</span>' :
                '<span class="badge bg-secondary">未活跃</span>';

            // 获取最后消息时间
            const lastMessageTime = listener.last_message_time ?
                formatDateTime(listener.last_message_time) :
                '无消息';

            listenerItem.innerHTML = `
                <div class="d-flex justify-content-between align-items-center">
                    <strong>${listener.chat_name}</strong>
                    ${statusLabel}
                </div>
                <div class="text-muted small">
                    <span>${listener.instance_id}</span>
                    <span class="ms-2">最后消息: ${lastMessageTime}</span>
                </div>
            `;

            // 绑定点击事件
            listenerItem.addEventListener('click', function() {
                // 移除其他项的选中状态
                document.querySelectorAll('.listener-item').forEach(item => {
                    item.classList.remove('active');
                });

                // 添加选中状态
                this.classList.add('active');

                // 设置当前选中的监听对象
                currentListener = listener;

                // 启用删除按钮
                document.getElementById('delete-listener').disabled = false;

                // 加载消息
                loadMessages(listener.instance_id, listener.chat_name, true);
            });

            listenersContainer.appendChild(listenerItem);
        });

        // 如果当前没有选中的监听对象，但有监听对象，则选中第一个
        if (!currentListener && listeners.length > 0) {
            const firstListenerItem = listenersContainer.querySelector('.listener-item');
            if (firstListenerItem) {
                firstListenerItem.click();
            }
        }
    } catch (error) {
        console.error('加载监听对象列表失败:', error);
        document.getElementById('listeners-list').innerHTML = `
            <div class="empty-state">
                <i class="fas fa-exclamation-circle text-danger"></i>
                <p>加载失败，请重试</p>
            </div>
        `;
    }
}

/**
 * 加载消息
 * @param {string} instanceId - 实例ID
 * @param {string} chatName - 聊天对象名称
 * @param {boolean} reset - 是否重置（清空现有消息）
 */
async function loadMessages(instanceId, chatName, reset = false) {
    try {
        const messagesContainer = document.getElementById('messages-list');

        // 如果是重置，则清空容器并显示加载中
        if (reset) {
            messagesContainer.innerHTML = `
                <div class="text-center py-5">
                    <div class="spinner-border text-primary" role="status">
                        <span class="visually-hidden">加载中...</span>
                    </div>
                    <p class="mt-2">加载消息...</p>
                </div>
            `;
            lastMessageTimestamp = 0;
        }

        // 构建API URL（添加时间戳参数避免缓存）
        const timestamp = new Date().getTime();
        let url = `/api/messages?instance_id=${encodeURIComponent(instanceId)}&chat_name=${encodeURIComponent(chatName)}&limit=50&t=${timestamp}`;
        if (lastMessageTimestamp > 0 && !reset) {
            url += `&since=${lastMessageTimestamp}`;
        }

        // 获取消息
        const messages = await fetchAPI(url);

        // 如果是重置或有新消息，则更新容器
        if (reset || messages.length > 0) {
            // 如果是重置，则清空容器
            if (reset) {
                messagesContainer.innerHTML = '';
            }

            // 如果没有消息
            if (messages.length === 0 && reset) {
                messagesContainer.innerHTML = `
                    <div class="empty-state">
                        <i class="fas fa-comment-slash"></i>
                        <p>暂无消息</p>
                    </div>
                `;
                return;
            }

            // 对消息按时间排序（降序）
            messages.sort((a, b) => b.create_time - a.create_time);

            // 添加消息
            messages.forEach(message => {
                // 更新最后一条消息的时间戳
                if (message.create_time > lastMessageTimestamp) {
                    lastMessageTimestamp = message.create_time;
                }

                const messageItem = document.createElement('div');
                messageItem.className = 'message-item';

                const sender = message.sender || '系统';
                const content = message.content || '(无内容)';
                const time = formatDateTime(message.create_time);

                // 根据消息类型设置不同的样式
                let messageClass = '';
                if (message.message_type === 'image') {
                    messageClass = 'message-image';
                } else if (message.message_type === 'file') {
                    messageClass = 'message-file';
                }

                // 构建消息内容HTML
                let contentHtml = '';
                if (message.message_type === 'image' && message.content) {
                    // 如果是图片消息，显示图片
                    contentHtml = `<img src="${message.content}" alt="图片消息" class="message-image-content">`;
                } else if (message.message_type === 'file' && message.content) {
                    // 如果是文件消息，显示文件链接
                    contentHtml = `<a href="${message.content}" target="_blank" class="message-file-link"><i class="fas fa-file"></i> 文件附件</a>`;
                } else {
                    // 普通文本消息
                    contentHtml = content;
                }

                messageItem.innerHTML = `
                    <div class="message-sender">${sender}:</div>
                    <div class="message-content ${messageClass}">
                        ${contentHtml}
                        <div class="message-time">${time}</div>
                    </div>
                `;

                // 如果是重置，则添加到容器底部
                if (reset) {
                    messagesContainer.appendChild(messageItem);
                } else {
                    // 否则添加到容器顶部
                    messagesContainer.insertBefore(messageItem, messagesContainer.firstChild);
                }
            });

            // 如果是重置，则滚动到底部
            if (reset) {
                messagesContainer.scrollTop = messagesContainer.scrollHeight;
            }
        }
    } catch (error) {
        console.error('加载消息失败:', error);
        if (reset) {
            document.getElementById('messages-list').innerHTML = `
                <div class="empty-state">
                    <i class="fas fa-exclamation-circle text-danger"></i>
                    <p>加载失败，请重试</p>
                </div>
            `;
        }
    }
}

/**
 * 加载日志
 * @param {boolean} reset - 是否重置（清空现有日志）
 */
async function loadLogs(reset = false) {
    try {
        const logsContainer = document.getElementById('logs-list');

        // 如果是重置，则清空容器并显示加载中
        if (reset) {
            logsContainer.innerHTML = `
                <div class="text-center py-5">
                    <div class="spinner-border text-primary" role="status">
                        <span class="visually-hidden">加载中...</span>
                    </div>
                    <p class="mt-2">加载日志...</p>
                </div>
            `;
            lastLogTimestamp = 0;
        }

        // 构建API URL（添加时间戳参数避免缓存）
        const timestamp = new Date().getTime();
        let url = `/api/logs?limit=50&t=${timestamp}`;
        if (lastLogTimestamp > 0 && !reset) {
            url += `&since=${lastLogTimestamp}`;
        }

        // 获取日志
        const logs = await fetchAPI(url);

        // 如果是重置或有新日志，则更新容器
        if (reset || logs.length > 0) {
            // 如果是重置，则清空容器
            if (reset) {
                logsContainer.innerHTML = '';
            }

            // 如果没有日志
            if (logs.length === 0 && reset) {
                logsContainer.innerHTML = `
                    <div class="empty-state">
                        <i class="fas fa-clipboard-list"></i>
                        <p>暂无日志</p>
                    </div>
                `;
                return;
            }

            // 添加日志
            logs.forEach(log => {
                // 更新最后一条日志的时间戳
                if (log.timestamp > lastLogTimestamp) {
                    lastLogTimestamp = log.timestamp;
                }

                const logItem = document.createElement('div');
                logItem.className = `log-item ${getLogLevelClass(log.level)}`;

                const time = formatTime(log.timestamp);
                const level = log.level;
                const message = log.message;

                logItem.textContent = `${time} - ${level} - ${message}`;

                // 如果是重置，则添加到容器底部
                if (reset) {
                    logsContainer.appendChild(logItem);
                } else {
                    // 否则添加到容器顶部
                    logsContainer.insertBefore(logItem, logsContainer.firstChild);
                }
            });

            // 如果是重置，则滚动到底部
            if (reset) {
                logsContainer.scrollTop = logsContainer.scrollHeight;
            }
        }
    } catch (error) {
        console.error('加载日志失败:', error);
        if (reset) {
            document.getElementById('logs-list').innerHTML = `
                <div class="empty-state">
                    <i class="fas fa-exclamation-circle text-danger"></i>
                    <p>加载失败，请重试</p>
                </div>
            `;
        }
    }
}

/**
 * 加载实例列表
 */
async function loadInstances() {
    try {
        // 获取实例列表
        const instances = await fetchAPI('/api/instances');

        // 获取监听对象表单中的实例选择框
        const listenerInstance = document.getElementById('listener-instance');

        // 清空选项（保留默认选项）
        listenerInstance.innerHTML = '<option value="">请选择实例</option>';

        // 添加实例选项
        instances.forEach(instance => {
            // 只添加启用的实例
            if (instance.enabled === 1) {
                const option = document.createElement('option');
                option.value = instance.instance_id;
                option.textContent = instance.name;
                listenerInstance.appendChild(option);
            }
        });
    } catch (error) {
        console.error('加载实例列表失败:', error);
        showNotification('加载实例列表失败', 'danger');
    }
}

/**
 * 显示添加监听对象模态框
 */
function showAddListenerModal() {
    // 重置表单
    document.getElementById('listenerForm').reset();

    // 显示模态框
    const modal = new bootstrap.Modal(document.getElementById('listenerModal'));
    modal.show();
}

/**
 * 保存监听对象
 */
async function saveListener() {
    // 获取表单数据
    const instanceId = document.getElementById('listener-instance').value;
    const chatName = document.getElementById('listener-chat').value;

    // 验证表单
    if (!instanceId || !chatName) {
        showNotification('请填写必填字段', 'warning');
        return;
    }

    try {
        // 发送请求
        await fetchAPI('/api/listeners', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                instance_id: instanceId,
                chat_name: chatName
            })
        });

        // 关闭模态框
        const modal = bootstrap.Modal.getInstance(document.getElementById('listenerModal'));
        modal.hide();

        // 显示成功通知
        showNotification(`监听对象 ${chatName} 添加成功`, 'success');

        // 重新加载监听对象列表
        loadListeners();
    } catch (error) {
        console.error('添加监听对象失败:', error);
        showNotification(`添加监听对象失败: ${error.message}`, 'danger');
    }
}

/**
 * 删除监听对象
 */
async function deleteListener() {
    if (!currentListener) {
        showNotification('请先选择一个监听对象', 'warning');
        return;
    }

    // 确认删除
    if (!confirm(`确定要删除监听对象 ${currentListener.chat_name} 吗？`)) {
        return;
    }

    try {
        // 发送请求
        await fetchAPI('/api/listeners', {
            method: 'DELETE',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                instance_id: currentListener.instance_id,
                chat_name: currentListener.chat_name
            })
        });

        // 显示成功通知
        showNotification(`监听对象 ${currentListener.chat_name} 删除成功`, 'success');

        // 清空消息列表
        document.getElementById('messages-list').innerHTML = `
            <div class="empty-state">
                <i class="fas fa-comments"></i>
                <p>请选择一个监听对象查看消息</p>
            </div>
        `;

        // 重置当前选中的监听对象
        currentListener = null;

        // 禁用删除按钮
        document.getElementById('delete-listener').disabled = true;

        // 重新加载监听对象列表
        loadListeners();
    } catch (error) {
        console.error('删除监听对象失败:', error);
        showNotification(`删除监听对象失败: ${error.message}`, 'danger');
    }
}
