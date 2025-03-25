from PIL import Image, ImageDraw, ImageFilter, ImageChops, ImageOps
import os
import streamlit as st
import numpy as np
import random

def generate_fabric_texture(image, fabric_type, intensity=0.7):
    """
    生成程序化面料纹理并应用到图像
    
    参数:
    image - PIL图像对象
    fabric_type - 面料类型字符串
    intensity - 纹理强度，默认值从0.3增加到0.7
    
    返回:
    应用了纹理的图像
    """
    width, height = image.size
    
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
            color = (150, 150, 150, int(100 * intensity))
            draw.ellipse([x, y, x+size, y+size], fill=color)
            
    elif fabric_type == "Polyester":
        # 聚酯纤维：更多光滑的纹理线条
        for _ in range(width // 2):  # 增加线条数量
            x1 = np.random.randint(0, width)
            y1 = np.random.randint(0, height)
            x2 = x1 + np.random.randint(-30, 30)
            y2 = y1 + np.random.randint(-30, 30)
            color = (140, 140, 140, int(80 * intensity))
            draw.line([x1, y1, x2, y2], fill=color, width=1)
    
    elif fabric_type == "Linen":
        # 亚麻布：更明显的交叉纹理线
        for i in range(0, width, 4):  # 减小间距增加密度
            draw.line([i, 0, i, height], fill=(160, 155, 145, int(110 * intensity)), width=1)
        for i in range(0, height, 4):
            draw.line([0, i, width, i], fill=(160, 155, 145, int(110 * intensity)), width=1)
    
    elif fabric_type == "Jersey":
        # 针织面料：更密集的网格
        for y in range(0, height, 3):  # 减小间距
            for x in range(0, width, 3):
                if (x + y) % 6 == 0:  # 增加点的密度
                    size = 2  # 增加点的大小
                    draw.ellipse([x, y, x+size, y+size], fill=(140, 140, 140, int(120 * intensity)))
    
    elif fabric_type == "Bamboo":
        # 竹纤维：更明显的竖条纹
        for i in range(0, width, 6):  # 减小间距
            draw.line([i, 0, i, height], fill=(180, 180, 170, int(100 * intensity)), width=2)
            # 添加一些水平的细线
            if i % 18 == 0:
                for j in range(0, height, 20):
                    draw.line([0, j, width, j], fill=(180, 180, 170, int(80 * intensity)), width=1)
            
    else:  # Cotton-Polyester Blend 或其他
        # 增强混合纹理
        for _ in range(width * height // 100):  # 增加点的数量
            x = np.random.randint(0, width)
            y = np.random.randint(0, height)
            size = np.random.randint(1, 4)
            draw.ellipse([x, y, x+size, y+size], fill=(160, 160, 160, int(90 * intensity)))
        for i in range(0, width, 10):  # 减小线间距
            draw.line([i, 0, i, height], fill=(160, 160, 160, int(60 * intensity)), width=1)
    
    # 减少模糊程度，使纹理更加锐利
    texture = texture.filter(ImageFilter.GaussianBlur(radius=0.5))
    
    # 创建两个纹理图层，增加视觉深度
    texture2 = texture.copy()
    texture2 = texture2.filter(ImageFilter.GaussianBlur(radius=1.5))
    
    # 创建掩码，只在T恤区域应用纹理
    mask = Image.new("L", (width, height), 0)
    mask_draw = ImageDraw.Draw(mask)
    
    # 获取所有非透明区域作为掩码，但排除黑色边框
    # 黑色边框阈值 - 用于识别边框
    dark_threshold = 60  # 较低的值表示暗色，如黑色边框
    
    for y in range(height):
        for x in range(width):
            try:
                pixel = image.getpixel((x, y))
                if len(pixel) == 4:  # RGBA
                    r, g, b, a = pixel
                    if a > 0:  # 任何非完全透明的区域
                        brightness = (r + g + b) / 3
                        # 排除黑色边框 - 只在非黑色区域应用纹理
                        if brightness > dark_threshold:
                            # 根据颜色亮度调整纹理强度
                            intensity_factor = 1.0 if brightness > 100 else 0.8
                            mask_draw.point((x, y), fill=int(255 * intensity_factor))
                else:  # RGB
                    r, g, b = pixel
                    brightness = (r + g + b) / 3
                    # 排除黑色边框
                    if brightness > dark_threshold:
                        intensity_factor = 1.0 if brightness > 100 else 0.8
                        mask_draw.point((x, y), fill=int(255 * intensity_factor))
            except:
                continue
    
    # 应用纹理 - 先应用第一层
    result = image.copy()
    result.paste(texture, (0, 0), mask)
    
    # 再应用第二层纹理，增加深度效果，但避免使用可能不可用的函数
    mask_inv = Image.new("L", mask.size, 0)
    mask_inv_draw = ImageDraw.Draw(mask_inv)
    
    # 手动创建反转掩码
    for y in range(height):
        for x in range(width):
            try:
                v = mask.getpixel((x, y))
                mask_inv_draw.point((x, y), fill=255-v)
            except:
                continue
                
    # 将第二层纹理应用到结果上，但使用较低的透明度
    texture2_faded = Image.new("RGBA", texture2.size, (0, 0, 0, 0))
    texture2_data = texture2.getdata()
    new_data = []
    
    for item in texture2_data:
        r, g, b, a = item
        new_data.append((r, g, b, int(a * 0.5)))  # 减少第二层纹理的透明度
        
    texture2_faded.putdata(new_data)
    result.paste(texture2_faded, (0, 0), mask_inv)
    
    return result

# 导出apply_fabric_texture函数作为主接口，使用程序生成的纹理
def apply_fabric_texture(image, fabric_type, intensity=0.7):
    """
    应用面料纹理到T恤图像的主接口函数
    
    参数:
    image - PIL图像对象
    fabric_type - 面料类型
    intensity - 纹理强度，默认值从0.3增加到0.7
    """
    try:
        return generate_fabric_texture(image, fabric_type, intensity)
    except Exception as e:
        st.error(f"应用纹理时出错: {e}")
        return image  # 如果出错，返回原始图像
