# AI Co-Creation T-shirt Design Platform

This platform is designed for conducting consumer behavior experiments around AI co-creation in clothing design.

## New Features

- **AI Design Assistant**: Uses ChatGPT-4o-mini to generate various design combinations based on user's input concepts or themes. The assistant provides multiple design options with different styles, colors, and detailed descriptions.

- **Design Suggestions Implementation**: Users can select any AI-generated design suggestion and apply it directly to their T-shirt design.

- **Enhanced User Experience**: Improved UI with visual feedback during design generation, real-time preview, and better design organization.

## Experiment Groups

The platform features four distinct experiment groups:

1. **AI Customization Group** (Low Complexity - General Sales): Simple customization in a standard online shopping environment.
2. **AI Design Group** (Low Complexity - Pop-up Sales): Simple customization in a time-limited pop-up store setting.
3. **AI Creation Group** (High Complexity - Pop-up Sales): Advanced customization with extensive options in a pop-up environment.
4. **Preset Design Group** (High Complexity - General Sales): Advanced customization with pre-designed templates in a standard environment.

## Technical Requirements

See `requirements.txt` for detailed dependencies.

## Setup

1. Install dependencies: `pip install -r requirements.txt`
2. Run the application: `streamlit run app.py`

## Admin Access

The admin section for viewing experiment data is available on the welcome page with password "admin123".