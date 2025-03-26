import streamlit as st
from PIL import Image, ImageDraw
import requests
from io import BytesIO
import cairosvg
from openai import OpenAI
from streamlit_image_coordinates import streamlit_image_coordinates
import os

# API配置信息 - 实际使用时应从主文件传入或使用环境变量
API_KEY = "sk-lNVAREVHjj386FDCd9McOL7k66DZCUkTp6IbV0u9970qqdlg"
BASE_URL = "https://api.deepbricks.ai/v1/"

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
                    try:
                        png_data = cairosvg.svg2png(bytestring=image_resp.content)
                        return Image.open(BytesIO(png_data)).convert("RGBA")
                    except Exception as conv_err:
                        st.error(f"Error converting SVG to PNG: {conv_err}")
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

def apply_color_to_shirt(image, color_hex):
    """给T恤应用新颜色
    
    Args:
        image: 原始T恤图像
        color_hex: 十六进制颜色代码，如 "#FFFFFF"
        
    Returns:
        应用新颜色后的T恤图像
    """
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

# AI Design Group design page
def show_low_complexity_popup_sales():
    st.title("👕 AI Co-Creation Experiment Platform")
    st.markdown("### Low Task Complexity-Pop up Sales - Create Your Unique T-shirt Design")
    
    # 初始化T恤颜色状态变量
    if 'original_white_shirt' not in st.session_state:
        st.session_state.original_white_shirt = None  # 保存原始白色T恤图像
    if 'current_shirt_color' not in st.session_state:
        st.session_state.current_shirt_color = "#FFFFFF"  # 默认白色
        
    # 添加Pop-up Sales情境描述
    st.info("""
    **Pop-up Store Environment**
    
    You are visiting our temporary pop-up store in a busy shopping mall. There are other customers 
    waiting for their turn to use this customization kiosk. The store staff has informed you that 
    the experience is limited to 15 minutes per customer. Please design your T-shirt efficiently 
    while enjoying this exclusive in-person customization opportunity.
    """)
    
    # 任务复杂度说明
    st.markdown("""
    <div style="background-color:#f0f0f0; padding:10px; border-radius:5px; margin-bottom:15px">
    <b>Basic Customization Options</b>: In this experience, you can customize your T-shirt with simple options:
    <ul>
        <li>Choose colors for your design</li>
        <li>Add text or logo elements</li>
        <li>Generate design patterns</li>
        <li>Position your design on the T-shirt</li>
    </ul>
    </div>
    """, unsafe_allow_html=True)
    
    # Create two-column layout
    col1, col2 = st.columns([3, 2])
    
    with col1:
        st.markdown("## Design Area")
        
        # 添加AI建议框
        with st.expander("🤖 AI Design Suggestions", expanded=True):
            st.markdown("""
            **Quick Design Guide:**
            
            Choose a T-shirt color that matches your event theme for best results - casual events work well with blues or greens. Position your design centrally on the T-shirt for optimal visibility and professional appearance. Simple geometric shapes or patterns tend to look better and have broader appeal than complex designs. If you're short on time, selecting a preset logo or simple text is the quickest way to create an effective design. Always prioritize clarity and readability in your design choices, avoiding overly complex elements that might not translate well onto fabric. Remember that simplicity often creates the most elegant and versatile designs that work across various contexts.
            """)
    
        # Load T-shirt base image
        if st.session_state.base_image is None:
            try:
                # 加载原始白色T恤图像
                base_image = Image.open("white_shirt.png").convert("RGBA")
                # 保存原始白色T恤图像供后续颜色变化使用
                st.session_state.original_white_shirt = base_image.copy()
                # 应用当前选择的颜色（如果不是白色）
                if st.session_state.current_shirt_color != "#FFFFFF":
                    base_image = apply_color_to_shirt(base_image, st.session_state.current_shirt_color)
                st.session_state.base_image = base_image
                # Initialize by drawing selection box in the center
                initial_image, initial_pos = draw_selection_box(base_image)
                st.session_state.current_image = initial_image
                st.session_state.current_box_position = initial_pos
            except Exception as e:
                st.error(f"Error loading white T-shirt image: {e}")
                st.stop()
        
        # 在Design标签页激活时显示点击提示
        # 删除提示文本
        pass
        
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
            
            # 添加T恤规格信息显示
            # 创建颜色名称映射词典
            color_names = {
                "#FFFFFF": "White",
                "#000000": "Black",
                "#FF0000": "Red",
                "#00FF00": "Green",
                "#0000FF": "Blue",
                "#FFFF00": "Yellow",
                "#FF00FF": "Magenta",
                "#00FFFF": "Cyan",
                "#FFA500": "Orange",
                "#800080": "Purple",
                "#008000": "Dark Green",
                "#800000": "Maroon",
                "#008080": "Teal",
                "#000080": "Navy",
                "#808080": "Gray"
            }
            
            # 尝试匹配确切颜色，如果不存在则显示十六进制代码
            color_hex = st.session_state.current_shirt_color
            color_name = color_names.get(color_hex.upper(), f"Custom ({color_hex})")
            
            # 显示颜色信息
            st.markdown(f"**Color:** {color_name}")
            
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
            # 简化设计选项 - 只保留主题和颜色选择
            theme = st.text_input("Design theme or keyword (required)", "Elegant pattern")
            
            # 添加T恤颜色选择
            st.markdown("### T-shirt Color")
            shirt_color = st.color_picker("Choose your T-shirt color:", "#FFFFFF")
            
            # 如果颜色变化，更新T恤颜色
            if "current_shirt_color" not in st.session_state:
                st.session_state.current_shirt_color = "#FFFFFF"
                
            if st.session_state.current_shirt_color != shirt_color:
                st.session_state.current_shirt_color = shirt_color
                
                # 重新给白色T恤上色
                if st.session_state.base_image is not None:
                    # 给T恤重新上色
                    colored_shirt = apply_color_to_shirt(st.session_state.original_white_shirt.copy(), shirt_color)
                    st.session_state.base_image = colored_shirt
                    
                    # 更新当前图像以反映选择框
                    new_image, new_pos = draw_selection_box(colored_shirt, st.session_state.current_box_position)
                    st.session_state.current_image = new_image
                    st.session_state.current_box_position = new_pos
                    
                    # 如果已有最终设计，重新应用
                    if st.session_state.final_design is not None:
                        # 暂时保存生成的设计，并在有新的彩色T恤后重新应用
                        if st.session_state.generated_design is not None:
                            custom_design = st.session_state.generated_design
                            composite_image = colored_shirt.copy()
                            
                            # 放置设计在当前选择位置
                            left, top = st.session_state.current_box_position
                            box_size = int(1024 * 0.25)
                            
                            # 缩放生成的图案到选择区域大小
                            scaled_design = custom_design.resize((box_size, box_size), Image.LANCZOS)
                            
                            try:
                                # 确保使用透明通道进行粘贴
                                composite_image.paste(scaled_design, (left, top), scaled_design)
                            except Exception as e:
                                composite_image.paste(scaled_design, (left, top))
                            
                            st.session_state.final_design = composite_image
                    
                    st.rerun()
            
            # 简化颜色选择
            st.markdown("### Design Colors")
            color_scheme_options = [
                "Soft warm tones (pink, gold, light orange)",
                "Fresh cool tones (blue, mint, white)",
                "Nature colors (green, brown, beige)",
                "Bright and vibrant (red, yellow, orange)",
                "Black and white contrast",
                "Custom colors"
            ]
            color_scheme = st.selectbox("Color scheme", color_scheme_options)
            
            # If custom colors are selected, show input field
            if color_scheme == "Custom colors":
                colors = st.text_input("Enter desired colors (comma separated)", "pink, gold, sky blue")
            else:
                # Set corresponding color values based on selected scheme
                color_mapping = {
                    "Soft warm tones (pink, gold, light orange)": "pink, gold, light orange, cream",
                    "Fresh cool tones (blue, mint, white)": "sky blue, mint green, white, light gray",
                    "Nature colors (green, brown, beige)": "forest green, brown, beige, olive",
                    "Bright and vibrant (red, yellow, orange)": "bright red, yellow, orange, lemon yellow",
                    "Black and white contrast": "black, white, gray",
                }
                colors = color_mapping.get(color_scheme, "blue, green, red")
            
            # 设计风格 - 简化选项
            style_options = ["Minimalist", "Artistic", "Geometric", "Abstract"]
            style = st.selectbox("Design style", style_options)
            
            # 简化复杂度选项
            complexity = st.slider("Design complexity", 1, 10, 5)
            
            # 自动设置详细程度
            detail_level = "low" if complexity <= 3 else "medium" if complexity <= 7 else "high"
            
            # 生成设计按钮
            if st.button("Generate Design", key="generate_design"):
                if theme.strip() == "":
                    st.warning("Please enter a design theme!")
                else:
                    # 构建提示文本
                    prompt_text = (
                        f"Design a T-shirt pattern with '{theme}' theme in {style} style. "
                        f"Use the following colors: {colors}. "
                        f"Design complexity is {complexity}/10. "
                        f"Create a PNG format image with transparent background, suitable for T-shirt printing."
                    )
                    
                    with st.spinner("🔮 Generating design... please wait"):
                        # 调用生成函数
                        custom_design = generate_vector_image(prompt_text)
                        
                        if custom_design:
                            # 保存生成的设计
                            st.session_state.generated_design = custom_design
                            
                            # 创建合成图像
                            composite_image = st.session_state.base_image.copy()
                            
                            # 获取当前选择框位置
                            left, top = st.session_state.current_box_position
                            box_size = int(1024 * 0.25)
                            
                            # 调整设计大小以适应选择框
                            scaled_design = custom_design.resize((box_size, box_size), Image.LANCZOS)
                            
                            try:
                                # 使用透明通道粘贴
                                composite_image.paste(scaled_design, (left, top), scaled_design)
                            except Exception as e:
                                # 如果透明通道粘贴失败，使用直接粘贴
                                st.warning(f"Transparent paste failed: {e}")
                                composite_image.paste(scaled_design, (left, top))
                            
                            # 保存最终设计但不立即刷新页面
                            st.session_state.final_design = composite_image
                            
                            # 显示生成成功的消息
                            st.success("Design successfully generated! Check the left side for the result.")
                        else:
                            st.error("Failed to generate image. Please try again.")
        
        with tab2:
            # 添加文字/Logo选项
            st.write("Add text or logo to your design:")
            
            # 选择文字或Logo
            text_or_logo = st.radio("Select option:", ["Text", "Logo"], horizontal=True)
            
            if text_or_logo == "Text":
                # 文字选项
                text_content = st.text_input("Enter text to add:", "My Brand")
                
                # 添加字体选择
                font_options = ["Arial", "Times New Roman", "Courier", "Verdana", "Georgia", "Impact"]
                font_family = st.selectbox("Font family:", font_options)
                
                # 文字样式
                text_style = st.multiselect("Text style:", ["Bold", "Italic"], default=[])
                
                # 文字颜色
                text_color = st.color_picker("Text color:", "#000000")
                
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