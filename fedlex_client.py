import httpx
import urllib.parse
import asyncio

class FedlexClient:
    def __init__(self):
        self.endpoint = "https://fedlex.data.admin.ch/sparqlendpoint"
        self.client = httpx.Client(timeout=30.0, follow_redirects=True)

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
          # 1. Find the taxonomy node for the SR number (casting to string is crucial)
          ?node skos:notation ?notation .
          FILTER (str(?notation) = "{sr_number}") .
          
          # 2. Find the abstract work classified by this node
          # Use OPTIONAL in case the link is via a different property, but classifiedByTaxonomyEntry is standard for CC
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
                 url = f"{work_uri}" # The abstract URI usually redirects or is the base for /de

            return {
                "title": title or "Unknown Title",
                "url": url,
                "sr": sr_number
            }
            
        except Exception as e:
            print(f"Error fetching SR {sr_number}: {e}")
            return None

if __name__ == "__main__":
    client = FedlexClient()
    print("Fetching SR 210 (ZGB)...")
    res = client.fetch_article_by_sr("210")
    print(res)
    
    print("-" * 20)
    print("Fetching SR 0.312.11...")
    res = client.fetch_article_by_sr("0.312.11")
    print(res)
