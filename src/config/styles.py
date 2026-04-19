# src/config/styles.py

# Standard Leaflet style properties: 
# fillOpacity, color (border), fillColor, weight (border thickness)
DEFAULT_STYLE = {
    "fillColor": "#3186cc",
    "weight": 1,
    "opacity": 1,
    "fillOpacity": 0.6,
}

# Specific styles for portfolio layers
LAYER_STYLES = {
    "green_cover": {
        "fillColor": "#41a362",  
        "weight": 0.1,
        "fillOpacity": 1,
    },
    "canopy_cover": {
        "fillColor": "#007534", 
        "weight": 0.1,
        "fillOpacity": 1,
    },
    "water_bodies": {
        "fillColor": "#67aced",
        "weight": 0.1,
        "fillOpacity": 1,
    },
    "boundary": {
        "color": "#d42626",
        "weight": 1.5,
        "fillOpacity": 0,
    }
}

def get_layer_style(layer_name: str) -> dict:
    """
    Returns a style dictionary for the entire layer.
    """
    # Find a matching style or return the default
    # Look for a match in our config, otherwise use default
    for key, custom_style in LAYER_STYLES.items():
        if key in layer_name.lower():
            return custom_style
            
    return DEFAULT_STYLE