import httpx
import json

endpoint = "https://fedlex.data.admin.ch/sparqlendpoint"

query = """
PREFIX jolux: <http://data.legilux.public.lu/resource/ontology/jolux#>
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
PREFIX language: <http://publications.europa.eu/resource/authority/language/>

SELECT DISTINCT ?abbr ?sr
WHERE {
  ?work a jolux:ConsolidationAbstract .
  ?work jolux:classifiedByTaxonomyEntry ?node .
  ?node skos:notation ?sr .
  ?work jolux:isRealizedBy ?expr .
  ?expr jolux:language language:DEU .
  ?expr jolux:titleShort ?abbr .
}
LIMIT 2000
"""

try:
    print("Building abbreviation mapping...")
    params = {"query": query, "format": "json"}
    response = httpx.get(endpoint, params=params, headers={"Accept": "application/sparql-results+json"})
    
    if response.status_code == 200:
        data = response.json()
        bindings = data.get("results", {}).get("bindings", [])
        mapping = {}
        for b in bindings:
            abbr = b['abbr']['value'].strip()
            sr = b['sr']['value']
            mapping[abbr.upper()] = sr
            
            if abbr.upper() in ["OR", "ZGB", "BV"]:
                print(f"DEBUG: Found {abbr} -> {sr}")
        
        with open("abbreviation_mapping.json", "w", encoding="utf-8") as f:
            json.dump(mapping, f, indent=2)
        print(f"Mapped {len(mapping)} abbreviations to abbreviation_mapping.json")
    else:
        print("Error:", response.status_code, response.text[:500])

except Exception as e:
    print(f"Exception: {e}")
