#!/usr/bin/env python3
"""
WXAUTO-MGT 性能监控报告工具

用于生成性能监控报告，分析API调用性能和UI响应性。
"""

import sys
import os
import time
import json
from datetime import datetime, timedelta

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from wxauto_mgt.utils.performance_monitor import performance_monitor
from wxauto_mgt.ui.utils.ui_monitor import ui_monitor, task_monitor


class PerformanceReporter:
    """性能报告生成器"""
    
    def __init__(self):
        """初始化报告生成器"""
        self.report_data = {}
        self.start_time = time.time()
    
    def collect_performance_data(self):
        """收集性能数据"""
        print("正在收集性能数据...")
        
        # 收集性能监控数据
        self.report_data['performance_summary'] = performance_monitor.get_summary()
        
        # 收集UI监控数据
        self.report_data['ui_statistics'] = ui_monitor.get_statistics()
        
        # 收集异步任务数据
        self.report_data['task_statistics'] = task_monitor.get_task_statistics()
        
        # 收集系统信息
        self.report_data['system_info'] = self._get_system_info()
        
        # 收集时间信息
        self.report_data['report_time'] = datetime.now().isoformat()
        self.report_data['collection_duration'] = time.time() - self.start_time
        
        print("性能数据收集完成")
    
    def _get_system_info(self):
        """获取系统信息"""
        try:
            import psutil
            import platform
            
            return {
                'platform': platform.platform(),
                'python_version': platform.python_version(),
                'cpu_count': psutil.cpu_count(),
                'memory_total': psutil.virtual_memory().total / (1024**3),  # GB
                'memory_available': psutil.virtual_memory().available / (1024**3),  # GB
                'memory_percent': psutil.virtual_memory().percent
            }
        except Exception as e:
            return {'error': str(e)}
    
    def analyze_performance(self):
        """分析性能数据"""
        print("正在分析性能数据...")
        
        analysis = {}
        
        # 分析API性能
        perf_summary = self.report_data.get('performance_summary', {})
        operation_summary = perf_summary.get('operation_summary', {})
        
        api_analysis = {}
        for operation, stats in operation_summary.items():
            if stats.get('count', 0) > 0:
                avg_time = stats.get('avg', 0)
                max_time = stats.get('max', 0)
                
                # 性能评级
                if avg_time < 0.1:
                    grade = "优秀"
                elif avg_time < 0.5:
                    grade = "良好"
                elif avg_time < 1.0:
                    grade = "一般"
                else:
                    grade = "需要优化"
                
                api_analysis[operation] = {
                    'grade': grade,
                    'avg_time': avg_time,
                    'max_time': max_time,
                    'count': stats.get('count', 0)
                }
        
        analysis['api_performance'] = api_analysis
        
        # 分析UI响应性
        ui_stats = self.report_data.get('ui_statistics', {})
        responsiveness_rate = ui_stats.get('responsiveness_rate', 0)
        
        if responsiveness_rate >= 0.95:
            ui_grade = "优秀"
        elif responsiveness_rate >= 0.90:
            ui_grade = "良好"
        elif responsiveness_rate >= 0.80:
            ui_grade = "一般"
        else:
            ui_grade = "需要优化"
        
        analysis['ui_responsiveness'] = {
            'grade': ui_grade,
            'responsiveness_rate': responsiveness_rate,
            'blocked_count': ui_stats.get('blocked_count', 0),
            'total_checks': ui_stats.get('total_checks', 0)
        }
        
        # 分析异步任务性能
        task_stats = self.report_data.get('task_statistics', {})
        success_rate = task_stats.get('success_rate', 0)
        avg_duration = task_stats.get('average_duration', 0)
        
        if success_rate >= 0.95 and avg_duration < 1.0:
            task_grade = "优秀"
        elif success_rate >= 0.90 and avg_duration < 2.0:
            task_grade = "良好"
        elif success_rate >= 0.80:
            task_grade = "一般"
        else:
            task_grade = "需要优化"
        
        analysis['async_tasks'] = {
            'grade': task_grade,
            'success_rate': success_rate,
            'avg_duration': avg_duration,
            'active_tasks': task_stats.get('active_tasks', 0),
            'completed_tasks': task_stats.get('completed_tasks', 0),
            'failed_tasks': task_stats.get('failed_tasks', 0)
        }
        
        self.report_data['analysis'] = analysis
        print("性能数据分析完成")
    
    def generate_console_report(self):
        """生成控制台报告"""
        print("\n" + "="*80)
        print("WXAUTO-MGT 性能监控报告")
        print("="*80)
        print(f"报告时间: {self.report_data['report_time']}")
        print(f"数据收集耗时: {self.report_data['collection_duration']:.3f}秒")
        
        # 系统信息
        system_info = self.report_data.get('system_info', {})
        if 'error' not in system_info:
            print(f"\n系统信息:")
            print(f"  平台: {system_info.get('platform', 'Unknown')}")
            print(f"  Python版本: {system_info.get('python_version', 'Unknown')}")
            print(f"  CPU核心数: {system_info.get('cpu_count', 'Unknown')}")
            print(f"  内存总量: {system_info.get('memory_total', 0):.1f} GB")
            print(f"  可用内存: {system_info.get('memory_available', 0):.1f} GB")
            print(f"  内存使用率: {system_info.get('memory_percent', 0):.1f}%")
        
        # 性能分析
        analysis = self.report_data.get('analysis', {})
        
        # API性能
        api_analysis = analysis.get('api_performance', {})
        print(f"\nAPI性能分析:")
        if api_analysis:
            for operation, data in api_analysis.items():
                print(f"  {operation}:")
                print(f"    评级: {data['grade']}")
                print(f"    平均耗时: {data['avg_time']:.3f}秒")
                print(f"    最大耗时: {data['max_time']:.3f}秒")
                print(f"    调用次数: {data['count']}")
        else:
            print("  暂无API调用数据")
        
        # UI响应性
        ui_analysis = analysis.get('ui_responsiveness', {})
        print(f"\nUI响应性分析:")
        print(f"  评级: {ui_analysis.get('grade', 'Unknown')}")
        print(f"  响应率: {ui_analysis.get('responsiveness_rate', 0):.2%}")
        print(f"  阻塞次数: {ui_analysis.get('blocked_count', 0)}")
        print(f"  检查次数: {ui_analysis.get('total_checks', 0)}")
        
        # 异步任务
        task_analysis = analysis.get('async_tasks', {})
        print(f"\n异步任务分析:")
        print(f"  评级: {task_analysis.get('grade', 'Unknown')}")
        print(f"  成功率: {task_analysis.get('success_rate', 0):.2%}")
        print(f"  平均耗时: {task_analysis.get('avg_duration', 0):.3f}秒")
        print(f"  活跃任务: {task_analysis.get('active_tasks', 0)}")
        print(f"  完成任务: {task_analysis.get('completed_tasks', 0)}")
        print(f"  失败任务: {task_analysis.get('failed_tasks', 0)}")
        
        # 总体评估
        self._print_overall_assessment(analysis)
        
        print("\n" + "="*80)
    
    def _print_overall_assessment(self, analysis):
        """打印总体评估"""
        print(f"\n总体评估:")
        
        grades = []
        if 'api_performance' in analysis:
            api_grades = [data['grade'] for data in analysis['api_performance'].values()]
            if api_grades:
                grades.extend(api_grades)
        
        if 'ui_responsiveness' in analysis:
            grades.append(analysis['ui_responsiveness']['grade'])
        
        if 'async_tasks' in analysis:
            grades.append(analysis['async_tasks']['grade'])
        
        if not grades:
            print("  无足够数据进行评估")
            return
        
        # 计算总体评级
        grade_scores = {'优秀': 4, '良好': 3, '一般': 2, '需要优化': 1}
        avg_score = sum(grade_scores.get(grade, 0) for grade in grades) / len(grades)
        
        if avg_score >= 3.5:
            overall_grade = "优秀"
            emoji = "🎉"
        elif avg_score >= 2.5:
            overall_grade = "良好"
            emoji = "👍"
        elif avg_score >= 1.5:
            overall_grade = "一般"
            emoji = "⚠️"
        else:
            overall_grade = "需要优化"
            emoji = "🔧"
        
        print(f"  {emoji} 总体性能: {overall_grade}")
        
        # 提供建议
        if overall_grade == "需要优化":
            print(f"  建议:")
            print(f"    - 检查API调用是否存在阻塞问题")
            print(f"    - 优化数据库查询性能")
            print(f"    - 减少UI线程中的耗时操作")
        elif overall_grade == "一般":
            print(f"  建议:")
            print(f"    - 继续监控性能指标")
            print(f"    - 考虑进一步优化慢速操作")
    
    def save_json_report(self, filename=None):
        """保存JSON格式报告"""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"performance_report_{timestamp}.json"
        
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(self.report_data, f, indent=2, ensure_ascii=False)
            print(f"JSON报告已保存到: {filename}")
        except Exception as e:
            print(f"保存JSON报告失败: {e}")
    
    def generate_report(self, save_json=True):
        """生成完整报告"""
        self.collect_performance_data()
        self.analyze_performance()
        self.generate_console_report()
        
        if save_json:
            self.save_json_report()


def main():
    """主函数"""
    print("WXAUTO-MGT 性能监控报告工具")
    print("正在生成性能报告...")
    
    reporter = PerformanceReporter()
    reporter.generate_report()
    
    print("\n报告生成完成！")


if __name__ == "__main__":
    main()
