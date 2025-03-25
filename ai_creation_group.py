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

# AI Creation Group design page
def show_ai_creation_group():
    st.title("👕 AI Co-Creation Experiment Platform")
    st.markdown("### High Task Complexity-Pop up Sales - Create Your Unique T-shirt Design")
    
    # Create two-column layout
    col1, col2 = st.columns([3, 2])
    
    with col1:
        st.markdown("## Design Area")
    
        # Load T-shirt base image
        if st.session_state.base_image is None:
            try:
                base_image = Image.open("white_shirt.png").convert("RGBA")
                st.session_state.base_image = base_image
                # Initialize by drawing selection box in the center
                initial_image, initial_pos = draw_selection_box(base_image)
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
        
        # User input for personalization parameters - improved prompts and defaults
        theme = st.text_input("Theme or keyword (required)", "Elegant floral pattern")
        
        # Add style selection dropdown with more professional style options
        style_options = [
            "Watercolor style", "Sketch style", "Geometric shapes", "Minimalist", 
            "Vintage style", "Pop art", "Japanese style", "Nordic design",
            "Classical ornament", "Digital illustration", "Abstract art", "Ethnic motifs"
        ]
        style = st.selectbox("Design style", style_options, index=0)
        
        # Improved color selection
        color_scheme_options = [
            "Soft warm tones (pink, gold, light orange)",
            "Fresh cool tones (blue, mint, white)",
            "Nature colors (green, brown, beige)",
            "Bright and vibrant (red, yellow, orange)",
            "Elegant deep tones (navy, purple, dark green)",
            "Black and white contrast",
            "Colorful mix",
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
                "Elegant deep tones (navy, purple, dark green)": "navy blue, violet, dark green, burgundy",
                "Black and white contrast": "black, white, gray",
                "Colorful mix": "red, blue, yellow, green, purple, orange"
            }
            colors = color_mapping[color_scheme]
        
        # Improved design details options
        details_options = [
            "Fine outlines and lines",
            "Smooth gradient effects",
            "Floral and plant elements",
            "Geometric shapes and patterns",
            "Waves and curves",
            "Dotted textures",
            "Repeating patterns",
            "Randomly distributed elements",
            "Custom details"
        ]
        details_type = st.selectbox("Detail type", details_options)
        
        if details_type == "Custom details":
            details = st.text_area("Describe desired design details", "Elegant curves and swirling shapes")
        else:
            # Preset detail descriptions
            details_mapping = {
                "Fine outlines and lines": "Design includes fine outlines and smooth lines, highlighting the shape and contours of the pattern.",
                "Smooth gradient effects": "Design uses smooth color gradients, elegantly transitioning from one color to another.",
                "Floral and plant elements": "Design incorporates delicate flowers, leaves and other plant elements with a natural organic feel.",
                "Geometric shapes and patterns": "Design uses clean geometric shapes like triangles, circles, squares arranged in attractive patterns.",
                "Waves and curves": "Design incorporates flowing waves and elegant curves creating a sense of movement and rhythm.",
                "Dotted textures": "Design uses dot patterns to create texture and depth, similar to pointillism technique.",
                "Repeating patterns": "Design contains regularly repeating elements forming a unified, harmonious pattern.",
                "Randomly distributed elements": "Elements in the design are randomly distributed, creating a natural, irregular appearance."
            }
            details = details_mapping[details_type]
        
        # Add design complexity option
        complexity = st.slider("Design complexity", 1, 10, 5, 
                              help="1 means very simple, 10 means very complex")
        
        # Automatically set detail level based on complexity
        detail_level = "low" if complexity <= 3 else "medium" if complexity <= 7 else "high"
        
        # Improved design generation button
        if st.button("🎨 Generate AI Design"):
            if not theme.strip():
                st.warning("Please enter at least a theme or keyword!")
            else:
                # Generate more professional and detailed prompt text
                prompt_text = (
                    f"Design a T-shirt pattern with '{theme}' theme using {style}. "
                    f"Use the following colors: {colors}. "
                    f"Design details: {details}. "
                    f"Design complexity is {complexity}/10 with {detail_level} level of detail. "
                    f"The pattern should have an attractive, balanced composition suitable for a T-shirt print. "
                    f"Create a PNG format image with transparent background, ensuring only the design elements are visible with no background. "
                    f"The design style should be professional and modern, appropriate for clothing prints. "
                    f"Ensure the pattern has crisp edges and a high-quality appearance. "
                    f"The output must be PNG with alpha channel transparency."
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
        
        # Provide download option
        col1, col2 = st.columns(2)
        with col1:
            buf = BytesIO()
            st.session_state.final_design.save(buf, format="PNG")
            buf.seek(0)
            st.download_button(
                label="💾 Download Custom Design",
                data=buf,
                file_name="custom_tshirt.png",
                mime="image/png"
            )
        
        with col2:
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