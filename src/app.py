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

def load_layer(
    api_url: str, 
    s3_path: str, 
    target_list: list = None, 
    show_ui: bool = True
):
    """Callback function to fetch data and add it to session state."""
    if target_list is None:
        target_list = st.session_state["layers"]
        
    filename = s3_path.split("/")[-1]
    
    # Prevent duplicate loading in the final layers list
    if any(layer.s3_path == s3_path for layer in st.session_state["layers"]):
        return

    # Use spinner only if UI is requested (for fresh downloads)
    if show_ui:
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
                    target_list.append(new_layer)
                    
                elif s3_path.lower().endswith(RASTER_EXTENSIONS):
                    bounds = api_client.fetch_raster_metadata(api_url, s3_path)
                    image_b64 = api_client.fetch_raster_image_b64(api_url, s3_path)
                    new_layer = MapLayer(
                        type="raster", 
                        name=filename, 
                        s3_path=s3_path, 
                        raster_url=image_b64, 
                        raster_bounds=bounds
                    )
                    target_list.append(new_layer)
                
                st.session_state["toast_queue"].append(f"Successfully loaded {filename}")
            except Exception as e:
                st.error(f"Failed to load {filename}: {str(e)}")
    else:
        # Silent load (for cache hits on refresh)
        try:
            if s3_path.lower().endswith(VECTOR_EXTENSIONS):
                gdf = api_client.fetch_vector_data(api_url, s3_path)
                target_list.append(MapLayer(
                    type="vector", 
                    name=filename, 
                    s3_path=s3_path, 
                    vector_data=gdf
                ))
            elif s3_path.lower().endswith(RASTER_EXTENSIONS):
                bounds = api_client.fetch_raster_metadata(api_url, s3_path)
                image_b64 = api_client.fetch_raster_image_b64(api_url, s3_path)
                target_list.append(MapLayer(
                    type="raster", 
                    name=filename, 
                    s3_path=s3_path, 
                    raster_url=image_b64, 
                    raster_bounds=bounds
                ))
        except Exception:
            pass # Silent failure on background refresh is fine, next run will catch it with UI

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
    st.session_state["global_opacity"] = 1.0
    # Move PRELOAD_FILES to a queue and a buffer
    st.session_state["preload_queue"] = PRELOAD_FILES.copy()
    st.session_state["preload_buffer"] = []
    st.session_state["toast_queue"] = []
    st.session_state["initialized"] = True

# --- QUEUE SYNC ---
# On every run, ensure queue doesn't contain things already in layers
if st.session_state.get("preload_queue"):
    loaded = {l.s3_path for l in st.session_state["layers"]}
    st.session_state["preload_queue"] = [
        p for p in st.session_state["preload_queue"] if p not in loaded
    ]

# Handle pending notifications from previous runs
if st.session_state.get("toast_queue"):
    for msg in st.session_state["toast_queue"]:
        st.toast(msg, icon="✅")
    st.session_state["toast_queue"] = []

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
    st.error("Failed to connect to the backend container.")
    st.caption(str(e))

# Placeholder for the spinner to appear below the file explorer during preloads
preload_status = st.empty()

# --- RENDER MAP ---
m = leafmap.Map(draw_control=False, measure_control=False)
m.add_basemap("OpenStreetMap", show=False)
m.add_basemap("CartoDB.Positron")

# Track bounds to zoom the map correctly
layer_bounds_list = []

opacity_multiplier = st.session_state["global_opacity"]

for layer in st.session_state["layers"]:
    if layer.type == "vector" and layer.vector_data is not None:
        # Get custom styling. If name not specified within config/styles.py, it will default to the standard style.
        style = get_layer_style(layer.name).copy()
        # The global opacity is a multiplier on top of the layer-specific fillOpacity
        style["fillOpacity"] = style.get("fillOpacity", 0.6) * opacity_multiplier
        style["opacity"] = style.get("opacity", 1.0) * opacity_multiplier

        m.add_gdf(
            layer.vector_data, 
            layer_name=layer.name, 
            style=style, 
            zoom_to_layer=False, 
            info_mode="on_click", 
            opacity=opacity_multiplier
        )

        # Calculate bounds: [minx, miny, maxx, maxy] -> [[miny, minx], [maxy, maxx]]
        b = layer.vector_data.total_bounds
        layer_bounds_list.append([[b[1], b[0]], [b[3], b[2]]])

    elif layer.type == "raster" and layer.raster_bounds is not None:
        folium.raster_layers.ImageOverlay(
            name=layer.name, 
            image=layer.raster_url, 
            bounds=layer.raster_bounds, 
            opacity=opacity_multiplier, 
            interactive=True, 
            cross_origin=False, 
            zindex=1
        ).add_to(m)
        layer_bounds_list.append(layer.raster_bounds)

# Automatically fit map to the layers' combined extent
if layer_bounds_list:
    lats = [b[0][0] for b in layer_bounds_list] + [b[1][0] for b in layer_bounds_list]
    lons = [b[0][1] for b in layer_bounds_list] + [b[1][1] for b in layer_bounds_list]
    m.fit_bounds([[min(lats), min(lons)], [max(lats), max(lons)]])
else:
    # Set a default view for the Westminster area if no layers are loaded yet
    m.set_center(-0.13, 51.50, 12)

# Attribution / Copyright
attribution = "Contains OS data (C) Crown copyright 2026"
m.add_text(attribution, position="bottomright", fontsize=10)

m.add_layer_control()
m.to_streamlit(height=700)

# --- METADATA SECTION ---
if st.session_state["layers"]:
    with st.expander("Layer Details & Dataframes", expanded=False):
        for i, layer in enumerate(st.session_state["layers"]):
            st.markdown(f"**Layer {i + 1}: {layer.name}** (`{layer.type}`)")
            if layer.type == "vector" and layer.vector_data is not None:
                df_head = layer.vector_data.drop(
                    columns=['geometry'], 
                    errors='ignore'
                ).head()
                st.dataframe(df_head)

# --- INCREMENTAL BACKGROUND LOADER ---
# This part runs after the UI has been rendered for this turn
if st.session_state.get("preload_queue"):
    # Get the next file to load
    next_file = st.session_state["preload_queue"].pop(0)
    # Render the spinner in the designated placeholder area
    # Load into the buffer instead of the active layers list
    with preload_status:
        # We always use show_ui=True here because if it's a fresh session, we want the spinner.
        # If it's a reload, the cache hit will make this finish in milliseconds, 
        # meaning the spinner will barely be visible.
        load_layer(
            st.session_state["api_url"], 
            next_file, 
            target_list=st.session_state["preload_buffer"], 
            show_ui=True
        )
    
    # If the queue is now empty, move all buffered layers to the map
    if not st.session_state["preload_queue"]:
        st.session_state["layers"].extend(st.session_state["preload_buffer"])
        st.session_state["preload_buffer"] = []
        
    # Trigger a rerun to update the map and move to the next file (or show the final map)
    st.rerun()
