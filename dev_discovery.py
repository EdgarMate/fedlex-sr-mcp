import httpx

endpoint = "https://fedlex.data.admin.ch/sparqlendpoint"

query = """
PREFIX jolux: <http://data.legilux.public.lu/resource/ontology/jolux#>
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
PREFIX language: <http://publications.europa.eu/resource/authority/language/>

SELECT DISTINCT ?url ?format
WHERE {
  ?node skos:notation "210" .
  ?law jolux:classifiedByTaxonomyEntry ?node .
  
  ?sub jolux:subdivisionIsPartOfResource ?law .
  ?sub jolux:subdivisionIdentification "Art. 1" .
  
  ?sub jolux:isRealizedBy ?expr .
  ?expr jolux:language language:DEU .
  
  # Check for linked documents on the expression or manifestations
  { ?expr jolux:isEmbodiedBy ?manifestation . ?manifestation jolux:linkToContent ?url . ?manifestation jolux:format ?format . }
  UNION
  { ?expr jolux:isEmbodiedBy ?manifestation . ?manifestation jolux:isEmbodiedBy ?file . ?file jolux:linkToContent ?url . }
}
LIMIT 10
"""

try:
    print("Searching for Manifestation URLs for ZGB Art. 1...")
    params = {"query": query, "format": "json"}
    response = httpx.get(endpoint, params=params, headers={"Accept": "application/sparql-results+json"}, timeout=30.0)
    
    if response.status_code == 200:
        bindings = response.json().get("results", {}).get("bindings", [])
        print(f"Found {len(bindings)} manifestations:")
        for b in bindings:
            print(f"- URL: {b['url']['value']}")
            if 'format' in b:
                print(f"  Format: {b['format']['value']}")
    else:
        print(f"Error: {response.status_code}")
except Exception as e:
    print(f"Exception: {e}")
