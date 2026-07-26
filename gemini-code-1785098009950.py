import streamlit as st
import requests
from bs4 import BeautifulSoup
import re
from duckduckgo_search import DDGS

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
st.caption("Aggregating live data from **AllBud**, **Leafly**, **SeedFinder**, & **JointCommerce**.")

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

def search_ddg_native(query):
    """Uses official duckduckgo_search library to bypass html endpoint block."""
    combined_text = ""
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=5))
            for r in results:
                combined_text += f" {r.get('title', '')} {r.get('body', '')}"
    except Exception:
        # Fallback to lite ddg API if library throttles
        try:
            url = f"https://lite.duckduckgo.com/lite/"
            res = requests.post(
                url, 
                data={"q": query}, 
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}, 
                timeout=5
            )
            if res.status_code == 200:
                soup = BeautifulSoup(res.text, "html.parser")
                snippets = [td.get_text(strip=True) for td in soup.select(".result-snippet")]
                combined_text += " ".join(snippets)
        except Exception:
            pass
    return combined_text

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
    """Queries all 4 platforms and combines their payloads."""
    results = {
        "terpenes": set(),
        "flavors": set(),
        "classifications": [],
        "source_status": {}
    }
    
    clean_name = strain_name.strip()
    slug = clean_name.lower().replace(" ", "-").replace("'", "")
    
    # --- 1. ALLBUD.COM ---
    ab_text = search_ddg_native(f"site:allbud.com {clean_name} strain")
    if ab_text:
        t, f = scan_text(ab_text)
        results["terpenes"].update(t)
        results["flavors"].update(f)
        
        if "indica dominant" in ab_text.lower(): results["classifications"].append("Indica Dominant")
        elif "sativa dominant" in ab_text.lower(): results["classifications"].append("Sativa Dominant")
        elif "indica" in ab_text.lower(): results["classifications"].append("Indica")
        elif "sativa" in ab_text.lower(): results["classifications"].append("Sativa")
        elif "hybrid" in ab_text.lower(): results["classifications"].append("Hybrid")
        
        results["source_status"]["AllBud.com"] = f"Extracted data ({len(t)} terps, {len(f)} flavors)"
    else:
        results["source_status"]["AllBud.com"] = "No indexed text returned"

    # --- 2. LEAFLY.COM ---
    lf_text = search_ddg_native(f"site:leafly.com {clean_name} strain terpenes flavors")
    if lf_text:
        t, f = scan_text(lf_text)
        results["terpenes"].update(t)
        results["flavors"].update(f)
        
        if "indica" in lf_text.lower() and "sativa" in lf_text.lower(): results["classifications"].append("Hybrid")
        elif "indica" in lf_text.lower(): results["classifications"].append("Indica")
        elif "sativa" in lf_text.lower(): results["classifications"].append("Sativa")
        
        results["source_status"]["Leafly.com"] = f"Extracted data ({len(t)} terps, {len(f)} flavors)"
    else:
        results["source_status"]["Leafly.com"] = "No indexed text returned"

    # --- 3. SEEDFINDER.EU ---
    sf_text = search_ddg_native(f"site:seedfinder.eu {clean_name} strain info")
    if sf_text:
        t, f = scan_text(sf_text)
        results["terpenes"].update(t)
        results["flavors"].update(f)
        
        if "indica" in sf_text.lower() and "sativa" in sf_text.lower(): results["classifications"].append("Hybrid")
        elif "indica" in sf_text.lower(): results["classifications"].append("Indica")
        elif "sativa" in sf_text.lower(): results["classifications"].append("Sativa")
        
        results["source_status"]["SeedFinder.eu"] = f"Extracted data ({len(t)} terps, {len(f)} flavors)"
    else:
        results["source_status"]["SeedFinder.eu"] = "No indexed text returned"

    # --- 4. JOINTCOMMERCE.COM ---
    jc_text = search_ddg_native(f"site:jointcommerce.com {clean_name} strain profile")
    if jc_text:
        t, f = scan_text(jc_text)
        results["terpenes"].update(t)
        results["flavors"].update(f)
        results["source_status"]["JointCommerce.com"] = f"Extracted data ({len(t)} terps, {len(f)} flavors)"
    else:
        results["source_status"]["JointCommerce.com"] = "No indexed text returned"

    return results

# --- EXECUTION & DISPLAY ---
if st.button("Extract & Merge Strain Data", type="primary"):
    if not strain_input.strip():
        st.warning("Please enter a valid strain name.")
    else:
        with st.spinner(f"Aggregating profiles for '{strain_input}' across all 4 sources..."):
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
                st.info("No specific terpene names detected in the indexed results.")

        # FLAVORS DISPLAY
        with col2:
            st.markdown("### 👅 Typical Flavors")
            flavor_list = sorted(list(merged["flavors"]))
            if flavor_list:
                badges = "".join([f'<span class="badge-flavor">{f}</span>' for f in flavor_list])
                st.markdown(f'<div class="data-box">{badges}</div>', unsafe_allow_html=True)
            else:
                st.info("No specific flavor keywords detected in the indexed results.")

        # SOURCE DIAGNOSTICS
        st.write("")
        with st.expander("🔍 View Source Breakdown"):
            for site, status in merged["source_status"].items():
                st.write(f"- **{site}:** {status}")
