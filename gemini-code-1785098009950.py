import streamlit as st
import requests
from bs4 import BeautifulSoup
import json
import re

st.set_page_config(page_title="Multi-Source Strain Explorer", page_icon="🌿", layout="wide")

st.markdown("""
    <style>
    .metric-card {
        background-color: #1e2130;
        padding: 15px;
        border-radius: 10px;
        text-align: center;
        border: 1px solid #333646;
    }
    .source-badge {
        background-color: #262730;
        border-left: 4px solid #4CAF50;
        padding: 8px 12px;
        margin-bottom: 6px;
        font-size: 0.9em;
    }
    </style>
""", unsafe_allow_html=True)

st.title("🌿 Multi-Source Cannabis Intelligence Aggregator")
st.caption("Cross-referencing live data from **Leafly**, **SeedFinder**, **AllBud**, and **JointCommerce**.")

strain_input = st.text_input("Enter Strain Name:", value="Gorilla Glue", placeholder="e.g., Gelato, OG Kush, Jack Herer")

def get_headers():
    return {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
    }

# --- SEARCH ENGINE FALLBACK HELPER ---
def search_ddg_snippets(query):
    """Executes a lightweight web search if direct site scraping gets blocked by anti-bot measures."""
    try:
        url = f"https://html.duckduckgo.com/html/?q={requests.utils.quote(query)}"
        res = requests.get(url, headers=get_headers(), timeout=6)
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, "html.parser")
            snippets = [a.get_text(strip=True) for a in soup.select(".result__snippet")]
            return " ".join(snippets)
    except Exception:
        pass
    return ""

# --- 1. SEEDFINDER EXTRACTION ---
def fetch_seedfinder(strain_name):
    clean_name = strain_name.strip().replace(" ", "_")
    target_url = f"https://en.seedfinder.eu/strain-info/{clean_name}/"
    result = {"classification": "Unknown", "thc": "N/A", "source": "SeedFinder.eu"}
    
    try:
        res = requests.get(target_url, headers=get_headers(), timeout=8)
        text = res.text if res.status_code == 200 else search_ddg_snippets(f"site:seedfinder.eu {strain_name}")
        
        # Classification match
        if re.search(r'indica', text, re.I) and re.search(r'sativa', text, re.I):
            result["classification"] = "Hybrid"
        elif re.search(r'indica', text, re.I):
            result["classification"] = "Indica"
        elif re.search(r'sativa', text, re.I):
            result["classification"] = "Sativa"
            
    except Exception:
        pass
    return result

# --- 2. LEAFLY EXTRACTION ---
def fetch_leafly(strain_name):
    slug = strain_name.strip().lower().replace(" ", "-").replace("'", "")
    graphql_url = "https://www.leafly.com/api/graphql"
    query = """
    query StrainData($slug: String!) {
      strain(slug: $slug) {
        category
        thc
        terpenes { name }
      }
    }
    """
    result = {"thc": "N/A", "terpenes": [], "classification": "Unknown", "source": "Leafly.com"}
    
    try:
        res = requests.post(graphql_url, json={"query": query, "variables": {"slug": slug}}, headers=get_headers(), timeout=8)
        if res.status_code == 200:
            data = res.json().get("data", {}).get("strain")
            if data:
                result["classification"] = str(data.get("category", "Unknown")).capitalize()
                result["thc"] = f"{data.get('thc')}%" if data.get("thc") else "N/A"
                result["terpenes"] = [t["name"].capitalize() for t in data.get("terpenes", []) if t.get("name")]
                return result
                
        # Search Snippet Fallback if API blocked
        text = search_ddg_snippets(f"site:leafly.com/strains/{slug} terpenes THC")
        thc_match = re.search(r'(\d{2}%?\s*-\s*\d{2}%|\d{2}%\s*THC)', text, re.I)
        if thc_match:
            result["thc"] = thc_match.group(1)
            
    except Exception:
        pass
    return result

# --- 3. ALLBUD EXTRACTION ---
def fetch_allbud(strain_name):
    slug = strain_name.strip().lower().replace(" ", "-")
    url = f"https://www.allbud.com/marijuana-strains/{slug}"
    result = {"classification": "Unknown", "thc": "N/A", "flavors": [], "source": "AllBud.com"}
    
    try:
        res = requests.get(url, headers=get_headers(), timeout=8)
        text = res.text if res.status_code == 200 else search_ddg_snippets(f"site:allbud.com {strain_name} THC flavors")
        
        # Classification
        if "indica dominant" in text.lower():
            result["classification"] = "Indica Dominant Hybrid"
        elif "sativa dominant" in text.lower():
            result["classification"] = "Sativa Dominant Hybrid"
        elif "hybrid" in text.lower():
            result["classification"] = "Hybrid"
            
        # THC
        thc_match = re.search(r'THC:\s*([\d\s%\-]+)', text, re.I)
        if thc_match:
            result["thc"] = thc_match.group(1).strip()
            
        # Flavors
        flavors_match = re.search(r'Flavors?\s*:?\s*([A-Za-z,\s]+)', text, re.I)
        if flavors_match:
            raw_flavors = flavors_match.group(1).split(",")
            result["flavors"] = [f.strip().capitalize() for f in raw_flavors[:5] if len(f.strip()) > 2]
            
    except Exception:
        pass
    return result

# --- 4. JOINTCOMMERCE EXTRACTION ---
def fetch_jointcommerce(strain_name):
    slug = strain_name.strip().lower().replace(" ", "-")
    result = {"terpenes": [], "flavors": [], "source": "JointCommerce.com"}
    
    try:
        text = search_ddg_snippets(f"site:jointcommerce.com {strain_name} terpene flavor profile")
        
        # Terpene matching
        known_terps = ["Myrcene", "Limonene", "Caryophyllene", "Pinene", "Linalool", "Terpinolene", "Humulene", "Ocimene"]
        found_terps = [t for t in known_terps if re.search(rf'\b{t}\b', text, re.I)]
        result["terpenes"] = found_terps
        
        # Flavor matching
        known_flavors = ["Citrus", "Pine", "Earthy", "Sweet", "Berry", "Diesel", "Skunk", "Pepper", "Pungent", "Vanilla"]
        found_flavors = [f for f in known_flavors if re.search(rf'\b{f}\b', text, re.I)]
        result["flavors"] = found_flavors
        
    except Exception:
        pass
    return result

# --- AGGREGATION ENGINE ---
if st.button("Aggregate Strain Data", type="primary"):
    if not strain_input.strip():
        st.warning("Please enter a valid strain name.")
    else:
        with st.spinner(f"Scraping & combining data across Leafly, SeedFinder, AllBud, and JointCommerce..."):
            sf_res = fetch_seedfinder(strain_input)
            lf_res = fetch_leafly(strain_input)
            ab_res = fetch_allbud(strain_input)
            jc_res = fetch_jointcommerce(strain_input)

        # Merge & Normalize Results
        # 1. Classification
        classes = [x for x in [sf_res["classification"], lf_res["classification"], ab_res["classification"]] if x != "Unknown"]
        final_class = classes[0] if classes else "Hybrid / Unknown"
        
        # 2. THC Percentage
        thcs = [x for x in [lf_res["thc"], ab_res["thc"], sf_res["thc"]] if x != "N/A"]
        final_thc = thcs[0] if thcs else "15% - 25% (Average)"
        
        # 3. Dominant Terpenes
        all_terps = list(dict.fromkeys(lf_res["terpenes"] + jc_res["terpenes"]))
        
        # 4. Typical Flavors
        all_flavors = list(dict.fromkeys(ab_res["flavors"] + jc_res["flavors"]))

        st.markdown("---")
        
        # DISPLAY TOP SUMMARY METRICS
        c1, c2 = st.columns(2)
        with c1:
            st.markdown(f"""
                <div class="metric-card">
                    <h3>Classification</h3>
                    <h2>🌱 {final_class}</h2>
                </div>
            """, unsafe_allow_html=True)
        with c2:
            st.markdown(f"""
                <div class="metric-card">
                    <h3>THC Percentage Range</h3>
                    <h2>⚡ {final_thc}</h2>
                </div>
            """, unsafe_allow_html=True)

        st.write("")
        st.write("")

        # DISPLAY TERPENES & FLAVORS
        col_left, col_right = st.columns(2)
        
        with col_left:
            st.subheader("🧪 Dominant Terpenes")
            if all_terps:
                for terp in all_terps:
                    st.markdown(f"- **{terp}**")
            else:
                st.info("Myrcene, Limonene, Caryophyllene (Standard profile fallback)")

        with col_right:
            st.subheader("👅 Typical Flavors & Aromas")
            if all_flavors:
                for flavor in all_flavors:
                    st.markdown(f"- **{flavor}**")
            else:
                st.info("Earthy, Sweet, Pungent (Standard profile fallback)")

        # SOURCE BREAKDOWN ACCORDION
        with st.expander("🔍 View Raw Extracted Source Breakdown"):
            st.markdown(f"**SeedFinder.eu:** Classification: `{sf_res['classification']}`")
            st.markdown(f"**Leafly.com:** THC: `{lf_res['thc']}`, Classification: `{lf_res['classification']}`, Terpenes: `{lf_res['terpenes']}`")
            st.markdown(f"**AllBud.com:** THC: `{ab_res['thc']}`, Classification: `{ab_res['classification']}`, Flavors: `{ab_res['flavors']}`")
            st.markdown(f"**JointCommerce.com:** Extracted Terpenes: `{jc_res['terpenes']}`, Flavors: `{jc_res['flavors']}`")
