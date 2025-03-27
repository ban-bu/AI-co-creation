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
    
    # Default prompt if no user preferences
    if not user_preferences:
        user_preferences = "Fashion casual style T-shirt design"
    
    # Build the prompt
    prompt = f"""
    As a T-shirt design consultant, please provide the following design suggestions for the "{user_preferences}" style:

    1. Color Suggestions: Recommend 3 suitable colors, including:
       - Color name and hex code (e.g., Blue (#0000FF))
       - Why this color suits the style (2-3 sentences explanation)
       
    2. Text Suggestions: Recommend 2 suitable texts/phrases:
       - Specific text content
       - Recommended font style
       - Brief explanation of why it's suitable
       
    3. Logo Element Suggestions: Recommend 2 suitable design elements:
       - Element description
       - How to match with the overall style
       
    Make sure to include hex codes for colors, keep content detailed but concise.
    For text suggestions, put each recommended phrase/text on a separate line and wrap in quotes, e.g.: "Just Do It".
    """
    
    try:
        # Call GPT-4o-mini
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a professional T-shirt design consultant, providing useful and specific suggestions. Include sufficient details for users to understand your recommendations, but avoid unnecessary verbosity. Make sure to include hex codes for each color. For text suggestions, wrap recommended phrases in quotes and put them on separate lines."},
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
    
    # Add General Sales environment description
    st.info("""
    **General Sales Environment**
    
    Welcome to our regular T-shirt customization service available in our standard online store. 
    You are browsing our website from the comfort of your home or office, with no time pressure. 
    Take your time to explore the design options and create a T-shirt that matches your personal style.
    This is a typical online shopping experience where you can customize at your own pace.
    """)
    
    # Task complexity description
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
    
    # Initialize T-shirt color state variables
    if 'shirt_color_hex' not in st.session_state:
        st.session_state.shirt_color_hex = "#FFFFFF"  # Default white
    if 'original_base_image' not in st.session_state:
        st.session_state.original_base_image = None  # Save original white T-shirt image
    if 'base_image' not in st.session_state:
        st.session_state.base_image = None  # Ensure base_image variable is initialized
    if 'current_image' not in st.session_state:
        st.session_state.current_image = None  # Ensure current_image variable is initialized
    if 'final_design' not in st.session_state:
        st.session_state.final_design = None  # Ensure final_design variable is initialized
    if 'ai_suggestions' not in st.session_state:
        st.session_state.ai_suggestions = None  # Store AI suggestions
    
    # Reorganize layout, preview on left, controls on right
    st.markdown("## Design Area")
    
    # Create two-column layout
    preview_col, controls_col = st.columns([3, 2])
    
    with preview_col:
        # T-shirt preview area
        st.markdown("### Design Preview")
        
        # Load T-shirt base image
        if st.session_state.base_image is None:
            try:
                # Ensure os module is available in this scope
                import os
                
                # Load original white T-shirt image
                original_image_path = "white_shirt.png"
                # Check various possible paths
                possible_paths = [
                    "white_shirt.png",
                    "./white_shirt.png",
                    "../white_shirt.png",
                    "low_complexity_general_sales_files/white_shirt.png",
                    "images/white_shirt.png",
                    "white_shirt1.png",
                    "white_shirt2.png"
                ]
                
                # Try all possible paths
                found = False
                for path in possible_paths:
                    if os.path.exists(path):
                        original_image_path = path
                        st.success(f"Found T-shirt image: {path}")
                        found = True
                        break
                
                if not found:
                    # If not found, show current working directory and file list for debugging
                    current_dir = os.getcwd()
                    st.error(f"T-shirt image not found. Current working directory: {current_dir}")
                    files = os.listdir(current_dir)
                    st.error(f"Directory contents: {files}")
                
                st.info(f"Attempting to load image: {original_image_path}")
                # Load image
                original_image = Image.open(original_image_path).convert("RGBA")
                st.success("Successfully loaded T-shirt image!")
                
                # Save original white T-shirt image
                st.session_state.original_base_image = original_image.copy()
                
                # Apply current selected color
                colored_image = change_shirt_color(original_image, st.session_state.shirt_color_hex)
                st.session_state.base_image = colored_image
                
                # Initialize by drawing selection box in the center
                initial_image, initial_pos = draw_selection_box(colored_image)
                st.session_state.current_image = initial_image
                st.session_state.current_box_position = initial_pos
                
                # Set initial final design as colored T-shirt
                st.session_state.final_design = colored_image.copy()
            except Exception as e:
                st.error(f"Error loading T-shirt image: {e}")
                import traceback
                st.error(traceback.format_exc())
        else:
            # Add color change detection: save current applied color to check for changes
            if 'current_applied_color' not in st.session_state:
                st.session_state.current_applied_color = st.session_state.shirt_color_hex
            
            # Check if color has changed
            if st.session_state.current_applied_color != st.session_state.shirt_color_hex:
                # Color has changed, need to reapply
                original_image = st.session_state.original_base_image.copy()
                colored_image = change_shirt_color(original_image, st.session_state.shirt_color_hex)
                st.session_state.base_image = colored_image
                
                # Update current image and position
                new_image, _ = draw_selection_box(colored_image, st.session_state.current_box_position)
                st.session_state.current_image = new_image
                
                # If there's a final design, also need to reapply color
                st.session_state.final_design = colored_image.copy()
                
                # Update applied color state
                st.session_state.current_applied_color = st.session_state.shirt_color_hex
        
        # Display current image and get click coordinates
        # Ensure current_image exists
        if st.session_state.current_image is not None:
            current_image = st.session_state.current_image
            
            # Ensure T-shirt image displays completely
            coordinates = streamlit_image_coordinates(
                current_image,
                key="shirt_image",
                width="100%"
            )
            
            # Add CSS to fix image display issues
            st.markdown("""
            <style>
            .stImage img {
                max-width: 100%;
                height: auto;
                object-fit: contain;
            }
            </style>
            """, unsafe_allow_html=True)
            
            # Handle selection area logic
            if coordinates:
                current_point = (coordinates["x"], coordinates["y"])
                temp_image, new_pos = draw_selection_box(st.session_state.base_image, current_point)
                st.session_state.current_image = temp_image
                st.session_state.current_box_position = new_pos
                st.rerun()
        else:
            st.warning("Design preview not loaded yet. Please refresh the page.")
        
        # Display final design result (if available)
        if st.session_state.final_design is not None:
            st.markdown("### Final Result")
            st.image(st.session_state.final_design, use_container_width=True)
            
            # Display current color
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
            
            # Add clear design button
            if st.button("🗑️ Clear All Designs", key="clear_designs"):
                # Clear all design-related state variables
                st.session_state.generated_design = None
                st.session_state.applied_text = None
                st.session_state.applied_logo = None
                # Reset final design to base T-shirt image
                st.session_state.final_design = st.session_state.base_image.copy()
                # Reset current image to base image with selection box
                temp_image, _ = draw_selection_box(st.session_state.base_image, st.session_state.current_box_position)
                st.session_state.current_image = temp_image
                st.rerun()
            
            # Download and confirm buttons
            dl_col1, dl_col2 = st.columns(2)
            with dl_col1:
                buf = BytesIO()
                st.session_state.final_design.save(buf, format="PNG")
                buf.seek(0)
                st.download_button(
                    label="💾 Download Design",
                    data=buf,
                    file_name="custom_tshirt.png",
                    mime="image/png"
                )
            
            with dl_col2:
                # Confirm completion button
                if st.button("Confirm Completion"):
                    st.session_state.page = "survey"
                    st.rerun()
    
    with controls_col:
        # Control area with AI suggestions and other options
        with st.expander("🤖 AI Design Assistant", expanded=True):
            # Add user preference input
            user_preference = st.text_input("Describe your preferred style or usage", 
                placeholder="e.g., Sports style, Business casual, Daily wear, etc.")
            
            col_pref1, col_pref2 = st.columns([1, 1])
            with col_pref1:
                # Add preset style selection
                preset_styles = ["", "Fashion Casual", "Business Formal", "Sports Style", 
                               "Rock Punk", "Anime Style", "Vintage", "American Street"]
                selected_preset = st.selectbox("Or choose a preset style:", preset_styles)
                if selected_preset and not user_preference:
                    user_preference = selected_preset
            
            with col_pref2:
                # Add get suggestions button
                if st.button("Get AI Suggestions", key="get_ai_advice"):
                    with st.spinner("Generating personalized design suggestions..."):
                        suggestions = get_ai_design_suggestions(user_preference)
                        st.session_state.ai_suggestions = suggestions
            
            # Display AI suggestions
            if st.session_state.ai_suggestions:
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
                
                # Add apply suggestions section
                st.markdown("---")
                st.markdown("#### Apply AI Suggestions")
                
                # Color suggestions application
                if 'ai_suggested_colors' not in st.session_state:
                    st.session_state.ai_suggested_colors = {
                        "White": "#FFFFFF", 
                        "Black": "#000000", 
                        "Navy Blue": "#003366", 
                        "Light Gray": "#CCCCCC", 
                        "Light Blue": "#ADD8E6"
                    }
                
                st.markdown("##### Apply Recommended Colors")
                
                # Create color selection list
                colors = st.session_state.ai_suggested_colors
                color_cols = st.columns(min(3, len(colors)))
                
                for i, (color_name, color_hex) in enumerate(colors.items()):
                    with color_cols[i % 3]:
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
                        if st.button(f"Apply {color_name}", key=f"apply_{i}"):
                            st.session_state.shirt_color_hex = color_hex
                            st.rerun()
                
                # Add custom color adjustment
                st.markdown("##### Custom Color")
                custom_color = st.color_picker("Choose custom color:", st.session_state.shirt_color_hex, key="custom_color_picker")
                custom_col1, custom_col2 = st.columns([3, 1])
                
                with custom_col1:
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
                    if st.button("Apply Custom Color"):
                        st.session_state.shirt_color_hex = custom_color
                        st.rerun()
                
                # Text suggestions application
                st.markdown("##### Apply Recommended Text")
                
                if 'ai_suggested_texts' in st.session_state and st.session_state.ai_suggested_texts:
                    st.markdown("**Click suggested text below to apply:**")
                    suggested_texts_container = st.container()
                    with suggested_texts_container:
                        text_buttons = st.columns(min(2, len(st.session_state.ai_suggested_texts)))
                        
                        for i, text in enumerate(st.session_state.ai_suggested_texts):
                            with text_buttons[i % 2]:
                                if st.button(f'"{text}"', key=f"text_btn_{i}"):
                                    st.session_state.temp_text_selection = text
                                    st.rerun()
                
                # Text options
                text_col1, text_col2 = st.columns([2, 1])
                
                with text_col1:
                    default_input = ""
                    if 'temp_text_selection' in st.session_state:
                        default_input = st.session_state.temp_text_selection
                        del st.session_state.temp_text_selection
                    elif 'ai_text_suggestion' in st.session_state:
                        default_input = st.session_state.ai_text_suggestion
                    
                    text_content = st.text_input("Enter or copy AI recommended text", default_input, key="ai_text_suggestion")
                
                with text_col2:
                    text_color = st.color_picker("Text color:", "#000000", key="ai_text_color")
                
                # Font selection
                font_options = ["Arial", "Times New Roman", "Courier", "Verdana", "Georgia", "Script", "Impact"]
                font_family = st.selectbox("Font family:", font_options, key="ai_font_selection")
                
                # Text style options
                text_style = st.multiselect("Text style:", ["Bold", "Italic", "Underline", "Shadow", "Outline"], default=["Bold"])
                
                # Text size slider
                text_size = st.slider("Text size:", 20, 400, 39, key="ai_text_size")
                
                # Text effect options
                text_effect = st.selectbox("Text effect:", ["None", "Curved", "Arch", "Wave", "3D", "Gradient"])
                
                # Alignment options
                alignment = st.radio("Alignment:", ["Left", "Center", "Right"], horizontal=True, index=1)
                
                # Preview section
                if text_content:
                    # Build style string
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
                    
                    # Handle alignment
                    align_str = "center"
                    if alignment == "Left":
                        align_str = "left"
                    elif alignment == "Right":
                        align_str = "right"
                    
                    # Handle effects
                    effect_str = ""
                    if text_effect == "Curved":
                        effect_str = "transform: rotateX(10deg); transform-origin: center; "
                    elif text_effect == "Arch":
                        effect_str = "transform: perspective(100px) rotateX(10deg); "
                    elif text_effect == "Wave":
                        effect_str = "display: inline-block; transform: translateY(5px); animation: wave 2s ease-in-out infinite; "
                    elif text_effect == "3D":
                        effect_str = "text-shadow: 0 1px 0 #ccc, 0 2px 0 #c9c9c9, 0 3px 0 #bbb; "
                    elif text_effect == "Gradient":
                        effect_str = "background: linear-gradient(45deg, #f3ec78, #af4261); -webkit-background-clip: text; -webkit-text-fill-color: transparent; "
                    
                    preview_size = text_size * 1.5
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
                    
                # Apply text button
                if st.button("Apply Text to Design", key="apply_ai_text"):
                    if not text_content.strip():
                        st.warning("Please enter text content!")
                    else:
                        with st.spinner("Applying text design..."):
                            try:
                                # ... rest of the text application code ...
                                pass
                            except Exception as e:
                                st.error(f"Error applying text: {str(e)}")
                
                # Logo section
                st.markdown("##### Apply Logo")
                
                # Logo source selection
                logo_source = st.radio("Logo source:", ["Upload Logo", "Choose Preset Logo"], horizontal=True, key="ai_logo_source")
                
                if logo_source == "Upload Logo":
                    uploaded_logo = st.file_uploader("Upload logo image (PNG or JPG):", type=["png", "jpg", "jpeg"], key="ai_logo_upload")
                    logo_image = None
                    
                    if uploaded_logo is not None:
                        try:
                            logo_image = Image.open(BytesIO(uploaded_logo.getvalue())).convert("RGBA")
                            st.image(logo_image, caption="Uploaded Logo", width=150)
                        except Exception as e:
                            st.error(f"Error loading uploaded logo: {e}")
                else:
                    preset_logos = get_preset_logos()
                    
                    if not preset_logos:
                        st.warning("No preset logos found. Please add some images to the 'logos' folder.")
                        logo_image = None
                    else:
                        logo_cols = st.columns(min(3, len(preset_logos)))
                        selected_preset_logo = None
                        
                        for i, logo_path in enumerate(preset_logos):
                            with logo_cols[i % 3]:
                                logo_name = os.path.basename(logo_path)
                                try:
                                    logo_preview = Image.open(logo_path).convert("RGBA")
                                    preview_width = 80
                                    preview_height = int(preview_width * logo_preview.height / logo_preview.width)
                                    preview = logo_preview.resize((preview_width, preview_height))
                                    
                                    st.image(preview, caption=logo_name)
                                    if st.button(f"Select", key=f"ai_logo_{i}"):
                                        st.session_state.selected_preset_logo = logo_path
                                        st.rerun()
                                except Exception as e:
                                    st.error(f"Error loading logo {logo_name}: {e}")
                
                # Logo size and position settings
                if logo_source == "Upload Logo" and uploaded_logo is not None or \
                   logo_source == "Choose Preset Logo" and 'selected_preset_logo' in st.session_state:
                    
                    logo_size = st.slider("Logo size:", 10, 100, 40, format="%d%%", key="ai_logo_size")
                    
                    logo_position = st.radio("Position:", 
                        ["Top Left", "Top Center", "Top Right", "Center", "Bottom Left", "Bottom Center", "Bottom Right"], 
                        index=3, horizontal=True, key="ai_logo_position")
                    
                    logo_opacity = st.slider("Logo opacity:", 10, 100, 100, 5, format="%d%%", key="ai_logo_opacity")
                    
                    if st.button("Apply Logo to Design", key="apply_ai_logo"):
                        # ... rest of the logo application code ...
                        pass

    # Return to main interface button
    if st.button("Return to Home"):
        st.session_state.base_image = None
        st.session_state.current_image = None
        st.session_state.current_box_position = None
        st.session_state.generated_design = None
        st.session_state.final_design = None
        st.session_state.applied_text = None
        st.session_state.applied_logo = None
        st.session_state.page = "welcome"
        st.rerun()
