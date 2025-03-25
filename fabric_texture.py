from PIL import Image, ImageDraw, ImageFilter
import os
import streamlit as st
import numpy as np
import random

def generate_fabric_texture(image, fabric_type, intensity=0.3):
    """
    生成程序化面料纹理并应用到图像
    
    参数:
    image - PIL图像对象
    fabric_type - 面料类型字符串
    intensity - 纹理强度
    
    返回:
    应用了纹理的图像
    """
    width, height = image.size
    
    # 创建纹理图像（透明）
    texture = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(texture)
    
    # 根据面料类型生成不同的纹理
    if fabric_type == "Cotton":
        # 棉布：细小随机点
        for _ in range(width * height // 100):
            x = np.random.randint(0, width)
            y = np.random.randint(0, height)
            size = np.random.randint(1, 3)
            color = (200, 200, 200, int(60 * intensity))
            draw.ellipse([x, y, x+size, y+size], fill=color)
            
    elif fabric_type == "Polyester":
        # 聚酯纤维：光滑的纹理，少量细线
        for _ in range(width // 3):
            x1 = np.random.randint(0, width)
            y1 = np.random.randint(0, height)
            x2 = x1 + np.random.randint(-20, 20)
            y2 = y1 + np.random.randint(-20, 20)
            color = (180, 180, 180, int(40 * intensity))
            draw.line([x1, y1, x2, y2], fill=color, width=1)
    
    elif fabric_type == "Linen":
        # 亚麻布：交叉纹理线
        for i in range(0, width, 5):
            draw.line([i, 0, i, height], fill=(180, 175, 165, int(70 * intensity)), width=1)
        for i in range(0, height, 5):
            draw.line([0, i, width, i], fill=(180, 175, 165, int(70 * intensity)), width=1)
    
    elif fabric_type == "Jersey":
        # 针织面料：细小网格
        for y in range(0, height, 4):
            for x in range(0, width, 4):
                if (x + y) % 8 == 0:
                    draw.point((x, y), fill=(180, 180, 180, int(70 * intensity)))
    
    elif fabric_type == "Bamboo":
        # 竹纤维：竖条纹
        for i in range(0, width, 8):
            draw.line([i, 0, i, height], fill=(200, 200, 190, int(60 * intensity)), width=2)
            
    else:  # Cotton-Polyester Blend 或其他
        # 混合纹理
        for _ in range(width * height // 200):
            x = np.random.randint(0, width)
            y = np.random.randint(0, height)
            size = np.random.randint(1, 3)
            draw.ellipse([x, y, x+size, y+size], fill=(200, 200, 200, int(50 * intensity)))
        for i in range(0, width, 15):
            draw.line([i, 0, i, height], fill=(200, 200, 200, int(30 * intensity)), width=1)
    
    # 对纹理进行模糊处理，使其看起来更自然
    texture = texture.filter(ImageFilter.GaussianBlur(radius=1))
    
    # 创建掩码，只在T恤区域应用纹理
    mask = Image.new("L", (width, height), 0)
    mask_draw = ImageDraw.Draw(mask)
    
    # 获取所有白色/浅色区域
    threshold = 200
    for y in range(height):
        for x in range(width):
            try:
                r, g, b, a = image.getpixel((x, y))
                if r > threshold and g > threshold and b > threshold and a > 0:
                    mask_draw.point((x, y), fill=255)
            except:
                continue
    
    # 应用纹理
    result = image.copy()
    result.paste(texture, (0, 0), mask)
    
    return result

# 导出apply_fabric_texture函数作为主接口，使用程序生成的纹理
def apply_fabric_texture(image, fabric_type, intensity=0.3):
    """应用面料纹理到T恤图像的主接口函数"""
    return generate_fabric_texture(image, fabric_type, intensity)
