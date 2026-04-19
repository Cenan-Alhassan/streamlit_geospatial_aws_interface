"""
Main entry point for the Streamlit Application.
"""
import streamlit as st
import leafmap.foliumap as leafmap
import folium
import sys
import os
from typing import Any

# Ensure Python can find our custom modules
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from components.sidebar import render_sidebar
from config.styles import get_layer_style
from models import MapLayer
import api_client


# --- PORTFOLIO DEFAULTS ---
# The AWS container will be running on this URL by default, but you can change it in the sidebar if needed
DEFAULT_API_URL = "https://latdn3bjub.execute-api.eu-north-1.amazonaws.com/default"
DEFAULT_PREFIX = "westminster_green_cover/"

# Optional: Add paths to files you want automatically loaded on first boot (relative to the S3 bucket root)
PRELOAD_FILES = [
    "westminster_green_cover/water_bodies.gpkg",
    "westminster_green_cover/green_cover.gpkg",
    "westminster_green_cover/canopy_cover.gpkg",
    "westminster_green_cover/westminster_boundary.gpkg",
    "westminster_green_cover/mbb_boundary.gpkg"
]

RASTER_EXTENSIONS = (".tif", ".png")
VECTOR_EXTENSIONS = (".geojson", ".gpkg")

def load_layer(api_url: str, s3_path: str):
    """Callback function to fetch data and add it to session state."""
    filename = s3_path.split("/")[-1]
    
    # Prevent duplicate loading
    if any(layer.s3_path == s3_path for layer in st.session_state["layers"]):
        st.toast(f"{filename} is already loaded!", icon="⚠️")
        return

    with st.spinner(f"Loading {filename}..."):
        try:
            if s3_path.lower().endswith(VECTOR_EXTENSIONS):
                gdf = api_client.fetch_vector_data(api_url, s3_path)
                new_layer = MapLayer(
                    type="vector",
                    name=filename,
                    s3_path=s3_path,
                    vector_data=gdf
                )
                st.session_state["layers"].append(new_layer)
                
            elif s3_path.lower().endswith(RASTER_EXTENSIONS):
                bounds = api_client.fetch_raster_metadata(api_url, s3_path)
                
                # Fetch the actual image data as Base64 instead of a URL
                image_b64 = api_client.fetch_raster_image_b64(api_url, s3_path)
                
                new_layer = MapLayer(
                    type="raster",
                    name=filename,
                    s3_path=s3_path,
                    raster_url=image_b64, # Passing the Base64 string here
                    raster_bounds=bounds
                )
                st.session_state["layers"].append(new_layer)
                
            st.toast(f"Successfully loaded {filename}", icon="✅")
        except Exception as e:
            st.error(f"Failed to load {filename}: {str(e)}")

def render_tree(node: dict[str, Any], api_url: str):
    """
    Recursively renders Streamlit expanders and buttons based on a nested dictionary.
    Keys are folder/file names. 
    Values are either dictionaries (sub-folders) or strings (full S3 paths to files).
    """
    for key, value in node.items():
        if isinstance(value, dict):
            # It's a folder: create an expander and recurse inside it
            with st.expander(f"📁 {key}"):
                render_tree(value, api_url)
        elif isinstance(value, str):
            # It's a file path
            is_vector = value.lower().endswith(VECTOR_EXTENSIONS)
            is_raster = value.lower().endswith(RASTER_EXTENSIONS)
            
            if is_vector or is_raster:
                col1, col2 = st.columns([4, 1])
                col1.text(key)
                # Use the full s3_path as the unique button key
                if col2.button("➕", key=f"btn_{value}"):
                    load_layer(api_url, value)


# --- SESSION STATE INITIALIZATION ---
st.set_page_config(page_title="Geospatial AWS Visualiser", layout="wide")

if "initialized" not in st.session_state:
    st.session_state["api_url"] = DEFAULT_API_URL
    st.session_state["s3_prefix"] = DEFAULT_PREFIX
    st.session_state["layers"] = []
    st.session_state["global_opacity"] = 1
    st.session_state["initialized"] = True
    
    # Auto-load portfolio files on first boot
    for file_path in PRELOAD_FILES:
        load_layer(st.session_state["api_url"], file_path)

# --- RENDER UI ---
render_sidebar()

# --- FILE EXPLORER ---
st.subheader("AWS File Explorer")
try:
    file_tree = api_client.fetch_file_structure(
        st.session_state["api_url"], 
        st.session_state["s3_prefix"]
    )
    # Handle the root node correctly based on how the backend nests it
    render_tree(file_tree, st.session_state["api_url"])
except Exception as e:
    st.error("Failed to connect to the backend container. Check your URL.")
    st.caption(str(e))


# --- RENDER MAP ---
m = leafmap.Map(draw_control=False, measure_control=False)
m.add_basemap("OpenStreetMap", show=False)
m.add_basemap("CartoDB.Positron")

opacity_multiplier = st.session_state["global_opacity"]

for layer in st.session_state["layers"]:
    if layer.type == "vector" and layer.vector_data is not None:
        # Get custom styling. If name not specified within config/styles.py, it will default to the standard style.
        custom_style = get_layer_style(layer.name).copy()

        # The global opacity is a multiplier on top of the layer-specific fillOpacity
        base_fill = custom_style.get("fillOpacity", 0.6)
        base_line = custom_style.get("opacity", 1.0)
        
        custom_style["fillOpacity"] = base_fill * opacity_multiplier
        custom_style["opacity"] = base_line * opacity_multiplier

        m.add_gdf(
            layer.vector_data,
            layer_name=layer.name,
            style=custom_style,
            zoom_to_layer=True,
            info_mode="on_click",
            opacity=opacity_multiplier,
        )
        
    elif layer.type == "raster" and layer.raster_bounds is not None:
        m.fit_bounds(layer.raster_bounds)
        # Using the direct URL allows the browser to cache the image, making it much faster
        img_overlay = folium.raster_layers.ImageOverlay(
            name=layer.name,
            image=layer.raster_url,
            bounds=layer.raster_bounds,
            opacity=opacity_multiplier,
            interactive=True,
            cross_origin=False,
            zindex=1,
        )
        img_overlay.add_to(m)

m.add_layer_control()
m.to_streamlit(height=700)

# --- METADATA SECTION ---
if st.session_state["layers"]:
    with st.expander("Layer Details & Dataframes", expanded=False):
        for i, layer in enumerate(st.session_state["layers"]):
            st.markdown(f"**Layer {i + 1}: {layer.name}** (`{layer.type}`)")
            if layer.type == "vector" and layer.vector_data is not None:
                st.dataframe(layer.vector_data.drop(columns=['geometry'], errors='ignore').head())