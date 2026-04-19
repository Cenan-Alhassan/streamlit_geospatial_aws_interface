"""
API Client for communicating with the Geospatial AWS Server container.
"""
import requests
import json
import geopandas as gpd
from io import StringIO
from typing import Any
import base64

def _call_backend(api_url: str, path: str, method: str = "GET") -> Any:
    """
    Internal helper to handle the difference between 
    Live API Gateway (GET) and Local Emulator (POST).
    """
    if "localhost" in api_url:
        # 1. The specific URL the Emulator listens on
        emulator_url = f"{api_url}/2015-03-31/functions/function/invocations"
        
        # 2. Construct the mock API Gateway event
        payload = {
            "pathParameters": {"proxy": path},
            "httpMethod": method
        }
        
        response = requests.post(emulator_url, json=payload)
        response.raise_for_status()
        
        # 3. UNWRAP: The emulator returns {"statusCode": 200, "body": "...", ...}
        # We need to extract the 'body' and parse it as JSON
        lambda_result = response.json()
        return json.loads(lambda_result["body"])
    
    else:
        # Standard behavior for live AWS
        url = f"{api_url}/{path}"
        response = requests.get(url)
        response.raise_for_status()
        return response.json()

def fetch_file_structure(api_url: str, prefix: str) -> dict[str, Any]:
    return _call_backend(api_url, f"api/get-file-structure/{prefix}")

def fetch_vector_data(api_url: str, s3_path: str) -> gpd.GeoDataFrame:
    """
    Fetches the presigned URL from the backend and loads it into a GeoDataFrame.
    """
    # 1. Ask the backend for the data
    response_dict = _call_backend(api_url, f"api/get-data/{s3_path}")
    
    # 2. Extract the Presigned URL
    data_url = response_dict.get("url")
    
    if not data_url:
        raise ValueError("Backend did not return a valid URL.")
        
    # 3. Let GeoPandas download and parse the file directly from S3
    # This happens on the Streamlit server, bypassing the Lambda limits
    gdf = gpd.read_file(data_url)
    
    # 4. Ensure it is ready for web mapping
    if gdf.crs != "EPSG:4326":
        gdf = gdf.to_crs(epsg=4326)
        
    return gdf

def fetch_raster_metadata(api_url: str, s3_path: str) -> list[list[float]]:
    data = _call_backend(api_url, f"api/metadata/{s3_path}")
    # Extract bounds from the unwrapped body
    bounds = data.get("bounds")
    return [[bounds[1], bounds[0]], [bounds[3], bounds[2]]]

def fetch_raster_image_b64(api_url: str, s3_path: str) -> str:
    """Fetches the PNG bytes and returns a Base64 Data URI."""
    if "localhost" in api_url:
        emulator_url = f"{api_url}/2015-03-31/functions/function/invocations"
        payload = {
            "pathParameters": {"proxy": f"api/get-data/{s3_path}"},
            "httpMethod": "GET"
        }
        
        response = requests.post(emulator_url, json=payload)
        response.raise_for_status()
        lambda_result = response.json()
        
        # The Lambda emulator returns binary data as a base64-encoded body
        b64_data = lambda_result.get("body", "")
        
        # Ensure it is formatted as a Data URI for the browser
        return f"data:image/png;base64,{b64_data}"
        
    else:
        # Live AWS Environment
        url = f"{api_url}/api/get-data/{s3_path}"
        response = requests.get(url)
        response.raise_for_status()
        
        # Encode the raw bytes from API Gateway into Base64
        b64_data = base64.b64encode(response.content).decode('utf-8')
        return f"data:image/png;base64,{b64_data}"