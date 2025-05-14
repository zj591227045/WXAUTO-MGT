/**
 * 实例管理页面JavaScript
 */

// 当前编辑的实例ID
let currentInstanceId = null;
// 当前要删除的实例ID
let deleteInstanceId = null;

document.addEventListener('DOMContentLoaded', function() {
    // 初始化页面
    initInstancesPage();

    // 绑定刷新按钮事件
    document.getElementById('refresh-instances').addEventListener('click', loadInstances);

    // 绑定添加实例按钮事件
    document.getElementById('add-instance').addEventListener('click', showAddInstanceModal);

    // 绑定保存实例按钮事件
    document.getElementById('save-instance').addEventListener('click', saveInstance);

    // 绑定确认删除按钮事件
    document.getElementById('confirm-delete').addEventListener('click', deleteInstance);
});

/**
 * 初始化实例管理页面
 */
function initInstancesPage() {
    // 加载实例列表
    loadInstances();

    // 设置轮询刷新实例列表
    pollingManager.addTask('instances', loadInstances, 30000);
}

/**
 * 刷新所有在线实例的资源信息
 */
async function refreshAllInstanceResources() {
    try {
        // 获取所有实例卡片
        const instanceCards = document.querySelectorAll('.instance-card');

        // 遍历实例卡片
        for (const card of instanceCards) {
            // 获取实例ID
            const instanceId = card.id.replace('instance-card-', '');

            // 获取实例状态
            const statusElement = card.querySelector('.instance-status');
            if (statusElement && statusElement.classList.contains('status-online')) {
                // 如果实例在线，刷新资源
                await refreshInstanceResources(instanceId, true);

                // 添加延迟，避免同时发送太多请求
                await new Promise(resolve => setTimeout(resolve, 500));
            }
        }
    } catch (error) {
        console.error('刷新所有实例资源失败:', error);
    }
}

/**
 * 加载实例列表
 */
async function loadInstances() {
    try {
        const instancesContainer = document.getElementById('instances-container');

        // 显示加载中
        instancesContainer.innerHTML = `
            <div class="col-12 text-center py-5">
                <div class="spinner-border text-primary" role="status">
                    <span class="visually-hidden">加载中...</span>
                </div>
                <p class="mt-2">加载实例列表...</p>
            </div>
        `;

        // 获取实例列表
        const instances = await fetchAPI('/api/instances');

        // 清空容器
        instancesContainer.innerHTML = '';

        if (instances.length === 0) {
            instancesContainer.innerHTML = `
                <div class="col-12 text-center py-5">
                    <p class="text-muted">暂无实例，请点击"添加实例"按钮创建</p>
                </div>
            `;
            return;
        }

        // 添加实例卡片
        instances.forEach(instance => {
            const instanceCard = createInstanceCard(instance);
            instancesContainer.appendChild(instanceCard);
        });
    } catch (error) {
        console.error('加载实例列表失败:', error);
        document.getElementById('instances-container').innerHTML = `
            <div class="col-12 text-center py-5">
                <p class="text-danger">加载实例列表失败，请重试</p>
                <button class="btn btn-outline-primary mt-3" onclick="loadInstances()">
                    <i class="fas fa-sync-alt"></i> 重试
                </button>
            </div>
        `;
    }
}

/**
 * 创建实例卡片
 * @param {Object} instance - 实例数据
 * @returns {HTMLElement} - 实例卡片元素
 */
function createInstanceCard(instance) {
    // 创建卡片容器
    const cardCol = document.createElement('div');
    cardCol.className = 'col-md-6 col-lg-4';

    // 获取状态样式
    let statusClass = 'status-offline';
    if (instance.enabled === 0) {
        statusClass = 'status-disabled';
    } else if (instance.status === 'ONLINE') {
        statusClass = 'status-online';
    } else if (instance.status === 'ERROR') {
        statusClass = 'status-error';
    }

    // 获取状态文本
    let statusText = '离线';
    if (instance.enabled === 0) {
        statusText = '已禁用';
    } else if (instance.status === 'ONLINE') {
        statusText = '已连接';
    } else if (instance.status === 'ERROR') {
        statusText = '错误';
    }

    // 创建卡片HTML
    cardCol.innerHTML = `
        <div class="card instance-card" id="instance-card-${instance.instance_id}">
            <div class="instance-header">
                <h5 class="instance-title">${instance.name}</h5>
                <span class="instance-status ${statusClass}">${statusText}</span>
            </div>
            <div class="metric-container">
                <!-- 第一行：消息总数、监听对象 -->
                <div class="metric-box">
                    <div class="metric-value">${instance.messages_count}</div>
                    <div class="metric-label">消息总数</div>
                </div>
                <div class="metric-box">
                    <div class="metric-value">${instance.listeners_count}</div>
                    <div class="metric-label">监听对象</div>
                </div>

                <!-- 第二行：CPU、运行时间 -->
                <div class="metric-box">
                    <div class="metric-value" id="cpu-${instance.instance_id}">${instance.cpu_percent}%</div>
                    <div class="metric-label">CPU</div>
                </div>
                <div class="metric-box">
                    <div class="metric-value" id="runtime-${instance.instance_id}">${instance.runtime}</div>
                    <div class="metric-label">运行时间</div>
                </div>

                <!-- 第三行：内存、内存使用 -->
                <div class="metric-box">
                    <div class="metric-value" id="memory-percent-${instance.instance_id}">${instance.memory_percent}%</div>
                    <div class="metric-label">内存</div>
                </div>
                <div class="metric-box">
                    <div class="metric-value" id="memory-usage-${instance.instance_id}">${instance.memory_used}/${instance.memory_total}GB</div>
                    <div class="metric-label">内存使用</div>
                </div>
            </div>
            <div class="p-3">
                <p class="mb-1"><strong>ID:</strong> ${instance.instance_id}</p>
                <p class="mb-1"><strong>API地址:</strong> ${instance.base_url}</p>
            </div>
            <div class="instance-actions">
                <button class="btn btn-sm btn-outline-primary edit-instance" data-instance-id="${instance.instance_id}">
                    <i class="fas fa-edit"></i> 编辑
                </button>
                <button class="btn btn-sm btn-outline-danger delete-instance" data-instance-id="${instance.instance_id}" data-instance-name="${instance.name}">
                    <i class="fas fa-trash-alt"></i> 删除
                </button>
                ${instance.enabled === 1 ?
                    `<button class="btn btn-sm btn-outline-secondary disable-instance" data-instance-id="${instance.instance_id}">
                        <i class="fas fa-ban"></i> 禁用
                    </button>` :
                    `<button class="btn btn-sm btn-outline-success enable-instance" data-instance-id="${instance.instance_id}">
                        <i class="fas fa-check"></i> 启用
                    </button>`
                }
                <button class="btn btn-sm btn-outline-info refresh-resources" data-instance-id="${instance.instance_id}">
                    <i class="fas fa-sync-alt"></i> 刷新资源
                </button>
            </div>
        </div>
    `;

    // 绑定按钮事件
    cardCol.querySelector('.edit-instance').addEventListener('click', function() {
        const instanceId = this.getAttribute('data-instance-id');
        showEditInstanceModal(instanceId);
    });

    cardCol.querySelector('.delete-instance').addEventListener('click', function() {
        const instanceId = this.getAttribute('data-instance-id');
        const instanceName = this.getAttribute('data-instance-name');
        showDeleteConfirmModal(instanceId, instanceName);
    });

    if (instance.enabled === 1) {
        cardCol.querySelector('.disable-instance').addEventListener('click', function() {
            const instanceId = this.getAttribute('data-instance-id');
            disableInstance(instanceId);
        });
    } else {
        cardCol.querySelector('.enable-instance').addEventListener('click', function() {
            const instanceId = this.getAttribute('data-instance-id');
            enableInstance(instanceId);
        });
    }

    // 绑定刷新资源按钮事件
    cardCol.querySelector('.refresh-resources').addEventListener('click', function() {
        const instanceId = this.getAttribute('data-instance-id');
        refreshInstanceResources(instanceId);
    });

    return cardCol;
}

/**
 * 显示添加实例模态框
 */
function showAddInstanceModal() {
    // 重置表单
    document.getElementById('instanceForm').reset();
    document.getElementById('instance-id').value = '';

    // 设置标题
    document.getElementById('instanceModalTitle').textContent = '添加实例';

    // 重置当前编辑的实例ID
    currentInstanceId = null;

    // 显示模态框
    const modal = new bootstrap.Modal(document.getElementById('instanceModal'));
    modal.show();
}

/**
 * 显示编辑实例模态框
 * @param {string} instanceId - 实例ID
 */
async function showEditInstanceModal(instanceId) {
    try {
        // 获取实例详情
        const instances = await fetchAPI('/api/instances');
        const instance = instances.find(inst => inst.instance_id === instanceId);

        if (!instance) {
            showNotification('未找到实例', 'danger');
            return;
        }

        // 填充表单
        document.getElementById('instance-id').value = instance.instance_id;
        document.getElementById('instance-name').value = instance.name;
        document.getElementById('instance-base-url').value = instance.base_url;
        document.getElementById('instance-api-key').value = instance.api_key || '';
        document.getElementById('instance-enabled').checked = instance.enabled === 1;

        // 设置标题
        document.getElementById('instanceModalTitle').textContent = '编辑实例';

        // 设置当前编辑的实例ID
        currentInstanceId = instanceId;

        // 显示模态框
        const modal = new bootstrap.Modal(document.getElementById('instanceModal'));
        modal.show();
    } catch (error) {
        console.error('获取实例详情失败:', error);
        showNotification('获取实例详情失败', 'danger');
    }
}

/**
 * 保存实例
 */
async function saveInstance() {
    // 获取表单数据
    const instanceId = document.getElementById('instance-id').value;
    const name = document.getElementById('instance-name').value;
    const baseUrl = document.getElementById('instance-base-url').value;
    const apiKey = document.getElementById('instance-api-key').value;
    const enabled = document.getElementById('instance-enabled').checked;

    // 验证表单
    if (!name || !baseUrl) {
        showNotification('请填写必填字段', 'warning');
        return;
    }

    try {
        // 构建请求数据
        const data = {
            name,
            base_url: baseUrl,
            api_key: apiKey,
            enabled: enabled ? 1 : 0
        };

        // 发送请求
        let response;
        if (currentInstanceId) {
            // 更新实例
            response = await fetchAPI(`/api/instances/${currentInstanceId}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            });
            showNotification(`实例 ${name} 更新成功`, 'success');
        } else {
            // 添加实例
            response = await fetchAPI('/api/instances', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            });
            showNotification(`实例 ${name} 添加成功`, 'success');
        }

        // 关闭模态框
        const modal = bootstrap.Modal.getInstance(document.getElementById('instanceModal'));
        modal.hide();

        // 重新加载实例列表
        loadInstances();
    } catch (error) {
        console.error('保存实例失败:', error);
        showNotification(`保存实例失败: ${error.message}`, 'danger');
    }
}

/**
 * 显示删除确认模态框
 * @param {string} instanceId - 实例ID
 * @param {string} instanceName - 实例名称
 */
function showDeleteConfirmModal(instanceId, instanceName) {
    // 设置实例名称
    document.getElementById('delete-instance-name').textContent = instanceName;

    // 设置当前要删除的实例ID
    deleteInstanceId = instanceId;

    // 显示模态框
    const modal = new bootstrap.Modal(document.getElementById('deleteConfirmModal'));
    modal.show();
}

/**
 * 删除实例
 */
async function deleteInstance() {
    if (!deleteInstanceId) {
        showNotification('未指定要删除的实例', 'danger');
        return;
    }

    try {
        // 发送删除请求
        await fetchAPI(`/api/instances/${deleteInstanceId}`, {
            method: 'DELETE'
        });

        // 关闭模态框
        const modal = bootstrap.Modal.getInstance(document.getElementById('deleteConfirmModal'));
        modal.hide();

        // 显示成功通知
        showNotification('实例删除成功', 'success');

        // 重新加载实例列表
        loadInstances();
    } catch (error) {
        console.error('删除实例失败:', error);
        showNotification(`删除实例失败: ${error.message}`, 'danger');
    }
}

/**
 * 启用实例
 * @param {string} instanceId - 实例ID
 */
async function enableInstance(instanceId) {
    try {
        // 发送启用请求
        await fetchAPI(`/api/instances/${instanceId}/enable`, {
            method: 'POST'
        });

        // 显示成功通知
        showNotification('实例已启用', 'success');

        // 重新加载实例列表
        loadInstances();
    } catch (error) {
        console.error('启用实例失败:', error);
        showNotification(`启用实例失败: ${error.message}`, 'danger');
    }
}

/**
 * 禁用实例
 * @param {string} instanceId - 实例ID
 */
async function disableInstance(instanceId) {
    try {
        // 发送禁用请求
        await fetchAPI(`/api/instances/${instanceId}/disable`, {
            method: 'POST'
        });

        // 显示成功通知
        showNotification('实例已禁用', 'success');

        // 重新加载实例列表
        loadInstances();
    } catch (error) {
        console.error('禁用实例失败:', error);
        showNotification(`禁用实例失败: ${error.message}`, 'danger');
    }
}

/**
 * 刷新实例资源信息
 * @param {string} instanceId - 实例ID
 * @param {boolean} silent - 是否静默刷新（不显示通知）
 */
async function refreshInstanceResources(instanceId, silent = false) {
    try {
        // 获取按钮元素并添加加载状态
        const button = document.querySelector(`.refresh-resources[data-instance-id="${instanceId}"]`);
        if (button) {
            button.disabled = true;
            button.innerHTML = '<i class="fas fa-spinner fa-spin"></i> 刷新中...';
        }

        // 发送请求获取资源信息
        const response = await fetchAPI(`/api/system/resources?instance_id=${instanceId}`);

        // 检查响应
        if (response && response.data) {
            const data = response.data;

            // 更新CPU使用率
            const cpuElement = document.getElementById(`cpu-${instanceId}`);
            if (cpuElement && data.cpu && data.cpu.usage_percent !== undefined) {
                cpuElement.textContent = `${data.cpu.usage_percent.toFixed(1)}%`;
            }

            // 更新内存百分比
            const memoryPercentElement = document.getElementById(`memory-percent-${instanceId}`);
            if (memoryPercentElement && data.memory && data.memory.usage_percent !== undefined) {
                memoryPercentElement.textContent = `${data.memory.usage_percent.toFixed(1)}%`;
            }

            // 更新内存使用情况
            const memoryUsageElement = document.getElementById(`memory-usage-${instanceId}`);
            if (memoryUsageElement && data.memory) {
                // 注意：后端已经将 MB 转换为 GB 并保留一位小数
                const used = data.memory.used;
                const total = data.memory.total;
                // 直接显示数值，不需要再格式化小数位
                memoryUsageElement.textContent = `${used}/${total}GB`;
            }

            // 更新运行时间
            const runtimeElement = document.getElementById(`runtime-${instanceId}`);
            if (runtimeElement) {
                if (data.uptime) {
                    // 如果有uptime字段，优先使用
                    if (typeof data.uptime === 'number') {
                        // 如果是数字，需要格式化
                        const uptime_seconds = data.uptime;
                        const days = Math.floor(uptime_seconds / 86400);
                        const hours = Math.floor((uptime_seconds % 86400) / 3600);
                        const minutes = Math.floor((uptime_seconds % 3600) / 60);

                        if (days > 0) {
                            runtimeElement.textContent = `${days}天${hours}小时${minutes}分钟`;
                        } else if (hours > 0) {
                            runtimeElement.textContent = `${hours}小时${minutes}分钟`;
                        } else {
                            runtimeElement.textContent = `${minutes}分钟`;
                        }
                    } else {
                        // 如果是字符串，直接使用
                        runtimeElement.textContent = data.uptime;
                    }
                } else if (data.runtime) {
                    // 否则使用runtime字段
                    runtimeElement.textContent = data.runtime;
                }
            }

            // 显示成功通知
            if (!silent) {
                showNotification(`实例 ${instanceId} 资源信息已更新`, 'success');
            }
        } else {
            // 显示错误通知
            if (!silent) {
                showNotification('获取资源信息失败：响应格式不正确', 'warning');
            }
        }
    } catch (error) {
        console.error('刷新实例资源失败:', error);
        if (!silent) {
            showNotification(`刷新资源失败: ${error.message}`, 'danger');
        }
    } finally {
        // 恢复按钮状态
        const button = document.querySelector(`.refresh-resources[data-instance-id="${instanceId}"]`);
        if (button) {
            button.disabled = false;
            button.innerHTML = '<i class="fas fa-sync-alt"></i> 刷新资源';
        }
    }
}
