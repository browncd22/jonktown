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

# Custom Dark Modern Styling
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
        min-height: 160px;
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
    </style>
""", unsafe_allow_html=True)

st.title("🌿 Consolidated Strain Aggregator")
st.caption("Directly querying **AllBud**, **Leafly**, **SeedFinder**, & **JointCommerce** endpoints.")

strain_input = st.text_input("Enter Strain Name:", value="Granddaddy Purple", placeholder="e.g. Gorilla Glue, Gelato, Jack Herer")

# Master Chemical & Aroma Dictionaries
TERPENE_DICTIONARY = [
    "Caryophyllene", "Myrcene", "Limonene", "Linalool", "Pinene", "Humulene", 
    "Terpinolene", "Ocimene", "Bisabolol", "Camphene", "Geraniol", "Valencene", 
    "Carene", "Terpinene", "Eucalyptol", "Fenchol", "Phytol", "Nerolidol"
]

FLAVOR_DICTIONARY = [
    "Berry", "Grape", "Citrus", "Pine", "Earthy", "Sweet", "Diesel", "Skunk", 
    "Pepper", "Spicy", "Pungent", "Vanilla", "Cheese", "Nutty", "Tropical", 
    "Mango", "Lemon", "Lime", "Orange", "Blueberry", "Strawberry", "Flowery", 
    "Herbal", "Woody", "Chemical", "Mint", "Butter", "Coffee", "Fruit", "Kush"
]

def get_headers():
    return {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }

def scan_text(text):
    """Scans raw text against chemical and flavor dictionaries."""
    found_terps = set()
    found_flavors = set()
    
    for t in TERPENE_DICTIONARY:
        if re.search(rf'\b{re.escape(t)}\b', text, re.I):
            found_terps.add(t.capitalize())
            
    for f in FLAVOR_DICTIONARY:
        if re.search(rf'\b{re.escape(f)}\b', text, re.I):
            found_flavors.add(f.capitalize())
            
    return found_terps, found_flavors

def search_all_sources(strain_name):
    """Directly queries all 4 platforms via direct site endpoints."""
    results = {
        "terpenes": set(),
        "flavors": set(),
        "classifications": [],
        "source_status": {}
    }
    
    clean_name = strain_name.strip()
    slug_dash = clean_name.lower().replace(" ", "-").replace("'", "")
    slug_underscore = clean_name.replace(" ", "_")

    # --- 1. LEAFLY (DIRECT API & HTML NEXT_DATA) ---
    leafly_success = False
    try:
        # A. Try GraphQL API
        graphql_url = "https://www.leafly.com/api/graphql"
        query = """
        query StrainData($slug: String!) {
          strain(slug: $slug) {
            category
            terpenes { name }
          }
        }
        """
        res = requests.post(graphql_url, json={"query": query, "variables": {"slug": slug_dash}}, headers=get_headers(), timeout=4)
        if res.status_code == 200:
            data = res.json().get("data", {}).get("strain")
            if data:
                if data.get("category"): results["classifications"].append(data.get("category").capitalize())
                if data.get("terpenes"):
                    for terp in data["terpenes"]:
                        if terp.get("name"): results["terpenes"].add(terp["name"].capitalize())
                leafly_success = True
    except Exception:
        pass

    # B. Try Direct Web Scrape fallback for Leafly
    if not leafly_success:
        try:
            lf_url = f"https://www.leafly.com/strains/{slug_dash}"
            res = requests.get(lf_url, headers=get_headers(), timeout=4)
            if res.status_code == 200:
                soup = BeautifulSoup(res.text, "html.parser")
                # Look for __NEXT_DATA__ json payload
                next_data = soup.find("script", id="__NEXT_DATA__")
                if next_data:
                    payload = next_data.string
                    t, f = scan_text(payload)
                    results["terpenes"].update(t)
                    results["flavors"].update(f)
                    leafly_success = True
                else:
                    t, f = scan_text(res.text)
                    results["terpenes"].update(t)
                    results["flavors"].update(f)
                    leafly_success = True
        except Exception:
            pass

    results["source_status"]["Leafly.com"] = "Direct data extracted" if leafly_success else "Endpoint unindexed for slug"

    # --- 2. ALLBUD.COM (DIRECT SCRAPE) ---
    allbud_success = False
    try:
        ab_url = f"https://www.allbud.com/marijuana-strains/{slug_dash}"
        res = requests.get(ab_url, headers=get_headers(), timeout=4)
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, "html.parser")
            text = soup.get_text()
            t, f = scan_text(text)
            results["terpenes"].update(t)
            results["flavors"].update(f)
            
            if "indica dominant" in text.lower(): results["classifications"].append("Indica Dominant")
            elif "sativa dominant" in text.lower(): results["classifications"].append("Sativa Dominant")
            elif "indica" in text.lower(): results["classifications"].append("Indica")
            elif "sativa" in text.lower(): results["classifications"].append("Sativa")
            elif "hybrid" in text.lower(): results["classifications"].append("Hybrid")
            
            allbud_success = True
    except Exception:
        pass

    results["source_status"]["AllBud.com"] = "Direct data extracted" if allbud_success else "Endpoint unindexed for slug"

    # --- 3. SEEDFINDER.EU (DIRECT SCRAPE) ---
    seedfinder_success = False
    try:
        sf_url = f"https://en.seedfinder.eu/strain-info/{slug_underscore}/"
        res = requests.get(sf_url, headers=get_headers(), timeout=4)
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, "html.parser")
            text = soup.get_text()
            t, f = scan_text(text)
            results["terpenes"].update(t)
            results["flavors"].update(f)
            
            if "indica" in text.lower() and "sativa" in text.lower(): results["classifications"].append("Hybrid")
            elif "indica" in text.lower(): results["classifications"].append("Indica")
            elif "sativa" in text.lower(): results["classifications"].append("Sativa")
            
            seedfinder_success = True
    except Exception:
        pass

    results["source_status"]["SeedFinder.eu"] = "Direct data extracted" if seedfinder_success else "Endpoint unindexed for slug"

    # --- 4. JOINTCOMMERCE.COM (DIRECT SEARCH / API FALLBACK) ---
    jc_success = False
    try:
        jc_url = f"https://www.jointcommerce.com/strains/{slug_dash}"
        res = requests.get(jc_url, headers=get_headers(), timeout=4)
        if res.status_code == 200:
            t, f = scan_text(res.text)
            results["terpenes"].update(t)
            results["flavors"].update(f)
            jc_success = True
    except Exception:
        pass

    results["source_status"]["JointCommerce.com"] = "Direct data extracted" if jc_success else "Endpoint unindexed for slug"

    return results

# --- EXECUTION & DISPLAY ---
if st.button("Extract & Merge Strain Data", type="primary"):
    if not strain_input.strip():
        st.warning("Please enter a valid strain name.")
    else:
        with st.spinner(f"Querying direct site APIs & endpoints for '{strain_input}'..."):
            merged = search_all_sources(strain_input)

        # Classification Calculation
        classes = merged["classifications"]
        final_class = max(set(classes), key=classes.count) if classes else "Hybrid"

        st.markdown("---")

        # CONSENSUS CLASSIFICATION METRIC
        st.markdown(f"""
            <div class="metric-container">
                <span style="color: #8e8e93; font-size: 0.85em; text-transform: uppercase;">Consensus Genetic Profile</span>
                <h2 style="color: #4cd964; margin-top: 5px;">🌱 {final_class}</h2>
            </div>
        """, unsafe_allow_html=True)

        col1, col2 = st.columns(2)

        # TERPENES DISPLAY
        with col1:
            st.markdown("### 🧪 Terpenes Present")
            terp_list = sorted(list(merged["terpenes"]))
            if terp_list:
                badges = "".join([f'<span class="badge-terp">{t}</span>' for t in terp_list])
                st.markdown(f'<div class="data-box">{badges}</div>', unsafe_allow_html=True)
            else:
                st.info("No specific terpene names detected across direct endpoints.")

        # FLAVORS DISPLAY
        with col2:
            st.markdown("### 👅 Typical Flavors")
            flavor_list = sorted(list(merged["flavors"]))
            if flavor_list:
                badges = "".join([f'<span class="badge-flavor">{f}</span>' for f in flavor_list])
                st.markdown(f'<div class="data-box">{badges}</div>', unsafe_allow_html=True)
            else:
                st.info("No specific flavor keywords detected across direct endpoints.")

        # SOURCE DIAGNOSTICS
        st.write("")
        with st.expander("🔍 View Direct Source Diagnostics"):
            for site, status in merged["source_status"].items():
                st.write(f"- **{site}:** {status}")
