"""
Data models and type definitions for the Geospatial Portfolio UI.
"""
from typing import Any, Optional
from pydantic import BaseModel, Field

class RasterBounds(BaseModel):
    """Expected response from the backend metadata endpoint."""
    bounds: list[float] = Field(..., description="[min_lon, min_lat, max_lon, max_lat]")

    def to_leaflet_bounds(self) -> list[list[float]]:
        """Converts [min_lon, min_lat, max_lon, max_lat] to [[min_lat, min_lon], [max_lat, max_lon]]"""
        return [[self.bounds[1], self.bounds[0]], [self.bounds[3], self.bounds[2]]]

class MapLayer(BaseModel):
    """Represents a standardized layer loaded into the Streamlit session state."""
    type: str = Field(..., description="'vector' or 'raster'")
    name: str = Field(..., description="The display name of the layer")
    s3_path: str = Field(..., description="The full S3 path used as a unique identifier")
    
    # Using Any here because Pydantic doesn't natively validate GeoDataFrames easily without custom validators
    vector_data: Optional[Any] = None 
    raster_url: Optional[str] = None
    raster_bounds: Optional[list[list[float]]] = None

    class Config:
        arbitrary_types_allowed = True