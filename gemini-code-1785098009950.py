import streamlit as st
import requests
from bs4 import BeautifulSoup
import json
import re

st.set_page_config(
    page_title="Consolidated Strain Aggregator",
    page_icon="🌿",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Custom Styling
st.markdown("""
    <style>
    .metric-container {
        background-color: #1e2130;
        padding: 20px;
        border-radius: 10px;
        border: 1px solid #2d3142;
        text-align: center;
        margin-bottom: 20px;
    }
    .data-box {
        background-color: #1a1c24;
        padding: 20px;
        border-radius: 10px;
        border: 1px solid #2d3142;
        min-height: 180px;
    }
    .badge-terp {
        background-color: #1e3a29;
        color: #4cd964;
        padding: 6px 14px;
        border-radius: 15px;
        display: inline-block;
        margin: 4px;
        font-weight: 600;
        border: 1px solid #2e693e;
    }
    .badge-flavor {
        background-color: #3a2b1e;
        color: #ff9500;
        padding: 6px 14px;
        border-radius: 15px;
        display: inline-block;
        margin: 4px;
        font-weight: 600;
        border: 1px solid #694e2e;
    }
    .source-tag {
        font-size: 0.8em;
        color: #8e8e93;
        background-color: #262730;
        padding: 2px 8px;
        border-radius: 4px;
        margin-right: 5px;
    }
    </style>
""", unsafe_allow_html=True)

st.title("🌿 Consolidated Strain Aggregator")
st.caption("Searching **AllBud**, **Leafly**, **SeedFinder**, & **JointCommerce** simultaneously to build a single profile.")

strain_input = st.text_input("Enter Strain Name:", value="Granddaddy Purple", placeholder="e.g. Gorilla Glue, Gelato, Jack Herer")

# Master Chemical & Aroma Dictionaries
TERPENE_DICTIONARY = [
    "Caryophyllene", "Beta-Caryophyllene", "Myrcene", "Limonene", "Linalool", 
    "Pinene", "Alpha-Pinene", "Beta-Pinene", "Humulene", "Terpinolene", 
    "Ocimene", "Bisabolol", "Camphene", "Geraniol", "Valencene", "Carene", 
    "Terpinene", "Eucalyptol", "Fenchol", "Phytol", "Nerolidol"
]

FLAVOR_DICTIONARY = [
    "Berry", "Grape", "Citrus", "Pine", "Earthy", "Sweet", "Diesel", "Skunk", 
    "Pepper", "Spicy", "Pungent", "Vanilla", "Cheese", "Nutty", "Tropical", 
    "Mango", "Lemon", "Lime", "Orange", "Blueberry", "Strawberry", "Flowery", 
    "Herbal", "Woody", "Chemical", "Mint", "Butter", "Coffee", "Fruit"
]

def get_headers():
    return {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
    }

def fetch_search_snippet(domain, strain_name, terms=""):
    """Query DuckDuckGo for targeted domain indexing to bypass Cloudflare and pull raw text."""
    try:
        query = f"site:{domain} \"{strain_name}\" {terms}"
        url = f"https://html.duckduckgo.com/html/?q={requests.utils.quote(query)}"
        res = requests.get(url, headers=get_headers(), timeout=6)
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, "html.parser")
            snippets = [a.get_text(strip=True) for a in soup.select(".result__snippet")]
            return " ".join(snippets)
    except Exception:
        pass
    return ""

def scan_text(text):
    """Scans text against chemical and flavor dictionaries."""
    terps = []
    flavors = []
    
    for t in TERPENE_DICTIONARY:
        if re.search(rf'\b{re.escape(t)}\b', text, re.I):
            # Clean up Beta-Caryophyllene naming to standard Caryophyllene
            clean_t = "Caryophyllene" if "caryophyllene" in t.lower() else t
            terps.append(clean_t.capitalize())
            
    for f in FLAVOR_DICTIONARY:
        if re.search(rf'\b{re.escape(f)}\b', text, re.I):
            flavors.append(f.capitalize())
            
    return list(set(terps)), list(set(flavors))

def search_all_sources_simultaneously(strain_name):
    """Queries all 4 platforms simultaneously and combines their payloads."""
    results = {
        "terpenes": set(),
        "flavors": set(),
        "classifications": [],
        "source_status": {}
    }
    
    clean_name = strain_name.strip()
    slug = clean_name.lower().replace(" ", "-").replace("'", "")
    
    # --- 1. ALLBUD.COM ---
    ab_text = fetch_search_snippet("allbud.com", clean_name, "flavors terpenes indica sativa")
    if ab_text:
        t, f = scan_text(ab_text)
        results["terpenes"].update(t)
        results["flavors"].update(f)
        
        if "indica dominant" in ab_text.lower(): results["classifications"].append("Indica Dominant")
        elif "sativa dominant" in ab_text.lower(): results["classifications"].append("Sativa Dominant")
        elif "indica" in ab_text.lower(): results["classifications"].append("Indica")
        elif "sativa" in ab_text.lower(): results["classifications"].append("Sativa")
        elif "hybrid" in ab_text.lower(): results["classifications"].append("Hybrid")
        
        results["source_status"]["AllBud.com"] = f"Found {len(t)} terpenes, {len(f)} flavors"
    else:
        results["source_status"]["AllBud.com"] = "No direct match found"

    # --- 2. LEAFLY.COM ---
    # Try direct GraphQL first
    leafly_found = False
    try:
        graphql_url = "https://www.leafly.com/api/graphql"
        query = """
        query StrainData($slug: String!) {
          strain(slug: $slug) {
            category
            terpenes { name }
          }
        }
        """
        res = requests.post(graphql_url, json={"query": query, "variables": {"slug": slug}}, headers=get_headers(), timeout=5)
        if res.status_code == 200:
            data = res.json().get("data", {}).get("strain")
            if data:
                if data.get("category"): results["classifications"].append(data.get("category").capitalize())
                if data.get("terpenes"):
                    for terp in data["terpenes"]:
                        if terp.get("name"): results["terpenes"].add(terp["name"].capitalize())
                leafly_found = True
    except Exception:
        pass
        
    # Snippet Fallback for Leafly Flavors & Terpenes
    lf_text = fetch_search_snippet("leafly.com", clean_name, "terpenes flavor profile category")
    if lf_text:
        t, f = scan_text(lf_text)
        results["terpenes"].update(t)
        results["flavors"].update(f)
        leafly_found = True
        
    results["source_status"]["Leafly.com"] = "Successfully extracted data" if leafly_found else "No direct match found"

    # --- 3. SEEDFINDER.EU ---
    sf_text = fetch_search_snippet("seedfinder.eu", clean_name, "genetics strain info indica sativa")
    if sf_text:
        t, f = scan_text(sf_text)
        results["terpenes"].update(t)
        results["flavors"].update(f)
        
        if "indica" in sf_text.lower() and "sativa" in sf_text.lower(): results["classifications"].append("Hybrid")
        elif "indica" in sf_text.lower(): results["classifications"].append("Indica")
        elif "sativa" in sf_text.lower(): results["classifications"].append("Sativa")
        
        results["source_status"]["SeedFinder.eu"] = f"Extracted lineage & profile text"
    else:
        results["source_status"]["SeedFinder.eu"] = "No direct match found"

    # --- 4. JOINTCOMMERCE.COM ---
    jc_text = fetch_search_snippet("jointcommerce.com", clean_name, "terpene flavor profile")
    if jc_text:
        t, f = scan_text(jc_text)
        results["terpenes"].update(t)
        results["flavors"].update(f)
        results["source_status"]["JointCommerce.com"] = f"Found {len(t)} terpenes, {len(f)} flavors"
    else:
        results["source_status"]["JointCommerce.com"] = "No direct match found"

    return results

# --- ACTION & DISPLAY ---
if st.button("Extract & Merge Strain Data", type="primary"):
    if not strain_input.strip():
        st.warning("Please enter a valid strain name.")
    else:
        with st.spinner(f"Searching and combining data from AllBud, Leafly, SeedFinder, and JointCommerce..."):
            merged_data = search_all_sources_simultaneously(strain_input)

        # Determine Consensus Classification
        class_counts = merged_data["classifications"]
        if class_counts:
            # Pick most frequent classification returned across sources
            final_classification = max(set(class_counts), key=class_counts.count)
        else:
            final_classification = "Hybrid (Standard)"

        st.markdown("---")

        # METRIC HEADER
        st.markdown(f"""
            <div class="metric-container">
                <span style="color: #8e8e93; font-size: 0.85em; text-transform: uppercase;">Consensus Classification</span>
                <h2 style="color: #4cd964; margin-top: 5px;">🌱 {final_classification}</h2>
            </div>
        """, unsafe_allow_html=True)

        col1, col2 = st.columns(2)

        # TERPENES COLUMN
        with col1:
            st.markdown("### 🧪 Terpenes Present")
            terps_list = sorted(list(merged_data["terpenes"]))
            if terps_list:
                terp_html = "".join([f'<span class="badge-terp">{t}</span>' for t in terps_list])
                st.markdown(f'<div class="data-box">{terp_html}</div>', unsafe_allow_html=True)
            else:
                st.info("No explicit terpenes identified across the 4 sources for this strain.")

        # FLAVORS COLUMN
        with col2:
            st.markdown("### 👅 Typical Flavors")
            flavors_list = sorted(list(merged_data["flavors"]))
            if flavors_list:
                flavor_html = "".join([f'<span class="badge-flavor">{f}</span>' for f in flavors_list])
                st.markdown(f'<div class="data-box">{flavor_html}</div>', unsafe_allow_html=True)
            else:
                st.info("No explicit flavor notes identified across the 4 sources for this strain.")

        # SOURCE CONTRIBUTIONS
        st.write("")
        with st.expander("🔍 View Combined Source Diagnostics"):
            for site, status in merged_data["source_status"].items():
                st.write(f"- **{site}:** {status}")
