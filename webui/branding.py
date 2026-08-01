"""Branding UI components for ViralCutter WebUI."""
import gradio as gr
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def load_brand_presets():
    """Load list of available brand presets."""
    try:
        from scripts.brand_manager import list_presets
        presets = list_presets()
        return [p["name"] for p in presets]
    except Exception:
        return []


def create_branding_tab(watermark_controls):
    """
    Create branding configuration tab.
    
    Args:
        watermark_controls: dict with existing watermark control components
    Returns:
        dict of new branding components
    """
    with gr.Tab("Branding"):
        with gr.Row():
            brand_preset_selector = gr.Dropdown(
                choices=load_brand_presets(),
                label="Brand Preset",
                interactive=True,
                value=None,
            )
            load_preset_btn = gr.Button("Load Preset")
            save_preset_btn = gr.Button("Save Preset")
            refresh_presets_btn = gr.Button("Refresh")
        
        # Outro section
        with gr.Group():
            gr.Markdown("### Outro")
            with gr.Row():
                outro_enabled = gr.Checkbox(label="Enable Outro", value=False)
                outro_mode = gr.Radio(
                    ["per-clip", "compilation-only"],
                    label="Outro Mode",
                    value="compilation-only",
                )
            outro_type = gr.Radio(
                ["image", "video", "text"],
                label="Outro Type",
                value="image",
            )
            outro_source = gr.File(
                label="Outro Source (Image/Video)",
                file_count="single",
                file_types=["image", "video"],
                visible=True,
            )
            outro_text = gr.Textbox(
                label="Outro Text",
                value="Thanks for watching!",
                visible=False,
            )
            with gr.Row():
                outro_duration = gr.Slider(
                    minimum=1, maximum=30, value=5, step=1,
                    label="Duration (seconds)",
                )
                outro_transition = gr.Dropdown(
                    ["none", "fade", "crossfade"],
                    label="Transition",
                    value="fade",
                )
                outro_transition_duration = gr.Slider(
                    minimum=0.0, maximum=5.0, value=1.0, step=0.1,
                    label="Transition Duration (s)",
                )
    
    # Toggle outro type visibility
    def toggle_outro_type(outro_type):
        is_text = outro_type == "text"
        return gr.update(visible=not is_text), gr.update(visible=is_text)
    
    outro_type.change(
        toggle_outro_type,
        inputs=outro_type,
        outputs=[outro_source, outro_text],
    )
    
    return {
        "brand_preset_selector": brand_preset_selector,
        "load_preset_btn": load_preset_btn,
        "save_preset_btn": save_preset_btn,
        "refresh_presets_btn": refresh_presets_btn,
        "outro_enabled": outro_enabled,
        "outro_mode": outro_mode,
        "outro_type": outro_type,
        "outro_source": outro_source,
        "outro_text": outro_text,
        "outro_duration": outro_duration,
        "outro_transition": outro_transition,
        "outro_transition_duration": outro_transition_duration,
    }
