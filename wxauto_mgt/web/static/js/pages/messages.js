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

    // 绑定日志抽屉事件
    document.getElementById('toggle-logs-drawer').addEventListener('click', openLogsDrawer);
    document.getElementById('close-logs-drawer').addEventListener('click', closeLogsDrawer);
    document.getElementById('logs-drawer-overlay').addEventListener('click', closeLogsDrawer);

    // 绑定日志过滤事件（延迟绑定，确保元素存在）
    setTimeout(() => {
        const hideDebugEl = document.getElementById('hide-debug-logs');
        const showInfoEl = document.getElementById('show-info');
        const showWarningEl = document.getElementById('show-warning');
        const showErrorEl = document.getElementById('show-error');

        if (hideDebugEl) {
            hideDebugEl.addEventListener('change', function() {
                console.log('DEBUG过滤开关变化:', this.checked);
                applyLogFilters();
            });
        }

        if (showInfoEl) {
            showInfoEl.addEventListener('change', applyLogFilters);
        }

        if (showWarningEl) {
            showWarningEl.addEventListener('change', applyLogFilters);
        }

        if (showErrorEl) {
            showErrorEl.addEventListener('change', applyLogFilters);
        }

        console.log('日志过滤事件绑定完成');
    }, 100);

    // 绑定键盘事件
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape') {
            closeLogsDrawer();
        }
    });
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

        // 按活跃状态排序：活跃用户在前，未活跃用户在后
        listeners.sort((a, b) => {
            // 首先按活跃状态排序
            if (a.status === 'active' && b.status !== 'active') return -1;
            if (a.status !== 'active' && b.status === 'active') return 1;

            // 如果状态相同，按最后消息时间排序
            const aTime = a.last_message_time || 0;
            const bTime = b.last_message_time || 0;
            return bTime - aTime;
        });

        // 添加监听对象
        listeners.forEach(listener => {
            // 统一字段名：确保有chat_name字段
            if (!listener.chat_name && listener.who) {
                listener.chat_name = listener.who;
            }

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

            // 对消息按时间排序（升序，从旧到新）
            messages.sort((a, b) => a.create_time - b.create_time);

            // 添加消息
            messages.forEach(message => {
                // 更新最后一条消息的时间戳
                if (message.create_time > lastMessageTimestamp) {
                    lastMessageTimestamp = message.create_time;
                }

                const messageItem = document.createElement('div');

                const sender = message.sender || '系统';
                const content = message.content || '(无内容)';
                const time = formatDateTime(message.create_time);

                // 判断消息类型：用户消息 vs 系统消息
                const isUserMessage = sender && sender.toLowerCase() !== 'self' && sender !== '系统';
                const isSystemMessage = sender && (sender.toLowerCase() === 'self' || sender === '系统');

                // 设置消息项的基础样式类
                let messageItemClass = 'message-item';
                if (isUserMessage) {
                    messageItemClass += ' user-message';
                } else if (isSystemMessage) {
                    messageItemClass += ' system-message';
                }
                messageItem.className = messageItemClass;

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

                // 构建处理状态标签
                let statusBadges = '';

                // 处理状态
                if (message.processed === 1) {
                    statusBadges += '<span class="badge bg-success me-1">已处理</span>';
                } else {
                    statusBadges += '<span class="badge bg-secondary me-1">未处理</span>';
                }

                // 投递状态
                if (message.delivery_status === 1) {
                    statusBadges += '<span class="badge bg-info me-1">投递成功</span>';
                } else if (message.delivery_status === 2) {
                    statusBadges += '<span class="badge bg-warning me-1">投递失败</span>';
                }

                // 回复状态
                if (message.reply_status === 1) {
                    statusBadges += '<span class="badge bg-primary me-1">已回复</span>';
                }

                // 构建回复内容
                let replyHtml = '';
                if (message.reply_content) {
                    // 格式化AI回复内容，去掉多余的换行符
                    const formattedReplyContent = message.reply_content
                        .replace(/\n\s*\n/g, '\n')  // 将多个连续换行替换为单个换行
                        .trim();  // 去掉首尾空白

                    // 格式化回复时间
                    const replyTime = message.reply_time ? formatDateTime(message.reply_time) : '';

                    replyHtml = `
                        <div class="message-reply mt-2">
                            <div class="reply-header">
                                <div class="reply-label">AI回复:</div>
                                ${replyTime ? `<div class="reply-time">${replyTime}</div>` : ''}
                            </div>
                            <div class="reply-content">${formattedReplyContent}</div>
                        </div>
                    `;
                }

                // 构建消息HTML - 根据消息类型使用不同的布局
                if (isUserMessage) {
                    // 用户消息：右对齐，气泡样式
                    messageItem.innerHTML = `
                        <div class="message-wrapper user-message-wrapper">
                            <div class="message-bubble user-bubble">
                                <div class="message-content ${messageClass}">
                                    ${contentHtml}
                                </div>
                                <div class="message-meta">
                                    <span class="message-sender">${sender}</span>
                                    <span class="message-time">${time}</span>
                                </div>
                            </div>
                            <div class="message-status-row">
                                ${statusBadges}
                            </div>
                            ${replyHtml}
                        </div>
                    `;
                } else {
                    // 系统消息或AI回复：左对齐，不同样式
                    messageItem.innerHTML = `
                        <div class="message-wrapper system-message-wrapper">
                            <div class="message-bubble system-bubble">
                                <div class="message-header">
                                    <span class="message-sender">${sender}</span>
                                    <span class="message-time">${time}</span>
                                </div>
                                <div class="message-content ${messageClass}">
                                    ${contentHtml}
                                </div>
                            </div>
                            <div class="message-status-row">
                                ${statusBadges}
                            </div>
                            ${replyHtml}
                        </div>
                    `;
                }

                // 始终添加到容器底部（因为消息已按时间升序排序）
                messagesContainer.appendChild(messageItem);
            });

            // 滚动到底部显示最新消息
            messagesContainer.scrollTop = messagesContainer.scrollHeight;
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
                const logLevel = detectLogLevel(log.message);
                logItem.className = `log-item ${getLogLevelClass(logLevel)}`;
                logItem.setAttribute('data-log-level', logLevel);

                const time = formatTime(log.timestamp);
                const level = log.level || logLevel.toUpperCase();
                const message = log.message;

                logItem.textContent = `${time} - ${level} - ${message}`;

                // 调试信息
                console.log('添加日志项:', {
                    message: message.substring(0, 50) + '...',
                    detectedLevel: logLevel,
                    className: logItem.className
                });

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

            // 应用日志过滤
            applyLogFilters();
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
        const response = await fetchAPI('/api/listeners', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                instance_id: instanceId,
                chat_name: chatName
            })
        });

        // 检查响应
        if (response.code === 0) {
            // 关闭模态框
            const modal = bootstrap.Modal.getInstance(document.getElementById('listenerModal'));
            modal.hide();

            // 显示成功通知
            showNotification(`监听对象 ${chatName} 添加成功`, 'success');

            // 重新加载监听对象列表
            loadListeners(true); // 强制刷新
        } else {
            showNotification(`添加监听对象失败: ${response.message}`, 'danger');
        }
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
        const response = await fetchAPI('/api/listeners', {
            method: 'DELETE',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                instance_id: currentListener.instance_id,
                chat_name: currentListener.chat_name
            })
        });

        // 检查响应
        if (response.code === 0) {
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
            loadListeners(true); // 强制刷新
        } else {
            showNotification(`删除监听对象失败: ${response.message}`, 'danger');
        }
    } catch (error) {
        console.error('删除监听对象失败:', error);
        showNotification(`删除监听对象失败: ${error.message}`, 'danger');
    }
}

/**
 * 打开日志抽屉
 */
function openLogsDrawer() {
    const logsDrawer = document.getElementById('logs-drawer');
    const overlay = document.getElementById('logs-drawer-overlay');

    // 显示遮罩层和抽屉
    overlay.classList.add('show');
    logsDrawer.classList.add('open');

    // 禁用页面滚动
    document.body.style.overflow = 'hidden';

    // 绑定过滤事件（确保在抽屉打开时绑定）
    setTimeout(() => {
        bindLogFilterEvents();
    }, 100);

    // 如果日志抽屉为空，则加载日志
    const logsList = document.getElementById('logs-list');
    if (logsList.children.length === 0 || logsList.querySelector('.spinner-border')) {
        loadLogs(true);
    }
}

/**
 * 关闭日志抽屉
 */
function closeLogsDrawer() {
    const logsDrawer = document.getElementById('logs-drawer');
    const overlay = document.getElementById('logs-drawer-overlay');

    // 隐藏遮罩层和抽屉
    overlay.classList.remove('show');
    logsDrawer.classList.remove('open');

    // 恢复页面滚动
    document.body.style.overflow = '';
}

/**
 * 检测日志级别
 * @param {string} message - 日志消息
 * @returns {string} - 日志级别
 */
function detectLogLevel(message) {
    const msg = message.toLowerCase();

    // 更精确的DEBUG检测
    if (msg.includes('debug') || msg.includes('调试') ||
        msg.includes('- debug -') || msg.includes('[debug]') ||
        msg.includes('debug:') || msg.includes('debug ')) {
        return 'debug';
    } else if (msg.includes('error') || msg.includes('错误') ||
               msg.includes('失败') || msg.includes('异常') ||
               msg.includes('- error -') || msg.includes('[error]') ||
               msg.includes('error:')) {
        return 'error';
    } else if (msg.includes('warning') || msg.includes('warn') ||
               msg.includes('警告') || msg.includes('注意') ||
               msg.includes('- warning -') || msg.includes('[warning]') ||
               msg.includes('warning:') || msg.includes('warn:')) {
        return 'warning';
    } else {
        return 'info';
    }
}

/**
 * 获取日志级别对应的CSS类
 * @param {string} level - 日志级别
 * @returns {string} - CSS类名
 */
function getLogLevelClass(level) {
    switch (level.toLowerCase()) {
        case 'debug':
            return 'log-debug';
        case 'info':
            return 'log-info';
        case 'warning':
        case 'warn':
            return 'log-warning';
        case 'error':
            return 'log-error';
        default:
            return 'log-info';
    }
}

/**
 * 应用日志过滤
 */
function applyLogFilters() {
    const hideDebug = document.getElementById('hide-debug-logs')?.checked ?? true;
    const showInfo = document.getElementById('show-info')?.checked ?? true;
    const showWarning = document.getElementById('show-warning')?.checked ?? true;
    const showError = document.getElementById('show-error')?.checked ?? true;

    const logItems = document.querySelectorAll('.log-item');

    console.log('应用日志过滤:', {
        hideDebug,
        showInfo,
        showWarning,
        showError,
        totalItems: logItems.length
    });

    let hiddenCount = 0;

    logItems.forEach(item => {
        const logLevel = item.getAttribute('data-log-level');
        let shouldShow = true;

        // 检查DEBUG过滤
        if (hideDebug && logLevel === 'debug') {
            shouldShow = false;
        }

        // 检查级别过滤
        if (shouldShow) {
            switch (logLevel) {
                case 'info':
                    shouldShow = showInfo;
                    break;
                case 'warning':
                    shouldShow = showWarning;
                    break;
                case 'error':
                    shouldShow = showError;
                    break;
                case 'debug':
                    // DEBUG已经在上面处理过了
                    break;
            }
        }

        // 应用过滤
        if (shouldShow) {
            item.classList.remove('hidden');
        } else {
            item.classList.add('hidden');
            hiddenCount++;
        }
    });

    console.log(`过滤完成: 隐藏了 ${hiddenCount} 条日志`);
}

/**
 * 绑定日志过滤事件
 */
function bindLogFilterEvents() {
    const hideDebugEl = document.getElementById('hide-debug-logs');
    const showInfoEl = document.getElementById('show-info');
    const showWarningEl = document.getElementById('show-warning');
    const showErrorEl = document.getElementById('show-error');

    console.log('绑定日志过滤事件:', {
        hideDebugEl: !!hideDebugEl,
        showInfoEl: !!showInfoEl,
        showWarningEl: !!showWarningEl,
        showErrorEl: !!showErrorEl
    });

    if (hideDebugEl && !hideDebugEl.hasAttribute('data-event-bound')) {
        hideDebugEl.addEventListener('change', function() {
            console.log('DEBUG过滤开关变化:', this.checked);
            applyLogFilters();
        });
        hideDebugEl.setAttribute('data-event-bound', 'true');
    }

    if (showInfoEl && !showInfoEl.hasAttribute('data-event-bound')) {
        showInfoEl.addEventListener('change', function() {
            console.log('INFO过滤开关变化:', this.checked);
            applyLogFilters();
        });
        showInfoEl.setAttribute('data-event-bound', 'true');
    }

    if (showWarningEl && !showWarningEl.hasAttribute('data-event-bound')) {
        showWarningEl.addEventListener('change', function() {
            console.log('WARNING过滤开关变化:', this.checked);
            applyLogFilters();
        });
        showWarningEl.setAttribute('data-event-bound', 'true');
    }

    if (showErrorEl && !showErrorEl.hasAttribute('data-event-bound')) {
        showErrorEl.addEventListener('change', function() {
            console.log('ERROR过滤开关变化:', this.checked);
            applyLogFilters();
        });
        showErrorEl.setAttribute('data-event-bound', 'true');
    }
}
