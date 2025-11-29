"""
Pydantic Datenmodelle für DDR5 RAM Anzeigen.
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class RAMSpecifications(BaseModel):
    """RAM-Spezifikationen."""

    model_number: Optional[str] = Field(None, description="Modellnummer z.B. CMK32GX5M2B5200C40")
    manufacturer: Optional[str] = Field(None, description="Hersteller: Corsair, G.Skill, Kingston, etc.")
    capacity: Optional[str] = Field(None, description="Kapazität z.B. 32GB, 2x16GB")
    speed: Optional[str] = Field(None, description="Taktfrequenz z.B. 5200 MHz, 6000MT/s")
    latency: Optional[str] = Field(None, description="Latenz z.B. CL40, CL36")
    color: Optional[str] = Field(None, description="Farbe: Schwarz, Weiß, RGB, etc.")

    class Config:
        """Pydantic Config."""

        frozen = False


class Listing(BaseModel):
    """Anzeigen-Listing mit RAM-Spezifikationen."""

    ad_id: str = Field(..., description="Eindeutige ID von URL")
    title: str = Field(..., description="Titel der Anzeige")
    price: float = Field(..., description="Preis in Euro")
    location: str = Field("", description="Standort")
    url: str = Field(..., description="URL zur Anzeige")
    posted_date: str = Field("", description="Relativer String: vor 2 Stunden")
    posted_timestamp: datetime = Field(..., description="Berechneter absoluter Zeitpunkt")
    has_ovp: bool = Field(False, description="Originalverpackung vorhanden")
    has_invoice: bool = Field(False, description="Rechnung vorhanden")
    shipping_available: bool = Field(False, description="Versand möglich")
    specs: RAMSpecifications = Field(default_factory=RAMSpecifications, description="RAM-Spezifikationen")
    raw_description: str = Field("", description="Voller Text für Fallback")
    priority_score: int = Field(0, description="Priority Score für Ausgabe-Priorisierung")

    class Config:
        """Pydantic Config."""

        frozen = False

