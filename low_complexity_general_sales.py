import streamlit as st
from PIL import Image, ImageDraw
import requests
from io import BytesIO
import cairosvg
from openai import OpenAI
from streamlit_image_coordinates import streamlit_image_coordinates

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
    """Draw a fixed-size selection box on the image"""
    # Create a copy to avoid modifying the original image
    img_copy = image.copy()
    draw = ImageDraw.Draw(img_copy)
    
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
    
    x2, y2 = x1 + box_size, y1 + box_size
    
    # Draw red outline
    draw.rectangle(
        [(x1, y1), (x2, y2)],
        outline=(255, 0, 0),
        width=2
    )
    
    # Create separate transparent overlay for fill
    overlay = Image.new('RGBA', img_copy.size, (0, 0, 0, 0))
    draw_overlay = ImageDraw.Draw(overlay)
    
    # Draw semi-transparent fill
    draw_overlay.rectangle(
        [(x1, y1), (x2, y2)],
        fill=(255, 0, 0, 50)
    )
    
    # Ensure both images are in RGBA mode
    if img_copy.mode != 'RGBA':
        img_copy = img_copy.convert('RGBA')
    
    # Composite images
    try:
        return Image.alpha_composite(img_copy, overlay), (x1, y1)
    except Exception as e:
        st.warning(f"Image composition failed: {e}")
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
    
    # Create two-column layout
    col1, col2 = st.columns([3, 2])
    
    with col1:
        st.markdown("## Design Area")
    
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
        
        st.markdown("**👇 Click anywhere on the T-shirt to move the design frame**")
        
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
            theme = st.text_input("Theme or keyword (required)", "Elegant pattern")
            
            # 简化颜色选择
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
            
            # 生成AI设计按钮
            if st.button("🎨 Generate Design"):
                if not theme.strip():
                    st.warning("Please enter at least a theme or keyword!")
                else:
                    # 简化提示文本
                    prompt_text = (
                        f"Design a T-shirt pattern with '{theme}' theme in {style} style. "
                        f"Use the following colors: {colors}. "
                        f"Design complexity is {complexity}/10. "
                        f"Create a PNG format image with transparent background, suitable for T-shirt printing."
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
                            
                            st.session_state.final_design = composite_image
                            st.rerun()
                        else:
                            st.error("Failed to generate image, please try again later.")
        
        with tab2:
            # 添加文字/Logo选项
            st.write("Add text or logo to your design:")
            
            # 文字选项
            text_content = st.text_input("Enter text to add:", "My Brand")
            
            # 文字颜色
            text_color = st.color_picker("Text color:", "#000000")
            
            # 文字大小
            text_size = st.slider("Text size:", 10, 50, 24)
            
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
                        
                        # 导入字体(使用默认字体)
                        try:
                            from PIL import ImageFont
                            font = ImageFont.truetype("arial.ttf", text_size)
                        except:
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
                        
                        # 绘制文字
                        draw.text((text_x, text_y), text_content, fill=text_color, font=font)
                        
                        # 更新设计
                        st.session_state.final_design = new_design
                        st.rerun()
    
    # Display final effect - move out of col2, place at bottom of overall page
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
        specs_col1, specs_col2 = st.columns(2)
        
        with specs_col1:
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
        download_col1, download_col2 = st.columns(2)
        with download_col1:
            buf = BytesIO()
            st.session_state.final_design.save(buf, format="PNG")
            buf.seek(0)
            st.download_button(
                label="💾 Download Custom Design",
                data=buf,
                file_name="custom_tshirt.png",
                mime="image/png"
            )
        
        with download_col2:
            # Confirm completion button
            if st.button("Confirm Completion"):
                st.session_state.page = "survey"
                st.rerun()
    
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