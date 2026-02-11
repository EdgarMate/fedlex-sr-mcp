import httpx

endpoint = "https://fedlex.data.admin.ch/sparqlendpoint"

query = """
PREFIX jolux: <http://data.legilux.public.lu/resource/ontology/jolux#>

SELECT DISTINCT ?sub ?p ?o
WHERE {
  ?sub jolux:legalResourceSubdivisionIsPartOf <https://fedlex.data.admin.ch/eli/cc/24/233_245_233> .
  ?sub ?p ?o .
  FILTER(isLiteral(?o))
}
LIMIT 20
"""

try:
    print("Finding all subdivision literals for ZGB (SR 210)...")
    params = {"query": query, "format": "json"}
    response = httpx.get(endpoint, params=params, headers={"Accept": "application/sparql-results+json"}, timeout=30.0)
    
    if response.status_code == 200:
        bindings = response.json().get("results", {}).get("bindings", [])
        print(f"Found {len(bindings)} triples:")
        for b in bindings:
            p = b['p']['value']
            o = b['o']['value']
            print(f"- {p} -> {o}")
    else:
        print(f"Error: {response.status_code}")
except Exception as e:
    print(f"Exception: {e}")
