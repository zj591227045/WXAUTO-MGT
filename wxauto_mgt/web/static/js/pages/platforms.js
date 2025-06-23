/**
 * 服务平台和消息转发规则管理页面JavaScript
 */

// 当前编辑的平台ID
let currentPlatformId = null;
// 当前编辑的规则ID
let currentRuleId = null;
// 当前要删除的对象类型和ID
let deleteType = null;
let deleteId = null;
// 平台类型配置
const platformTypeConfigs = {
    dify: [
        { id: 'api_key', label: 'API密钥', type: 'text', required: true },
        { id: 'api_url', label: 'API地址', type: 'text', required: true, default: 'https://api.dify.ai/v1' }
    ],
    openai: [
        { id: 'api_key', label: 'API密钥', type: 'text', required: true },
        { id: 'api_base', label: 'API基础URL', type: 'text', required: false, default: 'https://api.openai.com/v1' },
        { id: 'model', label: '模型', type: 'text', required: true, default: 'gpt-3.5-turbo' },
        { id: 'temperature', label: '温度', type: 'number', required: true, default: 0.7, min: 0, max: 2, step: 0.1 },
        { id: 'system_prompt', label: '系统提示', type: 'textarea', required: false, default: '你是一个有用的助手。' },
        { id: 'max_tokens', label: '最大令牌数', type: 'number', required: false, default: 1000, min: 1, max: 4096 }
    ],
    keyword: [
        { id: 'keywords', label: '关键词（多个关键词用逗号分隔）', type: 'textarea', required: true },
        { id: 'replies', label: '回复（多个回复每行一个）', type: 'textarea', required: true },
        { id: 'match_type', label: '匹配方式', type: 'select', required: true, options: [
            { value: 'exact', label: '精确匹配' },
            { value: 'contains', label: '包含匹配' },
            { value: 'fuzzy', label: '模糊匹配' }
        ]},
        { id: 'random_delay', label: '随机延迟回复', type: 'checkbox', default: false },
        { id: 'min_delay', label: '最小延迟（秒）', type: 'number', default: 1, min: 0, max: 60 },
        { id: 'max_delay', label: '最大延迟（秒）', type: 'number', default: 5, min: 0, max: 60 }
    ]
};

document.addEventListener('DOMContentLoaded', function() {
    // 初始化页面
    initPlatformsPage();

    // 绑定刷新按钮事件
    document.getElementById('refresh-platforms').addEventListener('click', loadPlatforms);
    document.getElementById('refresh-rules').addEventListener('click', loadRules);

    // 绑定添加按钮事件
    document.getElementById('add-platform').addEventListener('click', showAddPlatformModal);
    document.getElementById('add-rule').addEventListener('click', showAddRuleModal);

    // 绑定保存按钮事件
    document.getElementById('save-platform').addEventListener('click', savePlatform);
    document.getElementById('save-rule').addEventListener('click', saveRule);

    // 绑定确认删除按钮事件
    document.getElementById('confirm-delete').addEventListener('click', confirmDelete);

    // 绑定平台类型选择事件
    document.getElementById('platform-type').addEventListener('change', function() {
        const platformType = this.value;
        loadPlatformConfigFields(platformType);
    });

    // 绑定实例过滤器事件
    document.getElementById('instance-filter').addEventListener('change', function() {
        const instanceId = this.value;
        loadRules(instanceId);
    });

    // 绑定@消息复选框事件
    document.getElementById('rule-only-at-messages').addEventListener('change', function() {
        const atNameContainer = document.getElementById('at-name-container');
        if (this.checked) {
            atNameContainer.style.display = 'block';
        } else {
            atNameContainer.style.display = 'none';
            document.getElementById('rule-at-name').value = '';
        }
    });
});

/**
 * 初始化服务平台和消息转发规则管理页面
 */
function initPlatformsPage() {
    // 加载服务平台列表
    loadPlatforms();

    // 加载消息转发规则列表
    loadRules();

    // 加载实例列表（用于过滤和规则表单）
    loadInstances();

    // 设置轮询刷新
    pollingManager.addTask('platforms', loadPlatforms, 10000);
    pollingManager.addTask('rules', function() {
        const instanceId = document.getElementById('instance-filter').value;
        loadRules(instanceId);
    }, 10000);
}

/**
 * 加载服务平台列表
 */
async function loadPlatforms() {
    try {
        const platformsTableBody = document.getElementById('platforms-table-body');

        // 显示加载中
        platformsTableBody.innerHTML = `
            <tr>
                <td colspan="5" class="text-center py-3">
                    <div class="spinner-border text-primary" role="status">
                        <span class="visually-hidden">加载中...</span>
                    </div>
                    <p class="mt-2">加载服务平台列表...</p>
                </td>
            </tr>
        `;

        // 获取服务平台列表
        const platforms = await fetchAPI('/api/platforms');

        // 清空表格
        platformsTableBody.innerHTML = '';

        if (platforms.length === 0) {
            platformsTableBody.innerHTML = `
                <tr>
                    <td colspan="5" class="text-center py-3">
                        <p class="text-muted">暂无服务平台，请点击"添加平台"按钮创建</p>
                    </td>
                </tr>
            `;
        } else {
            // 添加平台行
            platforms.forEach((platform, index) => {
                const row = createPlatformRow(platform, index + 1);
                platformsTableBody.appendChild(row);
            });
        }

        // 更新平台数量
        document.getElementById('platforms-count').textContent = `共 ${platforms.length} 个服务平台`;

        return platforms;
    } catch (error) {
        console.error('加载服务平台列表失败:', error);
        document.getElementById('platforms-table-body').innerHTML = `
            <tr>
                <td colspan="5" class="text-center py-3">
                    <p class="text-danger">加载服务平台列表失败，请重试</p>
                </td>
            </tr>
        `;
        return [];
    }
}

/**
 * 创建服务平台表格行
 * @param {Object} platform - 平台数据
 * @param {number} index - 序号
 * @returns {HTMLElement} - 表格行元素
 */
function createPlatformRow(platform, index) {
    const row = document.createElement('tr');

    // 获取状态样式
    const statusClass = platform.enabled ? 'status-enabled' : 'status-disabled';
    const statusText = platform.enabled ? '启用' : '禁用';

    // 设置行内容
    row.innerHTML = `
        <td>${index}</td>
        <td>${platform.name}</td>
        <td>${platform.type}</td>
        <td><span class="status-badge ${statusClass}">${statusText}</span></td>
        <td class="action-buttons">
            <button class="btn btn-sm btn-outline-primary edit-platform" data-platform-id="${platform.platform_id}">
                <i class="fas fa-edit"></i> 编辑
            </button>
            <button class="btn btn-sm btn-outline-danger delete-platform" data-platform-id="${platform.platform_id}" data-platform-name="${platform.name}">
                <i class="fas fa-trash-alt"></i> 删除
            </button>
            <button class="btn btn-sm btn-outline-info test-platform" data-platform-id="${platform.platform_id}">
                <i class="fas fa-vial"></i> 测试
            </button>
        </td>
    `;

    // 绑定按钮事件
    row.querySelector('.edit-platform').addEventListener('click', function() {
        const platformId = this.getAttribute('data-platform-id');
        showEditPlatformModal(platformId);
    });

    row.querySelector('.delete-platform').addEventListener('click', function() {
        const platformId = this.getAttribute('data-platform-id');
        const platformName = this.getAttribute('data-platform-name');
        showDeletePlatformConfirm(platformId, platformName);
    });

    row.querySelector('.test-platform').addEventListener('click', function() {
        const platformId = this.getAttribute('data-platform-id');
        testPlatform(platformId);
    });

    return row;
}

/**
 * 加载消息转发规则列表
 * @param {string} instanceId - 实例ID（可选，用于过滤）
 */
async function loadRules(instanceId = null) {
    try {
        const rulesTableBody = document.getElementById('rules-table-body');

        // 显示加载中
        rulesTableBody.innerHTML = `
            <tr>
                <td colspan="7" class="text-center py-3">
                    <div class="spinner-border text-primary" role="status">
                        <span class="visually-hidden">加载中...</span>
                    </div>
                    <p class="mt-2">加载消息转发规则列表...</p>
                </td>
            </tr>
        `;

        // 构建API URL
        let url = '/api/rules';
        if (instanceId) {
            url += `?instance_id=${instanceId}`;
        }

        // 获取规则列表
        const rules = await fetchAPI(url);

        // 清空表格
        rulesTableBody.innerHTML = '';

        if (rules.length === 0) {
            rulesTableBody.innerHTML = `
                <tr>
                    <td colspan="7" class="text-center py-3">
                        <p class="text-muted">暂无消息转发规则，请点击"添加规则"按钮创建</p>
                    </td>
                </tr>
            `;
        } else {
            // 获取平台列表（用于显示平台名称）
            const platforms = await fetchAPI('/api/platforms');
            const platformMap = {};
            platforms.forEach(platform => {
                platformMap[platform.platform_id] = platform.name;
            });

            // 添加规则行
            rules.forEach((rule, index) => {
                const row = createRuleRow(rule, index + 1, platformMap);
                rulesTableBody.appendChild(row);
            });
        }

        // 更新规则数量
        document.getElementById('rules-count').textContent = `共 ${rules.length} 个规则`;

        return rules;
    } catch (error) {
        console.error('加载消息转发规则列表失败:', error);
        document.getElementById('rules-table-body').innerHTML = `
            <tr>
                <td colspan="7" class="text-center py-3">
                    <p class="text-danger">加载消息转发规则列表失败，请重试</p>
                </td>
            </tr>
        `;
        return [];
    }
}

/**
 * 创建消息转发规则表格行
 * @param {Object} rule - 规则数据
 * @param {number} index - 序号
 * @param {Object} platformMap - 平台ID到名称的映射
 * @returns {HTMLElement} - 表格行元素
 */
function createRuleRow(rule, index, platformMap) {
    const row = document.createElement('tr');

    // 获取平台名称
    const platformName = platformMap[rule.platform_id] || rule.platform_id;

    // 设置行内容
    row.innerHTML = `
        <td>${index}</td>
        <td>${rule.name}</td>
        <td>${rule.instance_id === '*' ? '所有实例' : rule.instance_id}</td>
        <td>${rule.chat_pattern}</td>
        <td>${platformName}</td>
        <td>${rule.priority}</td>
        <td class="action-buttons">
            <button class="btn btn-sm btn-outline-primary edit-rule" data-rule-id="${rule.rule_id}">
                <i class="fas fa-edit"></i> 编辑
            </button>
            <button class="btn btn-sm btn-outline-danger delete-rule" data-rule-id="${rule.rule_id}" data-rule-name="${rule.name}">
                <i class="fas fa-trash-alt"></i> 删除
            </button>
        </td>
    `;

    // 绑定按钮事件
    row.querySelector('.edit-rule').addEventListener('click', function() {
        const ruleId = this.getAttribute('data-rule-id');
        showEditRuleModal(ruleId);
    });

    row.querySelector('.delete-rule').addEventListener('click', function() {
        const ruleId = this.getAttribute('data-rule-id');
        const ruleName = this.getAttribute('data-rule-name');
        showDeleteRuleConfirm(ruleId, ruleName);
    });

    return row;
}

/**
 * 加载实例列表
 */
async function loadInstances() {
    try {
        // 获取实例列表
        const instances = await fetchAPI('/api/instances');

        // 获取过滤器和规则表单中的实例选择框
        const instanceFilter = document.getElementById('instance-filter');
        const ruleInstance = document.getElementById('rule-instance');

        // 清空选项（保留默认选项）
        instanceFilter.innerHTML = '<option value="">全部实例</option>';
        ruleInstance.innerHTML = '<option value="">请选择实例</option><option value="*">所有实例</option>';

        // 添加实例选项
        instances.forEach(instance => {
            // 只添加启用的实例
            if (instance.enabled === 1) {
                const filterOption = document.createElement('option');
                filterOption.value = instance.instance_id;
                filterOption.textContent = instance.name;
                instanceFilter.appendChild(filterOption);

                const ruleOption = document.createElement('option');
                ruleOption.value = instance.instance_id;
                ruleOption.textContent = instance.name;
                ruleInstance.appendChild(ruleOption);
            }
        });

        return instances;
    } catch (error) {
        console.error('加载实例列表失败:', error);
        showNotification('加载实例列表失败', 'danger');
        return [];
    }
}

/**
 * 显示添加服务平台模态框
 */
function showAddPlatformModal() {
    // 重置表单
    document.getElementById('platformForm').reset();
    document.getElementById('platform-id').value = '';
    document.getElementById('platform-config-container').innerHTML = '';

    // 设置标题
    document.getElementById('platformModalTitle').textContent = '添加服务平台';

    // 重置当前编辑的平台ID
    currentPlatformId = null;

    // 显示模态框
    const modal = new bootstrap.Modal(document.getElementById('platformModal'));
    modal.show();
}

/**
 * 显示编辑服务平台模态框
 * @param {string} platformId - 平台ID
 */
async function showEditPlatformModal(platformId) {
    try {
        // 获取平台列表
        const platforms = await fetchAPI('/api/platforms');
        const platform = platforms.find(p => p.platform_id === platformId);

        if (!platform) {
            showNotification('未找到平台', 'danger');
            return;
        }

        // 填充表单
        document.getElementById('platform-id').value = platform.platform_id;
        document.getElementById('platform-name').value = platform.name;
        document.getElementById('platform-type').value = platform.type;
        document.getElementById('platform-enabled').checked = platform.enabled;

        // 加载平台配置字段
        loadPlatformConfigFields(platform.type, platform.config);

        // 设置标题
        document.getElementById('platformModalTitle').textContent = '编辑服务平台';

        // 设置当前编辑的平台ID
        currentPlatformId = platformId;

        // 显示模态框
        const modal = new bootstrap.Modal(document.getElementById('platformModal'));
        modal.show();
    } catch (error) {
        console.error('获取平台详情失败:', error);
        showNotification('获取平台详情失败', 'danger');
    }
}

/**
 * 加载平台配置字段
 * @param {string} platformType - 平台类型
 * @param {Object} configData - 配置数据（可选，用于编辑时填充）
 */
function loadPlatformConfigFields(platformType, configData = {}) {
    const container = document.getElementById('platform-config-container');
    container.innerHTML = '';

    if (!platformType || !platformTypeConfigs[platformType]) {
        return;
    }

    // 创建配置字段
    platformTypeConfigs[platformType].forEach(field => {
        const fieldId = `platform-config-${field.id}`;
        const fieldValue = configData[field.id] !== undefined ? configData[field.id] : field.default || '';

        const formGroup = document.createElement('div');
        formGroup.className = 'mb-3';

        // 创建标签
        const label = document.createElement('label');
        label.className = 'form-label';
        label.setAttribute('for', fieldId);
        label.textContent = field.label;
        if (field.required) {
            label.innerHTML += ' <span class="text-danger">*</span>';
        }
        formGroup.appendChild(label);

        // 创建输入字段
        let input;

        switch (field.type) {
            case 'textarea':
                input = document.createElement('textarea');
                input.className = 'form-control';
                input.id = fieldId;
                input.name = field.id;
                input.rows = 3;
                input.value = fieldValue;
                if (field.required) input.required = true;
                break;

            case 'select':
                input = document.createElement('select');
                input.className = 'form-select';
                input.id = fieldId;
                input.name = field.id;
                if (field.required) input.required = true;

                // 添加选项
                if (field.options) {
                    field.options.forEach(option => {
                        const optionElement = document.createElement('option');
                        optionElement.value = option.value;
                        optionElement.textContent = option.label;
                        if (option.value === fieldValue) {
                            optionElement.selected = true;
                        }
                        input.appendChild(optionElement);
                    });
                }
                break;

            case 'checkbox':
                const checkDiv = document.createElement('div');
                checkDiv.className = 'form-check';

                input = document.createElement('input');
                input.className = 'form-check-input';
                input.type = 'checkbox';
                input.id = fieldId;
                input.name = field.id;
                input.checked = fieldValue === true;

                const checkLabel = document.createElement('label');
                checkLabel.className = 'form-check-label';
                checkLabel.setAttribute('for', fieldId);
                checkLabel.textContent = field.label;

                checkDiv.appendChild(input);
                checkDiv.appendChild(checkLabel);

                formGroup.innerHTML = '';
                formGroup.appendChild(checkDiv);
                break;

            default: // text, number, etc.
                input = document.createElement('input');
                input.className = 'form-control';
                input.type = field.type;
                input.id = fieldId;
                input.name = field.id;
                input.value = fieldValue;
                if (field.required) input.required = true;
                if (field.min !== undefined) input.min = field.min;
                if (field.max !== undefined) input.max = field.max;
                if (field.step !== undefined) input.step = field.step;
                break;
        }

        // 如果不是checkbox（已经添加到formGroup）
        if (field.type !== 'checkbox') {
            formGroup.appendChild(input);
        }

        // 添加帮助文本
        if (field.help) {
            const helpText = document.createElement('div');
            helpText.className = 'form-text';
            helpText.textContent = field.help;
            formGroup.appendChild(helpText);
        }

        container.appendChild(formGroup);
    });
}

/**
 * 保存服务平台
 */
async function savePlatform() {
    // 获取表单数据
    const platformId = document.getElementById('platform-id').value;
    const name = document.getElementById('platform-name').value;
    const type = document.getElementById('platform-type').value;
    const enabled = document.getElementById('platform-enabled').checked;

    // 验证表单
    if (!name || !type) {
        showNotification('请填写必填字段', 'warning');
        return;
    }

    // 获取配置数据
    const config = {};
    if (platformTypeConfigs[type]) {
        for (const field of platformTypeConfigs[type]) {
            const fieldId = `platform-config-${field.id}`;
            const element = document.getElementById(fieldId);

            if (!element) continue;

            let value;
            if (field.type === 'checkbox') {
                value = element.checked;
            } else {
                value = element.value;
            }

            if (field.required && (value === '' || value === undefined)) {
                showNotification(`请填写 ${field.label}`, 'warning');
                return;
            }

            config[field.id] = value;
        }
    }

    try {
        // 构建请求数据
        const data = {
            name,
            type,
            config,
            enabled: enabled ? 1 : 0
        };

        // 发送请求
        let response;
        if (currentPlatformId) {
            // 更新平台
            response = await fetchAPI(`/api/platforms/${currentPlatformId}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            });
            showNotification(`平台 ${name} 更新成功`, 'success');
        } else {
            // 添加平台
            response = await fetchAPI('/api/platforms', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            });
            showNotification(`平台 ${name} 添加成功`, 'success');
        }

        // 关闭模态框
        const modal = bootstrap.Modal.getInstance(document.getElementById('platformModal'));
        modal.hide();

        // 重新加载平台列表
        loadPlatforms();
    } catch (error) {
        console.error('保存平台失败:', error);
        showNotification(`保存平台失败: ${error.message}`, 'danger');
    }
}

/**
 * 显示添加消息转发规则模态框
 */
async function showAddRuleModal() {
    // 重置表单
    document.getElementById('ruleForm').reset();
    document.getElementById('rule-id').value = '';

    // 设置标题
    document.getElementById('ruleModalTitle').textContent = '添加消息转发规则';

    // 重置当前编辑的规则ID
    currentRuleId = null;

    // 加载平台选项
    await loadPlatformOptions();

    // 显示模态框
    const modal = new bootstrap.Modal(document.getElementById('ruleModal'));
    modal.show();
}

/**
 * 显示编辑消息转发规则模态框
 * @param {string} ruleId - 规则ID
 */
async function showEditRuleModal(ruleId) {
    try {
        // 获取规则列表
        const rules = await fetchAPI('/api/rules');
        const rule = rules.find(r => r.rule_id === ruleId);

        if (!rule) {
            showNotification('未找到规则', 'danger');
            return;
        }

        // 填充表单
        document.getElementById('rule-id').value = rule.rule_id;
        document.getElementById('rule-name').value = rule.name;
        document.getElementById('rule-instance').value = rule.instance_id;
        document.getElementById('rule-chat').value = rule.chat_pattern;
        document.getElementById('rule-priority').value = rule.priority;
        document.getElementById('rule-enabled').checked = rule.enabled === 1;

        // 加载平台选项
        await loadPlatformOptions();
        document.getElementById('rule-platform').value = rule.platform_id;

        // 设置标题
        document.getElementById('ruleModalTitle').textContent = '编辑消息转发规则';

        // 设置当前编辑的规则ID
        currentRuleId = ruleId;

        // 显示模态框
        const modal = new bootstrap.Modal(document.getElementById('ruleModal'));
        modal.show();
    } catch (error) {
        console.error('获取规则详情失败:', error);
        showNotification('获取规则详情失败', 'danger');
    }
}

/**
 * 加载平台选项
 */
async function loadPlatformOptions() {
    try {
        // 获取平台列表
        const platforms = await fetchAPI('/api/platforms');

        // 获取规则表单中的平台选择框
        const rulePlatform = document.getElementById('rule-platform');

        // 清空选项（保留默认选项）
        rulePlatform.innerHTML = '<option value="">请选择服务平台</option>';

        // 添加平台选项
        platforms.forEach(platform => {
            // 只添加启用的平台
            if (platform.enabled) {
                const option = document.createElement('option');
                option.value = platform.platform_id;
                option.textContent = platform.name;
                rulePlatform.appendChild(option);
            }
        });
    } catch (error) {
        console.error('加载平台选项失败:', error);
        showNotification('加载平台选项失败', 'danger');
    }
}

/**
 * 保存消息转发规则
 */
async function saveRule() {
    // 获取表单数据
    const ruleId = document.getElementById('rule-id').value;
    const name = document.getElementById('rule-name').value;
    const instanceId = document.getElementById('rule-instance').value;
    const chatPattern = document.getElementById('rule-chat').value;
    const platformId = document.getElementById('rule-platform').value;
    const priority = document.getElementById('rule-priority').value;
    const enabled = document.getElementById('rule-enabled').checked;

    // 验证表单
    if (!name || !instanceId || !chatPattern || !platformId || !priority) {
        showNotification('请填写必填字段', 'warning');
        return;
    }

    try {
        // 构建请求数据
        const data = {
            name,
            instance_id: instanceId,
            chat_pattern: chatPattern,
            platform_id: platformId,
            priority: parseInt(priority),
            enabled: enabled ? 1 : 0
        };

        // 发送请求
        let response;
        if (currentRuleId) {
            // 更新规则
            response = await fetchAPI(`/api/rules/${currentRuleId}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            });
            showNotification(`规则 ${name} 更新成功`, 'success');
        } else {
            // 添加规则
            response = await fetchAPI('/api/rules', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            });
            showNotification(`规则 ${name} 添加成功`, 'success');
        }

        // 关闭模态框
        const modal = bootstrap.Modal.getInstance(document.getElementById('ruleModal'));
        modal.hide();

        // 重新加载规则列表
        const instanceFilter = document.getElementById('instance-filter').value;
        loadRules(instanceFilter);
    } catch (error) {
        console.error('保存规则失败:', error);
        showNotification(`保存规则失败: ${error.message}`, 'danger');
    }
}

/**
 * 显示删除平台确认对话框
 * @param {string} platformId - 平台ID
 * @param {string} platformName - 平台名称
 */
function showDeletePlatformConfirm(platformId, platformName) {
    // 设置删除类型和ID
    deleteType = 'platform';
    deleteId = platformId;

    // 设置确认消息
    document.getElementById('deleteModalTitle').textContent = '确认删除平台';
    document.getElementById('delete-confirm-message').textContent = `确定要删除平台 "${platformName}" 吗？`;

    // 显示模态框
    const modal = new bootstrap.Modal(document.getElementById('deleteConfirmModal'));
    modal.show();
}

/**
 * 显示删除规则确认对话框
 * @param {string} ruleId - 规则ID
 * @param {string} ruleName - 规则名称
 */
function showDeleteRuleConfirm(ruleId, ruleName) {
    // 设置删除类型和ID
    deleteType = 'rule';
    deleteId = ruleId;

    // 设置确认消息
    document.getElementById('deleteModalTitle').textContent = '确认删除规则';
    document.getElementById('delete-confirm-message').textContent = `确定要删除规则 "${ruleName}" 吗？`;

    // 显示模态框
    const modal = new bootstrap.Modal(document.getElementById('deleteConfirmModal'));
    modal.show();
}

/**
 * 确认删除
 */
async function confirmDelete() {
    if (!deleteType || !deleteId) {
        showNotification('未指定要删除的对象', 'danger');
        return;
    }

    try {
        // 根据删除类型发送请求
        if (deleteType === 'platform') {
            // 删除平台
            await fetchAPI(`/api/platforms/${deleteId}`, {
                method: 'DELETE'
            });
            showNotification('平台删除成功', 'success');

            // 重新加载平台列表
            loadPlatforms();
        } else if (deleteType === 'rule') {
            // 删除规则
            await fetchAPI(`/api/rules/${deleteId}`, {
                method: 'DELETE'
            });
            showNotification('规则删除成功', 'success');

            // 重新加载规则列表
            const instanceFilter = document.getElementById('instance-filter').value;
            loadRules(instanceFilter);
        }

        // 关闭模态框
        const modal = bootstrap.Modal.getInstance(document.getElementById('deleteConfirmModal'));
        modal.hide();
    } catch (error) {
        console.error('删除失败:', error);
        showNotification(`删除失败: ${error.message}`, 'danger');
    }
}

/**
 * 测试平台连接
 * @param {string} platformId - 平台ID
 */
async function testPlatform(platformId) {
    try {
        // 发送测试请求
        const response = await fetchAPI(`/api/platforms/${platformId}/test`, {
            method: 'POST'
        });

        // 显示测试结果
        // API返回格式: {"code": 0, "message": "测试完成", "data": result}
        if (response.code === 0) {
            // 检查测试结果
            const testResult = response.data;
            if (testResult && !testResult.error) {
                showNotification(`平台测试成功: ${testResult.message || '连接正常'}`, 'success');
            } else {
                const errorMsg = testResult ? testResult.error : '测试失败';
                showNotification(`平台测试失败: ${errorMsg}`, 'warning');
            }
        } else {
            showNotification(`平台测试失败: ${response.message}`, 'warning');
        }
    } catch (error) {
        console.error('测试平台失败:', error);
        showNotification(`测试平台失败: ${error.message}`, 'danger');
    }
}
