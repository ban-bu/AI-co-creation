import streamlit as st
from PIL import Image, ImageDraw
import requests
from io import BytesIO
import os  # 确保os模块在这里导入
# 添加try-except导入cairosvg，避免因缺少这个库而导致整个应用崩溃
try:
    import cairosvg
    CAIROSVG_AVAILABLE = True
except ImportError:
    CAIROSVG_AVAILABLE = False
    # 尝试导入备选SVG处理库
    try:
        from svglib.svglib import svg2rlg
        from reportlab.graphics import renderPM
        SVGLIB_AVAILABLE = True
    except ImportError:
        SVGLIB_AVAILABLE = False
        st.warning("SVG处理库未安装，SVG格式转换功能将不可用")
from openai import OpenAI
from streamlit_image_coordinates import streamlit_image_coordinates
import re
import math

# API配置信息 - 实际使用时应从主文件传入或使用环境变量
API_KEY = "sk-lNVAREVHjj386FDCd9McOL7k66DZCUkTp6IbV0u9970qqdlg"
BASE_URL = "https://api.deepbricks.ai/v1/"

# GPT-4o-mini API配置
GPT4O_MINI_API_KEY = "sk-lNVAREVHjj386FDCd9McOL7k66DZCUkTp6IbV0u9970qqdlg"
GPT4O_MINI_BASE_URL = "https://api.deepbricks.ai/v1/"

# 从svg_utils导入SVG转换函数
from svg_utils import convert_svg_to_png

def get_ai_design_suggestions(user_preferences=None):
    """Get design suggestions from GPT-4o-mini"""
    client = OpenAI(api_key=GPT4O_MINI_API_KEY, base_url=GPT4O_MINI_BASE_URL)
    
    # Default prompt if no user preferences provided
    if not user_preferences:
        user_preferences = "casual fashion t-shirt design"
    
    # Construct the prompt
    prompt = f"""
    Provide T-shirt design elements for "{user_preferences}" style:

    1. Colors (3 only):
    Format exactly like this: Color name (#HEXCODE)
    Example: Blue (#0000FF)

    2. Text (2 only):
    Format exactly like this: "Text phrase"
    Example: "Just Do It"

    IMPORTANT: Only provide the colors and text phrases. No explanations, no numbering, no titles, no extra descriptions.
    """
    
    try:
        # 调用GPT-4o-mini
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a minimal T-shirt design assistant. Reply with ONLY color names with hex codes and text suggestions in quotes. FORMAT MUST BE: Color name (#HEXCODE) for colors and \"Text phrase\" for text. DO NOT add any other text, explanations, numbering, titles or formatting."},
                {"role": "user", "content": prompt}
            ]
        )
        
        # 返回建议内容
        if response.choices and len(response.choices) > 0:
            suggestion_text = response.choices[0].message.content
            
            # 简化处理逻辑，直接解析原始文本
            try:
                # 存储颜色和文本建议
                color_matches = {}
                text_matches = []
                
                # 解析颜色 - 查找形如 "Color name (#XXXXXX)" 的模式
                color_pattern = r'([^\s\(\)]+)\s*\(#([0-9A-Fa-f]{6})\)'
                color_matches = re.findall(color_pattern, suggestion_text)
                
                # 格式化颜色结果并保存到会话状态
                if color_matches:
                    color_dict = {name.strip(): f"#{code}" for name, code in color_matches}
                    st.session_state.ai_suggested_colors = color_dict
                else:
                    st.session_state.ai_suggested_colors = {}
                
                # 解析文本建议 - 先尝试查找智能引号包围的文本
                text_pattern = r'[""]([^""]+)[""]'
                text_matches = re.findall(text_pattern, suggestion_text)
                
                # 如果没找到，尝试普通引号
                if not text_matches:
                    text_pattern2 = r'"([^"]+)"'
                    text_matches = re.findall(text_pattern2, suggestion_text)
                
                # 如果仍然没找到，尝试更宽松的匹配 - 寻找冒号后的内容或破折号后的内容
                if not text_matches:
                    # 尝试识别常见的文本模式，如"Text: Some phrase"或"Text - Some phrase"
                    text_pattern3 = r'(?:Text|Phrase|Slogan|Quote|Saying)(?:\s*[:：-]\s*)[""]?([^"\r\n]+?)[""]?(?:\s*$|\s*[\.,;])'
                    text_matches = re.findall(text_pattern3, suggestion_text, re.IGNORECASE | re.MULTILINE)
                
                # 最后，如果所有方法都失败，尝试按行拆分并找出看起来像文本建议的行
                if not text_matches:
                    lines = suggestion_text.split('\n')
                    for line in lines:
                        # 排除颜色行（通常包含#和十六进制代码）
                        if '#' not in line and len(line.strip()) > 5 and not line.strip().startswith('Color'):
                            # 清理行中可能的前缀，如"1. "，"- "，"* "等
                            cleaned_line = re.sub(r'^\s*[\d\.\-\*]+\s*', '', line.strip())
                            if cleaned_line:
                                text_matches.append(cleaned_line)
                
                # 保存文本建议到会话状态
                st.session_state.ai_suggested_texts = text_matches if text_matches else []
                
                # 打印调试信息
                print(f"Parsed colors: {st.session_state.ai_suggested_colors}")
                print(f"Parsed texts: {st.session_state.ai_suggested_texts}")
                
            except Exception as e:
                print(f"解析过程出错: {e}")
                import traceback
                print(traceback.format_exc())
                st.session_state.ai_suggested_colors = {}
                st.session_state.ai_suggested_texts = []
            
            # 返回原始文本
            return suggestion_text
        else:
            return "Can not get AI suggestions, please try again later."
    except Exception as e:
        return f"Error getting AI suggestions: {str(e)}"

def generate_vector_image(prompt):
    """Generate an image based on the prompt"""
    client = OpenAI(api_key=API_KEY, base_url=BASE_URL)
    try:
        resp = client.images.generate(
            model="dall-e-3",
            prompt=prompt,
            n=1,
            size="1024x1024",
            quality="standard"
        )
    except Exception as e:
        st.error(f"Error calling API: {e}")
        return None

    if resp and len(resp.data) > 0 and resp.data[0].url:
        image_url = resp.data[0].url
        try:
            image_resp = requests.get(image_url)
            if image_resp.status_code == 200:
                content_type = image_resp.headers.get("Content-Type", "")
                if "svg" in content_type.lower():
                    # 使用集中的SVG处理函数
                    return convert_svg_to_png(image_resp.content)
                else:
                    return Image.open(BytesIO(image_resp.content)).convert("RGBA")
            else:
                st.error(f"Failed to download image, status code: {image_resp.status_code}")
        except Exception as download_err:
            st.error(f"Error requesting image: {download_err}")
    else:
        st.error("Could not get image URL from API response.")
    return None

def draw_selection_box(image, point=None):
    """Calculate position for design placement without drawing visible selection box"""
    # Create a copy to avoid modifying the original image
    img_copy = image.copy()
    
    # Fixed box size (1024 * 0.25)
    box_size = int(1024 * 0.25)
    
    # If no position is specified, place it in the center
    if point is None:
        x1 = (image.width - box_size) // 2
        y1 = (image.height - box_size) // 2
    else:
        x1, y1 = point
        # Ensure the selection box doesn't extend beyond image boundaries
        x1 = max(0, min(x1 - box_size//2, image.width - box_size))
        y1 = max(0, min(y1 - box_size//2, image.height - box_size))
    
    # Return the image without drawing any visible box, just the position
    return img_copy, (x1, y1)

def get_selection_coordinates(point=None, image_size=None):
    """Get coordinates and dimensions of fixed-size selection box"""
    box_size = int(1024 * 0.25)
    
    if point is None and image_size is not None:
        width, height = image_size
        x1 = (width - box_size) // 2
        y1 = (height - box_size) // 2
    else:
        x1, y1 = point
        # Ensure selection box doesn't extend beyond image boundaries
        if image_size:
            width, height = image_size
            x1 = max(0, min(x1 - box_size//2, width - box_size))
            y1 = max(0, min(y1 - box_size//2, height - box_size))
    
    return (x1, y1, box_size, box_size)

def match_background_to_shirt(design_image, shirt_image):
    """Adjust design image background color to match shirt"""
    # Ensure images are in RGBA mode
    design_image = design_image.convert("RGBA")
    shirt_image = shirt_image.convert("RGBA")
    
    # Get shirt background color (assuming top-left corner color)
    shirt_bg_color = shirt_image.getpixel((0, 0))
    
    # Get design image data
    datas = design_image.getdata()
    newData = []
    
    for item in datas:
        # If pixel is transparent, keep it unchanged
        if item[3] == 0:
            newData.append(item)
        else:
            # Adjust non-transparent pixel background color to match shirt
            newData.append((shirt_bg_color[0], shirt_bg_color[1], shirt_bg_color[2], item[3]))
    
    design_image.putdata(newData)
    return design_image

# 添加一个用于改变T恤颜色的函数
def change_shirt_color(image, color_hex):
    """改变T恤的颜色"""
    # 转换十六进制颜色为RGB
    color_rgb = tuple(int(color_hex.lstrip('#')[i:i+2], 16) for i in (0, 2, 4))
    
    # 创建副本避免修改原图
    colored_image = image.copy().convert("RGBA")
    
    # 获取图像数据
    data = colored_image.getdata()
    
    # 创建新数据
    new_data = []
    # 白色阈值 - 调整这个值可以控制哪些像素被视为白色/浅色并被改变
    threshold = 200
    
    for item in data:
        # 判断是否是白色/浅色区域 (RGB值都很高)
        if item[0] > threshold and item[1] > threshold and item[2] > threshold and item[3] > 0:
            # 保持原透明度，改变颜色
            new_color = (color_rgb[0], color_rgb[1], color_rgb[2], item[3])
            new_data.append(new_color)
        else:
            # 保持其他颜色不变
            new_data.append(item)
    
    # 更新图像数据
    colored_image.putdata(new_data)
    return colored_image

def get_preset_logos():
    """获取预设logo文件夹中的所有图片 - 此函数已不再使用，保留以确保兼容性"""
    # 确保os模块在这个作用域内可用
    import os
    
    logos_dir = "logos"
    preset_logos = []
    
    # 检查logos文件夹是否存在
    if not os.path.exists(logos_dir):
        os.makedirs(logos_dir)
        return preset_logos
    
    # 获取所有支持的图片文件
    for file in os.listdir(logos_dir):
        if file.lower().endswith(('.png', '.jpg', '.jpeg')):
            preset_logos.append(os.path.join(logos_dir, file))
    
    return preset_logos

# AI Customization Group design page
def show_low_complexity_general_sales():
    st.title("👕 AI Co-Creation Experiment Platform")
    st.markdown("### Low Task Complexity-General Sales - Create Your Unique T-shirt Design")
    
    # 添加General Sales情境描述
    st.info("""
    **General Sales Environment**
    
    Welcome to our regular T-shirt customization service available in our standard online store. 
    You are browsing our website from the comfort of your home or office, with no time pressure. 
    Take your time to explore the design options and create a T-shirt that matches your personal style.
    This is a typical online shopping experience where you can customize at your own pace.
    """)
    
    # 修改任务复杂度说明
    st.markdown("""
    <div style="background-color:#f0f0f0; padding:20px; border-radius:10px; margin-bottom:20px; border-left:4px solid #2196F3">
    <h4 style="color:#1976D2; margin-top:0">Basic Customization Options</h4>
    <p>In this experience, you can customize your T-shirt with the following options:</p>
    
    <div style="margin-left:15px">
    <h5 style="color:#2196F3">1. T-shirt Color Selection</h5>
    <p>Choose your preferred T-shirt color from AI recommendations, preset options, or use a custom color picker to find the perfect shade for your design.</p>
    
    <h5 style="color:#2196F3">2. Text Customization</h5>
    <p>Add personalized text with customizable font styles, sizes, colors, and special effects like shadows, outlines, or gradients to create eye-catching designs.</p>
    
    <h5 style="color:#2196F3">3. Design Positioning</h5>
    <p>Fine-tune the placement of your text elements using intuitive positioning controls and preset alignment options for perfect composition.</p>
    </div>
    
    <p style="margin-top:15px; color:#666">
    <i>💡 Tip: Start with AI suggestions for the best results, then customize further based on your preferences.</i>
    </p>
    </div>
    """, unsafe_allow_html=True)
    
    # 初始化T恤颜色状态变量
    if 'shirt_color_hex' not in st.session_state:
        st.session_state.shirt_color_hex = "#FFFFFF"  # 默认白色
    if 'original_base_image' not in st.session_state:
        st.session_state.original_base_image = None  # 保存原始白色T恤图像
    if 'base_image' not in st.session_state:
        st.session_state.base_image = None  # 确保base_image变量被初始化
    if 'current_image' not in st.session_state:
        st.session_state.current_image = None  # 确保current_image变量被初始化
    if 'final_design' not in st.session_state:
        st.session_state.final_design = None  # 确保final_design变量被初始化
    if 'ai_suggestions' not in st.session_state:
        st.session_state.ai_suggestions = None  # 存储AI建议
    
    # 重新组织布局，将预览图放在左侧，操作区放在右侧
    st.markdown("## Design Area")
    
    # 创建左右两列布局
    preview_col, controls_col = st.columns([3, 2])
    
    with preview_col:
        # T恤预览区
        st.markdown("### T-shirt Design")
        
        # Load T-shirt base image
        if st.session_state.base_image is None:
            try:
                # 确保os模块在这个作用域内可用
                import os
                
                # 加载原始白色T恤图像
                original_image_path = "white_shirt.png"
                # 检查各种可能的路径
                possible_paths = [
                    "white_shirt.png",
                    "./white_shirt.png",
                    "../white_shirt.png",
                    "low_complexity_general_sales_files/white_shirt.png",
                    "images/white_shirt.png",
                    "white_shirt1.png",
                    "white_shirt2.png"
                ]
                
                # 尝试所有可能的路径
                found = False
                for path in possible_paths:
                    if os.path.exists(path):
                        original_image_path = path
                        found = True
                        break
                
                if not found:
                    # 如果未找到，显示当前工作目录和文件列表以便调试
                    current_dir = os.getcwd()
                    st.error(f"T-shirt image not found. Current working directory: {current_dir}")
                    files = os.listdir(current_dir)
                    st.error(f"Directory contents: {files}")
                
                # 加载图像
                original_image = Image.open(original_image_path).convert("RGBA")
                
                # 保存原始白色T恤图像
                st.session_state.original_base_image = original_image.copy()
                
                # 应用当前选择的颜色
                colored_image = change_shirt_color(original_image, st.session_state.shirt_color_hex)
                st.session_state.base_image = colored_image
                
                # Initialize by drawing selection box in the center
                initial_image, initial_pos = draw_selection_box(colored_image)
                st.session_state.current_image = initial_image
                st.session_state.current_box_position = initial_pos
                
                # 设置初始最终设计为彩色T恤
                st.session_state.final_design = colored_image.copy()
            except Exception as e:
                st.error(f"Error loading t-shirt image: {e}")
                import traceback
                st.error(traceback.format_exc())
        else:
            # 添加颜色变化检测：保存当前应用的颜色，用于检查是否发生变化
            if 'current_applied_color' not in st.session_state:
                st.session_state.current_applied_color = st.session_state.shirt_color_hex
            
            # 检查颜色是否发生变化
            if st.session_state.current_applied_color != st.session_state.shirt_color_hex:
                # 颜色已变化，需要重新应用
                original_image = st.session_state.original_base_image.copy()
                colored_image = change_shirt_color(original_image, st.session_state.shirt_color_hex)
                st.session_state.base_image = colored_image
                
                # 更新当前图像和位置
                new_image, _ = draw_selection_box(colored_image, st.session_state.current_box_position)
                st.session_state.current_image = new_image
                
                # 如果有最终设计，也需要重新应用颜色
                st.session_state.final_design = colored_image.copy()
                
                # 修改颜色变更时重新应用文字的代码
                if 'applied_text' in st.session_state:
                    text_info = st.session_state.applied_text
                    
                    # 确保text_info存在且包含必要的信息
                    if text_info and isinstance(text_info, dict):
                        # 如果使用了绘图方法，同样以绘图方法重新应用
                        if text_info.get("use_drawing_method", False):
                            try:
                                # 图像尺寸
                                img_width, img_height = st.session_state.final_design.size
                                
                                # 创建小图像用于绘制文字
                                initial_text_width = min(400, img_width // 2)
                                initial_text_height = 200
                                text_img = Image.new('RGBA', (initial_text_width, initial_text_height), (0, 0, 0, 0))
                                text_draw = ImageDraw.Draw(text_img)
                                
                                # 加载字体
                                from PIL import ImageFont
                                import os
                                
                                # 创建text_info对象来存储文本信息
                                text_info = {
                                    "text": text_info["text"],
                                    "font": text_info["font"],
                                    "color": text_info["color"],
                                    "size": text_info["size"],
                                    "style": text_info["style"],
                                    "effect": text_info["effect"],
                                    "alignment": text_info["alignment"]
                                }
                                
                                # 尝试加载系统字体
                                font = None
                                try:
                                    # 确保os模块可用
                                    import os
                                    # 尝试直接加载系统字体
                                    if os.path.exists("C:/Windows/Fonts/arial.ttf"):
                                        font = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 40)
                                except Exception:
                                    pass
                                
                                # 如果系统字体加载失败，使用默认字体
                                if font is None:
                                    font = ImageFont.load_default()
                                
                                # 在小图像上绘制文字
                                small_text_x = initial_text_width // 2
                                small_text_y = initial_text_height // 2
                                
                                # 应用效果
                                if "style" in text_info:
                                    if "outline" in text_info["style"]:
                                        offset = 2
                                        for offset_x, offset_y in [(offset,0), (-offset,0), (0,offset), (0,-offset)]:
                                            text_draw.text((small_text_x + offset_x, small_text_y + offset_y), 
                                                          text_info["text"], fill="black", font=font, anchor="mm")
                                    
                                    if "shadow" in text_info["style"]:
                                        shadow_offset = 4
                                        text_draw.text((small_text_x + shadow_offset, small_text_y + shadow_offset), 
                                                      text_info["text"], fill=(0, 0, 0, 180), font=font, anchor="mm")
                                
                                # 绘制主文字
                                text_draw.text((small_text_x, small_text_y), text_info["text"], 
                                              fill=text_info["color"], font=font, anchor="mm")
                                
                                # 裁剪图像
                                bbox = text_img.getbbox()
                                if bbox:
                                    text_img = text_img.crop(bbox)
                                
                                # 计算放大比例
                                scale_factor = text_info["size"] / 40
                                new_width = max(int(text_img.width * scale_factor), 10)
                                new_height = max(int(text_img.height * scale_factor), 10)
                                
                                # 放大文字图像
                                text_img_resized = text_img.resize((new_width, new_height), Image.LANCZOS)
                                
                                # 计算位置
                                if text_info["alignment"] == "left":
                                    paste_x = int(img_width * 0.2)
                                elif text_info["alignment"] == "right":
                                    paste_x = int(img_width * 0.8 - text_img_resized.width)
                                else:  # 居中
                                    paste_x = (img_width - text_img_resized.width) // 2
                                
                                # 垂直位置
                                paste_y = int(img_height * 0.4 - text_img_resized.height // 2)
                                
                                # 粘贴到T恤上
                                st.session_state.final_design.paste(text_img_resized, (paste_x, paste_y), text_img_resized)
                                st.session_state.current_image = st.session_state.final_design.copy()
                                
                                # 更新位置信息
                                st.session_state.applied_text["position"] = (paste_x, paste_y)
                                
                            except Exception as e:
                                st.warning(f"Error reapplying text using drawing method: {e}")
                                import traceback
                                st.warning(traceback.format_exc())
                        else:
                            with st.spinner("Applying text design..."):
                                try:
                                    # 获取当前图像
                                    if st.session_state.final_design is not None:
                                        new_design = st.session_state.final_design.copy()
                                    else:
                                        new_design = st.session_state.base_image.copy()
                                    
                                    # 获取图像尺寸
                                    img_width, img_height = new_design.size
                                    
                                    # 添加调试信息
                                    st.session_state.tshirt_size = (img_width, img_height)
                                    
                                    # 创建小图像用于绘制文字
                                    initial_text_width = min(400, img_width // 2)
                                    initial_text_height = 200
                                    text_img = Image.new('RGBA', (initial_text_width, initial_text_height), (0, 0, 0, 0))
                                    text_draw = ImageDraw.Draw(text_img)
                                    
                                    # 加载字体
                                    from PIL import ImageFont
                                    import os
                                    import platform
                                    
                                    # 初始化调试信息列表
                                    font_debug_info = []
                                    font_debug_info.append("Starting high-definition text design")
                                    
                                    # 尝试加载系统字体 - 增强字体处理部分
                                    font = None
                                    try:
                                        # 确保os模块可用
                                        import os
                                        import platform
                                        
                                        # 记录系统信息以便调试
                                        system = platform.system()
                                        font_debug_info.append(f"System type: {system}")
                                        
                                        # 根据不同系统尝试不同的字体路径
                                        if system == 'Windows':
                                            # Windows系统字体路径
                                            font_paths = [
                                                "C:/Windows/Fonts/arial.ttf",
                                                "C:/Windows/Fonts/ARIAL.TTF",
                                                "C:/Windows/Fonts/calibri.ttf",
                                                "C:/Windows/Fonts/simsun.ttc",  # 中文宋体
                                                "C:/Windows/Fonts/msyh.ttc",    # 微软雅黑
                                            ]
                                        elif system == 'Darwin':  # macOS
                                            font_paths = [
                                                "/Library/Fonts/Arial.ttf",
                                                "/System/Library/Fonts/Helvetica.ttc",
                                                "/System/Library/Fonts/PingFang.ttc"  # 苹方字体
                                            ]
                                        else:  # Linux或其他
                                            font_paths = [
                                                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                                                "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
                                                "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"
                                            ]
                                        
                                        # 直接使用完整尺寸的字体大小
                                        render_size = text_info["size"]
                                        font_debug_info.append(f"Trying to load font, size: {render_size}px")
                                        
                                        # 尝试加载每个字体
                                        for font_path in font_paths:
                                            if os.path.exists(font_path):
                                                try:
                                                    font = ImageFont.truetype(font_path, render_size)
                                                    font_debug_info.append(f"Successfully loaded font: {font_path}")
                                                    break
                                                except Exception as font_err:
                                                    font_debug_info.append(f"load font failed: {font_path} - {str(font_err)}")
                                    except Exception as e:
                                        font_debug_info.append(f"font loading process error: {str(e)}")
                                    
                                    # 如果系统字体加载失败，再尝试默认字体
                                    if font is None:
                                        try:
                                            font_debug_info.append("Using PIL default font, which will result in low resolution")
                                            font = ImageFont.load_default()
                                        except Exception as default_err:
                                            font_debug_info.append(f"Default font loading failed: {str(default_err)}")
                                            # 如果连默认字体都失败，创建一个紧急情况文本图像
                                            font_debug_info.append("All fonts loading failed, using emergency solution")
                                    
                                    # 改进的文本渲染方法 - 直接在高分辨率画布上绘制
                                    try:
                                        # 获取T恤图像尺寸
                                        img_width, img_height = new_design.size
                                        
                                        # 创建一个透明的文本图层，大小与T恤相同
                                        text_layer = Image.new('RGBA', (img_width, img_height), (0, 0, 0, 0))
                                        text_draw = ImageDraw.Draw(text_layer)
                                        
                                        # 获取文本边界框以计算尺寸
                                        if font:
                                            # 处理文本换行 - 当文本太长时
                                            max_text_width = int(img_width * 0.7)  # 最大文本宽度为T恤宽度的70%
                                            lines = []
                                            words = text_info["text"].split()
                                            current_line = words[0] if words else ""
                                            
                                            # 逐词检查并换行
                                            for word in words[1:]:
                                                test_line = current_line + " " + word
                                                # 检查添加这个词后的宽度
                                                test_bbox = text_draw.textbbox((0, 0), test_line, font=font)
                                                test_width = test_bbox[2] - test_bbox[0]
                                                
                                                if test_width <= max_text_width:
                                                    current_line = test_line
                                                else:
                                                    lines.append(current_line)
                                                    current_line = word
                                            
                                            # 添加最后一行
                                            lines.append(current_line)
                                            
                                            # 计算总高度和最大宽度
                                            line_height = render_size * 1.2  # 行高略大于字体大小
                                            total_height = len(lines) * line_height
                                            max_width = 0
                                            
                                            for line in lines:
                                                line_bbox = text_draw.textbbox((0, 0), line, font=font)
                                                line_width = line_bbox[2] - line_bbox[0]
                                                max_width = max(max_width, line_width)
                                            
                                            # 原始文本尺寸
                                            original_text_width = max_width
                                            original_text_height = total_height
                                            font_debug_info.append(f"Original text dimensions: {original_text_width}x{original_text_height}px")
                                            
                                            # 放大系数，使文字更清晰
                                            scale_factor = 2.0  # 增加到2倍以提高清晰度
                                            
                                            # 创建高分辨率图层用于渲染文字
                                            hr_width = img_width * 2
                                            hr_height = img_height * 2
                                            hr_layer = Image.new('RGBA', (hr_width, hr_height), (0, 0, 0, 0))
                                            hr_draw = ImageDraw.Draw(hr_layer)
                                            
                                            # 尝试创建高分辨率字体
                                            hr_font = None
                                            try:
                                                hr_font_size = render_size * 2
                                                if st.session_state.loaded_font_path:
                                                    hr_font = ImageFont.truetype(st.session_state.loaded_font_path, hr_font_size)
                                                    font_debug_info.append(f"Created high-res font: {hr_font_size}px")
                                            except Exception as hr_font_err:
                                                font_debug_info.append(f"Failed to create high-res font: {str(hr_font_err)}")
                                            
                                            if hr_font is None:
                                                hr_font = font
                                                font_debug_info.append("Using original font for high-res rendering")
                                            
                                            # 高分辨率尺寸
                                            hr_line_height = line_height * 2
                                            hr_text_width = max_width * 2
                                            hr_text_height = total_height * 2
                                            
                                            # 根据对齐方式计算X位置
                                            if alignment.lower() == "left":
                                                text_x = int(img_width * 0.2)
                                            elif alignment.lower() == "right":
                                                text_x = int(img_width * 0.8 - original_text_width)
                                            else:  # 居中
                                                text_x = (img_width - original_text_width) // 2
                                            
                                            # 垂直位置 - 上移以更好地展示在T恤上
                                            text_y = int(img_height * 0.3 - original_text_height // 2)
                                            
                                            # 高分辨率位置
                                            hr_text_x = text_x * 2
                                            hr_text_y = text_y * 2
                                            
                                            font_debug_info.append(f"HR text position: ({hr_text_x}, {hr_text_y})")
                                            
                                            # 先应用特效 - 在高分辨率画布上
                                            if "Outline" in text_style:
                                                # 增强轮廓效果
                                                outline_color = "black"
                                                outline_width = max(8, hr_font_size // 10)  # 加粗轮廓宽度
                                                
                                                # 多方向轮廓，让描边更均匀
                                                for angle in range(0, 360, 30):  # 每30度一个点，更平滑
                                                    rad = math.radians(angle)
                                                    offset_x = int(outline_width * math.cos(rad))
                                                    offset_y = int(outline_width * math.sin(rad))
                                                    
                                                    # 处理多行文本
                                                    for i, line in enumerate(lines):
                                                        line_y = hr_text_y + i * hr_line_height
                                                        if alignment.lower() == "center":
                                                            line_bbox = hr_draw.textbbox((0, 0), line, font=hr_font)
                                                            line_width = line_bbox[2] - line_bbox[0]
                                                            line_x = hr_text_x + (hr_text_width - line_width) // 2
                                                        elif alignment.lower() == "right":
                                                            line_bbox = hr_draw.textbbox((0, 0), line, font=hr_font)
                                                            line_width = line_bbox[2] - line_bbox[0]
                                                            line_x = hr_text_x + (hr_text_width - line_width)
                                                        else:
                                                            line_x = hr_text_x
                                                        
                                                        hr_draw.text((line_x + offset_x, line_y + offset_y), 
                                                                      line, fill=outline_color, font=hr_font)
                                            
                                            if "Shadow" in text_style:
                                                # 增强阴影效果
                                                shadow_color = (0, 0, 0, 150)  # 半透明黑色
                                                shadow_offset = max(15, hr_font_size // 8)  # 增加阴影偏移距离
                                                
                                                # 处理多行文本
                                                for i, line in enumerate(lines):
                                                    line_y = hr_text_y + i * hr_line_height
                                                    if alignment.lower() == "center":
                                                        line_bbox = hr_draw.textbbox((0, 0), line, font=hr_font)
                                                        line_width = line_bbox[2] - line_bbox[0]
                                                        line_x = hr_text_x + (hr_text_width - line_width) // 2
                                                    elif alignment.lower() == "right":
                                                        line_bbox = hr_draw.textbbox((0, 0), line, font=hr_font)
                                                        line_width = line_bbox[2] - line_bbox[0]
                                                        line_x = hr_text_x + (hr_text_width - line_width)
                                                    else:
                                                        line_x = hr_text_x
                                                    
                                                    # 创建更平滑的阴影效果
                                                    blur_steps = 8  # 更多步骤，更平滑的阴影
                                                    for step in range(blur_steps):
                                                        offset = shadow_offset * (step + 1) / blur_steps
                                                        alpha = int(150 * (1 - step/blur_steps))
                                                        cur_shadow = (0, 0, 0, alpha)
                                                        hr_draw.text((line_x + offset, line_y + offset), 
                                                                   line, fill=cur_shadow, font=hr_font)
                                        
                                        # 将文字颜色从十六进制转换为RGBA
                                        text_rgb = tuple(int(text_color.lstrip('#')[i:i+2], 16) for i in (0, 2, 4))
                                        text_rgba = text_rgb + (255,)  # 完全不透明
                                        
                                        # 绘制主文字 - 在高分辨率画布上
                                        for i, line in enumerate(lines):
                                            line_y = hr_text_y + i * hr_line_height
                                            if alignment.lower() == "center":
                                                line_bbox = hr_draw.textbbox((0, 0), line, font=hr_font)
                                                line_width = line_bbox[2] - line_bbox[0]
                                                line_x = hr_text_x + (hr_text_width - line_width) // 2
                                            elif alignment.lower() == "right":
                                                line_bbox = hr_draw.textbbox((0, 0), line, font=hr_font)
                                                line_width = line_bbox[2] - line_bbox[0]
                                                line_x = hr_text_x + (hr_text_width - line_width)
                                            else:
                                                line_x = hr_text_x
                                            
                                            hr_draw.text((line_x, line_y), line, fill=text_rgba, font=hr_font)
                                        
                                        # 特殊效果处理
                                        if text_effect != "None":
                                            font_debug_info.append(f"Applying special effect: {text_effect}")
                                            # 未来可以在这里添加高分辨率特效处理
                                        
                                        # 将高分辨率图层缩小回原始尺寸 - 使用LANCZOS重采样以获得最佳质量
                                        text_layer = hr_layer.resize((img_width, img_height), Image.LANCZOS)
                                        font_debug_info.append("Downsampled high-res text layer to original size")
                                        
                                        # 应用文字到设计
                                        new_design.paste(text_layer, (0, 0), text_layer)
                                        
                                        # 保存相关信息
                                        st.session_state.text_position = (text_x, text_y)
                                        st.session_state.text_size_info = {
                                            "font_size": render_size,
                                            "text_width": text_width,
                                            "text_height": text_height
                                        }
                                        
                                        # 应用成功
                                        font_debug_info.append("High-definition text rendering applied successfully")
                                    
                                    except Exception as render_err:
                                        font_debug_info.append(f"High-definition rendering failed: {str(render_err)}")
                                        import traceback
                                        font_debug_info.append(traceback.format_exc())
                                        
                                        # 紧急备用方案 - 创建一个简单文字图像
                                        try:
                                            font_debug_info.append("Using emergency backup rendering method")
                                            # 创建一个白色底的图像
                                            emergency_img = Image.new('RGBA', (img_width//2, img_height//5), (255, 255, 255, 255))
                                            emergency_draw = ImageDraw.Draw(emergency_img)
                                            
                                            # 使用黑色绘制文字，较大字号确保可见
                                            emergency_draw.text((10, 10), text_info["text"], fill="black")
                                            
                                            # 放置在T恤中心位置
                                            paste_x = (img_width - emergency_img.width) // 2
                                            paste_y = (img_height - emergency_img.height) // 2
                                            
                                            new_design.paste(emergency_img, (paste_x, paste_y))
                                            font_debug_info.append("Applied emergency text rendering")
                                        except Exception as emergency_err:
                                            font_debug_info.append(f"Emergency rendering also failed: {str(emergency_err)}")
                                    
                                    # 保存字体加载和渲染信息
                                    st.session_state.font_debug_info = font_debug_info
                                    
                                    # 更新设计和预览
                                    st.session_state.final_design = new_design
                                    st.session_state.current_image = new_design.copy()
                                    
                                    # 保存完整的文字信息
                                    st.session_state.applied_text = {
                                        "text": text_info["text"],
                                        "font": text_info["font"],
                                        "color": text_info["color"],
                                        "size": text_info["size"],
                                        "style": text_style,
                                        "effect": text_effect,
                                        "alignment": text_info["alignment"],
                                        "position": (text_x, text_y),
                                        "use_drawing_method": True  # 标记使用了绘图方法
                                    }
                                    
                                    # 添加详细调试信息
                                    success_msg = f"""
                                    Text applied to design successfully!
                                    Font: {text_info["font"]}
                                    Size: {text_info["size"]}px
                                    Actual width: {text_width}px
                                    Actual height: {text_height}px
                                    Position: ({text_x}, {text_y})
                                    T-shirt size: {img_width} x {img_height}
                                    Rendering method: High-definition rendering
                                    """
                                    
                                    st.success(success_msg)
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Error applying text: {str(e)}")
                                    import traceback
                                    st.error(traceback.format_exc())
        
        # Display current image and get click coordinates
        # 确保current_image存在
        if st.session_state.current_image is not None:
            current_image = st.session_state.current_image
            
            # 确保T恤图像能完整显示
            coordinates = streamlit_image_coordinates(
                current_image,
                key="shirt_image",
                width="100%"
            )
            
            # 添加CSS修复图像显示问题
            st.markdown("""
            <style>
            .stImage img {
                max-width: 100%;
                height: auto;
                object-fit: contain;
            }
            </style>
            """, unsafe_allow_html=True)
            
            # Handle selection area logic - simplify to directly move red box
            if coordinates:
                # Update selection box at current mouse position
                current_point = (coordinates["x"], coordinates["y"])
                temp_image, new_pos = draw_selection_box(st.session_state.base_image, current_point)
                st.session_state.current_image = temp_image
                st.session_state.current_box_position = new_pos
                st.rerun()
        else:
            st.warning("Design preview not loaded, please refresh the page and try again.")
        
        # 显示最终设计结果（如果有）
        if st.session_state.final_design is not None:
            st.markdown("### Final result")
            st.image(st.session_state.final_design, use_container_width=True)
            
            # 显示当前颜色
            color_name = {
                "#FFFFFF": "White",
                "#000000": "Black",
                "#FF0000": "Red",
                "#00FF00": "Green",
                "#0000FF": "Blue",
                "#FFFF00": "Yellow",
                "#FF00FF": "Magenta",
                "#00FFFF": "Cyan",
                "#C0C0C0": "Silver",
                "#808080": "Gray"
            }.get(st.session_state.shirt_color_hex.upper(), "Custom")
            st.markdown(f"**Color:** {color_name} ({st.session_state.shirt_color_hex})")
            
            # 显示调试信息
            if st.checkbox("Show debug information", value=True):
                st.write("---")
                st.subheader("Debug information")
                
                # 显示图像尺寸信息
                if hasattr(st.session_state, 'tshirt_size'):
                    st.write(f"T-shirt image size: {st.session_state.tshirt_size[0]} x {st.session_state.tshirt_size[1]} pixels")
                
                # 显示文字信息
                if hasattr(st.session_state, 'text_size_info'):
                    text_info = st.session_state.text_size_info
                    st.write(f"Font size: {text_info['font_size']} pixels")
                    st.write(f"Text width: {text_info['text_width']} pixels")
                    st.write(f"Text height: {text_info['text_height']} pixels")
                
                # 显示位置信息
                if hasattr(st.session_state, 'text_position'):
                    st.write(f"Text position: {st.session_state.text_position}")
                
                # 显示设计区域信息
                if hasattr(st.session_state, 'design_area'):
                    design_area = st.session_state.design_area
                    st.write(f"Design area: Top-left({design_area[0]}, {design_area[1]}), width({design_area[2]}, {design_area[3]})")
                
                # 显示字体加载路径
                if hasattr(st.session_state, 'loaded_font_path'):
                    st.write(f"Loaded font path: {st.session_state.loaded_font_path}")
                
                # 显示字体加载状态
                if hasattr(st.session_state, 'using_fallback_text'):
                    if st.session_state.using_fallback_text:
                        st.error("Font loading failed, using fallback rendering method")
                    else:
                        st.success("Font loaded successfully")
                
                # 显示详细的字体加载信息（如果存在）
                if hasattr(st.session_state, 'font_debug_info'):
                    with st.expander("Font loading detailed information"):
                        for info in st.session_state.font_debug_info:
                            st.write(f"- {info}")
            
            # 添加清空设计按钮
            if st.button("🗑️ Clear all designs", key="clear_designs"):
                # 清空所有设计相关的状态变量
                st.session_state.generated_design = None
                st.session_state.applied_text = None
                st.session_state.final_design = st.session_state.base_image.copy()
                # 重置当前图像为带选择框的基础图像
                temp_image, _ = draw_selection_box(st.session_state.base_image, st.session_state.current_box_position)
                st.session_state.current_image = temp_image
                st.rerun()
            
            # 下载和确认按钮
            dl_col1, dl_col2 = st.columns(2)
            with dl_col1:
                buf = BytesIO()
                st.session_state.final_design.save(buf, format="PNG")
                buf.seek(0)
                st.download_button(
                    label="💾 Download design",
                    data=buf,
                    file_name="custom_tshirt.png",
                    mime="image/png"
                )
            
            with dl_col2:
                # Confirm completion button
                if st.button("Confirm completion"):
                    st.session_state.page = "survey"
                    st.rerun()
    
    with controls_col:
        # 操作区，包含AI建议和其他控制选项
        
        # 重新组织布局，将所有控制选项都独立为可展开的部分，并默认展开
        with st.expander("🤖 AI Design Suggestions", expanded=True):
            # 添加用户偏好输入
            user_preference = st.text_input("Describe your preferred style or usage", placeholder="For example: sports style, business, casual daily, etc.")
            
            col_pref1, col_pref2 = st.columns([1, 1])
            with col_pref1:
                # 添加预设风格选择
                preset_styles = ["", "Fashion Casual", "Business Formal", "Sports Style", "Rock", "Japanese Anime", "Artistic Retro", "American Street"]
                selected_preset = st.selectbox("Or select a preset style:", preset_styles)
                if selected_preset and not user_preference:
                    user_preference = selected_preset
            
            with col_pref2:
                # 添加获取建议按钮
                if st.button("Get personalized AI suggestions", key="get_ai_advice"):
                    with st.spinner("Generating personalized design suggestions..."):
                        suggestions = get_ai_design_suggestions(user_preference)
                        st.session_state.ai_suggestions = suggestions
            
            # 显示AI建议
            if st.session_state.ai_suggestions:
                # 简化建议显示样式
                st.markdown("""
                <style>
                .ai-suggestion-header {
                    font-weight: 600;
                    margin-bottom: 8px;
                    padding: 5px 10px;
                    background-color: #e9f7fe;
                    border-left: 3px solid #1e88e5;
                    border-radius: 3px;
                }
                .color-item {
                    display: flex;
                    align-items: center;
                    margin-bottom: 10px;
                    padding: 8px;
                    border-radius: 5px;
                    background-color: #f8f9fa;
                }
                .color-box {
                    width: 30px;
                    height: 30px;
                    margin-right: 10px;
                    border: 1px solid #ddd;
                    border-radius: 3px;
                }
                .text-item {
                    margin-bottom: 8px;
                    cursor: pointer;
                    padding: 10px;
                    background-color: #f8f9fa;
                    border-radius: 5px;
                    font-weight: 500;
                }
                .text-item:hover {
                    background-color: #e9ecef;
                }
                </style>
                """, unsafe_allow_html=True)
                
                # 显示原始AI响应，用于调试
                if st.checkbox("Show raw AI response", value=False):
                    st.code(st.session_state.ai_suggestions)
                
                # 创建容器显示简化内容
                with st.container():
                    # 颜色部分处理
                    st.markdown("<div class='ai-suggestion-header'>🤖 AI Recommended Colors</div>", unsafe_allow_html=True)
                    st.markdown("*These colors are suggested by AI based on your style preferences*")
                    
                    # 直接使用st.session_state.ai_suggested_colors
                    if 'ai_suggested_colors' in st.session_state and st.session_state.ai_suggested_colors:
                        for i, (color_name, hex_code) in enumerate(st.session_state.ai_suggested_colors.items()):
                            col1, col2, col3 = st.columns([1, 4, 3])
                            with col1:
                                st.markdown(f"""
                                <div class="color-box" style="background-color: {hex_code};"></div>
                                """, unsafe_allow_html=True)
                            with col2:
                                st.write(f"{color_name}")
                            with col3:
                                if st.button(f"Try Color", key=f"ai_color_{i}_{hex_code.replace('#', '')}"):
                                    st.session_state.shirt_color_hex = hex_code
                                    st.rerun()
                    else:
                        st.info("No color suggestions available")
                    
                    # 文本部分处理
                    st.markdown("<div class='ai-suggestion-header'>🤖 AI Recommended Texts</div>", unsafe_allow_html=True)
                    st.markdown("*Click 'Use' to apply these AI-suggested text phrases to your design*")
                    
                    # 调试：显示会话状态中的文本建议
                    if st.checkbox("Debug text suggestions", value=False):
                        st.write("Session state AI suggested texts:", st.session_state.get('ai_suggested_texts', 'Not found'))
                    
                    # 直接使用st.session_state.ai_suggested_texts
                    if 'ai_suggested_texts' in st.session_state and st.session_state.ai_suggested_texts:
                        # 显示文本建议数量
                        st.info(f"Found {len(st.session_state.ai_suggested_texts)} text suggestions")
                        
                        for i, text in enumerate(st.session_state.ai_suggested_texts):
                            if text.strip():
                                col1, col2 = st.columns([5, 1])
                                with col1:
                                    st.markdown(f"""
                                    <div class="text-item">{text}</div>
                                    """, unsafe_allow_html=True)
                                with col2:
                                    if st.button("Use", key=f"use_text_{i}"):
                                        st.session_state.temp_text_selection = text
                                        st.rerun()
                    else:
                        # 显示没有文本建议的原因
                        if 'ai_suggested_texts' not in st.session_state:
                            st.warning("No text suggestions available (session state key missing)")
                        elif not st.session_state.ai_suggested_texts:
                            st.warning("No text suggestions available (empty list)")
                        else:
                            st.info("No text suggestions available")
            else:
                # 显示欢迎信息
                st.markdown("""
                <div style="background-color: #f0f7ff; padding: 15px; border-radius: 10px; border-left: 5px solid #1e88e5;">
                <h4 style="color: #1e88e5; margin-top: 0;">👋 Welcome to the AI Design Assistant</h4>
                <p>Describe your preferred style or T-shirt purpose, and the AI assistant will provide personalized design suggestions, including:</p>
                <ul>
                    <li>T-shirt color recommendations suited to your style</li>
                    <li>Text content and font style suggestions</li>
                </ul>
                <p>Click the "Get personalized AI suggestions" button to start!</p>
                </div>
                """, unsafe_allow_html=True)
        
        # 颜色与面料部分 - 独立出来，确保始终显示
        with st.expander("🎨 Color Selection", expanded=True):
            # 颜色选择部分 - 只保留自定义颜色选择功能
            st.markdown("##### Custom Color")
            custom_color = st.color_picker("Select a custom color:", st.session_state.shirt_color_hex, key="custom_color_picker")
            custom_col1, custom_col2 = st.columns([3, 1])
            
            with custom_col1:
                # 显示自定义颜色预览
                st.markdown(
                    f"""
                    <div style="
                        background-color: {custom_color}; 
                        width: 100%; 
                        height: 40px; 
                        border-radius: 5px;
                        border: 1px solid #ddd;
                        margin-bottom: 5px;">
                    </div>
                    """, 
                    unsafe_allow_html=True
                )
            
            with custom_col2:
                if st.button("Apply custom color"):
                    st.session_state.shirt_color_hex = custom_color
                    st.rerun()
        
        # 文字设计部分 - 独立出来，确保始终显示
        with st.expander("✍️ Text Design", expanded=True):
            # 文字选项
            text_col1, text_col2 = st.columns([2, 1])
            
            with text_col1:
                # 使用临时变量的值作为默认值
                default_input = ""
                if 'temp_text_selection' in st.session_state:
                    default_input = st.session_state.temp_text_selection
                    # 使用后清除临时状态
                    del st.session_state.temp_text_selection
                elif 'ai_text_suggestion' in st.session_state:
                    default_input = st.session_state.ai_text_suggestion
                
                text_content = st.text_input("Enter or copy AI recommended text", default_input, key="ai_text_suggestion")
            
            with text_col2:
                text_color = st.color_picker("Text color:", "#000000", key="ai_text_color")
            
            # 字体选择 - 扩展为高复杂度方案的选项
            font_options = ["Arial", "Times New Roman", "Courier", "Verdana", "Georgia", "Script", "Impact"]
            font_family = st.selectbox("Font family:", font_options, key="ai_font_selection")
            
            # 添加文字样式选项
            text_style = st.multiselect("Text style:", ["Bold", "Italic", "Underline", "Shadow", "Outline"], default=["Bold"])
            
            # 添加动态文字大小滑块 - 增加最大值
            text_size = st.slider("Text size:", 20, 400, 100, key="ai_text_size")
            
            # 添加文字效果选项
            text_effect = st.selectbox("Text effect:", ["None", "Bent", "Arch", "Wave", "3D", "Gradient"])
            
            # 添加对齐方式选项
            alignment = st.radio("Alignment:", ["Left", "Center", "Right"], horizontal=True, index=1)
            
            # 修改预览部分，将中文样式转换为英文样式名称
            if text_content:
                # 构建样式字符串
                style_str = ""
                if "Bold" in text_style:
                    style_str += "font-weight: bold; "
                if "Italic" in text_style:
                    style_str += "font-style: italic; "
                if "Underline" in text_style:
                    style_str += "text-decoration: underline; "
                if "Shadow" in text_style:
                    style_str += "text-shadow: 2px 2px 4px rgba(0,0,0,0.5); "
                if "Outline" in text_style:
                    style_str += "-webkit-text-stroke: 1px #000; "
                
                # 处理对齐
                align_str = "center"
                if alignment == "Left":
                    align_str = "left"
                elif alignment == "Right":
                    align_str = "right"
                
                # 处理效果
                effect_str = ""
                if text_effect == "Bent":
                    effect_str = "transform: rotateX(10deg); transform-origin: center; "
                elif text_effect == "Arch":
                    effect_str = "transform: perspective(100px) rotateX(10deg); "
                elif text_effect == "Wave":
                    effect_str = "display: inline-block; transform: translateY(5px); animation: wave 2s ease-in-out infinite; "
                elif text_effect == "3D":
                    effect_str = "text-shadow: 0 1px 0 #ccc, 0 2px 0 #c9c9c9, 0 3px 0 #bbb; "
                elif text_effect == "Gradient":
                    effect_str = "background: linear-gradient(45deg, #f3ec78, #af4261); -webkit-background-clip: text; -webkit-text-fill-color: transparent; "
                
                preview_size = text_size * 1.5  # 预览大小略大
                st.markdown(
                    f"""
                    <style>
                    @keyframes wave {{
                        0%, 100% {{ transform: translateY(0px); }}
                        50% {{ transform: translateY(-10px); }}
                    }}
                    </style>
                    <div style="
                        padding: 10px;
                        margin: 10px 0;
                        border: 1px solid #ddd;
                        border-radius: 5px;
                        font-family: {font_family}, sans-serif;
                        color: {text_color};
                        text-align: {align_str};
                        font-size: {preview_size}px;
                        line-height: 1.2;
                        {style_str}
                        {effect_str}
                    ">
                    {text_content}
                    </div>
                    """,
                    unsafe_allow_html=True
                )
                
            # 应用文字按钮
            if st.button("Apply text to design", key="apply_ai_text"):
                if not text_content.strip():
                    st.warning("Please enter text content!")
                else:
                    # 文字应用逻辑
                    with st.spinner("Applying text design..."):
                        try:
                            # 获取当前图像
                            if st.session_state.final_design is not None:
                                new_design = st.session_state.final_design.copy()
                            else:
                                new_design = st.session_state.base_image.copy()
                            
                            # 获取图像尺寸
                            img_width, img_height = new_design.size
                            
                            # 添加调试信息
                            st.session_state.tshirt_size = (img_width, img_height)
                            
                            # 创建透明的文本图层，大小与T恤相同
                            text_layer = Image.new('RGBA', (img_width, img_height), (0, 0, 0, 0))
                            text_draw = ImageDraw.Draw(text_layer)
                            
                            # 加载字体
                            from PIL import ImageFont
                            import os
                            import platform
                            
                            # 初始化调试信息列表
                            font_debug_info = []
                            font_debug_info.append("Starting text design application")
                            
                            # 尝试加载系统字体
                            font = None
                            try:
                                # 记录系统信息以便调试
                                system = platform.system()
                                font_debug_info.append(f"System type: {system}")
                                
                                # 根据不同系统尝试不同的字体路径
                                if system == 'Windows':
                                    # Windows系统字体路径
                                    font_paths = [
                                        "C:/Windows/Fonts/arial.ttf",
                                        "C:/Windows/Fonts/ARIAL.TTF",
                                        "C:/Windows/Fonts/calibri.ttf",
                                        "C:/Windows/Fonts/simsun.ttc",  # 中文宋体
                                        "C:/Windows/Fonts/msyh.ttc",    # 微软雅黑
                                    ]
                                elif system == 'Darwin':  # macOS
                                    font_paths = [
                                        "/Library/Fonts/Arial.ttf",
                                        "/System/Library/Fonts/Helvetica.ttc",
                                        "/System/Library/Fonts/PingFang.ttc"  # 苹方字体
                                    ]
                                else:  # Linux或其他
                                    font_paths = [
                                        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                                        "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
                                        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"
                                    ]
                                
                                # 设定字体大小
                                render_size = text_size
                                font_debug_info.append(f"Trying to load font, size: {render_size}px")
                                
                                # 尝试加载每个字体
                                for font_path in font_paths:
                                    if os.path.exists(font_path):
                                        try:
                                            font = ImageFont.truetype(font_path, render_size)
                                            st.session_state.loaded_font_path = font_path
                                            font_debug_info.append(f"Successfully loaded font: {font_path}")
                                            break
                                        except Exception as font_err:
                                            font_debug_info.append(f"Load font failed: {font_path} - {str(font_err)}")
                            except Exception as e:
                                font_debug_info.append(f"Font loading process error: {str(e)}")
                            
                            # 如果系统字体加载失败，使用默认字体
                            if font is None:
                                try:
                                    font_debug_info.append("Using PIL default font")
                                    font = ImageFont.load_default()
                                    st.session_state.using_fallback_text = True
                                except Exception as default_err:
                                    font_debug_info.append(f"Default font loading failed: {str(default_err)}")
                            
                            # 文本渲染逻辑
                            if font:
                                # 处理文本换行 - 当文本太长时
                                max_text_width = int(img_width * 0.7)  # 最大文本宽度为T恤宽度的70%
                                lines = []
                                words = text_content.split()
                                current_line = words[0] if words else ""
                                
                                # 逐词检查并换行
                                for word in words[1:]:
                                    test_line = current_line + " " + word
                                    # 检查添加这个词后的宽度
                                    test_bbox = text_draw.textbbox((0, 0), test_line, font=font)
                                    test_width = test_bbox[2] - test_bbox[0]
                                    
                                    if test_width <= max_text_width:
                                        current_line = test_line
                                    else:
                                        lines.append(current_line)
                                        current_line = word
                                
                                # 添加最后一行
                                lines.append(current_line)
                                
                                # 计算总高度和最大宽度
                                line_height = render_size * 1.2  # 行高略大于字体大小
                                total_height = len(lines) * line_height
                                max_width = 0
                                
                                for line in lines:
                                    line_bbox = text_draw.textbbox((0, 0), line, font=font)
                                    line_width = line_bbox[2] - line_bbox[0]
                                    max_width = max(max_width, line_width)
                                
                                # 原始文本尺寸
                                original_text_width = max_width
                                original_text_height = total_height
                                font_debug_info.append(f"Original text dimensions: {original_text_width}x{original_text_height}px")
                                
                                # 放大系数，使文字更清晰
                                scale_factor = 2.0  # 增加到2倍以提高清晰度
                                
                                # 创建高分辨率图层用于渲染文字
                                hr_width = img_width * 2
                                hr_height = img_height * 2
                                hr_layer = Image.new('RGBA', (hr_width, hr_height), (0, 0, 0, 0))
                                hr_draw = ImageDraw.Draw(hr_layer)
                                
                                # 尝试创建高分辨率字体
                                hr_font = None
                                try:
                                    hr_font_size = render_size * 2
                                    if st.session_state.loaded_font_path:
                                        hr_font = ImageFont.truetype(st.session_state.loaded_font_path, hr_font_size)
                                        font_debug_info.append(f"Created high-res font: {hr_font_size}px")
                                except Exception as hr_font_err:
                                    font_debug_info.append(f"Failed to create high-res font: {str(hr_font_err)}")
                                
                                if hr_font is None:
                                    hr_font = font
                                    font_debug_info.append("Using original font for high-res rendering")
                                
                                # 高分辨率尺寸
                                hr_line_height = line_height * 2
                                hr_text_width = max_width * 2
                                hr_text_height = total_height * 2
                                
                                # 根据对齐方式计算X位置
                                if alignment.lower() == "left":
                                    text_x = int(img_width * 0.2)
                                elif alignment.lower() == "right":
                                    text_x = int(img_width * 0.8 - original_text_width)
                                else:  # 居中
                                    text_x = (img_width - original_text_width) // 2
                                
                                # 垂直位置 - 上移以更好地展示在T恤上
                                text_y = int(img_height * 0.3 - original_text_height // 2)
                                
                                # 高分辨率位置
                                hr_text_x = text_x * 2
                                hr_text_y = text_y * 2
                                
                                font_debug_info.append(f"HR text position: ({hr_text_x}, {hr_text_y})")
                                
                                # 先应用特效 - 在高分辨率画布上
                                if "Outline" in text_style:
                                    # 增强轮廓效果
                                    outline_color = "black"
                                    outline_width = max(8, hr_font_size // 10)  # 加粗轮廓宽度
                                    
                                    # 多方向轮廓，让描边更均匀
                                    for angle in range(0, 360, 30):  # 每30度一个点，更平滑
                                        rad = math.radians(angle)
                                        offset_x = int(outline_width * math.cos(rad))
                                        offset_y = int(outline_width * math.sin(rad))
                                        
                                        # 处理多行文本
                                        for i, line in enumerate(lines):
                                            line_y = hr_text_y + i * hr_line_height
                                            if alignment.lower() == "center":
                                                line_bbox = hr_draw.textbbox((0, 0), line, font=hr_font)
                                                line_width = line_bbox[2] - line_bbox[0]
                                                line_x = hr_text_x + (hr_text_width - line_width) // 2
                                            elif alignment.lower() == "right":
                                                line_bbox = hr_draw.textbbox((0, 0), line, font=hr_font)
                                                line_width = line_bbox[2] - line_bbox[0]
                                                line_x = hr_text_x + (hr_text_width - line_width)
                                            else:
                                                line_x = hr_text_x
                                            
                                            hr_draw.text((line_x + offset_x, line_y + offset_y), 
                                                      line, fill=outline_color, font=hr_font)
                                
                                if "Shadow" in text_style:
                                    # 增强阴影效果
                                    shadow_color = (0, 0, 0, 150)  # 半透明黑色
                                    shadow_offset = max(15, hr_font_size // 8)  # 增加阴影偏移距离
                                    
                                    # 处理多行文本
                                    for i, line in enumerate(lines):
                                        line_y = hr_text_y + i * hr_line_height
                                        if alignment.lower() == "center":
                                            line_bbox = hr_draw.textbbox((0, 0), line, font=hr_font)
                                            line_width = line_bbox[2] - line_bbox[0]
                                            line_x = hr_text_x + (hr_text_width - line_width) // 2
                                        elif alignment.lower() == "right":
                                            line_bbox = hr_draw.textbbox((0, 0), line, font=hr_font)
                                            line_width = line_bbox[2] - line_bbox[0]
                                            line_x = hr_text_x + (hr_text_width - line_width)
                                        else:
                                            line_x = hr_text_x
                                        
                                        # 创建更平滑的阴影效果
                                        blur_steps = 8  # 更多步骤，更平滑的阴影
                                        for step in range(blur_steps):
                                            offset = shadow_offset * (step + 1) / blur_steps
                                            alpha = int(150 * (1 - step/blur_steps))
                                            cur_shadow = (0, 0, 0, alpha)
                                            hr_draw.text((line_x + offset, line_y + offset), 
                                                       line, fill=cur_shadow, font=hr_font)
                                
                                # 将文字颜色从十六进制转换为RGBA
                                text_rgb = tuple(int(text_color.lstrip('#')[i:i+2], 16) for i in (0, 2, 4))
                                text_rgba = text_rgb + (255,)  # 完全不透明
                                
                                # 绘制主文字 - 在高分辨率画布上
                                for i, line in enumerate(lines):
                                    line_y = hr_text_y + i * hr_line_height
                                    if alignment.lower() == "center":
                                        line_bbox = hr_draw.textbbox((0, 0), line, font=hr_font)
                                        line_width = line_bbox[2] - line_bbox[0]
                                        line_x = hr_text_x + (hr_text_width - line_width) // 2
                                    elif alignment.lower() == "right":
                                        line_bbox = hr_draw.textbbox((0, 0), line, font=hr_font)
                                        line_width = line_bbox[2] - line_bbox[0]
                                        line_x = hr_text_x + (hr_text_width - line_width)
                                    else:
                                        line_x = hr_text_x
                                    
                                    hr_draw.text((line_x, line_y), line, fill=text_rgba, font=hr_font)
                                
                                # 特殊效果处理
                                if text_effect != "None":
                                    font_debug_info.append(f"Applying special effect: {text_effect}")
                                    # 未来可以在这里添加高分辨率特效处理
                                
                                # 将高分辨率图层缩小回原始尺寸 - 使用LANCZOS重采样以获得最佳质量
                                text_layer = hr_layer.resize((img_width, img_height), Image.LANCZOS)
                                font_debug_info.append("Downsampled high-res text layer to original size")
                                
                                # 应用文字到设计
                                new_design.paste(text_layer, (0, 0), text_layer)
                                
                                # 保存相关信息
                                st.session_state.text_position = (text_x, text_y)
                                st.session_state.text_size_info = {
                                    "font_size": render_size,
                                    "text_width": text_width,
                                    "text_height": text_height
                                }
                                
                                # 应用成功
                                font_debug_info.append("Text rendering applied successfully")
                                
                                # 更新设计和预览
                                st.session_state.final_design = new_design
                                st.session_state.current_image = new_design.copy()
                                
                                # 保存完整的文字信息
                                st.session_state.applied_text = {
                                    "text": text_content,
                                    "font": font_family,
                                    "color": text_color,
                                    "size": text_size,
                                    "style": text_style,
                                    "effect": text_effect,
                                    "alignment": alignment,
                                    "position": (text_x, text_y),
                                    "use_drawing_method": True
                                }
                                
                                # 保存字体加载和渲染信息
                                st.session_state.font_debug_info = font_debug_info
                                
                                # 显示成功消息
                                st.success("Text applied to design successfully!")
                                st.rerun()
                            else:
                                st.error("Failed to load any font. Cannot apply text.")
                        except Exception as e:
                            st.error(f"Error applying text: {str(e)}")
                            import traceback
                            st.error(traceback.format_exc())

    # 返回主页按钮 - 将中文改为英文
    if st.button("Back to main page"):
        # 清空所有设计相关的状态
        keys_to_clear = [
            # 基本图像状态
            'base_image', 'current_image', 'current_box_position', 
            'original_base_image', 'final_design', 'generated_design',
            
            # 颜色和面料相关
            'shirt_color_hex', 'current_applied_color',
            
            # AI建议相关
            'ai_suggestions', 'ai_suggested_colors', 'ai_suggested_texts',
            
            # 文字相关
            'applied_text', 'current_text_info', 'ai_text_suggestion',
            'temp_text_selection', 'text_position', 'text_size_info',
            
            # 调试信息
            'font_debug_info', 'tshirt_size', 'design_area',
            'loaded_font_path', 'using_fallback_text'
        ]
        
        # 循环清除所有状态
        for key in keys_to_clear:
            if key in st.session_state:
                del st.session_state[key]
        
        # 保留用户信息和实验组，但清除当前页面状态
        st.session_state.page = "welcome"
        
        # 添加成功提示
        st.success("All designs have been cleared, returning to the main page...")
        st.rerun()
