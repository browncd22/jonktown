import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import json
import re

st.set_page_config(page_title="Cannabis Lineage & Terpene Explorer", page_icon="🌿", layout="wide")

st.title("🌿 Strain Intelligence: Lineage & Terpene Aggregator")
st.write("Extracting and combining lineage data from **SeedFinder.eu** with terpene profiles from **Leafly**.")

# User Input
strain_input = st.text_input("Enter Strain Name:", value="Gorilla Glue")

def get_headers():
    return {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

def fetch_seedfinder_lineage(strain_name):
    """Scrapes strain search results and extracts lineage table/tree from SeedFinder.eu."""
    clean_name = strain_name.strip().replace(" ", "_")
    search_url = f"https://en.seedfinder.eu/search/extended/"
    
    # Direct guess URL pattern for Seedfinder
    target_url = f"https://en.seedfinder.eu/strain-info/{clean_name}/"
    
    res = requests.get(target_url, headers=get_headers(), timeout=10)
    
    # Fallback to search if direct URL fails
    if res.status_code != 200:
        search_res = requests.get(f"https://en.seedfinder.eu/search/extended/?q={strain_name}", headers=get_headers())
        soup_search = BeautifulSoup(search_res.text, "html.parser")
        first_link = soup_search.select_one("table.strainlist a")
        if first_link:
            target_url = "https://en.seedfinder.eu" + first_link["href"]
            res = requests.get(target_url, headers=get_headers())
        else:
            return None, "Strain not found on SeedFinder."

    soup = BeautifulSoup(res.text, "html.parser")
    
    # Extract Lineage Section
    lineage_div = soup.find("div", id="lineage") or soup.find("div", class_="stree")
    
    lineage_items = []
    if lineage_div:
        # Extract text elements representing parents/crosses
        for li in lineage_div.find_all(["li", "p", "a"]):
            text = li.get_text(strip=True)
            if text and text not in lineage_items:
                lineage_items.append(text)
                
    return {
        "url": target_url,
        "lineage_raw": lineage_items if lineage_items else ["Lineage table structure detected; see direct page for full graphic tree."]
    }, None

def fetch_leafly_terpenes(strain_name):
    """Fetches terpene profile embedded in Leafly's page data JSON."""
    slug = strain_name.strip().lower().replace(" ", "-")
    url = f"https://www.leafly.com/strains/{slug}"
    
    res = requests.get(url, headers=get_headers(), timeout=10)
    if res.status_code != 200:
        return None, f"Strain '{strain_name}' not found on Leafly."
        
    soup = BeautifulSoup(res.text, "html.parser")
    
    # Leafly stores page data inside a NEXT_DATA JSON script block
    script_tag = soup.find("script", id="__NEXT_DATA__")
    
    terpenes = []
    top_terpene = "Unknown"
    strain_type = "Unknown"
    
    if script_tag:
        try:
            data = json.loads(script_tag.string)
            strain_data = data['props']['pageProps']['strain']
            
            strain_type = strain_data.get('category', 'N/A')
            
            # Extract terpene profile list
            terp_data = strain_data.get('terpenes', {})
            if terp_data:
                top_terpene = terp_data.get('dominant', 'N/A')
                terpenes = terp_data.get('array', [])
        except Exception:
            pass

    # HTML Fallback if JSON parsing yields no results
    if not terpenes:
        terp_elements = soup.select("[data-testid='terpene-name']")
        terpenes = [t.get_text(strip=True) for t in terp_elements]

    return {
        "url": url,
        "type": strain_type,
        "top_terpene": top_terpene,
        "terpenes": terpenes
    }, None

# Submit Action
if st.button("Search & Combine Data", type="primary"):
    if not strain_input:
        st.warning("Please enter a strain name.")
    else:
        with st.spinner(f"Scraping SeedFinder and Leafly for '{strain_input}'..."):
            sf_data, sf_err = fetch_seedfinder_lineage(strain_input)
            leafly_data, leafly_err = fetch_leafly_terpenes(strain_input)
            
        st.markdown("---")
        
        # Display Combined Dashboard
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("🌲 Lineage & Genealogy (SeedFinder.eu)")
            if sf_err:
                st.error(sf_err)
            else:
                st.markdown(f"**Source Page:** [SeedFinder Profile]({sf_data['url']})")
                st.write("**Extracted Parent Strains & Ancestry:**")
                for item in sf_data["lineage_raw"]:
                    st.markdown(f"- {item}")

        with col2:
            st.subheader("🧪 Terpene & Chemotype Profile (Leafly.com)")
            if leafly_err:
                st.error(leafly_err)
            else:
                st.markdown(f"**Source Page:** [Leafly Profile]({leafly_data['url']})")
                st.write(f"**Category / Type:** {leafly_data['type'].capitalize()}")
                st.write(f"**Primary Dominant Terpene:** {leafly_data['top_terpene']}")
                
                st.write("**Terpene Breakdown:**")
                if leafly_data["terpenes"]:
                    for terp in leafly_data["terpenes"]:
                        st.markdown(f"- {terp}")
                else:
                    st.info("No detailed terpene percentage breakdown available for this strain.")