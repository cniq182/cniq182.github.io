#!/usr/bin/env python3
"""
SF Crime Data Story - Visualization Generator
Generates all static and interactive charts for the website,
including a Folium heatmap for geographic crime distribution.

Requirements:
    pip install pandas plotly matplotlib seaborn folium
"""

import os
import pandas as pd
import plotly.express as px
import matplotlib.pyplot as plt
import seaborn as sns
import folium
from folium.plugins import HeatMap

# ─── Setup ────────────────────────────────────────────────────────────────────

os.makedirs("paginas", exist_ok=True)

# ─── Load & Clean Data ────────────────────────────────────────────────────────

print("Loading dataset...")
df = pd.read_csv(
    "Police_Department.csv",
    engine="python",
    on_bad_lines="skip",
)

# Rename columns for easier access
df = df.rename(columns={
    "Incident Category": "category",
    "Police District":   "police_district",
    "Incident Date":     "incident_date",
    "Incident Time":     "incident_time",
    "Incident Year":     "year",
    "Latitude":          "latitude",
    "Longitude":         "longitude",
})

# Date + year
df["incident_date"] = pd.to_datetime(df["incident_date"], errors="coerce")
df["year"] = df["incident_date"].dt.year

# Normalise Vandalism label
df["category"] = df["category"].replace({
    "Malicious Mischief":              "Vandalism and Malicious Mischief",
    "VANDALISM AND MALICIOUS MISCHIEF": "Vandalism and Malicious Mischief",
})

# Focus crimes (2018-2025)
FOCUS_CRIMES = [
    "Assault", "Robbery", "Motor Vehicle Theft",
    "Vandalism and Malicious Mischief", "Fraud",
    "Drug Offense", "Weapons Offense",
]

df_modern = df[(df["year"] >= 2018) & (df["year"] <= 2025)].copy()
df_focus  = df_modern[df_modern["category"].isin(FOCUS_CRIMES)].copy()

print(f"Loaded {len(df_focus):,} focus-crime rows (2018-2025).")

# ─── Figure 1: Crime Trends Line Chart (PNG) ──────────────────────────────────

print("Generating crime_trends.png …")

LINE_SUBSET = ["Robbery", "Drug Offense", "Vandalism and Malicious Mischief", "Motor Vehicle Theft"]
df_trend = (
    df_focus[df_focus["category"].isin(LINE_SUBSET)]
    .groupby(["year", "category"])
    .size()
    .reset_index(name="count")
)

plt.figure(figsize=(10, 6))
sns.lineplot(
    data=df_trend, x="year", y="count",
    hue="category", marker="o",
    palette="viridis", linewidth=2.5,
)
plt.title("Evolution of Key Crimes in SF (2018-2025)", fontsize=14)
plt.ylabel("Number of Incidents")
plt.xlabel("year")
plt.grid(True, alpha=0.3)
plt.legend(bbox_to_anchor=(1.05, 1), loc="upper left")
plt.tight_layout()
plt.savefig("paginas/crime_trends.png", dpi=300, bbox_inches="tight")
plt.close()
print("  ✓ paginas/crime_trends.png")

# ─── Figure 2: Crime Map – Bar Chart by District (HTML) ───────────────────────

print("Generating crime_map.html …")

VALID_DISTRICTS = [
    "Mission", "Northern", "Tenderloin", "Bayview", "Central",
    "Ingleside", "Taraval", "Richmond", "Southern", "Park",
]

df_map = (
    df_focus[df_focus["year"] == 2020]
    .groupby("police_district")
    .size()
    .reset_index(name="total_crimes")
)
df_map_clean = df_map[df_map["police_district"].isin(VALID_DISTRICTS)]

fig_map = px.bar(
    df_map_clean, x="police_district", y="total_crimes", color="total_crimes",
    title="Crime Distribution by District (Pandemic Year 2020)",
    color_continuous_scale="Viridis",
    labels={"police_district": "Police District", "total_crimes": "Total Incidents"},
    template="plotly_white",
)
fig_map.update_layout(xaxis={"categoryorder": "total descending"})
fig_map.write_html("paginas/crime_map.html")
print("  ✓ paginas/crime_map.html")

# ─── Figure 3: Hourly Crime Rhythm – Animated Scatter (HTML) ──────────────────

print("Generating interactive_plot.html …")

df_focus["hour"] = (
    pd.to_datetime(df_focus["incident_time"], format="%H:%M", errors="coerce")
    .dt.hour
)
df_inter = (
    df_focus.groupby(["hour", "category", "year"])
    .size()
    .reset_index(name="count")
)

fig_inter = px.scatter(
    df_inter, x="hour", y="count", color="category",
    animation_frame="year", size="count",
    hover_name="category",
    title="Hourly Crime Rhythm (2018-2025)",
    labels={"hour": "Hour of Day", "count": "Incidents"},
    template="plotly_white",
)
fig_inter.update_yaxes(range=[0, df_inter["count"].max() + 100])
fig_inter.write_html("paginas/interactive_plot.html")
print("  ✓ paginas/interactive_plot.html")

# ─── Figure 4: Folium Heatmap – Geographic Crime Density (HTML) ───────────────

print("Generating crime_heatmap.html …")

# Keep rows with valid coordinates
df_heat = df_focus.dropna(subset=["latitude", "longitude"]).copy()
df_heat["latitude"]  = pd.to_numeric(df_heat["latitude"],  errors="coerce")
df_heat["longitude"] = pd.to_numeric(df_heat["longitude"], errors="coerce")
df_heat = df_heat.dropna(subset=["latitude", "longitude"])

# Remove obviously bad coordinates (SF bounding box)
df_heat = df_heat[
    (df_heat["latitude"]  >= 37.6)  & (df_heat["latitude"]  <= 37.85) &
    (df_heat["longitude"] >= -122.55) & (df_heat["longitude"] <= -122.3)
]

# ---- Overall heatmap (all years combined) ----
m = folium.Map(
    location=[37.7749, -122.4194],   # SF city centre
    zoom_start=13,
    tiles="CartoDB dark_matter",     # dark tile for dramatic contrast
)

# Prepare [lat, lon, weight] list – weight by 1 (equal) or use count
heat_data = df_heat[["latitude", "longitude"]].values.tolist()

HeatMap(
    heat_data,
    radius=10,
    blur=15,
    max_zoom=16,
    gradient={0.2: "blue", 0.5: "lime", 0.8: "yellow", 1.0: "red"},
).add_to(m)

# ---- Year-layer heatmap (one layer per year, toggle in legend) ----
years = sorted(df_heat["year"].dropna().unique().astype(int))

m_years = folium.Map(
    location=[37.7749, -122.4194],
    zoom_start=13,
    tiles="CartoDB dark_matter",
)

for year in years:
    df_yr = df_heat[df_heat["year"] == year]
    pts   = df_yr[["latitude", "longitude"]].values.tolist()
    layer = folium.FeatureGroup(name=str(year), show=(year == 2020))
    HeatMap(
        pts,
        radius=10,
        blur=15,
        max_zoom=16,
        gradient={0.2: "blue", 0.5: "lime", 0.8: "yellow", 1.0: "red"},
    ).add_to(layer)
    layer.add_to(m_years)

folium.LayerControl(collapsed=False).add_to(m_years)

# We save the multi-year version as the main heatmap
m_years.save("paginas/crime_heatmap.html")
print("  ✓ paginas/crime_heatmap.html")

print("\nAll visualizations generated successfully!")
print("Run `open index.html` or serve the folder with a local HTTP server.")