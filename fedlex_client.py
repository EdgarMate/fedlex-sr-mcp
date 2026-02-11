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

    def search_fedlex_topics(self, query: str):
        """
        Searches for laws or articles by keywords in the title or labels.
        """
        keywords = query.split()
        if not keywords:
            return []
            
        # Build regex filters for all keywords (Logical AND)
        # We search in ?title which can come from jolux:title or skos:prefLabel
        regex_filters = " && ".join([f'regex(?title, "{kw}", "i")' for kw in keywords])
        
        sparql_query = f"""
        PREFIX jolux: <http://data.legilux.public.lu/resource/ontology/jolux#>
        PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
        PREFIX language: <http://publications.europa.eu/resource/authority/language/>
        PREFIX filetype: <http://publications.europa.eu/resource/authority/file-type/>

        SELECT DISTINCT ?sr ?title ?subLabel ?url
        WHERE {{
          # Match titles/labels in German
          {{ ?res jolux:title ?title . }} UNION {{ ?res skos:prefLabel ?title . }}
          FILTER(lang(?title) = "de")
          
          # The resource could be an Expression realizing a Work, or a Work itself
          {{
            ?res jolux:realizes ?work .
          }} UNION {{
            # Some metadata might be directly on the Work in some datasets
            BIND(?res AS ?work)
            ?work a jolux:ConsolidationAbstract .
          }}
          
          # Logic to get the SR number and Subdivision label
          {{
            # Scenario 1: Result is the Law itself
            ?work a jolux:ConsolidationAbstract .
            BIND("-" AS ?subLabel)
            ?work jolux:classifiedByTaxonomyEntry ?node .
          }} UNION {{
            # Scenario 2: Result is a Subdivision (Article/Section)
            ?work jolux:subdivisionIsPartOfResource ?law .
            ?law jolux:classifiedByTaxonomyEntry ?node .
            OPTIONAL {{ ?work jolux:subdivisionIdentification ?subLabel }}
          }}
          
          ?node skos:notation ?sr .
          FILTER({regex_filters})
          
          # Optional: Get direct URL if embodied as HTML
          OPTIONAL {{
              ?res jolux:isEmbodiedBy ?manifestation .
              ?manifestation jolux:format filetype:HTML .
              ?manifestation jolux:linkToContent ?url .
          }}
        }}
        ORDER BY ?sr ?subLabel
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
                
                # If no direct URL, construct a likely one
                if not res_url:
                    res_url = f"https://www.fedlex.admin.ch/eli/cc/{sr_val}/de"
                    
                results.append({
                    "sr": sr_val,
                    "title": b.get("title", {}).get("value"),
                    "sub_label": sub_val if sub_val != "-" else None,
                    "url": res_url
                })
            return results
            
        except Exception as e:
            # Fallback for unexpected SPARQL issues
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
