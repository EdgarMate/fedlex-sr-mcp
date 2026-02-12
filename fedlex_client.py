import httpx
import urllib.parse
import json
import re
import os
from bs4 import BeautifulSoup

class FedlexClient:
    def __init__(self):
        self.endpoint = "https://fedlex.data.admin.ch/sparqlendpoint"
        self.client = httpx.Client(timeout=30.0, follow_redirects=True)
        
        # Load abbreviation mapping
        mapping_path = os.path.join(os.path.dirname(__file__), "abbreviation_mapping.json")
        try:
            with open(mapping_path, "r", encoding="utf-8") as f:
                self.mapping = json.load(f)
        except Exception as e:
            print(f"Warning: Could not load abbreviation mapping: {e}")
            self.mapping = {}

    def fetch_law_by_citation(self, query: str):
        """
        Fetches law details by citation. Supports:
        - SR Numbers: 210, 101, 0.312.11
        - Code + Art: OR 41, ZGB 1, CC 210, CO 1
        - Art + Code: Art. 41 OR, Art 1 ZGB
        - Detail: OR 41, Abs. 2, lit. c
        """
        query = query.strip()
        
        # 1. Direct SR Number
        if re.match(r"^[\d\.]+$", query):
            return self.fetch_article_by_sr(query)
            
        # 2. Extract components
        # Pre-process: handle "Art. 41 OR" -> normalize to "OR 41" for matching
        # Regex: matches "Art. 41" or "Art 41" and a following abbreviation
        norm_query = re.sub(r"^(?:Art\.\s*|Art\s+)?(\d+\w*)[\s,]+([a-zA-Z\u00C0-\u017F]+)", r"\2 \1", query, flags=re.IGNORECASE)
        
        # Pattern for "Abbr [Art] [, Abs X] [, lit Y]"
        pattern = r"^([a-zA-Z\u00C0-\u017F]+)(?:\s+([\d\w\.]+))?(?:[, \s]+(?:Abs\.|Absatz)\s+(\d+))?(?:[, \s]+(?:lit\.|Buchstabe|Ziff\.|Ziffer|lbl)\s+([\d\w]+))?$"
        match = re.match(pattern, norm_query, re.IGNORECASE)
        
        if match:
            abbr = match.group(1).upper()
            art_num = match.group(2)
            abs_num = match.group(3)
            lit_num = match.group(4)
            
            sr_number = self.mapping.get(abbr)
            if not sr_number:
                return None
                
            result = self.fetch_article_by_sr(sr_number)
            if result:
                result["article"] = art_num
                if art_num:
                    fragment = f"#art_{art_num.lower()}"
                    if abs_num:
                        fragment += f"/para_{abs_num}"
                        result["paragraph"] = abs_num
                        if lit_num:
                            fragment += f"/lbl_{lit_num.lower()}"
                            result["literal"] = lit_num
                    
                    result["url"] = f"{result['url']}{fragment}"
                return result
            
        return None

    def fetch_article_by_sr(self, sr_number: str):
        # SPARQL query to find the legislation by SR number
        # We use str(?notation) to ensures we match the literal regardless of datatype
        query = f"""
        PREFIX jolux: <http://data.legilux.public.lu/resource/ontology/jolux#>
        PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
        PREFIX filetype: <http://publications.europa.eu/resource/authority/file-type/>
        PREFIX language: <http://publications.europa.eu/resource/authority/language/>
        
        SELECT ?work ?title ?url
        WHERE {{
          # 1. Find the taxonomy node for the SR number
          ?node skos:notation ?notation .
          FILTER (str(?notation) = "{sr_number}") .
          
          # 2. Find the abstract work classified by this node
          ?work jolux:classifiedByTaxonomyEntry ?node .
          ?work a jolux:ConsolidationAbstract .
          
          # 3. Get title (try German)
          OPTIONAL {{
              ?work jolux:isRealizedBy ?expression .
              ?expression jolux:language language:DEU .
              ?expression jolux:title ?title .
          }}
          
          # 4. Get URL (try HTML)
          OPTIONAL {{
              ?work jolux:isRealizedBy ?expression .
              ?expression jolux:language language:DEU .
              ?expression jolux:isEmbodiedBy ?manifestation .
              ?manifestation jolux:format filetype:HTML .
              ?manifestation jolux:linkToContent ?url .
          }}
        }}
        LIMIT 1
        """
        
        try:
            params = {"query": query, "format": "json"}
            headers = {"Accept": "application/sparql-results+json"}
            
            response = self.client.get(self.endpoint, params=params, headers=headers)
            response.raise_for_status()
            
            if "json" not in response.headers.get("content-type", "").lower():
                 return None

            data = response.json()
            bindings = data.get("results", {}).get("bindings", [])
            
            if not bindings:
                return None
                
            result = bindings[0]
            title = result.get("title", {}).get("value")
            url = result.get("url", {}).get("value")
            work_uri = result.get("work", {}).get("value")
            
            if not url and work_uri:
                 url = f"{work_uri}/de"

            return {
                "title": title or "Unknown Title",
                "url": url,
                "sr": sr_number
            }
            
        except Exception as e:
            print(f"Error fetching SR {sr_number}: {e}")
            return None

    def fetch_article_text(self, sr_number: str, article_id: str):
        """
        Fetches the wording of a specific article.
        Uses version-aware lookup from the GitHub assets mirror.
        """
        # 1. Get the Law URI and Title via SPARQL
        # We also look for all members (consolidations) to find the latest version
        sparql_query = f"""
        PREFIX jolux: <http://data.legilux.public.lu/resource/ontology/jolux#>
        PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
        PREFIX language: <http://publications.europa.eu/resource/authority/language/>

        SELECT DISTINCT ?law ?title ?member
        WHERE {{
          ?node skos:notation ?notation .
          FILTER (str(?notation) = "{sr_number}") .
          ?law jolux:classifiedByTaxonomyEntry ?node .
          ?law a jolux:ConsolidationAbstract .
          
          # Get Title
          OPTIONAL {{
            ?law jolux:isRealizedBy ?expr .
            ?expr jolux:language language:DEU .
            ?expr jolux:title ?title .
          }}
          
          # Get Consolidations
          OPTIONAL {{
            ?member jolux:isMemberOf ?law .
            ?member a jolux:Consolidation .
          }}
        }}
        ORDER BY DESC(?member)
        LIMIT 20
        """
        
        law_uri = None
        title = None
        versions = []
        
        try:
            params = {"query": sparql_query, "format": "json"}
            headers = {"Accept": "application/sparql-results+json"}
            response = self.client.get(self.endpoint, params=params, headers=headers)
            if response.status_code == 200:
                bindings = response.json().get("results", {}).get("bindings", [])
                if bindings:
                    law_uri = bindings[0]['law']['value']
                    title = bindings[0].get('title', {}).get('value') or f"SR {sr_number}"
                    for b in bindings:
                        if 'member' in b:
                            versions.append(b['member']['value'])
        except Exception as e:
            print(f"Error fetching law metadata: {e}")

        if not law_uri:
            return None

        # 2. Try to fetch wording from GitHub mirror for candidate versions
        eli_path = law_uri.replace("https://fedlex.data.admin.ch/eli/cc/", "")
        
        # Candidate versions: From SPARQL (latest first) or common guesses
        candidates = []
        for v_uri in versions:
            v_val = v_uri.split('/')[-1]
            if v_val not in candidates:
                candidates.append(v_val)
        
        if "20260101" not in candidates: candidates.append("20260101")
        if "20250101" not in candidates: candidates.append("20250101")

        content_text = None
        found_version = None
        
        # Clean article_id for CSS (e.g. '41' -> 'art_41')
        clean_id = str(article_id).lower().replace("art.", "").strip().replace(" ", "_")
        target_id = f"art_{clean_id}"

        for version in candidates[:3]: # Try only top 3 to keep it snappy
            filename = f"fedlex-data-admin-ch-eli-cc-{eli_path.replace('/', '-')}-{version}-de-html.html"
            github_url = f"https://raw.githubusercontent.com/droid-f/fedlex-assets/main/eli/cc/{eli_path}/{version}/de/html/{filename}"
            
            try:
                r = self.client.get(github_url, timeout=5.0)
                if r.status_code == 200:
                    soup = BeautifulSoup(r.text, 'html.parser')
                    article_tag = soup.find(id=target_id)
                    if not article_tag:
                        article_tag = soup.find(id=re.compile(f"^{target_id}", re.I))
                    
                    if article_tag:
                        content_text = article_tag.get_text(separator="\n", strip=True)
                        found_version = version
                        break
            except Exception:
                continue

        # Construct final response
        eli_link = f"https://www.fedlex.admin.ch/eli/cc/{sr_number}/de#art_{clean_id}"
        
        if content_text:
            return {
                "title": f"Art. {article_id}: {title}",
                "link": eli_link,
                "text": content_text,
                "source": f"Swiss Federal Law Mirror (GitHub Assets, Version {found_version})"
            }
        else:
            return {
                "title": f"Art. {article_id}: {title}",
                "link": eli_link,
                "text": f"[Volltext verfügbar unter: {eli_link}]\nDas Fedlex-Portal unterbindet automatisierte Browser. Der Text konnte im Mirror nicht lokalisiert werden. Möglicherweise ist die gewählte Artikel-Nummer ungültig oder der Mirror ist noch nicht auf dem neuesten Stand.",
                "source": "Offizielles Fedlex-Basisregister"
            }

    def search_fedlex_topics(self, query_str: str):
        """
        Searches for laws by keywords with high relevance ranking.
        Prioritizes ConsolidationAbstract (main laws) and newest versions.
        """
        keywords = query_str.split()
        if not keywords:
            return []
            
        # Build regex filters for all keywords (Case insensitive)
        # We search in a combined pool of titles and subjects
        regex_filters = " && ".join([f'regex(str(?allLabels), "{kw}", "i")' for kw in keywords])
        
        sparql_query = f"""
        PREFIX jolux: <http://data.legilux.public.lu/resource/ontology/jolux#>
        PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
        PREFIX language: <http://publications.europa.eu/resource/authority/language/>
        PREFIX dc: <http://purl.org/dc/elements/1.1/>

        SELECT DISTINCT ?sr ?title ?url (COUNT(?keywordMatch) AS ?rank)
        WHERE {{
          {{
            # Keyword in Law Title or skos:prefLabel
            {{ ?res jolux:title ?allLabels . }} UNION {{ ?res skos:prefLabel ?allLabels . }}
            BIND(?allLabels AS ?keywordMatch)
            
            # Resolve to the main Law (ConsolidationAbstract)
            {{
              ?res jolux:realizes ?law .
              ?law a jolux:ConsolidationAbstract .
            }} UNION {{
              ?res a jolux:ConsolidationAbstract .
              BIND(?res AS ?law)
            }}
          }}
          UNION
          {{
            # Keyword in Subject/Theme (via Taxonomy Entry or Concept)
            {{
                # Via Classification Node directly
                ?law jolux:classifiedByTaxonomyEntry ?themeNode .
                ?themeNode skos:prefLabel ?allLabels .
            }} 
            UNION 
            {{
                # Via Subject Concept linked to Classification Node
                ?law jolux:classifiedByTaxonomyEntry ?themeNode .
                ?themeNode dc:subject ?concept .
                ?concept skos:prefLabel ?allLabels .
            }}
            BIND(?allLabels AS ?keywordMatch)
            ?law a jolux:ConsolidationAbstract .
          }}

          # Ensure we have an SR number (from a classification node with a notation)
          ?law jolux:classifiedByTaxonomyEntry ?srNode .
          ?srNode skos:notation ?sr .
          # Filter SR: must look like a formal SR number (digits and dots)
          FILTER(regex(str(?sr), "^[0-9]{{1,3}}\\\\.[0-9\\\\.]+$") || regex(str(?sr), "^[0-9]{{1,3}}$"))
          
          # Get the preferred Title (German if possible, else French/Italian)
          OPTIONAL {{
            ?law jolux:isRealizedBy ?expr_de .
            ?expr_de jolux:language language:DEU .
            ?expr_de jolux:title ?title_de .
          }}
          OPTIONAL {{
            ?law jolux:isRealizedBy ?expr_fr .
            ?expr_fr jolux:language language:FRA .
            ?expr_fr jolux:title ?title_fr .
          }}
          BIND(COALESCE(?title_de, ?title_fr, "Law " + str(?sr)) AS ?title)

          FILTER({regex_filters})
          
          # Get current URL
          OPTIONAL {{
              ?law jolux:isRealizedBy ?expr_url .
              ?expr_url jolux:isEmbodiedBy ?manifestation .
              ?manifestation jolux:format <http://publications.europa.eu/resource/authority/file-type/HTML> .
              ?manifestation jolux:linkToContent ?url .
          }}
        }}
        GROUP BY ?sr ?title ?url
        ORDER BY DESC(?rank) ?sr
        LIMIT 10
        """
        
        try:
            params = {"query": sparql_query, "format": "json"}
            headers = {"Accept": "application/sparql-results+json"}
            
            response = self.client.get(self.endpoint, params=params, headers=headers)
            response.raise_for_status()
            
            data = response.json()
            bindings = data.get("results", {}).get("bindings", [])
            
            results = []
            seen_sr = set()
            for b in bindings:
                sr_val = b.get("sr", {}).get("value")
                if sr_val in seen_sr:
                    continue
                seen_sr.add(sr_val)
                
                res_url = b.get("url", {}).get("value")
                if not res_url:
                    res_url = f"https://www.fedlex.admin.ch/eli/cc/{sr_val}/de"
                    
                results.append({
                    "sr": sr_val,
                    "title": b.get("title", {}).get("value"),
                    "url": res_url
                })
            return results
        except Exception:
            return []

if __name__ == "__main__":
    client = FedlexClient()
    print("Testing 'OR 41'...")
    res = client.fetch_law_by_citation("OR 41")
    print(res)
    
    print("-" * 20)
    print("Testing 'ZGB 1'...")
    res = client.fetch_law_by_citation("ZGB 1")
    print(res)
    
    print("-" * 20)
    print("Testing 'BV'...")
    res = client.fetch_law_by_citation("BV")
    print(res)
