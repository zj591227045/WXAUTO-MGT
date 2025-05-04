"""
实例管理API

提供wxauto实例的管理接口，包括获取实例列表、添加实例、更新实例和删除实例等功能。
"""

import logging
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel

# 导入服务层
from ..services.instance_service import InstanceService
from ..models.instance import InstanceCreate, InstanceUpdate, InstanceResponse, InstanceStatus
from ..security import get_current_user, User

logger = logging.getLogger(__name__)

router = APIRouter()

@router.get("/", response_model=List[InstanceResponse])
async def get_instances(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    current_user: User = Depends(get_current_user)
):
    """
    获取所有实例
    
    Args:
        skip: 跳过的记录数
        limit: 返回的最大记录数
        current_user: 当前用户
        
    Returns:
        List[InstanceResponse]: 实例列表
    """
    try:
        service = InstanceService()
        instances = await service.get_instances(skip, limit)
        return instances
    except Exception as e:
        logger.error(f"获取实例列表失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取实例列表失败: {str(e)}")

@router.get("/{instance_id}", response_model=InstanceResponse)
async def get_instance(
    instance_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    获取特定实例
    
    Args:
        instance_id: 实例ID
        current_user: 当前用户
        
    Returns:
        InstanceResponse: 实例信息
    """
    try:
        service = InstanceService()
        instance = await service.get_instance(instance_id)
        if not instance:
            raise HTTPException(status_code=404, detail=f"实例 {instance_id} 不存在")
        return instance
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取实例 {instance_id} 失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取实例失败: {str(e)}")

@router.post("/", response_model=InstanceResponse, status_code=201)
async def create_instance(
    instance: InstanceCreate,
    current_user: User = Depends(get_current_user)
):
    """
    创建新实例
    
    Args:
        instance: 实例创建数据
        current_user: 当前用户
        
    Returns:
        InstanceResponse: 创建的实例信息
    """
    try:
        service = InstanceService()
        created_instance = await service.create_instance(instance)
        return created_instance
    except Exception as e:
        logger.error(f"创建实例失败: {e}")
        raise HTTPException(status_code=500, detail=f"创建实例失败: {str(e)}")

@router.put("/{instance_id}", response_model=InstanceResponse)
async def update_instance(
    instance_id: str,
    instance: InstanceUpdate,
    current_user: User = Depends(get_current_user)
):
    """
    更新实例
    
    Args:
        instance_id: 实例ID
        instance: 实例更新数据
        current_user: 当前用户
        
    Returns:
        InstanceResponse: 更新后的实例信息
    """
    try:
        service = InstanceService()
        updated_instance = await service.update_instance(instance_id, instance)
        if not updated_instance:
            raise HTTPException(status_code=404, detail=f"实例 {instance_id} 不存在")
        return updated_instance
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新实例 {instance_id} 失败: {e}")
        raise HTTPException(status_code=500, detail=f"更新实例失败: {str(e)}")

@router.delete("/{instance_id}", status_code=204)
async def delete_instance(
    instance_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    删除实例
    
    Args:
        instance_id: 实例ID
        current_user: 当前用户
    """
    try:
        service = InstanceService()
        success = await service.delete_instance(instance_id)
        if not success:
            raise HTTPException(status_code=404, detail=f"实例 {instance_id} 不存在")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除实例 {instance_id} 失败: {e}")
        raise HTTPException(status_code=500, detail=f"删除实例失败: {str(e)}")

@router.patch("/{instance_id}/status", response_model=InstanceResponse)
async def update_instance_status(
    instance_id: str,
    status: InstanceStatus,
    current_user: User = Depends(get_current_user)
):
    """
    更新实例状态
    
    Args:
        instance_id: 实例ID
        status: 新状态
        current_user: 当前用户
        
    Returns:
        InstanceResponse: 更新后的实例信息
    """
    try:
        service = InstanceService()
        updated_instance = await service.update_instance_status(instance_id, status)
        if not updated_instance:
            raise HTTPException(status_code=404, detail=f"实例 {instance_id} 不存在")
        return updated_instance
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新实例 {instance_id} 状态失败: {e}")
        raise HTTPException(status_code=500, detail=f"更新实例状态失败: {str(e)}")

@router.get("/{instance_id}/metrics", response_model=dict)
async def get_instance_metrics(
    instance_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    获取实例性能指标
    
    Args:
        instance_id: 实例ID
        current_user: 当前用户
        
    Returns:
        dict: 性能指标数据
    """
    try:
        service = InstanceService()
        metrics = await service.get_instance_metrics(instance_id)
        if not metrics:
            raise HTTPException(status_code=404, detail=f"实例 {instance_id} 不存在或无性能指标")
        return metrics
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取实例 {instance_id} 性能指标失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取实例性能指标失败: {str(e)}")
