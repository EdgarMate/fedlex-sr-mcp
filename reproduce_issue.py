from fedlex_client import FedlexClient
import json

client = FedlexClient()

def test_search(query):
    print(f"\n--- Testing Search: '{query}' ---")
    results = client.search_fedlex_topics(query)
    print(f"Found {len(results)} results:")
    for r in results:
        print(f"- {r['sr']}: {r['title']} ({r.get('sub_label', 'No Sublabel')})")
        print(f"  URL: {r['url']}")

def test_citation(citation):
    print(f"\n--- Testing Citation: '{citation}' ---")
    res = client.fetch_law_by_citation(citation)
    print(json.dumps(res, indent=2))

if __name__ == "__main__":
    test_search("Stockwerkeigentum")
    test_citation("ZGB 712a")
    test_search("Stockwerk")
