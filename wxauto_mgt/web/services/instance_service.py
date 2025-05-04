"""
实例服务

提供wxauto实例的业务逻辑服务，包括获取实例列表、添加实例、更新实例和删除实例等功能。
"""

import logging
import time
import uuid
from typing import List, Optional, Dict, Any

from wxauto_mgt.data.db_manager import db_manager
from ..models.instance import InstanceCreate, InstanceUpdate, InstanceResponse, InstanceStatus

logger = logging.getLogger(__name__)

class InstanceService:
    """实例服务类"""
    
    async def get_instances(self, skip: int = 0, limit: int = 100) -> List[InstanceResponse]:
        """
        获取实例列表
        
        Args:
            skip: 跳过的记录数
            limit: 返回的最大记录数
            
        Returns:
            List[InstanceResponse]: 实例列表
        """
        try:
            # 查询数据库
            instances = await db_manager.fetchall(
                "SELECT * FROM instances ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (limit, skip)
            )
            
            # 转换为响应模型
            result = []
            for instance in instances:
                result.append(InstanceResponse(
                    instance_id=instance["instance_id"],
                    name=instance["name"],
                    base_url=instance["base_url"],
                    status=InstanceStatus(instance["status"]),
                    enabled=bool(instance["enabled"]),
                    last_active=instance["last_active"],
                    created_at=instance["created_at"],
                    updated_at=instance["updated_at"],
                    config=instance.get("config", {})
                ))
            
            return result
        
        except Exception as e:
            logger.error(f"获取实例列表失败: {e}")
            raise
    
    async def get_instance(self, instance_id: str) -> Optional[InstanceResponse]:
        """
        获取特定实例
        
        Args:
            instance_id: 实例ID
            
        Returns:
            Optional[InstanceResponse]: 实例信息，如果不存在则返回None
        """
        try:
            # 查询数据库
            instance = await db_manager.fetchone(
                "SELECT * FROM instances WHERE instance_id = ?",
                (instance_id,)
            )
            
            if not instance:
                return None
            
            # 转换为响应模型
            return InstanceResponse(
                instance_id=instance["instance_id"],
                name=instance["name"],
                base_url=instance["base_url"],
                status=InstanceStatus(instance["status"]),
                enabled=bool(instance["enabled"]),
                last_active=instance["last_active"],
                created_at=instance["created_at"],
                updated_at=instance["updated_at"],
                config=instance.get("config", {})
            )
        
        except Exception as e:
            logger.error(f"获取实例 {instance_id} 失败: {e}")
            raise
    
    async def create_instance(self, instance: InstanceCreate) -> InstanceResponse:
        """
        创建新实例
        
        Args:
            instance: 实例创建数据
            
        Returns:
            InstanceResponse: 创建的实例信息
        """
        try:
            # 生成实例ID
            instance_id = str(uuid.uuid4())
            now = int(time.time())
            
            # 准备数据
            data = {
                "instance_id": instance_id,
                "name": instance.name,
                "base_url": instance.base_url,
                "api_key": instance.api_key,
                "status": InstanceStatus.INACTIVE.value,
                "enabled": 1,
                "created_at": now,
                "updated_at": now,
                "config": instance.config or {}
            }
            
            # 插入数据库
            await db_manager.insert("instances", data)
            
            # 返回创建的实例
            return InstanceResponse(
                instance_id=instance_id,
                name=instance.name,
                base_url=instance.base_url,
                status=InstanceStatus.INACTIVE,
                enabled=True,
                created_at=now,
                updated_at=now,
                config=instance.config or {}
            )
        
        except Exception as e:
            logger.error(f"创建实例失败: {e}")
            raise
    
    async def update_instance(self, instance_id: str, instance: InstanceUpdate) -> Optional[InstanceResponse]:
        """
        更新实例
        
        Args:
            instance_id: 实例ID
            instance: 实例更新数据
            
        Returns:
            Optional[InstanceResponse]: 更新后的实例信息，如果不存在则返回None
        """
        try:
            # 检查实例是否存在
            existing = await self.get_instance(instance_id)
            if not existing:
                return None
            
            # 准备更新数据
            update_data = {}
            if instance.name is not None:
                update_data["name"] = instance.name
            if instance.base_url is not None:
                update_data["base_url"] = instance.base_url
            if instance.api_key is not None:
                update_data["api_key"] = instance.api_key
            if instance.enabled is not None:
                update_data["enabled"] = 1 if instance.enabled else 0
            if instance.config is not None:
                update_data["config"] = instance.config
            
            # 添加更新时间
            update_data["updated_at"] = int(time.time())
            
            # 更新数据库
            if update_data:
                await db_manager.update("instances", update_data, {"instance_id": instance_id})
            
            # 返回更新后的实例
            return await self.get_instance(instance_id)
        
        except Exception as e:
            logger.error(f"更新实例 {instance_id} 失败: {e}")
            raise
    
    async def delete_instance(self, instance_id: str) -> bool:
        """
        删除实例
        
        Args:
            instance_id: 实例ID
            
        Returns:
            bool: 是否成功删除
        """
        try:
            # 检查实例是否存在
            existing = await self.get_instance(instance_id)
            if not existing:
                return False
            
            # 删除数据库记录
            await db_manager.delete("instances", {"instance_id": instance_id})
            
            return True
        
        except Exception as e:
            logger.error(f"删除实例 {instance_id} 失败: {e}")
            raise
    
    async def update_instance_status(self, instance_id: str, status: InstanceStatus) -> Optional[InstanceResponse]:
        """
        更新实例状态
        
        Args:
            instance_id: 实例ID
            status: 新状态
            
        Returns:
            Optional[InstanceResponse]: 更新后的实例信息，如果不存在则返回None
        """
        try:
            # 检查实例是否存在
            existing = await self.get_instance(instance_id)
            if not existing:
                return None
            
            # 更新状态
            now = int(time.time())
            await db_manager.update(
                "instances",
                {"status": status.value, "updated_at": now, "last_active": now},
                {"instance_id": instance_id}
            )
            
            # 返回更新后的实例
            return await self.get_instance(instance_id)
        
        except Exception as e:
            logger.error(f"更新实例 {instance_id} 状态失败: {e}")
            raise
    
    async def get_instance_metrics(self, instance_id: str) -> Optional[Dict[str, Any]]:
        """
        获取实例性能指标
        
        Args:
            instance_id: 实例ID
            
        Returns:
            Optional[Dict[str, Any]]: 性能指标数据，如果不存在则返回None
        """
        try:
            # 检查实例是否存在
            existing = await self.get_instance(instance_id)
            if not existing:
                return None
            
            # 查询最近的性能指标
            metrics = await db_manager.fetchall(
                """
                SELECT metric_type, value, create_time
                FROM performance_metrics
                WHERE instance_id = ?
                ORDER BY create_time DESC
                LIMIT 100
                """,
                (instance_id,)
            )
            
            # 处理指标数据
            result = {
                "cpu_usage": [],
                "memory_usage": [],
                "timestamps": []
            }
            
            for metric in metrics:
                metric_type = metric["metric_type"]
                if metric_type == "cpu_usage":
                    result["cpu_usage"].append(metric["value"])
                elif metric_type == "memory_usage":
                    result["memory_usage"].append(metric["value"])
                
                # 添加时间戳
                if metric_type == "cpu_usage":  # 只添加一次时间戳
                    result["timestamps"].append(metric["create_time"])
            
            return result
        
        except Exception as e:
            logger.error(f"获取实例 {instance_id} 性能指标失败: {e}")
            raise
