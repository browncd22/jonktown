import streamlit as st
import requests
from bs4 import BeautifulSoup
import json
import re

st.set_page_config(
    page_title="Cannabis Terpene & Flavor Aggregator",
    page_icon="🌿",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# --- MODERN CLEAN UI STYLING ---
st.markdown("""
    <style>
    /* Dark glassmorphic container styling */
    .metric-card {
        background-color: #1a1c24;
        padding: 20px;
        border-radius: 12px;
        border: 1px solid #2d3142;
        text-align: center;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    .data-card {
        background-color: #1a1c24;
        padding: 20px;
        border-radius: 12px;
        border: 1px solid #2d3142;
        margin-bottom: 15px;
    }
    .badge-terp {
        background-color: #1e3a29;
        color: #4cd964;
        padding: 6px 12px;
        border-radius: 15px;
        display: inline-block;
        margin: 4px;
        font-weight: 600;
        font-size: 0.9em;
        border: 1px solid #2e693e;
    }
    .badge-flavor {
        background-color: #3a2b1e;
        color: #ff9500;
        padding: 6px 12px;
        border-radius: 15px;
        display: inline-block;
        margin: 4px;
        font-weight: 600;
        font-size: 0.9em;
        border: 1px solid #694e2e;
    }
    </style>
""", unsafe_allow_html=True)

st.title("🌿 Strain Profile & Terpene Aggregator")
st.caption("Deep-searching **Leafly**, **SeedFinder**, **AllBud**, and **JointCommerce** for detailed chemical and flavor profiles.")

# Search Input
strain_input = st.text_input("Enter Strain Name:", value="Gorilla Glue", placeholder="e.g., Gelato, OG Kush, Jack Herer, Wedding Cake")

def get_headers():
    return {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
    }

# --- MASTER CHEMICAL & FLAVOR DICTIONARIES ---
KNOWN_TERPENES = [
    "Caryophyllene", "Myrcene", "Limonene", "Linalool", "Pinene", "Alpha-Pinene", "Beta-Pinene",
    "Humulene", "Terpinolene", "Ocimene", "Bisabolol", "Camphene", "Geraniol", "Valencene",
    "Carene", "Terpinene", "Eucalyptol", "Fenchol", "Phytol", "Nerolidol"
]

KNOWN_FLAVORS = [
    "Citrus", "Pine", "Earthy", "Sweet", "Berry", "Diesel", "Skunk", "Pepper", "Pungent",
    "Vanilla", "Cheese", "Nutty", "Tropical", "Mango", "Lemon", "Lime", "Orange", "Grape",
    "Blueberry", "Strawberry", "Flowery", "Spicy", "Herbal", "Woody", "Chemical", "Mint", "Butter"
]

def search_snippets(query):
    """Deep search helper to pull indexed text from search engines if direct page scraper is blocked."""
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

def scan_text_for_matches(text):
    """Scans raw html/text blobs against terpene and flavor dictionaries."""
    found_terps = []
    found_flavors = []
    
    for terp in KNOWN_TERPENES:
        if re.search(rf'\b{re.escape(terp)}\b', text, re.IGNORECASE):
            found_terps.append(terp.capitalize())
            
    for flavor in KNOWN_FLAVORS:
        if re.search(rf'\b{re.escape(flavor)}\b', text, re.IGNORECASE):
            found_flavors.append(flavor.capitalize())
            
    return list(set(found_terps)), list(set(found_flavors))

# --- DEEP SEARCH SCRAPING ENGINES ---
def fetch_all_sources(strain_name):
    slug = strain_name.strip().lower().replace(" ", "-").replace("'", "")
    clean_name = strain_name.strip()
    
    aggregated_terps = []
    aggregated_flavors = []
    thc_values = []
    classifications = []
    source_logs = []

    # 1. LEAFLY GRAPHQL + SEARCH
    try:
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
        res = requests.post(graphql_url, json={"query": query, "variables": {"slug": slug}}, headers=get_headers(), timeout=6)
        if res.status_code == 200:
            data = res.json().get("data", {}).get("strain")
            if data:
                if data.get("category"): classifications.append(data.get("category").capitalize())
                if data.get("thc"): thc_values.append(f"{data.get('thc')}%")
                if data.get("terpenes"):
                    for t in data.get("terpenes"):
                        if t.get("name"): aggregated_terps.append(t["name"].capitalize())
                source_logs.append("Leafly API: Successfully retrieved data")
    except Exception:
        pass

    # Leafly Search Snippet Scan (Deep Terpene / Flavor Recovery)
    lf_snippet = search_snippets(f"site:leafly.com/strains/{slug} terpenes flavor THC")
    if lf_snippet:
        t_match, f_match = scan_text_for_matches(lf_snippet)
        aggregated_terps.extend(t_match)
        aggregated_flavors.extend(f_match)
        source_logs.append(f"Leafly Search: Extracted {len(t_match)} terpenes & {len(f_match)} flavors")

    # 2. ALLBUD SCRAPER
    try:
        allbud_url = f"https://www.allbud.com/marijuana-strains/{slug}"
        res = requests.get(allbud_url, headers=get_headers(), timeout=6)
        text = res.text if res.status_code == 200 else search_snippets(f"site:allbud.com {clean_name} strain THC flavors terpenes")
        
        # Classification & THC
        if "indica dominant" in text.lower(): classifications.append("Indica Dominant Hybrid")
        elif "sativa dominant" in text.lower(): classifications.append("Sativa Dominant Hybrid")
        elif "hybrid" in text.lower(): classifications.append("Hybrid")
        
        thc_m = re.search(r'THC:\s*([\d\s%\-]+)', text, re.I)
        if thc_m: thc_values.append(thc_m.group(1).strip())
        
        t_match, f_match = scan_text_for_matches(text)
        aggregated_terps.extend(t_match)
        aggregated_flavors.extend(f_match)
        source_logs.append(f"AllBud: Extracted {len(t_match)} terpenes & {len(f_match)} flavors")
    except Exception:
        pass

    # 3. SEEDFINDER SEARCH
    sf_text = search_snippets(f"site:seedfinder.eu {clean_name} strain genetics terpenes")
    if sf_text:
        t_match, f_match = scan_text_for_matches(sf_text)
        aggregated_terps.extend(t_match)
        aggregated_flavors.extend(f_match)
        source_logs.append(f"SeedFinder: Extracted {len(t_match)} terpenes & {len(f_match)} flavors")

    # 4. JOINTCOMMERCE DEEP SEARCH
    jc_text = search_snippets(f"site:jointcommerce.com {clean_name} terpene flavor profile")
    if jc_text:
        t_match, f_match = scan_text_for_matches(jc_text)
        aggregated_terps.extend(t_match)
        aggregated_flavors.extend(f_match)
        source_logs.append(f"JointCommerce: Extracted {len(t_match)} terpenes & {len(f_match)} flavors")

    # Final Deduplication & Sorting
    final_terps = list(dict.fromkeys(aggregated_terps))
    final_flavors = list(dict.fromkeys(aggregated_flavors))
    
    final_class = classifications[0] if classifications else "Hybrid"
    final_thc = thc_values[0] if thc_values else "18% - 24% (Est.)"

    return {
        "classification": final_class,
        "thc": final_thc,
        "terpenes": final_terps,
        "flavors": final_flavors,
        "logs": source_logs
    }

# --- DISPLAY LOGIC ---
if st.button("Deep Search Strain Profile", type="primary"):
    if not strain_input.strip():
        st.warning("Please enter a valid strain name.")
    else:
        with st.spinner(f"Performing deep chemical & aroma scan for '{strain_input}' across all sources..."):
            results = fetch_all_sources(strain_input)

        st.markdown("---")
        
        # TOP SUMMARY METRICS
        m1, m2 = st.columns(2)
        with m1:
            st.markdown(f"""
                <div class="metric-card">
                    <span style="color: #8e8e93; font-size: 0.85em; text-transform: uppercase;">Classification</span>
                    <h2 style="color: #4cd964; margin-top: 5px;">🌱 {results['classification']}</h2>
                </div>
            """, unsafe_allow_html=True)
            
        with m2:
            st.markdown(f"""
                <div class="metric-card">
                    <span style="color: #8e8e93; font-size: 0.85em; text-transform: uppercase;">THC Level</span>
                    <h2 style="color: #ff9500; margin-top: 5px;">⚡ {results['thc']}</h2>
                </div>
            """, unsafe_allow_html=True)

        st.write("")
        st.write("")

        # MAIN TERPENE & FLAVOR DISPLAY
        c_terp, c_flavor = st.columns(2)
        
        with c_terp:
            st.markdown("### 🧪 Terpenes Present")
            if results["terpenes"]:
                terp_html = "".join([f'<span class="badge-terp">{t}</span>' for t in results["terpenes"]])
                st.markdown(f'<div class="data-card">{terp_html}</div>', unsafe_allow_html=True)
            else:
                st.info("No specific terpene profile indexed for this strain name.")

        with c_flavor:
            st.markdown("### 👅 Flavors & Aromas")
            if results["flavors"]:
                flavor_html = "".join([f'<span class="badge-flavor">{f}</span>' for f in results["flavors"]])
                st.markdown(f'<div class="data-card">{flavor_html}</div>', unsafe_allow_html=True)
            else:
                st.info("No specific flavor notes indexed for this strain name.")

        # RAW EXTRACTION LOGS
        with st.expander("🔍 Scraper Diagnostics & Source Logs"):
            for log in results["logs"]:
                st.write(f"- {log}")
