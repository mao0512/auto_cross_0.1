import time
import threading
from typing import Dict, Any
from src.utils.redis_store import RedisTaskStore


class WorkflowMonitor:
    """工作流监控器"""

    def __init__(self):
        self.task_store = RedisTaskStore()
        self.running = False
        self.monitor_thread = None

    def start_monitoring(self):
        """启动监控线程"""
        self.running = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        print("[Monitor] 监控服务已启动")

    def _monitor_loop(self):
        """监控主循环"""
        while self.running:
            try:
                # 获取所有待处理任务
                pending_tasks = self.task_store.get_tasks_by_status("pending")
                processing_tasks = self.task_store.get_tasks_by_status("processing")

                # 打印监控信息
                print(f"\n[Monitor] 待处理任务: {len(pending_tasks)} | 处理中任务: {len(processing_tasks)}")

                # 检查长时间运行的任务（超过5分钟）
                current_time = time.time()
                for task in processing_tasks:
                    if current_time - task.get('start_time', 0) > 300:  # 5分钟
                        print(f"[Monitor] ⚠️ 警告: 任务 {task['product_id']} 运行时间过长")

            except Exception as e:
                print(f"[Monitor] 监控异常: {e}")

            time.sleep(10)  # 每10秒检查一次

    def stop_monitoring(self):
        """停止监控"""
        self.running = False
        if self.monitor_thread:
            self.monitor_thread.join()
        print("[Monitor] 监控服务已停止")