#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
生成绿色微信风格的应用图标
"""

import os
from PIL import Image, ImageDraw, ImageFont
import math

def create_wechat_style_icon(size=256, output_path="wxauto_mgt/resources/icons/app_icon.ico"):
    """创建绿色微信风格的图标"""
    
    # 创建图像
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # 微信绿色
    wechat_green = (7, 193, 96)  # #07C160
    dark_green = (5, 150, 75)   # 深一点的绿色用于阴影
    white = (255, 255, 255)
    
    # 绘制圆角矩形背景
    corner_radius = size // 8
    margin = size // 20
    
    # 绘制阴影效果
    shadow_offset = size // 40
    draw.rounded_rectangle(
        [margin + shadow_offset, margin + shadow_offset, 
         size - margin + shadow_offset, size - margin + shadow_offset],
        radius=corner_radius,
        fill=(0, 0, 0, 50)  # 半透明黑色阴影
    )
    
    # 绘制主背景
    draw.rounded_rectangle(
        [margin, margin, size - margin, size - margin],
        radius=corner_radius,
        fill=wechat_green
    )
    
    # 绘制渐变效果（简化版）
    for i in range(5):
        alpha = 30 - i * 5
        draw.rounded_rectangle(
            [margin + i, margin + i, size - margin - i, size - margin - i],
            radius=corner_radius - i,
            outline=(*wechat_green, alpha),
            width=1
        )
    
    # 绘制聊天气泡图标
    center_x, center_y = size // 2, size // 2
    bubble_size = size // 3
    
    # 主聊天气泡
    bubble1_x = center_x - bubble_size // 4
    bubble1_y = center_y - bubble_size // 6
    bubble1_size = bubble_size
    
    draw.ellipse(
        [bubble1_x - bubble1_size // 2, bubble1_y - bubble1_size // 2,
         bubble1_x + bubble1_size // 2, bubble1_y + bubble1_size // 2],
        fill=white
    )
    
    # 小聊天气泡
    bubble2_x = center_x + bubble_size // 3
    bubble2_y = center_y + bubble_size // 4
    bubble2_size = bubble_size // 2
    
    draw.ellipse(
        [bubble2_x - bubble2_size // 2, bubble2_y - bubble2_size // 2,
         bubble2_x + bubble2_size // 2, bubble2_y + bubble2_size // 2],
        fill=white
    )
    
    # 绘制聊天气泡的小尾巴
    tail_points = [
        (bubble1_x + bubble1_size // 3, bubble1_y + bubble1_size // 3),
        (bubble1_x + bubble1_size // 2, bubble1_y + bubble1_size // 2),
        (bubble1_x + bubble1_size // 4, bubble1_y + bubble1_size // 2)
    ]
    draw.polygon(tail_points, fill=white)
    
    # 在气泡内绘制小点表示文字
    dot_size = size // 40
    for i, (dx, dy) in enumerate([(-15, -8), (0, -8), (15, -8)]):
        dot_x = bubble1_x + dx * size // 256
        dot_y = bubble1_y + dy * size // 256
        draw.ellipse(
            [dot_x - dot_size, dot_y - dot_size, dot_x + dot_size, dot_y + dot_size],
            fill=wechat_green
        )
    
    # 在小气泡内绘制一个小点
    small_dot_size = size // 60
    draw.ellipse(
        [bubble2_x - small_dot_size, bubble2_y - small_dot_size,
         bubble2_x + small_dot_size, bubble2_y + small_dot_size],
        fill=wechat_green
    )
    
    # 添加高光效果
    highlight_size = size // 6
    highlight_x = margin + size // 4
    highlight_y = margin + size // 4
    
    # 创建高光渐变
    highlight = Image.new('RGBA', (highlight_size, highlight_size), (0, 0, 0, 0))
    highlight_draw = ImageDraw.Draw(highlight)
    
    for i in range(highlight_size // 2):
        alpha = int(30 * (1 - i / (highlight_size // 2)))
        highlight_draw.ellipse(
            [i, i, highlight_size - i, highlight_size - i],
            fill=(255, 255, 255, alpha)
        )
    
    # 将高光合并到主图像
    img.paste(highlight, (highlight_x, highlight_y), highlight)
    
    # 确保输出目录存在
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    # 创建多种尺寸的图标
    sizes = [16, 32, 48, 64, 128, 256]
    images = []
    
    for icon_size in sizes:
        resized = img.resize((icon_size, icon_size), Image.Resampling.LANCZOS)
        images.append(resized)
    
    # 保存为ICO文件
    images[0].save(
        output_path,
        format='ICO',
        sizes=[(s, s) for s in sizes],
        append_images=images[1:]
    )
    
    # 也保存为PNG文件用于预览
    png_path = output_path.replace('.ico', '.png')
    img.save(png_path, format='PNG')
    
    print(f"图标已生成:")
    print(f"  ICO文件: {output_path}")
    print(f"  PNG文件: {png_path}")
    
    return output_path

def main():
    """主函数"""
    print("正在生成绿色微信风格图标...")
    
    try:
        icon_path = create_wechat_style_icon()
        print("图标生成成功！")
        return True
    except Exception as e:
        print(f"图标生成失败: {e}")
        return False

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
