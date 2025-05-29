"""
对话框组件

该模块包含各种对话框组件，用于添加、编辑和管理实例、服务平台和消息转发规则。
"""

# 导入对话框组件
from wxauto_mgt.ui.components.dialogs.platform_dialog import AddEditPlatformDialog
from wxauto_mgt.ui.components.dialogs.rule_dialog import AddEditRuleDialog

# 导入现有的对话框组件
try:
    from wxauto_mgt.ui.components.dialogs.add_instance_dialog import AddInstanceDialog
    from wxauto_mgt.ui.components.dialogs.edit_instance_dialog import EditInstanceDialog
except ImportError:
    # 如果现有对话框组件不存在，使用占位符
    class AddInstanceDialog:
        pass
    
    class EditInstanceDialog:
        pass

# 导出所有对话框组件
__all__ = [
    'AddEditPlatformDialog',
    'AddEditRuleDialog',
    'AddInstanceDialog',
    'EditInstanceDialog'
]


