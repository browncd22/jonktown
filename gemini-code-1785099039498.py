import streamlit as st
import requests
from bs4 import BeautifulSoup
import json
import re

st.set_page_config(page_title="Cannabis Lineage & Terpene Explorer", page_icon="🌿", layout="wide")

# Custom CSS for polished layout
st.markdown("""
    <style>
    .stMetric {
        background-color: #1e2130;
        padding: 12px;
        border-radius: 8px;
    }
    .genetics-card {
        background-color: #262730;
        border-left: 4px solid #4CAF50;
        padding: 10px 15px;
        margin-bottom: 8px;
        border-radius: 0 8px 8px 0;
    }
    </style>
""", unsafe_allow_html=True)

st.title("🌿 Strain Intelligence: Lineage & Terpene Aggregator")
st.caption("Aggregating genetic history from SeedFinder.eu & chemical profiles from Leafly")

strain_input = st.text_input("Enter Strain Name:", value="Gorilla Glue", placeholder="e.g. Gelato, Jack Herer, OG Kush")

def get_headers():
    return {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
    }

def fetch_seedfinder_lineage(strain_name):
    """Scrapes and cleans strain genetics/lineage from SeedFinder.eu."""
    formatted_name = strain_name.strip().replace(" ", "_")
    target_url = f"https://en.seedfinder.eu/strain-info/{formatted_name}/"
    
    try:
        res = requests.get(target_url, headers=get_headers(), timeout=10)
        
        # Fallback to search query if direct URL fails
        if res.status_code != 200:
            search_url = f"https://en.seedfinder.eu/search/extended/?q={strain_name.strip()}"
            search_res = requests.get(search_url, headers=get_headers(), timeout=10)
            soup_search = BeautifulSoup(search_res.text, "html.parser")
            first_link = soup_search.select_one("table.strainlist a[href*='/strain-info/']")
            if first_link:
                target_url = "https://en.seedfinder.eu" + first_link["href"]
                res = requests.get(target_url, headers=get_headers(), timeout=10)
            else:
                return None, "Strain not found on SeedFinder."

        soup = BeautifulSoup(res.text, "html.parser")
        
        # Target the lineage container
        lineage_container = soup.find("div", id="lineage") or soup.find("div", class_="stree")
        
        lineage_list = []
        if lineage_container:
            # Extract links and bullet text specifically to filter out nav noise
            for item in lineage_container.find_all(["a", "li"]):
                text = item.get_text(strip=True)
                # Filter unwanted UI text
                if text and not any(ignore in text.lower() for ignore in ["picture", "upload", "info", "seedfinder", "tree", "map"]):
                    # Clean up trailing arrows or weird formatting symbols
                    text_clean = re.sub(r'^[»›\-\s]+', '', text)
                    if text_clean and text_clean not in lineage_list:
                        lineage_list.append(text_clean)

        return {
            "url": target_url,
            "genetics": lineage_list if lineage_list else ["Lineage structure available on source page."]
        }, None

    except Exception as e:
        return None, f"SeedFinder Fetch Error: {e}"

def fetch_leafly_terpenes(strain_name):
    """Queries Leafly's internal GraphQL backend directly for clean terpene and cannabinoid data."""
    slug = strain_name.strip().lower().replace(" ", "-").replace("'", "")
    
    # Primary strategy: Fetch via Leafly's GraphQL endpoint
    graphql_url = "https://www.leafly.com/api/graphql"
    query = """
    query StrainData($slug: String!) {
      strain(slug: $slug) {
        name
        category
        thc
        cbd
        terpenes {
          name
          score
        }
        effects {
          name
        }
      }
    }
    """
    
    headers = get_headers()
    headers["Content-Type"] = "application/json"
    
    try:
        response = requests.post(
            graphql_url, 
            json={"query": query, "variables": {"slug": slug}}, 
            headers=headers, 
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            strain_data = data.get("data", {}).get("strain")
            
            if strain_data:
                terps = [t["name"] for t in strain_data.get("terpenes", []) if t.get("name")]
                return {
                    "url": f"https://www.leafly.com/strains/{slug}",
                    "category": strain_data.get("category", "N/A"),
                    "thc": strain_data.get("thc"),
                    "cbd": strain_data.get("cbd"),
                    "terpenes": terps,
                    "effects": [e["name"] for e in strain_data.get("effects", [])[:5]]
                }, None

        # Fallback Strategy: Web Page HTML / Next.js JSON Extraction
        web_url = f"https://www.leafly.com/strains/{slug}"
        web_res = requests.get(web_url, headers=get_headers(), timeout=10)
        
        if web_res.status_code == 200:
            soup = BeautifulSoup(web_res.text, "html.parser")
            script_tag = soup.find("script", id="__NEXT_DATA__")
            
            if script_tag:
                json_data = json.loads(script_tag.string)
                # Traversal through Next.js state structure
                page_props = json_data.get("props", {}).get("pageProps", {})
                strain = page_props.get("strain", {}) or page_props.get("initialData", {}).get("strain", {})
                
                terps_list = []
                terp_data = strain.get("terpenes", {})
                if isinstance(terp_data, dict):
                    terps_list = [t.get("name") for t in terp_data.get("array", []) if isinstance(t, dict)]
                elif isinstance(terp_data, list):
                    terps_list = [t.get("name") for t in terp_data if isinstance(t, dict)]

                return {
                    "url": web_url,
                    "category": strain.get("category", "N/A"),
                    "thc": strain.get("thc", "N/A"),
                    "cbd": strain.get("cbd", "N/A"),
                    "terpenes": terps_list,
                    "effects": []
                }, None

        return None, f"Could not locate '{strain_name}' on Leafly."

    except Exception as e:
        return None, f"Leafly Fetch Error: {e}"

# Search execution
if st.button("Search & Combine Data", type="primary"):
    if not strain_input.strip():
        st.warning("Please enter a strain name.")
    else:
        with st.spinner(f"Querying SeedFinder & Leafly for '{strain_input}'..."):
            sf_data, sf_err = fetch_seedfinder_lineage(strain_input)
            leafly_data, leafly_err = fetch_leafly_terpenes(strain_input)

        st.markdown("---")
        col1, col2 = st.columns(2)

        # LEFT COLUMN: SeedFinder Lineage
        with col1:
            st.subheader("🌲 Lineage & Genealogy")
            st.caption("Source: SeedFinder.eu")
            
            if sf_err:
                st.error(sf_err)
            else:
                st.markdown(f"🔗 [View Full Tree on SeedFinder]({sf_data['url']})")
                st.write("**Extracted Genetic Lineage:**")
                
                for item in sf_data["genetics"]:
                    st.markdown(f"""
                        <div class="genetics-card">
                            <strong>🧬</strong> {item}
                        </div>
                    """, unsafe_allow_html=True)

        # RIGHT COLUMN: Leafly Chemotype & Terpenes
        with col2:
            st.subheader("🧪 Terpene & Profile")
            st.caption("Source: Leafly.com")
            
            if leafly_err:
                st.error(leafly_err)
            else:
                st.markdown(f"🔗 [View Profile on Leafly]({leafly_data['url']})")
                
                # Category & Cannabinoids
                m1, m2, m3 = st.columns(3)
                m1.metric("Category", str(leafly_data['category']).capitalize())
                m2.metric("THC", f"{leafly_data['thc']}%" if leafly_data['thc'] else "N/A")
                m3.metric("CBD", f"{leafly_data['cbd']}%" if leafly_data['cbd'] else "N/A")
                
                st.markdown("### **Dominant Terpenes:**")
                if leafly_data["terpenes"]:
                    for idx, terp in enumerate(leafly_data["terpenes"], 1):
                        st.markdown(f"**{idx}. {terp.capitalize()}**")
                else:
                    st.info("No detailed terpene profile breakdown returned for this strain.")
                
                if leafly_data.get("effects"):
                    st.markdown("### **Top Reported Effects:**")
                    st.write(", ".join([e.capitalize() for e in leafly_data["effects"]]))