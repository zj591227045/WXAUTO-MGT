"""
对话框组件

该模块包含各种对话框组件，用于添加、编辑和管理实例、服务平台和消息转发规则。
"""

# 导入对话框组件
from wxauto_mgt.ui.components.dialogs.platform_dialog import AddEditPlatformDialog
from wxauto_mgt.ui.components.dialogs.rule_dialog import AddEditRuleDialog

# 导入设置对话框
try:
    # 从同级目录的settings_dialog.py文件导入
    from .settings_dialog import SettingsDialog
except ImportError as e:
    print(f"导入SettingsDialog失败: {e}")
    # 如果仍然无法导入，使用占位符
    class SettingsDialog:
        def __init__(self, parent=None):
            raise NotImplementedError("SettingsDialog导入失败，请检查settings_dialog.py文件")

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
    'EditInstanceDialog',
    'SettingsDialog'
]
