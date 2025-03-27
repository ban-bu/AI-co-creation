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
                import re
                
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
            # 强调引号内的文字并添加点击功能
            formatted_text = re.sub(r'[""]([^""]+)[""]', r'<span class="suggested-text" onclick="selectText(\'text-\1\')">"<strong>\1</strong>"</span>', formatted_text)
            formatted_text = re.sub(r'"([^"]+)"', r'<span class="suggested-text" onclick="selectText(\'text-\1\')">"<strong>\1</strong>"</span>', formatted_text)
            
            # 添加JavaScript函数用于选择文本
            suggestion_with_style = f"""
            <script>
            function selectText(textId) {{
                // 发送消息到Streamlit
                const data = {{
                    text: textId.substring(5),  // 移除'text-'前缀
                    type: "select_text"
                }};
                
                // 使用window.parent发送消息
                window.parent.postMessage({{
                    type: "streamlit:setComponentValue",
                    value: data
                }}, "*");
            }}
            </script>
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
    if 'ai_suggestions' not in st.session_state:
        st.session_state.ai_suggestions = None  # 存储AI建议
    
    # Create two-column layout
    col1, col2 = st.columns([3, 2])
    
    with col1:
        st.markdown("## Design Area")
        
        # 添加AI建议框
        with st.expander("🤖 AI Design Suggestions", expanded=True):
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
                
                # 添加JavaScript回调处理，接收点击事件
                components_callback = st.components.v1.html(
                    """
                    <script>
                    window.addEventListener('message', function(event) {
                        if (event.data.type === 'streamlit:setComponentValue') {
                            const data = event.data.value;
                            if (data && data.type === 'select_text') {
                                window.parent.postMessage({
                                    type: 'streamlit:setComponentValue',
                                    value: {
                                        selectedText: data.text,
                                        targetKey: 'ai_text_suggestion'
                                    }
                                }, '*');
                            }
                        }
                    });
                    </script>
                    """,
                    height=0
                )
                
                # 处理文本选择回调
                if components_callback and 'selectedText' in components_callback:
                    # 设置文本到会话状态
                    selected_text = components_callback['selectedText']
                    st.session_state.ai_text_suggestion = selected_text
                    st.rerun()
                
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
                
                # 文字建议应用
                st.markdown("##### 应用推荐文字")
                
                # 显示解析的推荐文字，点击直接填充
                if 'ai_suggested_texts' in st.session_state and st.session_state.ai_suggested_texts:
                    st.markdown("**点击下方推荐文字快速应用：**")
                    text_buttons = st.columns(min(2, len(st.session_state.ai_suggested_texts)))
                    
                    for i, text in enumerate(st.session_state.ai_suggested_texts):
                        with text_buttons[i % 2]:
                            if st.button(f'"{text}"', key=f"text_btn_{i}"):
                                st.session_state.ai_text_suggestion = text
                                st.rerun()
                
                # 改进文字应用部分的布局
                text_col1, text_col2 = st.columns([2, 1])
                
                with text_col1:
                    text_suggestion = st.text_input("输入或复制AI推荐的文字", "", key="ai_text_suggestion")
                
                with text_col2:
                    text_color = st.color_picker("文字颜色:", "#000000", key="ai_text_color")
                
                # 字体选择部分
                font_options = ["Arial", "Times New Roman", "Courier", "Verdana", "Georgia", "Impact"]
                ai_font = st.selectbox("选择字体风格:", font_options, key="ai_font_selection")
                
                # 预览效果
                if text_suggestion:
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
                            font-size: 18px;
                        ">
                        {text_suggestion}
                        </div>
                        """,
                        unsafe_allow_html=True
                    )
                
                # 应用按钮
                if st.button("应用文字到设计", key="apply_ai_text"):
                    # 将文字添加到会话状态中，以便在文字选项卡中使用
                    st.session_state.ai_text_suggestion = text_suggestion
                    st.session_state.ai_font_selection = ai_font
                    st.session_state.ai_text_color = text_color
                    st.success(f"已选择文字设置，请在\"Add Text/Logo\"选项卡中点击\"Add Text to Design\"应用")
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
        
        # Load T-shirt base image
        if st.session_state.base_image is None:
            try:
                # 加载原始白色T恤图像
                original_image = Image.open("white_shirt.png").convert("RGBA")
                # 保存原始白色T恤图像
                st.session_state.original_base_image = original_image.copy()
                
                # 应用当前选择的颜色
                colored_image = change_shirt_color(original_image, st.session_state.shirt_color_hex)
                st.session_state.base_image = colored_image
                
                # Initialize by drawing selection box in the center
                initial_image, initial_pos = draw_selection_box(colored_image)
                st.session_state.current_image = initial_image
                st.session_state.current_box_position = initial_pos
            except Exception as e:
                st.error(f"Error loading white T-shirt image: {e}")
                st.stop()
        
        # Display current image and get click coordinates
        current_image = st.session_state.current_image
        coordinates = streamlit_image_coordinates(
            current_image,
            key="shirt_image"
        )
        
        # Handle selection area logic - simplify to directly move red box
        if coordinates:
            # Update selection box at current mouse position
            current_point = (coordinates["x"], coordinates["y"])
            temp_image, new_pos = draw_selection_box(st.session_state.base_image, current_point)
            st.session_state.current_image = temp_image
            st.session_state.current_box_position = new_pos
            st.rerun()
            
        # 将Final Result部分移到左侧栏中
        if st.session_state.final_design is not None:
            st.markdown("### Final Result")
            
            # 添加清空设计按钮
            if st.button("🗑️ Clear All Designs", key="clear_designs"):
                # 清空所有设计相关的状态变量
                st.session_state.generated_design = None
                # 重置最终设计为基础T恤图像
                st.session_state.final_design = None
                # 重置当前图像为带选择框的基础图像
                temp_image, _ = draw_selection_box(st.session_state.base_image, st.session_state.current_box_position)
                st.session_state.current_image = temp_image
                st.rerun()
            
            st.image(st.session_state.final_design, use_container_width=True)
            
            # 添加T恤规格信息
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
            
            # Provide download option
            col1a, col1b = st.columns(2)
            with col1a:
                buf = BytesIO()
                st.session_state.final_design.save(buf, format="PNG")
                buf.seek(0)
                st.download_button(
                    label="💾 Download Custom Design",
                    data=buf,
                    file_name="custom_tshirt.png",
                    mime="image/png"
                )
            
            with col1b:
                # Confirm completion button
                if st.button("Confirm Completion"):
                    st.session_state.page = "survey"
                    st.rerun()

    with col2:
        st.markdown("## Design Parameters")
        
        # Simplified design option tabs
        tab1, tab2 = st.tabs(["Generate Design", "Add Text/Logo"])
        
        with tab1:
            st.markdown("### Design Options")
            
            # 添加颜色选择器
            shirt_color = st.color_picker("T-shirt color:", st.session_state.shirt_color_hex)
            
            # 如果颜色发生变化，更新T恤颜色
            if shirt_color != st.session_state.shirt_color_hex:
                st.session_state.shirt_color_hex = shirt_color
                
                # 重新着色T恤图像
                if st.session_state.original_base_image is not None:
                    # 对原始白色T恤应用新颜色
                    new_colored_image = change_shirt_color(st.session_state.original_base_image, shirt_color)
                    st.session_state.base_image = new_colored_image
                    
                    # 更新当前图像（带红框的）
                    new_current_image, _ = draw_selection_box(new_colored_image, st.session_state.current_box_position)
                    st.session_state.current_image = new_current_image
                    
                    # 如果有最终设计，也需要更新
                    if st.session_state.final_design is not None:
                        # 重置最终设计，让用户重新应用设计元素
                        st.session_state.final_design = None
                    
                    st.rerun()
            
            # 设计生成主题
            theme = st.text_input("Design prompt (describe your design idea)", "Elegant minimalist pattern in blue and white colors")
            
            # 生成AI设计按钮
            if st.button("🎨 Generate Design"):
                if not theme.strip():
                    st.warning("Please enter a design prompt!")
                else:
                    # 简化提示文本
                    prompt_text = (
                        f"Design a pattern with the following description: {theme}. "
                        f"Create a PNG format image with transparent background, suitable for printing."
                    )
                    
                    with st.spinner("🔮 Generating design... please wait"):
                        custom_design = generate_vector_image(prompt_text)
                        
                        if custom_design:
                            st.session_state.generated_design = custom_design
                            
                            # Composite on the original image
                            composite_image = st.session_state.base_image.copy()
                            
                            # Place design at current selection position
                            left, top = st.session_state.current_box_position
                            box_size = int(1024 * 0.25)
                            
                            # Scale generated pattern to selection area size
                            scaled_design = custom_design.resize((box_size, box_size), Image.LANCZOS)
                            
                            try:
                                # Ensure transparency channel is used for pasting
                                composite_image.paste(scaled_design, (left, top), scaled_design)
                            except Exception as e:
                                st.warning(f"Transparent channel paste failed, direct paste: {e}")
                                composite_image.paste(scaled_design, (left, top))
                            
                            # 保存最终设计但不立即刷新页面
                            st.session_state.final_design = composite_image
                            
                            # 同时更新current_image以便在T恤图像上直接显示设计
                            st.session_state.current_image = composite_image.copy()
                            
                            # 显示生成成功的消息
                            st.success("Design successfully generated! Check the design area for the result.")
                            
                            # 强制页面刷新以显示结果
                            st.rerun()
                        else:
                            st.error("Failed to generate image, please try again later.")
        
        with tab2:
            # 添加文字/Logo选项
            st.write("Add text or logo to your design:")
            
            # 选择文字或Logo
            text_or_logo = st.radio("Select option:", ["Text", "Logo"], horizontal=True)
            
            if text_or_logo == "Text":
                # 文字选项
                # 如果有AI推荐的文字，默认填充
                default_text = st.session_state.get('ai_text_suggestion', "My Brand")
                text_content = st.text_input("Enter text to add:", default_text)
                
                # 添加字体选择
                font_options = ["Arial", "Times New Roman", "Courier", "Verdana", "Georgia", "Impact"]
                # 如果有AI推荐的字体，默认选择
                default_font_index = 0
                if 'ai_font_selection' in st.session_state:
                    try:
                        default_font_index = font_options.index(st.session_state.ai_font_selection)
                    except ValueError:
                        default_font_index = 0
                font_family = st.selectbox("Font family:", font_options, index=default_font_index)
                
                # 文字样式
                text_style = st.multiselect("Text style:", ["Bold", "Italic"], default=[])
                
                # 文字颜色 - 使用AI推荐的颜色（如果有）
                default_text_color = st.session_state.get('ai_text_color', "#000000")
                text_color = st.color_picker("Text color:", default_text_color)
                
                # 增大默认文字大小范围
                text_size = st.slider("Text size:", 20, 120, 48)
                
                # 添加文字按钮
                if st.button("Add Text to Design"):
                    if not text_content.strip():
                        st.warning("Please enter some text!")
                    else:
                        # 创建带有文字的设计
                        if st.session_state.base_image is None:
                            st.warning("Please wait for the T-shirt image to load")
                        else:
                            # 创建一个新的设计或使用现有最终设计
                            if st.session_state.final_design is not None:
                                new_design = st.session_state.final_design.copy()
                            else:
                                new_design = st.session_state.base_image.copy()
                            
                            # 准备绘图对象
                            draw = ImageDraw.Draw(new_design)
                            
                            # 字体映射
                            font_mapping = {
                                "Arial": "arial.ttf",
                                "Times New Roman": "times.ttf",
                                "Courier": "cour.ttf",
                                "Verdana": "verdana.ttf",
                                "Georgia": "georgia.ttf",
                                "Impact": "impact.ttf"
                            }
                            
                            # 通用字体备选方案
                            fallback_fonts = ["DejaVuSans.ttf", "FreeSans.ttf", "LiberationSans-Regular.ttf"]
                            
                            # 导入字体，尝试获取选择的字体
                            font = None
                            try:
                                from PIL import ImageFont
                                # 尝试获取选择的字体
                                font_file = font_mapping.get(font_family, "arial.ttf")
                                
                                # 尝试加载字体，如果失败则尝试备选字体
                                try:
                                    font = ImageFont.truetype(font_file, text_size)
                                except:
                                    # 尝试系统字体路径
                                    system_font_paths = [
                                        "/Library/Fonts/",  # macOS
                                        "/System/Library/Fonts/",  # macOS系统
                                        "C:/Windows/Fonts/",  # Windows
                                        "/usr/share/fonts/truetype/",  # Linux
                                    ]
                                    
                                    # 尝试所有可能的字体位置
                                    for path in system_font_paths:
                                        try:
                                            font = ImageFont.truetype(path + font_file, text_size)
                                            break
                                        except:
                                            continue
                                    
                                    # 如果仍然失败，尝试备选字体
                                    if font is None:
                                        for fallback in fallback_fonts:
                                            try:
                                                for path in system_font_paths:
                                                    try:
                                                        font = ImageFont.truetype(path + fallback, text_size)
                                                        break
                                                    except:
                                                        continue
                                                if font:
                                                    break
                                            except:
                                                continue
                                
                                # 如果所有尝试都失败，使用默认字体
                                if font is None:
                                    font = ImageFont.load_default()
                                    # 尝试将默认字体放大到指定大小
                                    default_size = 10  # 假设默认字体大小
                                    scale_factor = text_size / default_size
                                    # 注意：这种方法可能不是最佳方案，但可以在没有字体的情况下提供备选
                            except Exception as e:
                                st.warning(f"Font loading error: {e}")
                                font = None
                            
                            # 获取当前选择框位置
                            left, top = st.session_state.current_box_position
                            box_size = int(1024 * 0.25)
                            
                            # 在选择框中居中绘制文字
                            text_bbox = draw.textbbox((0, 0), text_content, font=font)
                            text_width = text_bbox[2] - text_bbox[0]
                            text_height = text_bbox[3] - text_bbox[1]
                            
                            text_x = left + (box_size - text_width) // 2
                            text_y = top + (box_size - text_height) // 2
                            
                            # 绘制文字，使用抗锯齿渲染
                            draw.text((text_x, text_y), text_content, fill=text_color, font=font)
                            
                            # 更新设计
                            st.session_state.final_design = new_design
                            
                            # 同时更新current_image以保持两个显示区域的一致性
                            st.session_state.current_image = new_design.copy()
                            
                            # 强制页面刷新以显示最新结果
                            st.rerun()
            else:  # Logo选项
                # Logo来源选择
                logo_source = st.radio("Logo source:", ["Upload your logo", "Choose from presets"], horizontal=True)
                
                if logo_source == "Upload your logo":
                    # Logo上传选项
                    uploaded_logo = st.file_uploader("Upload your logo (PNG or JPG file):", type=["png", "jpg", "jpeg"])
                    logo_image = None
                    
                    if uploaded_logo is not None:
                        try:
                            logo_image = Image.open(BytesIO(uploaded_logo.getvalue())).convert("RGBA")
                        except Exception as e:
                            st.error(f"Error loading uploaded logo: {e}")
                else:  # Choose from presets
                    # 获取预设logo
                    preset_logos = get_preset_logos()
                    
                    if not preset_logos:
                        st.warning("No preset logos found. Please add some images to the 'logos' folder.")
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
                                    preview_width = 100
                                    preview_height = int(preview_width * logo_preview.height / logo_preview.width)
                                    preview = logo_preview.resize((preview_width, preview_height))
                                    
                                    st.image(preview, caption=logo_name)
                                    if st.button(f"Select {logo_name}", key=f"logo_{i}"):
                                        selected_preset_logo = logo_path
                                except Exception as e:
                                    st.error(f"Error loading logo {logo_name}: {e}")
                        
                        # 如果选择了预设logo
                        logo_image = None
                        if selected_preset_logo:
                            try:
                                logo_image = Image.open(selected_preset_logo).convert("RGBA")
                                st.success(f"Selected logo: {os.path.basename(selected_preset_logo)}")
                            except Exception as e:
                                st.error(f"Error loading selected logo: {e}")
                
                # Logo大小和位置
                logo_size = st.slider("Logo size:", 10, 100, 40, format="%d%%")
                logo_position = st.radio("Position:", ["Top Left", "Top Center", "Top Right", "Center", "Bottom Left", "Bottom Center", "Bottom Right"], index=3)
                
                # Logo透明度
                logo_opacity = st.slider("Logo opacity:", 10, 100, 100, 5, format="%d%%")
                
                # 应用Logo按钮
                if st.button("Apply Logo", key="apply_logo"):
                    if logo_image is None:
                        if logo_source == "Upload your logo":
                            st.warning("Please upload a logo first!")
                        else:
                            st.warning("Please select a preset logo first!")
                    else:
                        # 处理Logo
                        try:
                            # 调整Logo大小
                            box_size = int(1024 * 0.25)
                            logo_width = int(box_size * logo_size / 100)
                            logo_height = int(logo_width * logo_image.height / logo_image.width)
                            logo_resized = logo_image.resize((logo_width, logo_height), Image.LANCZOS)
                            
                            # 创建新的设计或使用现有最终设计
                            if st.session_state.final_design is not None:
                                new_design = st.session_state.final_design.copy()
                            else:
                                new_design = st.session_state.base_image.copy()
                            
                            # 获取选择框位置
                            left, top = st.session_state.current_box_position
                            
                            # 计算Logo位置
                            if logo_position == "Top Left":
                                logo_x, logo_y = left + 10, top + 10
                            elif logo_position == "Top Center":
                                logo_x, logo_y = left + (box_size - logo_width) // 2, top + 10
                            elif logo_position == "Top Right":
                                logo_x, logo_y = left + box_size - logo_width - 10, top + 10
                            elif logo_position == "Center":
                                logo_x, logo_y = left + (box_size - logo_width) // 2, top + (box_size - logo_height) // 2
                            elif logo_position == "Bottom Left":
                                logo_x, logo_y = left + 10, top + box_size - logo_height - 10
                            elif logo_position == "Bottom Center":
                                logo_x, logo_y = left + (box_size - logo_width) // 2, top + box_size - logo_height - 10
                            else:  # Bottom Right
                                logo_x, logo_y = left + box_size - logo_width - 10, top + box_size - logo_height - 10
                            
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
                                st.warning(f"Logo paste failed: {e}")
                            
                            # 更新设计
                            st.session_state.final_design = new_design
                            
                            # 同时更新current_image以保持两个显示区域的一致性
                            st.session_state.current_image = new_design.copy()
                            
                            # 强制页面刷新以显示最新结果
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error processing logo: {e}")
    
    # 删除原来页面底部的Final Result部分
    # Return to main interface button - modified here
    if st.button("Return to Main Page"):
        # Clear all design-related states
        st.session_state.base_image = None
        st.session_state.current_image = None
        st.session_state.current_box_position = None
        st.session_state.generated_design = None
        st.session_state.final_design = None
        # Only change page state, retain user info and experiment group
        st.session_state.page = "welcome"
        st.rerun() 
