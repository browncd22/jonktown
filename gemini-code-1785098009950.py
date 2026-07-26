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
st.caption("Deep-parsing structured JSON & page payloads from **AllBud**, **Leafly**, **SeedFinder**, & **JointCommerce**.")

strain_input = st.text_input("Enter Strain Name:", value="Granddaddy Purple", placeholder="e.g. Gorilla Glue, Gelato, Jack Herer, Wedding Cake")

# TERPENE DICTIONARY WITH SYNONYM MAPPINGS
TERPENE_MAP = {
    "Caryophyllene": [r"caryophyllene", r"beta-caryophyllene", r"b-caryophyllene"],
    "Myrcene": [r"myrcene", r"beta-myrcene", r"b-myrcene"],
    "Limonene": [r"limonene", r"d-limonene"],
    "Linalool": [r"linalool"],
    "Pinene": [r"pinene", r"alpha-pinene", r"beta-pinene", r"a-pinene", r"b-pinene"],
    "Humulene": [r"humulene", r"alpha-humulene", r"a-humulene"],
    "Terpinolene": [r"terpinolene"],
    "Ocimene": [r"ocimene"],
    "Bisabolol": [r"bisabolol", r"alpha-bisabolol"],
    "Camphene": [r"camphene"],
    "Geraniol": [r"geraniol"],
    "Valencene": [r"valencene"],
    "Carene": [r"carene", r"delta-3-carene"],
    "Terpinene": [r"terpinene"],
    "Eucalyptol": [r"eucalyptol", r"cineole"],
    "Fenchol": [r"fenchol", r"fenchyl alcohol"],
    "Nerolidol": [r"nerolidol"]
}

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

def scan_text_and_json(text_payload):
    """Scans raw strings, script tags, and JSON payloads for terpenes and flavor notes."""
    found_terps = []
    found_flavors = []
    
    # 1. Terpene Regex Search using Synonym Patterns
    for canonical_name, patterns in TERPENE_MAP.items():
        for pattern in patterns:
            matches = len(re.findall(rf'\b{pattern}\b', text_payload, re.IGNORECASE))
            if matches > 0:
                found_terps.extend([canonical_name] * matches)
                break  # avoid double counting same terpene under multiple alias synonyms in single hit
                
    # 2. Flavor Regex Search
    for flavor in FLAVOR_DICTIONARY:
        matches = len(re.findall(rf'\b{re.escape(flavor)}\b', text_payload, re.IGNORECASE))
        if matches > 0:
            found_flavors.extend([flavor.capitalize()] * matches)
            
    return found_terps, found_flavors

def extract_json_scripts(soup):
    """Extracts text contents of embedded JSON / NEXT_DATA scripts before stripping DOM tags."""
    extracted_json_text = ""
    for script in soup.find_all("script"):
        if script.get("type") == "application/json" or script.get("id") == "__NEXT_DATA__" or "ld+json" in str(script.get("type")):
            if script.string:
                extracted_json_text += " " + script.string
    return extracted_json_text

def search_all_sources(strain_name):
    all_terp_mentions = []
    all_flavor_mentions = []
    classifications = []
    source_status = {}
    
    clean_name = strain_name.strip()
    slug_dash = clean_name.lower().replace(" ", "-").replace("'", "")
    slug_underscore = clean_name.replace(" ", "_")

    # --- 1. LEAFLY (GRAPHQL API + PAGE PAYLOAD) ---
    leafly_ok = False
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
                if data.get("category"): classifications.append(data.get("category").capitalize())
                if data.get("terpenes"):
                    for terp in data["terpenes"]:
                        if terp.get("name"):
                            # Directly weight structured GraphQL hits
                            all_terp_mentions.extend([terp["name"].capitalize()] * 5)
                leafly_ok = True
    except Exception:
        pass

    # B. Leafly Page Scrape Fallback (targeting JSON scripts)
    if not leafly_ok:
        try:
            res = requests.get(f"https://www.leafly.com/strains/{slug_dash}", headers=get_headers(), timeout=4)
            if res.status_code == 200:
                soup = BeautifulSoup(res.text, "html.parser")
                json_blob = extract_json_scripts(soup)
                full_payload = json_blob + " " + soup.get_text()
                
                t, f = scan_text_and_json(full_payload)
                all_terp_mentions.extend(t)
                all_flavor_mentions.extend(f)
                leafly_ok = True
        except Exception:
            pass

    source_status["Leafly.com"] = "Terpenes & Data Extracted" if leafly_ok else "No direct match"

    # --- 2. ALLBUD.COM ---
    allbud_ok = False
    try:
        res = requests.get(f"https://www.allbud.com/marijuana-strains/{slug_dash}", headers=get_headers(), timeout=4)
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, "html.parser")
            json_blob = extract_json_scripts(soup)
            full_payload = json_blob + " " + soup.get_text()
            
            t, f = scan_text_and_json(full_payload)
            all_terp_mentions.extend(t)
            all_flavor_mentions.extend(f)
            
            text_lower = full_payload.lower()
            if "indica dominant" in text_lower: classifications.append("Indica Dominant")
            elif "sativa dominant" in text_lower: classifications.append("Sativa Dominant")
            elif "indica" in text_lower: classifications.append("Indica")
            elif "sativa" in text_lower: classifications.append("Sativa")
            elif "hybrid" in text_lower: classifications.append("Hybrid")
            
            allbud_ok = True
    except Exception:
        pass

    source_status["AllBud.com"] = "Terpenes & Data Extracted" if allbud_ok else "No direct match"

    # --- 3. SEEDFINDER.EU ---
    sf_ok = False
    try:
        res = requests.get(f"https://en.seedfinder.eu/strain-info/{slug_underscore}/", headers=get_headers(), timeout=4)
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, "html.parser")
            json_blob = extract_json_scripts(soup)
            full_payload = json_blob + " " + soup.get_text()
            
            t, f = scan_text_and_json(full_payload)
            all_terp_mentions.extend(t)
            all_flavor_mentions.extend(f)
            
            text_lower = full_payload.lower()
            if "indica" in text_lower and "sativa" in text_lower: classifications.append("Hybrid")
            elif "indica" in text_lower: classifications.append("Indica")
            elif "sativa" in text_lower: classifications.append("Sativa")
            
            sf_ok = True
    except Exception:
        pass

    source_status["SeedFinder.eu"] = "Terpenes & Data Extracted" if sf_ok else "No direct match"

    # --- 4. JOINTCOMMERCE.COM ---
    jc_ok = False
    try:
        res = requests.get(f"https://www.jointcommerce.com/strains/{slug_dash}", headers=get_headers(), timeout=4)
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, "html.parser")
            json_blob = extract_json_scripts(soup)
            full_payload = json_blob + " " + soup.get_text()
            
            t, f = scan_text_and_json(full_payload)
            all_terp_mentions.extend(t)
            all_flavor_mentions.extend(f)
            jc_ok = True
    except Exception:
        pass

    source_status["JointCommerce.com"] = "Terpenes & Data Extracted" if jc_ok else "No direct match"

    # --- EXTRACT TOP DOMINANT RESULTS ---
    terp_counts = Counter(all_terp_mentions)
    dominant_terps = [terp for terp, count in terp_counts.most_common(4)]

    flavor_counts = Counter(all_flavor_mentions)
    dominant_flavors = [flavor for flavor, count in flavor_counts.most_common(5)]

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
        with st.spinner(f"Extracting terpenes & flavors for '{strain_input}'..."):
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
                st.info("No specific terpene profile detected in page JSON/payloads for this strain.")

        # TYPICAL FLAVORS DISPLAY
        with col2:
            st.markdown("### 👅 Signature Flavors")
            if merged["flavors"]:
                badges = "".join([f'<span class="badge-flavor">{f}</span>' for f in merged["flavors"]])
                st.markdown(f'<div class="data-box">{badges}</div>', unsafe_allow_html=True)
            else:
                st.info("No specific flavor notes detected in page JSON/payloads for this strain.")

        # SOURCE DIAGNOSTICS
        st.write("")
        with st.expander("🔍 View Source Diagnostics"):
            for site, status in merged["source_status"].items():
                st.write(f"- **{site}:** {status}")
