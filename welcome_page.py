import streamlit as st
import pandas as pd
import os

# 从主文件导入常量
DATA_FILE = "experiment_data.csv"

# Welcome and information collection page
def show_welcome_page():
    st.title("👕 AI Co-Creation Clothing Consumer Behavior Experiment")
    
    with st.container():
        st.markdown('<div class="welcome-card">', unsafe_allow_html=True)
        st.markdown("### Welcome to our experiment!")
        st.markdown("""
        This experiment aims to study the impact of AI Co-Creation on consumer purchasing behavior. You will have the opportunity to experience the T-shirt customization process and share your feedback.
        
        **Experiment Process**:
        1. Choose an experiment group
        2. Complete T-shirt customization
        3. Submit survey feedback
        
        Your participation is crucial to our research. Thank you for your support!
        """)
        st.markdown('</div>', unsafe_allow_html=True)
    
    st.markdown("### Please select the experiment group you want to participate in")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.markdown('<div class="group-card">', unsafe_allow_html=True)
        st.markdown("#### Low Task Complexity-General Sales")
        st.markdown("""
        - Simple customization tasks 
        - General sales environment
        - Create unique designs based on your preferences
        - Freely place design patterns on the T-shirt
        """)
        if st.button("Choose Low Complexity-General"):
            st.session_state.experiment_group = "AI Customization Group"
            st.session_state.user_info = {
                'age': 25,  # 默认值
                'gender': "Male",  # 默认值
                'shopping_frequency': "Weekly",  # 默认值
                'customize_experience': "Some experience",  # 默认值
                'ai_attitude': 5,  # 默认值
                'uniqueness_importance': 5  # 默认值
            }
            st.session_state.page = "design"
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
    
    with col2:
        st.markdown('<div class="group-card">', unsafe_allow_html=True)
        st.markdown("#### High Task Complexity-General Sales")
        st.markdown("""
        - Advanced customization options
        - General sales environment
        - Choose and manipulate professional designs
        - Multiple customization features available
        """)
        if st.button("Choose High Complexity-General"):
            st.session_state.experiment_group = "Preset Design Group"
            st.session_state.user_info = {
                'age': 25,  # 默认值
                'gender': "Male",  # 默认值
                'shopping_frequency': "Weekly",  # 默认值
                'customize_experience': "Some experience",  # 默认值
                'ai_attitude': 5,  # 默认值
                'uniqueness_importance': 5  # 默认值
            }
            st.session_state.page = "design"
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
    
    with col3:
        st.markdown('<div class="group-card">', unsafe_allow_html=True)
        st.markdown("#### Low Task Complexity-Pop up Sales")
        st.markdown("""
        - Simple customization tasks
        - Pop-up store experience
        - Create designs with minimal options
        - Quick and straightforward process
        """)
        if st.button("Choose Low Complexity-Pop-up"):
            st.session_state.experiment_group = "AI Design Group"
            st.session_state.user_info = {
                'age': 25,  # 默认值
                'gender': "Male",  # 默认值
                'shopping_frequency': "Weekly",  # 默认值
                'customize_experience': "Some experience",  # 默认值
                'ai_attitude': 5,  # 默认值
                'uniqueness_importance': 5  # 默认值
            }
            st.session_state.page = "design"
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
        
    with col4:
        st.markdown('<div class="group-card">', unsafe_allow_html=True)
        st.markdown("#### High Task Complexity-Pop up Sales")
        st.markdown("""
        - Advanced customization options
        - Pop-up store experience
        - Create highly detailed designs
        - Extensive customization features 
        """)
        if st.button("Choose High Complexity-Pop-up"):
            st.session_state.experiment_group = "AI Creation Group"
            st.session_state.user_info = {
                'age': 25,  # 默认值
                'gender': "Male",  # 默认值
                'shopping_frequency': "Weekly",  # 默认值
                'customize_experience': "Some experience",  # 默认值
                'ai_attitude': 5,  # 默认值
                'uniqueness_importance': 5  # 默认值
            }
            st.session_state.page = "design"
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

    # Admin area - Experiment data analysis (password protected)
    st.markdown("---")
    with st.expander("Experiment Data Analysis (Admin Only)"):
        admin_password = st.text_input("Admin Password", type="password")
        if admin_password == "admin123":  # Simple password example, use more secure authentication in actual applications
            try:
                # Read experiment data
                experiment_df = pd.read_csv(DATA_FILE)
                
                if not experiment_df.empty:
                    st.markdown("### Experiment Data Statistics")
                    
                    # Basic statistics
                    st.markdown("#### Participant Statistics")
                    group_counts = experiment_df['experiment_group'].value_counts()
                    st.write(f"Total participants: {len(experiment_df)}")
                    st.write(f"Low Task Complexity-General Sales: {group_counts.get('AI Customization Group', 0)} people")
                    st.write(f"High Task Complexity-General Sales: {group_counts.get('Preset Design Group', 0)} people")
                    st.write(f"Low Task Complexity-Pop up Sales: {group_counts.get('AI Design Group', 0)} people")
                    st.write(f"High Task Complexity-Pop up Sales: {group_counts.get('AI Creation Group', 0)} people")
                    
                    # Purchase intention comparison
                    st.markdown("#### Purchase Intention Comparison")
                    purchase_by_group = experiment_df.groupby('experiment_group')['purchase_intent'].mean()
                    st.bar_chart(purchase_by_group)
                    
                    # Satisfaction comparison
                    st.markdown("#### Satisfaction Comparison")
                    satisfaction_by_group = experiment_df.groupby('experiment_group')['satisfaction_score'].mean()
                    st.bar_chart(satisfaction_by_group)
                    
                    # Willing to pay price comparison
                    st.markdown("#### Willing to Pay Price Comparison")
                    price_by_group = experiment_df.groupby('experiment_group')['price_willing_to_pay'].mean()
                    st.bar_chart(price_by_group)
                    
                    # Export data button
                    st.download_button(
                        label="Export Complete Data (CSV)",
                        data=experiment_df.to_csv(index=False).encode('utf-8'),
                        file_name="experiment_data_export.csv",
                        mime="text/csv"
                    )
                else:
                    st.info("No experiment data yet, please wait for user participation.")
            except Exception as e:
                st.error(f"Error loading or analyzing data: {e}")
        elif admin_password:
            st.error("Incorrect password, unable to access admin area.") 