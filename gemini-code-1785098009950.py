import streamlit as st
import requests
from bs4 import BeautifulSoup
import json
import re
from collections import Counter

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
        min-height: 140px;
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
st.caption("Aggregating dominant profile data from **AllBud**, **Leafly**, **SeedFinder**, & **JointCommerce**.")

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
    "Herbal", "Woody", "Chemical", "Mint", "Butter", "Coffee", "Fruit"
]

def get_headers():
    return {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }

def clean_strain_content(soup):
    """Removes headers, footers, sidebars, and recommendation carousels to stop cross-strain leakage."""
    for element in soup(["footer", "header", "nav", "aside", "script", "style"]):
        element.decompose()
        
    # Remove common recommendation and related-strain containers
    for extra in soup.find_all(class_=re.compile(r'(recommend|related|similar|popular|footer|sidebar)', re.I)):
        extra.decompose()
        
    return soup.get_text()

def extract_primary_terms(text):
    """Extracts terms with frequency counts."""
    terp_found = []
    flavor_found = []
    
    for t in TERPENE_DICTIONARY:
        matches = len(re.findall(rf'\b{re.escape(t)}\b', text, re.I))
        if matches > 0:
            terp_found.extend([t.capitalize()] * matches)
            
    for f in FLAVOR_DICTIONARY:
        matches = len(re.findall(rf'\b{re.escape(f)}\b', text, re.I))
        if matches > 0:
            flavor_found.extend([f.capitalize()] * matches)
            
    return terp_found, flavor_found

def search_all_sources(strain_name):
    """Directly queries endpoints and applies strict dominant frequency ranking."""
    all_terp_mentions = []
    all_flavor_mentions = []
    classifications = []
    source_status = {}
    
    clean_name = strain_name.strip()
    slug_dash = clean_name.lower().replace(" ", "-").replace("'", "")
    slug_underscore = clean_name.replace(" ", "_")

    # --- 1. LEAFLY GRAPHQL & NEXT_DATA ---
    leafly_ok = False
    try:
        # A. GraphQL exact structured payload
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
                if data.get("category"): classifications.append(data.get("category").capitalize())
                if data.get("terpenes"):
                    for terp in data["terpenes"]:
                        if terp.get("name"):
                            # Direct structured hits get weight boost
                            all_terp_mentions.extend([terp["name"].capitalize()] * 3)
                leafly_ok = True
    except Exception:
        pass

    # B. HTML Fallback
    if not leafly_ok:
        try:
            res = requests.get(f"https://www.leafly.com/strains/{slug_dash}", headers=get_headers(), timeout=4)
            if res.status_code == 200:
                soup = BeautifulSoup(res.text, "html.parser")
                text = clean_strain_content(soup)
                t, f = extract_primary_terms(text)
                all_terp_mentions.extend(t)
                all_flavor_mentions.extend(f)
                leafly_ok = True
        except Exception:
            pass

    source_status["Leafly.com"] = "Data Extracted" if leafly_ok else "No direct match"

    # --- 2. ALLBUD.COM ---
    allbud_ok = False
    try:
        res = requests.get(f"https://www.allbud.com/marijuana-strains/{slug_dash}", headers=get_headers(), timeout=4)
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, "html.parser")
            
            # Target primary strain body area
            main_content = soup.find("section", id="strain-detail") or soup.find("main") or soup
            text = clean_strain_content(main_content)
            
            t, f = extract_primary_terms(text)
            all_terp_mentions.extend(t)
            all_flavor_mentions.extend(f)
            
            if "indica dominant" in text.lower(): classifications.append("Indica Dominant")
            elif "sativa dominant" in text.lower(): classifications.append("Sativa Dominant")
            elif "indica" in text.lower(): classifications.append("Indica")
            elif "sativa" in text.lower(): classifications.append("Sativa")
            elif "hybrid" in text.lower(): classifications.append("Hybrid")
            
            allbud_ok = True
    except Exception:
        pass

    source_status["AllBud.com"] = "Data Extracted" if allbud_ok else "No direct match"

    # --- 3. SEEDFINDER.EU ---
    sf_ok = False
    try:
        res = requests.get(f"https://en.seedfinder.eu/strain-info/{slug_underscore}/", headers=get_headers(), timeout=4)
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, "html.parser")
            text = clean_strain_content(soup)
            t, f = extract_primary_terms(text)
            all_terp_mentions.extend(t)
            all_flavor_mentions.extend(f)
            
            if "indica" in text.lower() and "sativa" in text.lower(): classifications.append("Hybrid")
            elif "indica" in text.lower(): classifications.append("Indica")
            elif "sativa" in text.lower(): classifications.append("Sativa")
            
            sf_ok = True
    except Exception:
        pass

    source_status["SeedFinder.eu"] = "Data Extracted" if sf_ok else "No direct match"

    # --- 4. JOINTCOMMERCE.COM ---
    jc_ok = False
    try:
        res = requests.get(f"https://www.jointcommerce.com/strains/{slug_dash}", headers=get_headers(), timeout=4)
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, "html.parser")
            text = clean_strain_content(soup)
            t, f = extract_primary_terms(text)
            all_terp_mentions.extend(t)
            all_flavor_mentions.extend(f)
            jc_ok = True
    except Exception:
        pass

    source_status["JointCommerce.com"] = "Data Extracted" if jc_ok else "No direct match"

    # --- FILTER TO DOMINANT TOP RESULTS ---
    # Pick Top 4 Dominant Terpenes
    terp_counts = Counter(all_terp_mentions)
    dominant_terps = [terp for terp, count in terp_counts.most_common(4)]

    # Pick Top 5 Typical Flavors
    flavor_counts = Counter(all_flavor_mentions)
    dominant_flavors = [flavor for flavor, count in flavor_counts.most_common(5)]

    # Calculate Consensus Genetic Profile
    final_class = Counter(classifications).most_common(1)[0][0] if classifications else "Hybrid"

    return {
        "terpenes": dominant_terps,
        "flavors": dominant_flavors,
        "classification": final_class,
        "source_status": source_status
    }

# --- EXECUTION & DISPLAY ---
if st.button("Extract & Merge Strain Data", type="primary"):
    if not strain_input.strip():
        st.warning("Please enter a valid strain name.")
    else:
        with st.spinner(f"Filtering dominant profiles for '{strain_input}'..."):
            merged = search_all_sources(strain_input)

        st.markdown("---")

        # CONSENSUS CLASSIFICATION METRIC
        st.markdown(f"""
            <div class="metric-container">
                <span style="color: #8e8e93; font-size: 0.85em; text-transform: uppercase;">Consensus Genetic Profile</span>
                <h2 style="color: #4cd964; margin-top: 5px;">🌱 {merged['classification']}</h2>
            </div>
        """, unsafe_allow_html=True)

        col1, col2 = st.columns(2)

        # DOMINANT TERPENES DISPLAY
        with col1:
            st.markdown("### 🧪 Dominant Terpenes")
            if merged["terpenes"]:
                badges = "".join([f'<span class="badge-terp">{t}</span>' for t in merged["terpenes"]])
                st.markdown(f'<div class="data-box">{badges}</div>', unsafe_allow_html=True)
            else:
                st.info("No specific dominant terpenes identified.")

        # TYPICAL FLAVORS DISPLAY
        with col2:
            st.markdown("### 👅 Signature Flavors")
            if merged["flavors"]:
                badges = "".join([f'<span class="badge-flavor">{f}</span>' for f in merged["flavors"]])
                st.markdown(f'<div class="data-box">{badges}</div>', unsafe_allow_html=True)
            else:
                st.info("No specific signature flavors identified.")

        # SOURCE DIAGNOSTICS
        st.write("")
        with st.expander("🔍 View Source Diagnostics"):
            for site, status in merged["source_status"].items():
                st.write(f"- **{site}:** {status}")
