import streamlit as st
from PIL import Image, ImageDraw
import requests
from io import BytesIO
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
import os
import re

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
                # 加载原始白色T恤图像
                original_image_path = "white_shirt.png"
                if not os.path.exists(original_image_path):
                    st.error(f"T恤图像文件未找到: {original_image_path}")
                    # 尝试其他可能的路径
                    alternative_paths = ["./white_shirt.png", "../white_shirt.png", "images/white_shirt.png"]
                    for alt_path in alternative_paths:
                        if os.path.exists(alt_path):
                            original_image_path = alt_path
                            st.success(f"在备选路径找到T恤图像: {alt_path}")
                            break
                
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
                st.error(f"加载T恤图像时出错: {e}")
                # 创建一个简单的默认T恤图像
                try:
                    default_img = Image.new('RGBA', (1024, 1024), color=(255, 255, 255, 255))
                    draw = ImageDraw.Draw(default_img)
                    draw.rectangle([(300, 200), (724, 800)], outline=(200, 200, 200), width=2)
                    draw.text((450, 500), "T-Shirt", fill=(100, 100, 100))
                    
                    st.session_state.original_base_image = default_img.copy()
                    st.session_state.base_image = default_img.copy()
                    initial_image, initial_pos = draw_selection_box(default_img)
                    st.session_state.current_image = initial_image
                    st.session_state.current_box_position = initial_pos
                    st.session_state.final_design = default_img.copy()
                except Exception as ex:
                    st.error(f"创建默认图像也失败: {ex}")
                    st.stop()
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
                    draw = ImageDraw.Draw(st.session_state.final_design)
                    
                    try:
                        # 将字体映射和ImageFont导入移到try外部
                        from PIL import ImageFont
                        font_mapping = {
                            "Arial": "arial.ttf",
                            "Times New Roman": "times.ttf",
                            "Courier": "cour.ttf",
                            "Verdana": "verdana.ttf",
                            "Georgia": "georgia.ttf",
                            "Impact": "impact.ttf"
                        }
                        
                        system_font_paths = [
                            "/Library/Fonts/",
                            "/System/Library/Fonts/",
                            "C:/Windows/Fonts/",
                            "/usr/share/fonts/truetype/",
                        ]
                        
                        # 使用固定的大像素值，与应用文字逻辑保持一致
                        font_size = 250  # 固定使用250像素的大字体
                        
                        font_file = font_mapping.get(text_info["font"], "arial.ttf")
                        for path in system_font_paths:
                            try:
                                font = ImageFont.truetype(path + font_file, font_size)
                                break
                            except:
                                continue
                        
                        if font is None:
                            font = ImageFont.load_default()
                        
                        # 计算文字位置 - 在中心位置
                        img_width, img_height = st.session_state.final_design.size
                        text_bbox = draw.textbbox((0, 0), text_info["text"], font=font)
                        text_width = text_bbox[2] - text_bbox[0]
                        text_height = text_bbox[3] - text_bbox[1]
                        
                        # 居中位置
                        text_x = (img_width - text_width) // 2
                        text_y = (img_height // 2) - (text_height // 2)
                        
                        # 将位置略微向上移动
                        text_y = int(text_y * 0.8)
                        
                        # 绘制文字
                        draw.text((text_x, text_y), text_info["text"], fill=text_info["color"], font=font)
                        
                        # 更新当前图像
                        st.session_state.current_image = st.session_state.final_design.copy()
                        
                        # 更新文字信息
                        st.session_state.applied_text["size"] = font_size
                        st.session_state.applied_text["position"] = (text_x, text_y)
                        
                    except Exception as e:
                        st.warning(f"重新应用文字时出错: {e}")
                
                # 重新应用Logo
                if 'applied_logo' in st.session_state and 'selected_preset_logo' in st.session_state:
                    logo_info = st.session_state.applied_logo
                    
                    try:
                        logo_path = st.session_state.selected_preset_logo
                        logo_image = Image.open(logo_path).convert("RGBA")
                        
                        # 获取图像尺寸并使用更大的绘制区域
                        img_width, img_height = st.session_state.final_design.size
                        
                        # 定义更大的T恤前胸区域
                        chest_width = int(img_width * 0.95)  # 几乎整个宽度
                        chest_height = int(img_height * 0.6)  # 更大的高度范围
                        chest_left = (img_width - chest_width) // 2
                        chest_top = int(img_height * 0.2)  # 更高的位置
                        
                        # 调整Logo大小 - 相对于T恤区域而不是小框
                        logo_size_factor = logo_info["size"] / 100
                        logo_width = int(chest_width * logo_size_factor * 0.5)  # 控制最大为区域的一半
                        logo_height = int(logo_width * logo_image.height / logo_image.width)
                        logo_resized = logo_image.resize((logo_width, logo_height), Image.LANCZOS)
                        
                        # 计算位置
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
                        
                        logo_x, logo_y = position_mapping.get(logo_info["position"], (chest_left + 10, chest_top + 10))
                        
                        # 设置透明度
                        if logo_info["opacity"] < 100:
                            logo_data = logo_resized.getdata()
                            new_data = []
                            for item in logo_data:
                                r, g, b, a = item
                                new_a = int(a * logo_info["opacity"] / 100)
                                new_data.append((r, g, b, new_a))
                            logo_resized.putdata(new_data)
                        
                        # 粘贴Logo到设计
                        st.session_state.final_design.paste(logo_resized, (logo_x, logo_y), logo_resized)
                        
                        # 更新当前图像
                        st.session_state.current_image = st.session_state.final_design.copy()
                    except Exception as e:
                        st.warning(f"重新应用Logo时出错: {e}")
                
                # 更新已应用的颜色状态
                st.session_state.current_applied_color = st.session_state.shirt_color_hex
        
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
            st.warning("设计预览图尚未加载，请刷新页面重试。")
        
        # 显示最终设计结果（如果有）
        if st.session_state.final_design is not None:
            st.markdown("### 最终效果")
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
            st.markdown(f"**颜色:** {color_name} ({st.session_state.shirt_color_hex})")
            
            # 添加清空设计按钮
            if st.button("🗑️ 清空所有设计", key="clear_designs"):
                # 清空所有设计相关的状态变量
                st.session_state.generated_design = None
                st.session_state.applied_text = None
                st.session_state.applied_logo = None
                # 重置最终设计为基础T恤图像
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
                    label="💾 下载设计",
                    data=buf,
                    file_name="custom_tshirt.png",
                    mime="image/png"
                )
            
            with dl_col2:
                # Confirm completion button
                if st.button("确认完成"):
                    st.session_state.page = "survey"
                    st.rerun()
    
    with controls_col:
        # 操作区，包含AI建议和其他控制选项
        with st.expander("🤖 AI设计建议", expanded=True):
            # 添加用户偏好输入
            user_preference = st.text_input("描述您喜欢的风格或用途", placeholder="例如：运动风格、商务场合、休闲日常等")
            
            col_pref1, col_pref2 = st.columns([1, 1])
            with col_pref1:
                # 添加预设风格选择
                preset_styles = ["", "时尚休闲", "商务正式", "运动风格", "摇滚朋克", "日系动漫", "文艺复古", "美式街头"]
                selected_preset = st.selectbox("或选择预设风格:", preset_styles)
                if selected_preset and not user_preference:
                    user_preference = selected_preset
            
            with col_pref2:
                # 添加获取建议按钮
                if st.button("获取个性化AI建议", key="get_ai_advice"):
                    with st.spinner("正在生成个性化设计建议..."):
                        suggestions = get_ai_design_suggestions(user_preference)
                        st.session_state.ai_suggestions = suggestions
            
            # 显示AI建议
            if st.session_state.ai_suggestions:
                # 添加格式化的建议显示
                st.markdown("""
                <style>
                .suggestion-container {
                    background-color: #f8f9fa;
                    border-left: 4px solid #4CAF50;
                    padding: 15px;
                    margin: 10px 0;
                    border-radius: 0 5px 5px 0;
                }
                .suggestion-section {
                    margin-bottom: 12px;
                    font-weight: 500;
                }
                .suggestion-item {
                    margin-left: 15px;
                    margin-bottom: 8px;
                }
                .color-name {
                    font-weight: 500;
                }
                .color-code {
                    font-family: monospace;
                    background-color: #f1f1f1;
                    padding: 2px 4px;
                    border-radius: 3px;
                }
                .suggested-text {
                    cursor: pointer;
                    color: #0066cc;
                    transition: all 0.2s;
                }
                .suggested-text:hover {
                    background-color: #e6f2ff;
                    text-decoration: underline;
                }
                </style>
                """, unsafe_allow_html=True)
                
                st.markdown(st.session_state.ai_suggestions, unsafe_allow_html=True)
                
                # 添加应用建议的部分
                st.markdown("---")
                st.markdown("#### 应用AI建议")
                
                # 颜色建议应用
                if 'ai_suggested_colors' not in st.session_state:
                    # 初始提供一些默认颜色选项
                    st.session_state.ai_suggested_colors = {
                        "白色": "#FFFFFF", 
                        "黑色": "#000000", 
                        "藏青色": "#003366", 
                        "浅灰色": "#CCCCCC", 
                        "浅蓝色": "#ADD8E6"
                    }
                
                st.markdown("##### 应用推荐颜色")
                
                # 创建颜色选择列表 - 动态创建
                colors = st.session_state.ai_suggested_colors
                color_cols = st.columns(min(3, len(colors)))
                
                for i, (color_name, color_hex) in enumerate(colors.items()):
                    with color_cols[i % 3]:
                        # 显示颜色预览
                        st.markdown(
                            f"""
                            <div style="
                                background-color: {color_hex}; 
                                width: 100%; 
                                height: 40px; 
                                border-radius: 5px;
                                border: 1px solid #ddd;
                                margin-bottom: 5px;">
                            </div>
                            <div style="text-align: center; margin-bottom: 10px;">
                                {color_name}<br>
                                <span style="font-family: monospace; font-size: 0.9em;">{color_hex}</span>
                            </div>
                            """, 
                            unsafe_allow_html=True
                        )
                        if st.button(f"应用{color_name}", key=f"apply_{i}"):
                            st.session_state.shirt_color_hex = color_hex
                            st.rerun()
                
                # 添加自定义颜色调整功能
                st.markdown("##### 自定义颜色")
                custom_color = st.color_picker("选择自定义颜色:", st.session_state.shirt_color_hex, key="custom_color_picker")
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
                    if st.button("应用自定义颜色"):
                        st.session_state.shirt_color_hex = custom_color
                        st.rerun()
                
                # 文字建议应用
                st.markdown("##### 应用推荐文字")
                
                # 显示解析的推荐文字，点击直接填充
                if 'ai_suggested_texts' in st.session_state and st.session_state.ai_suggested_texts:
                    st.markdown("**点击下方推荐文字快速应用：**")
                    suggested_texts_container = st.container()
                    with suggested_texts_container:
                        text_buttons = st.columns(min(2, len(st.session_state.ai_suggested_texts)))
                        
                        for i, text in enumerate(st.session_state.ai_suggested_texts):
                            with text_buttons[i % 2]:
                                # 修改按钮实现方式，避免直接设置会话状态
                                if st.button(f'"{text}"', key=f"text_btn_{i}"):
                                    # 创建一个临时状态变量
                                    st.session_state.temp_text_selection = text
                                    st.rerun()
                
                # 改进文字应用部分的布局
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
                    
                    text_suggestion = st.text_input("输入或复制AI推荐的文字", default_input, key="ai_text_suggestion")
                
                with text_col2:
                    text_color = st.color_picker("文字颜色:", "#000000", key="ai_text_color")
                
                # 字体选择部分
                font_options = ["Arial", "Times New Roman", "Courier", "Verdana", "Georgia", "Impact"]
                ai_font = st.selectbox("选择字体风格:", font_options, key="ai_font_selection")
                
                # 修改文字大小滑块
                text_size = st.slider("文字大小:", 8, 25, 15, key="ai_text_size")
                
                # 修改预览部分
                if text_suggestion:
                    preview_size = 36  # 固定预览大小
                    st.markdown(
                        f"""
                        <div style="
                            padding: 10px;
                            margin: 10px 0;
                            border: 1px solid #ddd;
                            border-radius: 5px;
                            font-family: {ai_font}, sans-serif;
                            color: {text_color};
                            text-align: center;
                            font-size: {preview_size}px;
                            line-height: 1.2;
                        ">
                        <strong>{text_suggestion}</strong>
                        </div>
                        """,
                        unsafe_allow_html=True
                    )
                    
                    # 修改预览信息，说明使用固定大小
                    st.info("预览文字大小仅供参考。应用到T恤上的文字将使用固定的250像素大小，确保清晰可见。")
                
                # 修改应用文字到设计部分的代码，使用固定像素大小
                if st.button("应用文字到设计", key="apply_ai_text"):
                    if not text_suggestion.strip():
                        st.warning("请输入文字内容!")
                    else:
                        try:
                            # 获取当前图像
                            if st.session_state.final_design is not None:
                                new_design = st.session_state.final_design.copy()
                            else:
                                new_design = st.session_state.base_image.copy()
                            
                            # 创建绘图对象
                            draw = ImageDraw.Draw(new_design)
                            
                            # 将字体映射和ImageFont导入移到try外部
                            # 导入字体
                            from PIL import ImageFont
                            font = None
                            
                            # 字体映射
                            font_mapping = {
                                "Arial": "arial.ttf",
                                "Times New Roman": "times.ttf",
                                "Courier": "cour.ttf",
                                "Verdana": "verdana.ttf",
                                "Georgia": "georgia.ttf",
                                "Impact": "impact.ttf"
                            }
                            
                            # 使用固定的大像素值，不再基于图像百分比
                            font_size = 250  # 固定使用250像素的大字体
                            
                            # 记录实际使用的字体大小
                            st.session_state.actual_font_size = font_size
                            
                            # 尝试常见的系统字体路径
                            system_font_paths = [
                                "/Library/Fonts/",  # macOS
                                "/System/Library/Fonts/",  # macOS系统
                                "C:/Windows/Fonts/",  # Windows
                                "/usr/share/fonts/truetype/",  # Linux
                            ]
                            
                            # 加载字体
                            font_file = font_mapping.get(ai_font, "arial.ttf")
                            for path in system_font_paths:
                                try:
                                    font = ImageFont.truetype(path + font_file, font_size)
                                    break
                                except:
                                    continue
                            
                            # 如果无法加载字体，使用默认字体
                            if font is None:
                                try:
                                    # 尝试使用PIL的默认字体
                                    font = ImageFont.load_default()
                                except:
                                    st.error("无法加载字体，请尝试其他字体。")
                                    return
                            
                            # 获取图像尺寸
                            img_width, img_height = new_design.size
                            
                            # 计算文字位置
                            try:
                                # 获取文字边界框
                                text_bbox = draw.textbbox((0, 0), text_suggestion, font=font)
                                text_width = text_bbox[2] - text_bbox[0]
                                text_height = text_bbox[3] - text_bbox[1]
                                
                                # 计算居中位置
                                text_x = (img_width - text_width) // 2
                                text_y = (img_height // 2) - (text_height // 2)  # 垂直居中
                                
                                # 将位置略微向上移动
                                text_y = int(text_y * 0.8)  # 移到中心位置稍上方
                                
                                # 绘制文字
                                draw.text((text_x, text_y), text_suggestion, fill=text_color, font=font)
                                
                                # 更新设计
                                st.session_state.final_design = new_design
                                st.session_state.current_image = new_design.copy()
                                
                                # 保存文字信息
                                st.session_state.applied_text = {
                                    "text": text_suggestion,
                                    "font": ai_font,
                                    "color": text_color,
                                    "size": font_size,
                                    "position": (text_x, text_y)
                                }
                                
                                st.success(f"文字已成功应用到设计中！字体大小: {font_size}px")
                                st.rerun()
                            except Exception as e:
                                st.error(f"应用文字时出错: {e}")
                                
                        except Exception as e:
                            st.error(f"创建设计时出错: {e}")
                
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
