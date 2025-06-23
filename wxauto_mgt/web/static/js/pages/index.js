/**
 * 首页（仪表盘）JavaScript
 */

/**
 * 根据日志级别获取CSS类
 * @param {string} level - 日志级别
 * @returns {string} CSS类
 */
function getLogLevelClass(level) {
    switch (level.toUpperCase()) {
        case 'ERROR':
            return 'log-error';
        case 'WARNING':
            return 'log-warning';
        case 'INFO':
            return 'log-info';
        default:
            return '';
    }
}

/**
 * 格式化日期时间
 * @param {number} timestamp - 时间戳（秒或毫秒）
 * @returns {string} 格式化后的日期时间
 */
function formatDateTime(timestamp) {
    // 确保时间戳是毫秒
    if (timestamp < 10000000000) {
        timestamp *= 1000; // 转换秒为毫秒
    }

    const date = new Date(timestamp);

    // 格式化日期和时间
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    const hours = String(date.getHours()).padStart(2, '0');
    const minutes = String(date.getMinutes()).padStart(2, '0');
    const seconds = String(date.getSeconds()).padStart(2, '0');

    return `${year}-${month}-${day} ${hours}:${minutes}:${seconds}`;
}

document.addEventListener('DOMContentLoaded', function() {
    // 测试API连接
    testApiConnection();

    // 初始化页面
    initDashboard();

    // 绑定刷新按钮事件
    document.getElementById('refresh-messages').addEventListener('click', function() {
        loadRecentMessages();
    });

    document.getElementById('refresh-logs').addEventListener('click', function() {
        loadSystemLogs();
    });
});

/**
 * 测试API连接
 */
async function testApiConnection() {
    try {
        const response = await fetch('/api/test');
        if (!response.ok) {
            const errorText = await response.text();
            console.error(`API测试失败: ${response.status} ${response.statusText} - ${errorText}`);
            showNotification(`API测试失败: ${response.status} ${response.statusText}`, 'danger');
            return;
        }

        const data = await response.json();
        console.log('API测试成功:', data);
    } catch (error) {
        console.error('API测试错误:', error);
        showNotification(`API测试错误: ${error.message}`, 'danger');
    }
}

/**
 * 初始化仪表盘
 */
function initDashboard() {
    // 加载系统状态
    loadSystemStatus();

    // 加载最近消息
    loadRecentMessages();

    // 加载系统日志
    loadSystemLogs();

    // 设置轮询刷新
    pollingManager.addTask('systemStatus', loadSystemStatus, 5000);
    pollingManager.addTask('recentMessages', loadRecentMessages, 10000);
    pollingManager.addTask('systemLogs', loadSystemLogs, 10000);
}

/**
 * 加载系统状态
 */
async function loadSystemStatus() {
    try {
        const data = await fetchAPI('/api/system/status');

        // 更新系统状态
        document.getElementById('system-status').textContent = data.system_status.status;
        document.getElementById('system-uptime').textContent = data.system_status.uptime;
        document.getElementById('system-version').textContent = data.system_status.version;
        // 添加软件更新状态
        document.getElementById('system-update').textContent = '最新';

        // 更新实例状态
        document.getElementById('instance-online').textContent = data.instance_status.online;
        document.getElementById('instance-offline').textContent = data.instance_status.offline;
        document.getElementById('instance-error').textContent = data.instance_status.error;
        // 添加最近活跃实例
        if (data.instance_status.active_instance) {
            document.getElementById('instance-active').textContent = data.instance_status.active_instance;
        } else {
            document.getElementById('instance-active').textContent = '无';
        }

        // 更新消息处理
        document.getElementById('message-today').textContent = data.message_processing.today_messages;
        document.getElementById('message-success-rate').textContent = data.message_processing.success_rate + '%';
        document.getElementById('message-total').textContent = data.message_processing.total_messages;
        // 添加监听对象数量
        document.getElementById('message-listeners').textContent = data.message_processing.listeners_count || '0';

        // 更新系统资源
        // CPU 使用率
        const cpuPercent = data.system_resources.cpu_percent;
        document.getElementById('resource-cpu-text').textContent = cpuPercent.toFixed(1) + '%';
        const cpuBar = document.getElementById('resource-cpu-bar');
        cpuBar.style.width = cpuPercent + '%';

        // 内存使用率
        const memoryUsedGB = data.system_resources.memory_used_gb.toFixed(1);
        const memoryTotalGB = data.system_resources.memory_total_gb.toFixed(1);
        const memoryPercent = data.system_resources.memory_percent;
        document.getElementById('resource-memory-text').textContent =
            `${memoryUsedGB} GB / ${memoryTotalGB} GB`;
        const memoryBar = document.getElementById('resource-memory-bar');
        memoryBar.style.width = memoryPercent + '%';

        // 磁盘使用率
        const diskUsedGB = data.system_resources.disk_used_gb.toFixed(1);
        const diskTotalGB = data.system_resources.disk_total_gb.toFixed(1);
        const diskPercent = data.system_resources.disk_percent;
        document.getElementById('resource-disk-text').textContent =
            `${diskUsedGB} GB / ${diskTotalGB} GB`;
        const diskBar = document.getElementById('resource-disk-bar');
        diskBar.style.width = diskPercent + '%';
    } catch (error) {
        console.error('加载系统状态失败:', error);
    }
}

/**
 * 加载最近消息
 */
async function loadRecentMessages() {
    try {
        const messagesContainer = document.getElementById('recent-messages');

        // 获取最近消息
        const messages = await fetchAPI('/api/messages?limit=10');

        // 清空容器
        messagesContainer.innerHTML = '';

        if (messages.length === 0) {
            messagesContainer.innerHTML = '<div class="text-center py-3">暂无消息</div>';
            return;
        }

        // 添加消息
        messages.forEach(message => {
            const messageTime = formatDateTime(message.create_time);
            const messageType = message.message_type || 'text';
            const sender = message.sender || '系统';
            const chatName = message.chat_name || '未知';

            let content = message.content;
            if (content && content.length > 50) {
                content = content.substring(0, 50) + '...';
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

            // 使用统一的简洁列表样式，在消息后面添加状态图例
            const messageElement = document.createElement('div');
            messageElement.className = 'log-entry';
            messageElement.innerHTML = `
                <div class="d-flex justify-content-between align-items-start">
                    <div class="flex-grow-1">
                        <span class="text-muted">${messageTime}</span>
                        <span class="badge bg-primary me-1">${chatName}</span>
                        <span class="fw-bold">${sender}:</span>
                        <span>${content || '(无内容)'}</span>
                    </div>
                    <div class="message-status-badges ms-2">
                        ${statusBadges}
                    </div>
                </div>
            `;

            messagesContainer.appendChild(messageElement);
        });
    } catch (error) {
        console.error('加载最近消息失败:', error);
        document.getElementById('recent-messages').innerHTML =
            '<div class="text-center py-3 text-danger">加载失败，请重试</div>';
    }
}

/**
 * 加载系统日志
 */
async function loadSystemLogs() {
    try {
        const logsContainer = document.getElementById('system-logs');

        // 获取系统日志
        const logs = await fetchAPI('/api/logs?limit=20');

        // 清空容器
        logsContainer.innerHTML = '';

        if (logs.length === 0) {
            logsContainer.innerHTML = '<div class="text-center py-3">暂无日志</div>';
            return;
        }

        // 添加日志
        logs.forEach(log => {
            const logTime = formatDateTime(log.timestamp);
            const logLevel = log.level;
            const logMessage = log.message;

            const logElement = document.createElement('div');
            logElement.className = `log-entry ${getLogLevelClass(logLevel)}`;
            logElement.innerHTML = `
                <span class="text-muted">${logTime}</span>
                <span class="badge bg-secondary">${logLevel}</span>
                <span>${logMessage}</span>
            `;

            logsContainer.appendChild(logElement);
        });
    } catch (error) {
        console.error('加载系统日志失败:', error);
        document.getElementById('system-logs').innerHTML =
            '<div class="text-center py-3 text-danger">加载失败，请重试</div>';
    }
}
