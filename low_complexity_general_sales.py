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

def get_ai_design_suggestions(user_preferences=None):
    """从GPT-4o-mini获取设计建议"""
    client = OpenAI(api_key=GPT4O_MINI_API_KEY, base_url=GPT4O_MINI_BASE_URL)
    
    # 默认提示如果没有用户偏好
    if not user_preferences:
        user_preferences = "时尚休闲风格的T恤设计"
    
    # 构建提示词
    prompt = f"""
    作为T恤设计顾问，请为"{user_preferences}"风格提供以下设计建议：

    1. 颜色建议：推荐3种适合的颜色，包括：
       - 颜色名称和十六进制代码(如 蓝色 (#0000FF))
       - 为什么这种颜色适合该风格(2-3句话解释)
       
    2. 文字建议：推荐2个适合的文字/短语：
       - 具体文字内容
       - 推荐的字体风格
       - 简短说明为什么适合
       
    3. Logo元素建议：推荐2种适合的设计元素：
       - 元素描述
       - 如何与整体风格搭配
       
    确保包含颜色的十六进制代码，保持内容详实但不过于冗长。
    文字建议部分，请将每个推荐的短语/文字单独放在一行上，并使用引号包裹，例如："Just Do It"。
    """
    
    try:
        # 调用GPT-4o-mini
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "你是一个专业的T恤设计顾问，提供有用且具体的建议。包含足够细节让用户理解你的推荐理由，但避免不必要的冗长。确保为每种颜色包含十六进制代码。对于文字建议，请将推荐的短语用引号包裹并单独放在一行。"},
                {"role": "user", "content": prompt}
            ]
        )
        
        # 返回建议内容
        if response.choices and len(response.choices) > 0:
            suggestion_text = response.choices[0].message.content
            
            # 尝试解析颜色代码
            try:
                # 提取颜色代码的简单方法
                color_matches = {}
                
                # 查找形如 "颜色名 (#XXXXXX)" 的模式
                color_pattern = r'([^\s\(\)]+)\s*\(#([0-9A-Fa-f]{6})\)'
                matches = re.findall(color_pattern, suggestion_text)
                
                if matches:
                    color_matches = {name.strip(): f"#{code}" for name, code in matches}
                    
                # 保存到会话状态
                if color_matches:
                    st.session_state.ai_suggested_colors = color_matches
                    
                # 尝试提取推荐文字
                text_pattern = r'[""]([^""]+)[""]'
                text_matches = re.findall(text_pattern, suggestion_text)
                
                # 保存推荐文字到会话状态
                if text_matches:
                    st.session_state.ai_suggested_texts = text_matches
                else:
                    # 尝试使用另一种模式匹配
                    text_pattern2 = r'"([^"]+)"'
                    text_matches = re.findall(text_pattern2, suggestion_text)
                    if text_matches:
                        st.session_state.ai_suggested_texts = text_matches
                    else:
                        st.session_state.ai_suggested_texts = []
                        
            except Exception as e:
                print(f"解析过程出错: {e}")
                st.session_state.ai_suggested_texts = []
                
            # 使用更好的排版处理文本
            # 替换标题格式
            formatted_text = suggestion_text
            # 处理序号段落
            formatted_text = re.sub(r'(\d\. .*?)(?=\n\d\. |\n*$)', r'<div class="suggestion-section">\1</div>', formatted_text)
            # 处理子项目符号
            formatted_text = re.sub(r'- (.*?)(?=\n- |\n[^-]|\n*$)', r'<div class="suggestion-item">• \1</div>', formatted_text)
            # 强调颜色名称和代码
            formatted_text = re.sub(r'([^\s\(\)]+)\s*\(#([0-9A-Fa-f]{6})\)', r'<span class="color-name">\1</span> <span class="color-code">(#\2)</span>', formatted_text)
            
            # 不再使用JavaScript回调，而是简单地加粗文本
            formatted_text = re.sub(r'[""]([^""]+)[""]', r'"<strong>\1</strong>"', formatted_text)
            formatted_text = re.sub(r'"([^"]+)"', r'"<strong>\1</strong>"', formatted_text)
            
            suggestion_with_style = f"""
            <div class="suggestion-container">
            {formatted_text}
            </div>
            """
            
            return suggestion_with_style
        else:
            return "无法获取AI建议，请稍后再试。"
    except Exception as e:
        return f"获取AI建议时出错: {str(e)}"

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
                    # 判断SVG处理库是否可用
                    if CAIROSVG_AVAILABLE:
                        try:
                            png_data = cairosvg.svg2png(bytestring=image_resp.content)
                            return Image.open(BytesIO(png_data)).convert("RGBA")
                        except Exception as conv_err:
                            st.error(f"Error converting SVG to PNG with cairosvg: {conv_err}")
                            # 尝试使用备选方案
                            if SVGLIB_AVAILABLE:
                                try:
                                    svg_data = BytesIO(image_resp.content)
                                    drawing = svg2rlg(svg_data)
                                    png_data = BytesIO()
                                    renderPM.drawToFile(drawing, png_data, fmt="PNG")
                                    png_data.seek(0)
                                    return Image.open(png_data).convert("RGBA")
                                except Exception as svg_err:
                                    st.error(f"Error converting SVG to PNG with svglib: {svg_err}")
                            return None
                    elif SVGLIB_AVAILABLE:
                        # 使用svglib作为备选
                        try:
                            svg_data = BytesIO(image_resp.content)
                            drawing = svg2rlg(svg_data)
                            png_data = BytesIO()
                            renderPM.drawToFile(drawing, png_data, fmt="PNG")
                            png_data.seek(0)
                            return Image.open(png_data).convert("RGBA")
                        except Exception as svg_err:
                            st.error(f"Error converting SVG to PNG with svglib: {svg_err}")
                            return None
                    else:
                        st.error("无法处理SVG格式，SVG处理库未安装")
                        return None
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
    """获取预设logo文件夹中的所有图片"""
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
    
    # 任务复杂度说明
    st.markdown("""
    <div style="background-color:#f0f0f0; padding:10px; border-radius:5px; margin-bottom:15px">
    <b>Basic Customization Options</b>: In this experience, you can customize your T-shirt with simple options:
    <ul>
        <li>Choose T-shirt color</li>
        <li>Add text or logo elements</li>
        <li>Generate design patterns</li>
        <li>Position your design on the T-shirt</li>
    </ul>
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
        st.markdown("### 设计预览")
        
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
                        st.success(f"找到T恤图像: {path}")
                        found = True
                        break
                
                if not found:
                    # 如果未找到，显示当前工作目录和文件列表以便调试
                    current_dir = os.getcwd()
                    st.error(f"T恤图像未找到。当前工作目录: {current_dir}")
                    files = os.listdir(current_dir)
                    st.error(f"目录内容: {files}")
                
                st.info(f"尝试加载图像: {original_image_path}")
                # 加载图像
                original_image = Image.open(original_image_path).convert("RGBA")
                st.success("成功加载T恤图像!")
                
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
                st.error(f"加载T恤图像时出错: {e}")
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
                                if "轮廓" in text_info["style"]:
                                    offset = 2
                                    for offset_x, offset_y in [(offset,0), (-offset,0), (0,offset), (0,-offset)]:
                                        text_draw.text((small_text_x + offset_x, small_text_y + offset_y), 
                                                      text_info["text"], fill="black", font=font, anchor="mm")
                                
                                if "阴影" in text_info["style"]:
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
                            if text_info["alignment"] == "左对齐":
                                paste_x = int(img_width * 0.2)
                            elif text_info["alignment"] == "右对齐":
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
                            st.warning(f"使用绘图方法重新应用文字时出错: {e}")
                            import traceback
                            st.warning(traceback.format_exc())
                    else:
                        with st.spinner("正在应用文字设计..."):
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
                                
                                # 初始化调试信息列表
                                font_debug_info = []
                                font_debug_info.append("开始应用高清文字设计")
                                
                                # 尝试加载系统字体 - 增强字体处理部分
                                font = None
                                try:
                                    # 确保os模块可用
                                    import os
                                    import platform
                                    
                                    # 记录系统信息以便调试
                                    system = platform.system()
                                    font_debug_info.append(f"系统类型: {system}")
                                    
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
                                    font_debug_info.append(f"尝试加载字体，大小: {render_size}px")
                                    
                                    # 尝试加载每个字体
                                    for font_path in font_paths:
                                        if os.path.exists(font_path):
                                            try:
                                                font = ImageFont.truetype(font_path, render_size)
                                                font_debug_info.append(f"成功加载字体: {font_path}")
                                                break
                                            except Exception as font_err:
                                                font_debug_info.append(f"加载字体失败: {font_path} - {str(font_err)}")
                                except Exception as e:
                                    font_debug_info.append(f"字体加载过程错误: {str(e)}")
                                
                                # 如果系统字体加载失败，再尝试默认字体
                                if font is None:
                                    try:
                                        font_debug_info.append("使用PIL默认字体，但这会导致低分辨率")
                                        font = ImageFont.load_default()
                                    except Exception as default_err:
                                        font_debug_info.append(f"默认字体加载失败: {str(default_err)}")
                                        # 如果连默认字体都失败，创建一个紧急情况文本图像
                                        font_debug_info.append("所有字体加载失败，使用紧急方案")
                                
                                # 改进的文本渲染方法 - 直接在高分辨率画布上绘制
                                try:
                                    # 获取T恤图像尺寸
                                    img_width, img_height = new_design.size
                                    
                                    # 创建一个透明的文本图层，大小与T恤相同
                                    text_layer = Image.new('RGBA', (img_width, img_height), (0, 0, 0, 0))
                                    text_draw = ImageDraw.Draw(text_layer)
                                    
                                    # 获取文本边界框以计算尺寸
                                    if font:
                                        text_bbox = text_draw.textbbox((0, 0), text_info["text"], font=font)
                                        text_width = text_bbox[2] - text_bbox[0]
                                        text_height = text_bbox[3] - text_bbox[1]
                                        font_debug_info.append(f"文字实际尺寸: {text_width}x{text_height}px")
                                    else:
                                        # 估计尺寸
                                        text_width = len(text_info["text"]) * render_size * 0.6
                                        text_height = render_size * 1.2
                                        font_debug_info.append(f"估计文字尺寸: {text_width}x{text_height}px")
                                    
                                    # 根据对齐方式计算X位置
                                    if text_info["alignment"] == "左对齐":
                                        text_x = int(img_width * 0.2)
                                    elif text_info["alignment"] == "右对齐":
                                        text_x = int(img_width * 0.8 - text_width)
                                    else:  # 居中
                                        text_x = (img_width - text_width) // 2
                                    
                                    # 垂直位置 - 保持在T恤上部
                                    text_y = int(img_height * 0.4 - text_height // 2)
                                    
                                    # 文本自动换行处理
                                    lines = []
                                    if font:
                                        max_width = img_width * 0.8  # 最大宽度为图像宽度的80%
                                        words = text_info["text"].split()
                                        lines = []
                                        current_line = ""
                                        
                                        # 英文单词分割的情况
                                        if len(words) > 1:
                                            for word in words:
                                                test_line = current_line + " " + word if current_line else word
                                                # 计算当前行加上新单词的宽度
                                                test_bbox = text_draw.textbbox((0, 0), test_line, font=font)
                                                test_width = test_bbox[2] - test_bbox[0]
                                                
                                                if test_width <= max_width:
                                                    current_line = test_line
                                                else:
                                                    # 如果当前行已经有内容，添加到lines中
                                                    if current_line:
                                                        lines.append(current_line)
                                                    # 开始新行，从当前单词开始
                                                    current_line = word
                                            
                                            # 添加最后一行
                                            if current_line:
                                                lines.append(current_line)
                                        
                                        # 中文文本处理(如果没有空格分词)
                                        if (len(lines) <= 1 or not lines) and len(text_info["text"]) > 20 and " " not in text_info["text"]:
                                            lines = []
                                            chars_per_line = max(10, int(max_width / (render_size * 0.6)))
                                            text = text_info["text"]
                                            
                                            for i in range(0, len(text), chars_per_line):
                                                lines.append(text[i:i+chars_per_line])
                                        
                                        # 如果没有成功分行，使用原始文本
                                        if not lines:
                                            lines = [text_info["text"]]
                                        
                                        # 计算多行文本的总高度
                                        line_height = text_height * 1.2  # 行高为字体高度的1.2倍
                                        total_height = line_height * len(lines)
                                        
                                        # 根据对齐方式计算每行的X位置
                                        line_positions = []
                                        for line in lines:
                                            line_bbox = text_draw.textbbox((0, 0), line, font=font)
                                            line_width = line_bbox[2] - line_bbox[0]
                                            line_height = line_bbox[3] - line_bbox[1]
                                            
                                            if text_info["alignment"] == "左对齐":
                                                line_x = int(img_width * 0.2)
                                            elif text_info["alignment"] == "右对齐":
                                                line_x = int(img_width * 0.8 - line_width)
                                            else:  # 居中
                                                line_x = (img_width - line_width) // 2
                                                
                                            line_positions.append((line_x, line_width, line_height))
                                        
                                        # 垂直起始位置 - 保持在T恤上部并考虑总高度
                                        start_y = int(img_height * 0.35 - total_height // 2)
                                        
                                        # 更新text_width和text_height
                                        text_width = max([pos[1] for pos in line_positions])
                                        text_height = total_height
                                        font_debug_info.append(f"多行文本: {len(lines)}行, 总高度: {text_height}px")
                                        
                                        # 记录第一行位置作为文本位置
                                        text_x = line_positions[0][0]
                                        text_y = start_y
                                    
                                    # 先应用特效 - 轮廓和阴影
                                    if "style" in text_info:
                                        if "轮廓" in text_info["style"]:
                                            # 绘制粗轮廓 - 使用更多点以获得更平滑的轮廓
                                            outline_color = "black"
                                            outline_width = max(3, render_size // 20)
                                            
                                            # 8方向轮廓，让描边更均匀
                                            if len(lines) > 1:
                                                # 为多行文本应用轮廓
                                                for i, line in enumerate(lines):
                                                    line_x = line_positions[i][0]
                                                    line_y = start_y + i * line_height
                                                    
                                                    for angle in range(0, 360, 45):
                                                        rad = math.radians(angle)
                                                        offset_x = int(outline_width * math.cos(rad))
                                                        offset_y = int(outline_width * math.sin(rad))
                                                        text_draw.text((line_x + offset_x, line_y + offset_y), 
                                                                      line, fill=outline_color, font=font)
                                            else:
                                                # 单行文本轮廓
                                                for angle in range(0, 360, 45):
                                                    rad = math.radians(angle)
                                                    offset_x = int(outline_width * math.cos(rad))
                                                    offset_y = int(outline_width * math.sin(rad))
                                                    text_draw.text((text_x + offset_x, text_y + offset_y), 
                                                                  text_info["text"], fill=outline_color, font=font)
                                        
                                        if "阴影" in text_info["style"]:
                                            # 渐变阴影效果
                                            shadow_color = (0, 0, 0, 180)  # 半透明黑色
                                            shadow_offset = max(5, render_size // 15)
                                            blur_radius = shadow_offset // 2
                                            
                                            # 多层阴影创建模糊效果
                                            if len(lines) > 1:
                                                # 为多行文本应用阴影
                                                for i, line in enumerate(lines):
                                                    line_x = line_positions[i][0]
                                                    line_y = start_y + i * line_height
                                                    
                                                    for j in range(1, blur_radius+1):
                                                        opacity = 180 - (j * 150 // blur_radius)
                                                        current_shadow = (0, 0, 0, opacity)
                                                        offset_j = shadow_offset + j
                                                        text_draw.text((line_x + offset_j, line_y + offset_j), 
                                                                     line, fill=current_shadow, font=font)
                                            else:
                                                # 单行文本阴影
                                                for i in range(1, blur_radius+1):
                                                    opacity = 180 - (i * 150 // blur_radius)
                                                    current_shadow = (0, 0, 0, opacity)
                                                    offset_i = shadow_offset + i
                                                    text_draw.text((text_x + offset_i, text_y + offset_i), 
                                                                 text_info["text"], fill=current_shadow, font=font)
                                    
                                    # 将文字颜色从十六进制转换为RGBA
                                    text_rgb = tuple(int(text_info["color"].lstrip('#')[i:i+2], 16) for i in (0, 2, 4))
                                    text_rgba = text_rgb + (255,)  # 完全不透明
                                    
                                    # 绘制主文字 - 处理多行文本
                                    if len(lines) > 1:
                                        for i, line in enumerate(lines):
                                            line_x = line_positions[i][0]
                                            line_y = start_y + i * line_height
                                            text_draw.text((line_x, line_y), line, fill=text_rgba, font=font)
                                    else:
                                        # 单行文本直接绘制
                                        text_draw.text((text_x, text_y), text_info["text"], fill=text_rgba, font=font)
                                    
                                    # 特殊效果处理
                                    if text_info["effect"] != "无" and text_info["effect"] != "None":
                                        font_debug_info.append(f"应用特殊效果: {text_info['effect']}")
                                        if text_info["effect"] == "渐变":
                                            # 简单实现渐变效果
                                            gradient_layer = Image.new('RGBA', (img_width, img_height), (0, 0, 0, 0))
                                            gradient_draw = ImageDraw.Draw(gradient_layer)
                                            
                                            # 绘制文字蒙版 - 处理多行文本
                                            if len(lines) > 1:
                                                for i, line in enumerate(lines):
                                                    line_x = line_positions[i][0]
                                                    line_y = start_y + i * line_height
                                                    gradient_draw.text((line_x, line_y), line, 
                                                                      fill=(255, 255, 255, 255), font=font)
                                            else:
                                                # 单行文本蒙版
                                                gradient_draw.text((text_x, text_y), text_info["text"], 
                                                                 fill=(255, 255, 255, 255), font=font)
                                            
                                            # 创建渐变色彩
                                            from_color = text_rgb
                                            to_color = (255 - text_rgb[0], 255 - text_rgb[1], 255 - text_rgb[2])
                                            
                                            # 将渐变应用到文字
                                            gradient_data = gradient_layer.getdata()
                                            new_data = []
                                            for i, item in enumerate(gradient_data):
                                                y_pos = i // img_width  # 计算像素的y位置
                                                if item[3] > 0:  # 如果是文字部分
                                                    # 根据y位置计算颜色混合比例
                                                    ratio = y_pos / text_height
                                                    if ratio > 1: ratio = 1
                                                    
                                                    # 线性混合两种颜色
                                                    r = int(from_color[0] * (1 - ratio) + to_color[0] * ratio)
                                                    g = int(from_color[1] * (1 - ratio) + to_color[1] * ratio)
                                                    b = int(from_color[2] * (1 - ratio) + to_color[2] * ratio)
                                                    new_data.append((r, g, b, item[3]))
                                                else:
                                                    new_data.append(item)  # 保持透明部分
                                            
                                            gradient_layer.putdata(new_data)
                                            text_layer = gradient_layer
                                    
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
                                    font_debug_info.append("高清文字渲染成功应用")
                                except Exception as render_err:
                                    font_debug_info.append(f"高清渲染失败: {str(render_err)}")
                                    import traceback
                                    font_debug_info.append(traceback.format_exc())
                                    
                                    # 紧急备用方案 - 创建一个简单文字图像
                                    try:
                                        font_debug_info.append("使用紧急备用渲染方法")
                                        # 创建一个白色底的图像
                                        emergency_img = Image.new('RGBA', (img_width//2, img_height//5), (255, 255, 255, 255))
                                        emergency_draw = ImageDraw.Draw(emergency_img)
                                        
                                        # 使用黑色绘制文字，较大字号确保可见
                                        emergency_draw.text((10, 10), text_info["text"], fill="black")
                                        
                                        # 放置在T恤中心位置
                                        paste_x = (img_width - emergency_img.width) // 2
                                        paste_y = (img_height - emergency_img.height) // 2
                                        
                                        new_design.paste(emergency_img, (paste_x, paste_y))
                                        font_debug_info.append("应用了紧急文字渲染")
                                    except Exception as emergency_err:
                                        font_debug_info.append(f"紧急渲染也失败: {str(emergency_err)}")
                                
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
                                    "style": text_info["style"],
                                    "effect": text_info["effect"],
                                    "alignment": text_info["alignment"],
                                    "position": (text_x, text_y),
                                    "use_drawing_method": True  # 标记使用了绘图方法
                                }
                                
                                # 添加详细调试信息
                                success_msg = f"""
                                文字已应用到设计中！
                                字体: {text_info["font"]}
                                大小: {text_info["size"]}px
                                实际宽度: {text_width}px
                                实际高度: {text_height}px
                                位置: ({text_x}, {text_y})
                                T恤尺寸: {img_width} x {img_height}
                                渲染方法: 高清渲染
                                """
                                
                                st.success(success_msg)
                                st.rerun()
                            except Exception as e:
                                st.error(f"应用文字时出错: {str(e)}")
                                import traceback
                                st.error(traceback.format_exc())
                
                # 添加Logo选择功能
                st.markdown("##### 应用Logo")
                
                # Logo来源选择
                logo_source = st.radio("Logo来源:", ["上传Logo", "选择预设Logo"], horizontal=True, key="ai_logo_source")
                
                if logo_source == "上传Logo":
                    # Logo上传选项
                    uploaded_logo = st.file_uploader("上传Logo图片 (PNG或JPG文件):", type=["png", "jpg", "jpeg"], key="ai_logo_upload")
                    logo_image = None
                    
                    if uploaded_logo is not None:
                        try:
                            logo_image = Image.open(BytesIO(uploaded_logo.getvalue())).convert("RGBA")
                            st.image(logo_image, caption="上传的Logo", width=150)
                        except Exception as e:
                            st.error(f"加载上传的Logo时出错: {e}")
                else:  # 选择预设Logo
                    # 获取预设logo
                    preset_logos = get_preset_logos()
                    
                    if not preset_logos:
                        st.warning("未找到预设Logo。请在'logos'文件夹中添加一些图片。")
                        logo_image = None
                    else:
                        # 显示预设logo选择
                        logo_cols = st.columns(min(3, len(preset_logos)))
                        selected_preset_logo = None
                        
                        for i, logo_path in enumerate(preset_logos):
                            with logo_cols[i % 3]:
                                logo_name = os.path.basename(logo_path)
                                try:
                                    logo_preview = Image.open(logo_path).convert("RGBA")
                                    # 调整预览大小
                                    preview_width = 80
                                    preview_height = int(preview_width * logo_preview.height / logo_preview.width)
                                    preview = logo_preview.resize((preview_width, preview_height))
                                    
                                    st.image(preview, caption=logo_name)
                                    if st.button(f"选择", key=f"ai_logo_{i}"):
                                        st.session_state.selected_preset_logo = logo_path
                                        st.rerun()
                                except Exception as e:
                                    st.error(f"加载Logo {logo_name}时出错: {e}")
                        
                        # 如果已选择Logo
                        if 'selected_preset_logo' in st.session_state:
                            try:
                                logo_image = Image.open(st.session_state.selected_preset_logo).convert("RGBA")
                            except Exception as e:
                                st.error(f"加载选择的Logo时出错: {e}")
                                logo_image = None
                        else:
                            logo_image = None
                
                # Logo大小和位置设置(只在有logo_image时显示)
                if logo_source == "上传Logo" and uploaded_logo is not None or \
                   logo_source == "选择预设Logo" and 'selected_preset_logo' in st.session_state:
                    
                    # Logo大小
                    logo_size = st.slider("Logo大小:", 10, 100, 40, format="%d%%", key="ai_logo_size")
                    
                    # Logo位置
                    logo_position = st.radio("位置:", 
                        ["左上", "上中", "右上", "居中", "左下", "下中", "右下"], 
                        index=3, horizontal=True, key="ai_logo_position")
                    
                    # Logo透明度
                    logo_opacity = st.slider("Logo透明度:", 10, 100, 100, 5, format="%d%%", key="ai_logo_opacity")
                    
                    # 应用Logo按钮
                    if st.button("应用Logo到设计", key="apply_ai_logo"):
                        # 获取当前图像
                        if st.session_state.final_design is not None:
                            new_design = st.session_state.final_design.copy()
                        else:
                            new_design = st.session_state.base_image.copy()
                        
                        try:
                            # 对应的logo_image应该已经在上面的逻辑中被设置
                            if logo_image:
                                # 获取图像尺寸并使用更大的绘制区域
                                img_width, img_height = new_design.size
                                
                                # 定义更大的T恤前胸区域
                                chest_width = int(img_width * 0.95)  # 几乎整个宽度
                                chest_height = int(img_height * 0.6)  # 更大的高度范围
                                chest_left = (img_width - chest_width) // 2
                                chest_top = int(img_height * 0.2)  # 更高的位置
                                
                                # 调整Logo大小 - 相对于T恤区域而不是小框
                                logo_size_factor = logo_size / 100
                                logo_width = int(chest_width * logo_size_factor * 0.5)  # 控制最大为区域的一半
                                logo_height = int(logo_width * logo_image.height / logo_image.width)
                                logo_resized = logo_image.resize((logo_width, logo_height), Image.LANCZOS)
                                
                                # 位置映射 - 现在相对于胸前设计区域
                                position_mapping = {
                                    "左上": (chest_left + 10, chest_top + 10),
                                    "上中": (chest_left + (chest_width - logo_width) // 2, chest_top + 10),
                                    "右上": (chest_left + chest_width - logo_width - 10, chest_top + 10),
                                    "居中": (chest_left + (chest_width - logo_width) // 2, chest_top + (chest_height - logo_height) // 2),
                                    "左下": (chest_left + 10, chest_top + chest_height - logo_height - 10),
                                    "下中": (chest_left + (chest_width - logo_width) // 2, chest_top + chest_height - logo_height - 10),
                                    "右下": (chest_left + chest_width - logo_width - 10, chest_top + chest_height - logo_height - 10)
                                }
                                
                                logo_x, logo_y = position_mapping.get(logo_position, (chest_left + 10, chest_top + 10))
                                
                                # 设置透明度
                                if logo_opacity < 100:
                                    logo_data = logo_resized.getdata()
                                    new_data = []
                                    for item in logo_data:
                                        r, g, b, a = item
                                        new_a = int(a * logo_opacity / 100)
                                        new_data.append((r, g, b, new_a))
                                    logo_resized.putdata(new_data)
                                
                                # 粘贴Logo到设计
                                try:
                                    new_design.paste(logo_resized, (logo_x, logo_y), logo_resized)
                                except Exception as e:
                                    st.warning(f"Logo粘贴失败: {e}")
                                
                                # 更新设计
                                st.session_state.final_design = new_design
                                st.session_state.current_image = new_design.copy()
                                
                                # 保存Logo信息用于后续可能的更新
                                st.session_state.applied_logo = {
                                    "source": logo_source,
                                    "path": st.session_state.get('selected_preset_logo', None),
                                    "size": logo_size,
                                    "position": logo_position,
                                    "opacity": logo_opacity
                                }
                                
                                st.success("Logo已应用到设计中！")
                                st.rerun()
                            else:
                                st.error("请先选择或上传Logo")
                        except Exception as e:
                            st.error(f"应用Logo时出错: {e}")
            else:
                # 显示欢迎信息
                st.markdown("""
                <div style="background-color: #f0f7ff; padding: 15px; border-radius: 10px; border-left: 5px solid #1e88e5;">
                <h4 style="color: #1e88e5; margin-top: 0;">👋 欢迎使用AI设计助手</h4>
                <p>描述您喜欢的风格或T恤用途，AI助手将为您提供个性化设计建议，包括：</p>
                <ul>
                    <li>适合您风格的T恤颜色推荐</li>
                    <li>文字内容和字体风格建议</li>
                    <li>Logo选择和设计元素推荐</li>
                </ul>
                <p>点击"获取个性化AI建议"按钮开始吧！</p>
                </div>
                """, unsafe_allow_html=True)
    
    # Return to main interface button - modified here
    if st.button("返回主页"):
        # Clear all design-related states
        st.session_state.base_image = None
        st.session_state.current_image = None
        st.session_state.current_box_position = None
        st.session_state.generated_design = None
        st.session_state.final_design = None
        st.session_state.applied_text = None
        st.session_state.applied_logo = None
        # Only change page state, retain user info and experiment group
        st.session_state.page = "welcome"
        st.rerun() 
