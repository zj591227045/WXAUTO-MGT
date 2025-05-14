/**
 * 轮询刷新实现
 */

class PollingManager {
    constructor() {
        this.pollingTasks = {};
        this.defaultInterval = 5000; // 默认5秒
    }
    
    /**
     * 添加轮询任务
     * @param {string} taskId - 任务ID
     * @param {Function} callback - 回调函数
     * @param {number} interval - 轮询间隔（毫秒）
     */
    addTask(taskId, callback, interval = this.defaultInterval) {
        // 如果任务已存在，先停止
        this.stopTask(taskId);
        
        // 创建新任务
        const task = {
            callback,
            interval,
            timerId: setInterval(callback, interval)
        };
        
        this.pollingTasks[taskId] = task;
        
        // 立即执行一次
        callback();
        
        return taskId;
    }
    
    /**
     * 停止轮询任务
     * @param {string} taskId - 任务ID
     */
    stopTask(taskId) {
        if (this.pollingTasks[taskId]) {
            clearInterval(this.pollingTasks[taskId].timerId);
            delete this.pollingTasks[taskId];
        }
    }
    
    /**
     * 停止所有轮询任务
     */
    stopAllTasks() {
        for (const taskId in this.pollingTasks) {
            this.stopTask(taskId);
        }
    }
    
    /**
     * 修改轮询间隔
     * @param {string} taskId - 任务ID
     * @param {number} interval - 新的轮询间隔（毫秒）
     */
    updateInterval(taskId, interval) {
        if (this.pollingTasks[taskId]) {
            const task = this.pollingTasks[taskId];
            this.stopTask(taskId);
            this.addTask(taskId, task.callback, interval);
        }
    }
}

// 创建全局轮询管理器实例
const pollingManager = new PollingManager();
