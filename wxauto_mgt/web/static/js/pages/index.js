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
        showNotification(`API测试成功: ${data.message}`, 'success');
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

        // 更新实例状态
        document.getElementById('instance-online').textContent = data.instance_status.online;
        document.getElementById('instance-offline').textContent = data.instance_status.offline;
        document.getElementById('instance-error').textContent = data.instance_status.error;

        // 更新消息处理
        document.getElementById('message-today').textContent = data.message_processing.today_messages;
        document.getElementById('message-success-rate').textContent = data.message_processing.success_rate + '%';
        document.getElementById('message-pending').textContent = data.message_processing.pending;

        // 更新系统资源
        document.getElementById('resource-cpu').textContent = data.system_resources.cpu_percent + '%';
        document.getElementById('resource-memory').textContent =
            `${data.system_resources.memory_used_gb} GB / ${data.system_resources.memory_total_gb} GB (${data.system_resources.memory_percent}%)`;
        document.getElementById('resource-disk').textContent =
            `${data.system_resources.disk_used_gb} GB / ${data.system_resources.disk_total_gb} GB (${data.system_resources.disk_percent}%)`;
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

            const messageElement = document.createElement('div');
            messageElement.className = 'log-entry';
            messageElement.innerHTML = `
                <span class="text-muted">${messageTime}</span>
                <span class="badge bg-primary">${chatName}</span>
                <span class="fw-bold">${sender}:</span>
                <span>${content || '(无内容)'}</span>
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
