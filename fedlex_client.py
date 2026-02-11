import httpx
import urllib.parse
import json
import re
import os

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
        Fetches law details by citation (e.g., 'OR 41', 'ZGB 1', 'Art. 41, Abs. 2', 'Art. 52 Abs. 1 lit. c').
        """
        query = query.strip()
        
        # Pattern 1: SR Number (e.g., "210", "101", "0.312.11")
        if re.match(r"^[\d\.]+$", query):
            return self.fetch_article_by_sr(query)
            
        # Pattern 2: Citation (e.g., "OR 41", "ZGB 1a", "OR", "OR 41, Abs. 2", "Art. 52 Abs. 1 lit. c")
        # Supports: Abbr [Art] [, Abs. Num] [, lit./Ziff. ID]
        # Match: group(1)=Abbr, group(2)=Art, group(3)=Abs, group(4)=lit/Ziffer
        pattern = r"^([a-zA-Z\u00C0-\u017F]+)(?:\s+([\d\w\.]+))?(?:[, \s]+(?:Abs\.|Absatz)\s+(\d+))?(?:[, \s]+(?:lit\.|Buchstabe|Ziff\.|Ziffer)\s+([\d\w]+))?$"
        match = re.match(pattern, query, re.IGNORECASE)
        
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
                if art_num:
                    # Append fragment for specific article
                    fragment = f"#art_{art_num.lower()}"
                    
                    if abs_num:
                        # Append fragment for specific paragraph
                        fragment += f"/para_{abs_num}"
                        result["paragraph"] = abs_num
                        
                        if lit_num:
                            # Append fragment for specific litera or ziffer
                            fragment += f"/lbl_{lit_num.lower()}"
                            result["literal"] = lit_num
                    elif lit_num:
                        # Sometimes lit. follows Art. directly (rare but possible in some laws)
                        fragment += f"/lbl_{lit_num.lower()}"
                        result["literal"] = lit_num
                    
                    result["url"] = f"{result['url']}{fragment}"
                    result["article"] = art_num
            
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
        Fetches the metadata and deep link for a specific article.
        Returns a dictionary with title, link, and a message about the text.
        """
        # Clean article_id for SPARQL (e.g., 'Art. 41' or just '41')
        id_query = f"Art. {article_id}" if not str(article_id).startswith("Art.") else article_id
        
        sparql_query = f"""
        PREFIX jolux: <http://data.legilux.public.lu/resource/ontology/jolux#>
        PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
        PREFIX language: <http://publications.europa.eu/resource/authority/language/>

        SELECT DISTINCT ?title ?eli
        WHERE {{
          ?node skos:notation "{sr_number}" .
          ?law jolux:classifiedByTaxonomyEntry ?node .
          
          # Find the subdivision (article)
          ?sub jolux:subdivisionIsPartOfResource ?law .
          ?sub jolux:subdivisionIdentification "{id_query}" .
          
          # Get the title from the German expression
          ?sub jolux:isRealizedBy ?expr .
          ?expr jolux:language language:DEU .
          ?expr jolux:title ?title .
          
          # Get the ELI (deep link)
          OPTIONAL {{ ?sub jolux:isEmbodiedBy ?manifestation . ?manifestation jolux:linkToContent ?eli . }}
        }}
        LIMIT 1
        """
        
        try:
            params = {"query": sparql_query, "format": "json"}
            headers = {"Accept": "application/sparql-results+json"}
            
            response = self.client.get(self.endpoint, params=params, headers=headers)
            if response.status_code == 200:
                data = response.json()
                bindings = data.get("results", {}).get("bindings", [])
                if bindings:
                    b = bindings[0]
                    title = b['title']['value']
                    # Default ELI if not in SPARQL
                    eli = b.get('eli', {}).get('value') or f"https://www.fedlex.admin.ch/eli/cc/{sr_number}/de#art_{article_id.lower().replace(' ', '_')}"
                    
                    return {
                        "title": f"{id_query}: {title}",
                        "link": eli,
                        "text": f"[Volltext verfügbar unter: {eli}]\nDas Fedlex-Portal unterbindet automatisiertes Auslesen des Volltexts. Dieses Tool liefert jedoch die offizielle Bezeichnung und den direkten Link für rechtssichere Zitate.",
                        "source": "Offizielles Fedlex-Basisregister (SPARQL)"
                    }
        except Exception as e:
            print(f"Error fetching article text: {e}")
            
        return None

    def search_fedlex_topics(self, query_str: str):
        """
        Searches for laws or articles by keywords in titles, labels, or subjects.
        """
        keywords = query_str.split()
        if not keywords:
            return []
            
        # Build regex filters for all keywords
        regex_filters = " && ".join([f'regex(str(?allLabels), "{kw}", "i")' for kw in keywords])
        
        sparql_query = f"""
        PREFIX jolux: <http://data.legilux.public.lu/resource/ontology/jolux#>
        PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
        PREFIX language: <http://publications.europa.eu/resource/authority/language/>
        PREFIX dc: <http://purl.org/dc/elements/1.1/>

        SELECT DISTINCT ?sr ?title ?subLabel ?url
        WHERE {{
          {{
            # Scenario A: Keyword in Law/Expression title or label
            {{ ?res jolux:title ?allLabels . }} UNION {{ ?res skos:prefLabel ?allLabels . }}
            FILTER(lang(?allLabels) = "de")
            
            {{
                ?res jolux:realizes ?law .
                ?law a jolux:ConsolidationAbstract .
            }} UNION {{
                ?res a jolux:ConsolidationAbstract .
                BIND(?res AS ?law)
            }}
            ?law jolux:isRealizedBy ?expr .
            ?expr jolux:language language:DEU .
            ?expr jolux:title ?title .
            
            ?law jolux:classifiedByTaxonomyEntry ?node .
            ?node skos:notation ?sr .
            BIND("-" AS ?subLabel)
          }}
          UNION
          {{
            # Scenario B: Keyword in Subject/Theme (via Taxonomy)
            ?concept skos:prefLabel ?allLabels .
            FILTER(lang(?allLabels) = "de")
            ?node dc:subject ?concept .
            ?law jolux:classifiedByTaxonomyEntry ?node .
            ?law a jolux:ConsolidationAbstract .
            
            ?law jolux:isRealizedBy ?expr .
            ?expr jolux:language language:DEU .
            ?expr jolux:title ?title .
            ?node skos:notation ?sr .
            BIND("-" AS ?subLabel)
          }}
          
          FILTER({regex_filters})
          
          OPTIONAL {{
              ?law jolux:isRealizedBy ?expr_url .
              ?expr_url jolux:language language:DEU .
              ?expr_url jolux:isEmbodiedBy ?manifestation .
              ?manifestation jolux:format <http://publications.europa.eu/resource/authority/file-type/HTML> .
              ?manifestation jolux:linkToContent ?url .
          }}
        }}
        ORDER BY ?sr
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
            for b in bindings:
                res_url = b.get("url", {}).get("value")
                sr_val = b.get("sr", {}).get("value")
                sub_val = b.get("subLabel", {}).get("value")
                
                if not res_url:
                    res_url = f"https://www.fedlex.admin.ch/eli/cc/{sr_val}/de"
                    
                results.append({
                    "sr": sr_val,
                    "title": b.get("title", {}).get("value"),
                    "sub_label": sub_val if sub_val != "-" else None,
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
