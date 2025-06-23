/**
 * 显示添加消息转发规则模态框
 */
async function showAddRuleModal() {
    // 重置表单
    document.getElementById('ruleForm').reset();
    document.getElementById('rule-id').value = '';

    // 重置@消息相关字段
    document.getElementById('rule-only-at-messages').checked = false;
    document.getElementById('rule-at-name').value = '';
    document.getElementById('rule-reply-at-sender').checked = false;

    // 隐藏@名称输入框
    document.getElementById('at-name-container').style.display = 'none';

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

        // 填充@消息相关字段
        const onlyAtMessages = rule.only_at_messages === 1;
        document.getElementById('rule-only-at-messages').checked = onlyAtMessages;
        document.getElementById('rule-at-name').value = rule.at_name || '';
        document.getElementById('rule-reply-at-sender').checked = rule.reply_at_sender === 1;

        // 控制@名称输入框的显示
        const atNameContainer = document.getElementById('at-name-container');
        if (onlyAtMessages) {
            atNameContainer.style.display = 'block';
        } else {
            atNameContainer.style.display = 'none';
        }
        
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

    // 获取@消息相关字段
    const onlyAtMessages = document.getElementById('rule-only-at-messages').checked;
    const atName = document.getElementById('rule-at-name').value.trim();
    const replyAtSender = document.getElementById('rule-reply-at-sender').checked;
    
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
            enabled: enabled ? 1 : 0,
            only_at_messages: onlyAtMessages ? 1 : 0,
            at_name: atName,
            reply_at_sender: replyAtSender ? 1 : 0
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
