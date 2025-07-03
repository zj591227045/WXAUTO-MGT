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
async function initInstancesPage() {
    // 加载实例列表
    await loadInstances();

    // 延迟2秒后刷新所有在线实例的资源信息
    setTimeout(async () => {
        console.log('开始自动刷新实例资源信息...');
        await refreshAllInstanceResources();
    }, 2000);

    // 注释掉定时刷新，避免覆盖手动刷新的正确信息
    // pollingManager.addTask('instances', loadInstances, 30000);
}

/**
 * 刷新所有在线实例的资源信息
 */
async function refreshAllInstanceResources() {
    try {
        console.log('开始刷新所有实例资源信息...');

        // 获取所有实例卡片
        const instanceCards = document.querySelectorAll('.instance-card');
        console.log(`找到 ${instanceCards.length} 个实例卡片`);

        // 遍历实例卡片
        for (const card of instanceCards) {
            // 获取实例ID
            const instanceId = card.id.replace('instance-card-', '');
            console.log(`处理实例: ${instanceId}`);

            // 获取实例状态
            const statusElement = card.querySelector('.instance-status');
            const isOnline = statusElement && statusElement.classList.contains('status-online');
            console.log(`实例 ${instanceId} 在线状态: ${isOnline}`);

            if (isOnline) {
                // 如果实例在线，刷新资源
                console.log(`刷新实例 ${instanceId} 的资源信息...`);
                await refreshInstanceResources(instanceId, true);

                // 添加延迟，避免同时发送太多请求
                await new Promise(resolve => setTimeout(resolve, 1000));
            } else {
                // 即使离线也尝试刷新一次，可能状态不准确
                console.log(`实例 ${instanceId} 显示离线，但仍尝试刷新资源...`);
                await refreshInstanceResources(instanceId, true);
                await new Promise(resolve => setTimeout(resolve, 1000));
            }
        }

        console.log('所有实例资源信息刷新完成');
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

        // 调试信息：打印实例数据
        console.log('获取到的实例列表:', instances);
        instances.forEach((instance, index) => {
            console.log(`实例 ${index + 1}:`, {
                instance_id: instance.instance_id,
                name: instance.name,
                messages_count: instance.messages_count,
                listeners_count: instance.listeners_count
            });
        });

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
    cardCol.className = 'col-sm-6 col-md-4 col-lg-3 col-xl-3';

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
                    <div class="metric-value" id="cpu-${instance.instance_id}">加载中...</div>
                    <div class="metric-label">CPU</div>
                </div>
                <div class="metric-box">
                    <div class="metric-value" id="runtime-${instance.instance_id}">加载中...</div>
                    <div class="metric-label">运行时间</div>
                </div>

                <!-- 第三行：内存、内存使用 -->
                <div class="metric-box">
                    <div class="metric-value" id="memory-percent-${instance.instance_id}">加载中...</div>
                    <div class="metric-label">内存</div>
                </div>
                <div class="metric-box">
                    <div class="metric-value" id="memory-usage-${instance.instance_id}">加载中...</div>
                    <div class="metric-label">内存使用</div>
                </div>
            </div>
            <div class="instance-info">
                <p><strong>ID:</strong> ${instance.instance_id}</p>
                <p><strong>API地址:</strong> ${instance.base_url}</p>
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
                <button class="btn btn-sm btn-outline-success auto-login" data-instance-id="${instance.instance_id}">
                    <i class="fas fa-sign-in-alt"></i> 自动登录
                </button>
                <button class="btn btn-sm btn-outline-primary qrcode-login" data-instance-id="${instance.instance_id}">
                    <i class="fas fa-qrcode"></i> 登录码
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

    // 绑定自动登录按钮事件
    cardCol.querySelector('.auto-login').addEventListener('click', function() {
        const instanceId = this.getAttribute('data-instance-id');
        autoLogin(instanceId);
    });

    // 绑定二维码登录按钮事件
    cardCol.querySelector('.qrcode-login').addEventListener('click', function() {
        const instanceId = this.getAttribute('data-instance-id');
        showQRCodeLogin(instanceId);
    });

    return cardCol;
}

/**
 * 自动登录实例
 * @param {string} instanceId - 实例ID
 */
async function autoLogin(instanceId) {
    try {
        // 获取实例信息
        const instances = await fetchAPI('/api/instances');
        const instance = instances.find(inst => inst.instance_id === instanceId);

        if (!instance) {
            showNotification('未找到实例', 'danger');
            return;
        }

        // 显示进度提示
        showNotification(`正在为实例 ${instance.name} 执行自动登录...`, 'info');

        // 调用代理API
        const data = await fetchAPI(`/api/instances/${instanceId}/auto-login`, {
            method: 'POST'
        });

        if (data.code === 0) {
            const loginResult = data.data?.login_result;
            if (loginResult) {
                showNotification(`实例 ${instance.name} 自动登录成功`, 'success');

                // 开始微信初始化循环
                await startWeChatInitializationLoop(instanceId, instance);
            } else {
                showNotification(`实例 ${instance.name} 自动登录失败`, 'warning');
            }
        } else {
            showNotification(`自动登录失败: ${data.message || '未知错误'}`, 'danger');
        }

    } catch (error) {
        console.error('自动登录失败:', error);
        showNotification(`自动登录失败: ${error.message}`, 'danger');
    }
}

/**
 * 显示二维码登录
 * @param {string} instanceId - 实例ID
 */
async function showQRCodeLogin(instanceId) {
    try {
        // 获取实例信息
        const instances = await fetchAPI('/api/instances');
        const instance = instances.find(inst => inst.instance_id === instanceId);

        if (!instance) {
            showNotification('未找到实例', 'danger');
            return;
        }

        // 显示进度提示
        showNotification(`正在获取实例 ${instance.name} 的登录二维码...`, 'info');

        // 调用代理API
        const data = await fetchAPI(`/api/instances/${instanceId}/qrcode`, {
            method: 'POST'
        });

        if (data.code === 0) {
            const qrcodeDataUrl = data.data?.qrcode_data_url;
            if (qrcodeDataUrl) {
                showQRCodeModal(instanceId, instance, qrcodeDataUrl);
            } else {
                showNotification(`获取二维码失败: 无二维码数据`, 'danger');
            }
        } else {
            showNotification(`获取二维码失败: ${data.message || '未知错误'}`, 'danger');
        }

    } catch (error) {
        console.error('获取二维码失败:', error);
        showNotification(`获取二维码失败: ${error.message}`, 'danger');
    }
}

/**
 * 显示二维码模态框
 * @param {string} instanceId - 实例ID
 * @param {Object} instance - 实例信息
 * @param {string} qrcodeDataUrl - 二维码数据URL
 */
function showQRCodeModal(instanceId, instance, qrcodeDataUrl) {
    // 创建模态框HTML
    const modalHtml = `
        <div class="modal fade" id="qrcodeModal" tabindex="-1" aria-labelledby="qrcodeModalLabel" aria-hidden="true">
            <div class="modal-dialog modal-dialog-centered">
                <div class="modal-content">
                    <div class="modal-header">
                        <h5 class="modal-title" id="qrcodeModalLabel">微信登录二维码 - ${instance.name}</h5>
                        <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                    </div>
                    <div class="modal-body text-center">
                        <p class="mb-3">请使用微信扫描二维码登录</p>
                        <img src="${qrcodeDataUrl}" alt="登录二维码" class="img-fluid" style="max-width: 250px; border: 1px solid #ccc;">
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">关闭</button>
                        <button type="button" class="btn btn-success" id="loginSuccessBtn">登录成功</button>
                    </div>
                </div>
            </div>
        </div>
    `;

    // 移除已存在的模态框
    const existingModal = document.getElementById('qrcodeModal');
    if (existingModal) {
        existingModal.remove();
    }

    // 添加模态框到页面
    document.body.insertAdjacentHTML('beforeend', modalHtml);

    // 获取模态框元素
    const modalElement = document.getElementById('qrcodeModal');
    const modal = new bootstrap.Modal(modalElement);

    // 绑定登录成功按钮事件
    document.getElementById('loginSuccessBtn').addEventListener('click', async function() {
        modal.hide();

        // 开始微信初始化循环
        await startWeChatInitializationLoop(instanceId, instance);
    });

    // 显示模态框
    modal.show();

    // 模态框关闭时清理
    modalElement.addEventListener('hidden.bs.modal', function() {
        modalElement.remove();
    });
}

/**
 * 开始微信初始化循环
 * @param {string} instanceId - 实例ID
 * @param {Object} instance - 实例信息
 */
async function startWeChatInitializationLoop(instanceId, instance) {
    try {
        showNotification(`正在初始化实例 ${instance.name} 的微信连接...`, 'info');

        const maxAttempts = 30;
        let attempt = 0;

        while (attempt < maxAttempts) {
            try {
                // 调用代理API
                const data = await fetchAPI(`/api/instances/${instanceId}/wechat-init`, {
                    method: 'POST'
                });

                if (data.code === 0) {
                    const status = data.data?.status;
                    if (status === 'connected') {
                        showNotification(`实例 ${instance.name} 微信连接成功，消息监听已重启`, 'success');

                        // 刷新实例列表
                        await loadInstances();
                        break;
                    }
                }

                attempt++;
                console.log(`微信初始化尝试 ${attempt}/${maxAttempts}: ${instanceId}`);

                // 等待2秒后重试
                await new Promise(resolve => setTimeout(resolve, 2000));

            } catch (error) {
                attempt++;
                console.warn(`微信初始化尝试失败 ${attempt}/${maxAttempts}: ${instanceId}`, error);
                await new Promise(resolve => setTimeout(resolve, 2000));
            }
        }

        if (attempt >= maxAttempts) {
            showNotification(`实例 ${instance.name} 微信初始化失败，已达到最大尝试次数`, 'warning');
        }

    } catch (error) {
        console.error('微信初始化循环异常:', error);
        showNotification(`微信初始化过程出错: ${error.message}`, 'danger');
    }
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

        // 并行获取状态和资源信息
        const [statusResponse, resourceResponse] = await Promise.allSettled([
            fetchAPI(`/api/instances/${instanceId}/status`),
            fetchAPI(`/api/system/resources?instance_id=${instanceId}`)
        ]);

        // 处理状态信息
        let status = 'OFFLINE';
        let uptime = 'N/A';
        let wechatStatus = 'disconnected';

        if (statusResponse.status === 'fulfilled' && statusResponse.value) {
            const statusData = statusResponse.value;
            console.log(`实例 ${instanceId} 状态响应:`, statusData);

            // health接口可能直接返回数据，也可能包装在code/data中
            let healthData = statusData;
            if (statusData.code === 0 && statusData.data) {
                healthData = statusData.data;
            }

            // 检查状态
            if (healthData.status === 'ok') {
                status = 'ONLINE';
                wechatStatus = healthData.wechat_status || 'connected';

                // 处理uptime
                if (typeof healthData.uptime === 'number' && healthData.uptime > 0) {
                    const uptimeSeconds = healthData.uptime;
                    const days = Math.floor(uptimeSeconds / 86400);
                    const hours = Math.floor((uptimeSeconds % 86400) / 3600);
                    const minutes = Math.floor((uptimeSeconds % 3600) / 60);

                    if (days > 0) {
                        uptime = `${days}天${hours}小时${minutes}分钟`;
                    } else if (hours > 0) {
                        uptime = `${hours}小时${minutes}分钟`;
                    } else {
                        uptime = `${minutes}分钟`;
                    }
                }
            } else {
                // 如果状态不是ok，设置为离线
                status = 'OFFLINE';
                wechatStatus = healthData.wechat_status || 'disconnected';
            }
        } else {
            console.log(`实例 ${instanceId} 状态请求失败:`, statusResponse.reason);
        }

        // 处理资源信息
        let cpuPercent = 'N/A';
        let memoryPercent = 'N/A';
        let memoryUsage = 'N/A';

        if (resourceResponse.status === 'fulfilled' && resourceResponse.value) {
            const resourceData = resourceResponse.value;
            console.log(`实例 ${instanceId} 资源响应:`, resourceData);

            if (resourceData && resourceData.data) {
                const data = resourceData.data;

                // 处理CPU信息
                if (data.cpu && typeof data.cpu.usage_percent === 'number') {
                    cpuPercent = `${data.cpu.usage_percent.toFixed(1)}%`;
                }

                // 处理内存信息
                if (data.memory) {
                    if (typeof data.memory.usage_percent === 'number') {
                        memoryPercent = `${data.memory.usage_percent.toFixed(1)}%`;
                    }
                    if (typeof data.memory.used === 'number' && typeof data.memory.total === 'number') {
                        const used = (data.memory.used / 1024).toFixed(1);
                        const total = (data.memory.total / 1024).toFixed(1);
                        memoryUsage = `${used}/${total}GB`;
                    }
                }
            }
        }

        // 更新状态标签
        updateInstanceStatus(instanceId, status, wechatStatus);

        // 更新界面元素
        updateInstanceMetrics(instanceId, {
            cpu_percent: cpuPercent,
            memory_percent: memoryPercent,
            memory_usage: memoryUsage,
            runtime: uptime
        });

        // 显示成功通知
        if (!silent) {
            showNotification(`实例 ${instanceId} 信息已更新`, 'success');
        }

        console.log(`实例 ${instanceId} 信息刷新成功 - 状态: ${status}, 微信: ${wechatStatus}`);
    } catch (error) {
        console.error('刷新实例信息失败:', error);
        if (!silent) {
            showNotification(`刷新信息失败: ${error.message}`, 'danger');
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

/**
 * 格式化CPU使用率
 * @param {number|string} cpuPercent - CPU使用率
 * @returns {string} - 格式化后的CPU使用率
 */
function formatCpuPercent(cpuPercent) {
    if (cpuPercent === null || cpuPercent === undefined || cpuPercent === '') {
        return 'N/A';
    }

    const percent = parseFloat(cpuPercent);
    if (isNaN(percent)) {
        return 'N/A';
    }

    return `${percent.toFixed(1)}%`;
}

/**
 * 格式化内存使用率
 * @param {number|string} memoryPercent - 内存使用率
 * @returns {string} - 格式化后的内存使用率
 */
function formatMemoryPercent(memoryPercent) {
    if (memoryPercent === null || memoryPercent === undefined || memoryPercent === '') {
        return 'N/A';
    }

    const percent = parseFloat(memoryPercent);
    if (isNaN(percent)) {
        return 'N/A';
    }

    return `${percent.toFixed(1)}%`;
}

/**
 * 格式化内存使用情况
 * @param {number|string} memoryUsed - 已使用内存(GB)
 * @param {number|string} memoryTotal - 总内存(GB)
 * @returns {string} - 格式化后的内存使用情况
 */
function formatMemoryUsage(memoryUsed, memoryTotal) {
    if (memoryUsed === null || memoryUsed === undefined || memoryUsed === '' ||
        memoryTotal === null || memoryTotal === undefined || memoryTotal === '') {
        return 'N/A';
    }

    const used = parseFloat(memoryUsed);
    const total = parseFloat(memoryTotal);

    if (isNaN(used) || isNaN(total)) {
        return 'N/A';
    }

    return `${used.toFixed(1)}/${total.toFixed(1)}GB`;
}

/**
 * 格式化运行时间
 * @param {string} runtime - 运行时间
 * @returns {string} - 格式化后的运行时间
 */
function formatRuntime(runtime) {
    if (runtime === null || runtime === undefined || runtime === '') {
        return 'N/A';
    }

    // 如果已经是字符串格式，直接返回
    if (typeof runtime === 'string') {
        return runtime;
    }

    return 'N/A';
}

/**
 * 更新实例状态标签
 * @param {string} instanceId - 实例ID
 * @param {string} status - 状态 (ONLINE/OFFLINE/ERROR)
 * @param {string} wechatStatus - 微信状态 (connected/disconnected)
 */
function updateInstanceStatus(instanceId, status, wechatStatus) {
    const statusElement = document.querySelector(`#instance-card-${instanceId} .instance-status`);
    if (!statusElement) return;

    // 移除所有状态类
    statusElement.classList.remove('status-online', 'status-offline', 'status-error', 'status-disabled');

    // 根据状态设置样式和文本
    if (status === 'ONLINE' && wechatStatus === 'connected') {
        statusElement.classList.add('status-online');
        statusElement.textContent = '在线';
    } else if (status === 'ONLINE' && wechatStatus === 'disconnected') {
        statusElement.classList.add('status-offline');
        statusElement.textContent = '微信未连接';
    } else if (status === 'ERROR') {
        statusElement.classList.add('status-error');
        statusElement.textContent = '错误';
    } else {
        statusElement.classList.add('status-offline');
        statusElement.textContent = '离线';
    }
}

/**
 * 更新实例指标信息
 * @param {string} instanceId - 实例ID
 * @param {Object} metrics - 指标数据
 */
function updateInstanceMetrics(instanceId, metrics) {
    // 更新CPU使用率
    const cpuElement = document.getElementById(`cpu-${instanceId}`);
    if (cpuElement && metrics.cpu_percent !== undefined) {
        cpuElement.textContent = metrics.cpu_percent;
    }

    // 更新内存百分比
    const memoryPercentElement = document.getElementById(`memory-percent-${instanceId}`);
    if (memoryPercentElement && metrics.memory_percent !== undefined) {
        memoryPercentElement.textContent = metrics.memory_percent;
    }

    // 更新内存使用情况
    const memoryUsageElement = document.getElementById(`memory-usage-${instanceId}`);
    if (memoryUsageElement && metrics.memory_usage !== undefined) {
        memoryUsageElement.textContent = metrics.memory_usage;
    }

    // 更新运行时间
    const runtimeElement = document.getElementById(`runtime-${instanceId}`);
    if (runtimeElement && metrics.runtime !== undefined) {
        runtimeElement.textContent = metrics.runtime;
    }
}
