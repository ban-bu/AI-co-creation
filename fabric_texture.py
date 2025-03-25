from PIL import Image, ImageDraw, ImageFilter, ImageChops, ImageOps
import os
import streamlit as st
import numpy as np
import random

def generate_fabric_texture(image, fabric_type, intensity=0.5):
    """
    生成程序化面料纹理并应用到图像
    
    参数:
    image - PIL图像对象
    fabric_type - 面料类型字符串
    intensity - 纹理强度，默认值调整为0.5
    
    返回:
    应用了纹理的图像
    """
    width, height = image.size
    
    # 根据面料类型调整纹理强度
    fabric_intensity = {
        "Cotton": 0.6,         # 棉布纹理较明显
        "Polyester": 0.4,      # 聚酯纤维较平滑
        "Linen": 0.7,          # 亚麻布纹理很明显
        "Jersey": 0.5,         # 针织面料中等纹理
        "Bamboo": 0.55,        # 竹纤维中等偏上
        "Cotton-Polyester Blend": 0.5  # 混纺中等
    }.get(fabric_type, intensity)
    
    # 使用调整后的强度
    actual_intensity = fabric_intensity
    
    # 创建纹理图像（透明）
    texture = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(texture)
    
    # 根据面料类型生成不同的纹理
    if fabric_type == "Cotton":
        # 棉布：密集随机点模式
        for _ in range(width * height // 50):  # 增加点的数量
            x = np.random.randint(0, width)
            y = np.random.randint(0, height)
            size = np.random.randint(1, 4)  # 增加最大点大小
            # 使用更明显的纹理颜色
            color = (150, 150, 150, int(100 * actual_intensity))
            draw.ellipse([x, y, x+size, y+size], fill=color)
            
    elif fabric_type == "Polyester":
        # 聚酯纤维：更多光滑的纹理线条
        for _ in range(width // 2):  # 增加线条数量
            x1 = np.random.randint(0, width)
            y1 = np.random.randint(0, height)
            x2 = x1 + np.random.randint(-30, 30)
            y2 = y1 + np.random.randint(-30, 30)
            color = (140, 140, 140, int(80 * actual_intensity))
            draw.line([x1, y1, x2, y2], fill=color, width=1)
    
    elif fabric_type == "Linen":
        # 亚麻布：更明显的交叉纹理线
        for i in range(0, width, 4):  # 减小间距增加密度
            draw.line([i, 0, i, height], fill=(160, 155, 145, int(110 * actual_intensity)), width=1)
        for i in range(0, height, 4):
            draw.line([0, i, width, i], fill=(160, 155, 145, int(110 * actual_intensity)), width=1)
    
    elif fabric_type == "Jersey":
        # 针织面料：更密集的网格
        for y in range(0, height, 3):  # 减小间距
            for x in range(0, width, 3):
                if (x + y) % 6 == 0:  # 增加点的密度
                    size = 2  # 增加点的大小
                    draw.ellipse([x, y, x+size, y+size], fill=(140, 140, 140, int(120 * actual_intensity)))
    
    elif fabric_type == "Bamboo":
        # 竹纤维：更明显的竖条纹
        for i in range(0, width, 6):  # 减小间距
            draw.line([i, 0, i, height], fill=(180, 180, 170, int(100 * actual_intensity)), width=2)
            # 添加一些水平的细线
            if i % 18 == 0:
                for j in range(0, height, 20):
                    draw.line([0, j, width, j], fill=(180, 180, 170, int(80 * actual_intensity)), width=1)
            
    else:  # Cotton-Polyester Blend 或其他
        # 增强混合纹理
        for _ in range(width * height // 100):  # 增加点的数量
            x = np.random.randint(0, width)
            y = np.random.randint(0, height)
            size = np.random.randint(1, 4)
            draw.ellipse([x, y, x+size, y+size], fill=(160, 160, 160, int(90 * actual_intensity)))
        for i in range(0, width, 10):  # 减小线间距
            draw.line([i, 0, i, height], fill=(160, 160, 160, int(60 * actual_intensity)), width=1)
    
    # 减少模糊程度，使纹理更加锐利
    texture = texture.filter(ImageFilter.GaussianBlur(radius=0.5))
    
    # 创建两个纹理图层，增加视觉深度
    texture2 = texture.copy()
    texture2 = texture2.filter(ImageFilter.GaussianBlur(radius=1.5))
    
    # 创建保存原图像的副本
    result = image.copy()
    
    # ----- 改进的纹理应用方法 -----
    # 使用多阶段纹理应用，确保边缘保留清晰
    
    # 1. 识别T恤区域（非透明部分）和边缘区域（暗色区域）
    # 创建三个掩码: 
    # - 整个T恤区域的掩码
    # - 边缘区域的掩码
    # - 只有面料（非边缘）区域的掩码
    tshirt_mask = Image.new("L", (width, height), 0)  # 整个T恤
    edge_mask = Image.new("L", (width, height), 0)    # 边缘
    fabric_mask = Image.new("L", (width, height), 0)  # 面料区域
    
    tshirt_draw = ImageDraw.Draw(tshirt_mask)
    edge_draw = ImageDraw.Draw(edge_mask)
    fabric_draw = ImageDraw.Draw(fabric_mask)
    
    # 边缘检测参数
    edge_threshold = 40  # 更低的值能更好地捕捉边缘
    fabric_threshold = 100  # 明确的面料区域
    
    # 扫描图像以识别不同区域
    for y in range(height):
        for x in range(width):
            try:
                pixel = image.getpixel((x, y))
                if len(pixel) == 4:  # RGBA
                    r, g, b, a = pixel
                    if a > 0:  # 非透明像素 - T恤区域
                        brightness = (r + g + b) / 3
                        
                        # 整个T恤区域掩码
                        tshirt_draw.point((x, y), fill=255)
                        
                        # 边缘区域 - 暗色
                        if brightness <= edge_threshold:
                            edge_draw.point((x, y), fill=255)
                        
                        # 面料区域 - 非边缘
                        if brightness > edge_threshold:
                            # 根据亮度调整纹理强度
                            intensity_factor = min(1.0, brightness / 255)
                            fabric_draw.point((x, y), fill=int(255 * intensity_factor))
                else:  # RGB
                    r, g, b = pixel
                    brightness = (r + g + b) / 3
                    
                    # 同样处理RGB像素
                    tshirt_draw.point((x, y), fill=255)
                    
                    if brightness <= edge_threshold:
                        edge_draw.point((x, y), fill=255)
                    
                    if brightness > edge_threshold:
                        intensity_factor = min(1.0, brightness / 255)
                        fabric_draw.point((x, y), fill=int(255 * intensity_factor))
            except:
                continue
    
    # 扩大边缘区域，确保边缘完全被保护
    edge_mask = edge_mask.filter(ImageFilter.MaxFilter(3))
    
    # 确保面料区域不包含边缘区域
    for y in range(height):
        for x in range(width):
            if edge_mask.getpixel((x, y)) > 0:
                fabric_draw.point((x, y), fill=0)
    
    # 2. 仅将纹理应用于面料区域
    # 为了更好的视觉效果，稍微模糊面料掩码以平滑过渡
    fabric_mask = fabric_mask.filter(ImageFilter.GaussianBlur(radius=1))
    
    # 将第一层纹理应用到面料区域
    result.paste(texture, (0, 0), fabric_mask)
    
    # 创建纹理的暗部效果，增强立体感
    shadow_texture = Image.new("RGBA", texture.size, (0, 0, 0, 0))
    shadow_data = []
    
    # 调整纹理的暗部，减少透明度
    texture_data = texture.getdata()
    for item in texture_data:
        r, g, b, a = item
        # 降低亮度和透明度
        shadow_data.append((r//2, g//2, b//2, a//3))
    
    shadow_texture.putdata(shadow_data)
    
    # 创建暗部的掩码 - 与面料掩码类似但强度较低
    shadow_mask = Image.new("L", fabric_mask.size, 0)
    shadow_mask_data = fabric_mask.getdata()
    new_mask_data = []
    
    for item in shadow_mask_data:
        new_mask_data.append(item // 2)  # 减少强度
    
    shadow_mask.putdata(new_mask_data)
    
    # 应用暗部纹理以增加深度
    result.paste(shadow_texture, (0, 0), shadow_mask)
    
    # 确保边缘保持完全不变
    # 获取原始图像的边缘部分
    edge_region = image.copy()
    
    # 将原始边缘区域粘贴回结果图像，完全覆盖可能受到纹理影响的边缘
    result.paste(edge_region, (0, 0), edge_mask)
    
    return result

# 导出apply_fabric_texture函数作为主接口，使用程序生成的纹理
def apply_fabric_texture(image, fabric_type, intensity=0.5):
    """
    应用面料纹理到T恤图像的主接口函数
    
    参数:
    image - PIL图像对象
    fabric_type - 面料类型
    intensity - 纹理强度，默认值调整为0.5
    """
    try:
        return generate_fabric_texture(image, fabric_type, intensity)
    except Exception as e:
        st.error(f"应用纹理时出错: {e}")
        return image  # 如果出错，返回原始图像
