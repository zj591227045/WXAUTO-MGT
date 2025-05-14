/**
 * 通用JavaScript函数
 */

// 格式化日期时间
function formatDateTime(timestamp) {
    const date = new Date(timestamp * 1000);
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    const hours = String(date.getHours()).padStart(2, '0');
    const minutes = String(date.getMinutes()).padStart(2, '0');
    const seconds = String(date.getSeconds()).padStart(2, '0');

    return `${year}-${month}-${day} ${hours}:${minutes}:${seconds}`;
}

// 格式化时间（只有时分秒）
function formatTime(timestamp) {
    const date = new Date(timestamp * 1000);
    const hours = String(date.getHours()).padStart(2, '0');
    const minutes = String(date.getMinutes()).padStart(2, '0');
    const seconds = String(date.getSeconds()).padStart(2, '0');

    return `${hours}:${minutes}:${seconds}`;
}

// 显示通知
function showNotification(message, type = 'info') {
    // 创建通知元素
    const notification = document.createElement('div');
    notification.className = `alert alert-${type} alert-dismissible fade show notification`;
    notification.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
    `;

    // 添加到页面
    const container = document.querySelector('.container-fluid');
    if (container) {
        container.insertBefore(notification, container.firstChild);
    } else {
        // 如果找不到容器，添加到body
        document.body.appendChild(notification);
    }

    // 自动关闭
    setTimeout(() => {
        notification.classList.remove('show');
        setTimeout(() => notification.remove(), 300);
    }, 5000);
}

// 确保函数在全局范围内可用
window.showNotification = showNotification;

// 发送API请求
async function fetchAPI(url, options = {}) {
    try {
        console.log(`发送API请求: ${url}`);

        // 构建完整URL
        const baseUrl = window.location.origin;
        const fullUrl = url.startsWith('http') ? url : `${baseUrl}${url}`;

        // 发送请求
        const response = await fetch(fullUrl, options);

        if (!response.ok) {
            const errorText = await response.text();
            console.error(`API请求失败: ${response.status} ${response.statusText}`);
            console.error(`响应内容: ${errorText}`);
            throw new Error(`API请求失败: ${response.status} ${response.statusText} - ${errorText}`);
        }

        const contentType = response.headers.get('content-type');
        if (!contentType || !contentType.includes('application/json')) {
            const text = await response.text();
            console.error(`API响应不是JSON格式: ${contentType}`);
            console.error(`响应内容: ${text}`);
            throw new Error(`API响应不是JSON格式: ${contentType}`);
        }

        const data = await response.json();
        console.log(`API响应:`, data);
        return data;
    } catch (error) {
        console.error('API请求错误:', error);
        showNotification(`API请求错误: ${error.message}`, 'danger');
        throw error;
    }
}

// 确保函数在全局范围内可用
window.fetchAPI = fetchAPI;

// 获取日志级别对应的CSS类
function getLogLevelClass(level) {
    switch (level.toUpperCase()) {
        case 'DEBUG':
            return 'text-secondary';
        case 'INFO':
            return 'log-info';
        case 'WARNING':
            return 'log-warning';
        case 'ERROR':
            return 'log-error';
        default:
            return '';
    }
}

// 格式化文件大小
function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';

    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));

    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

// 防抖函数
function debounce(func, wait) {
    let timeout;
    return function(...args) {
        const context = this;
        clearTimeout(timeout);
        timeout = setTimeout(() => func.apply(context, args), wait);
    };
}
