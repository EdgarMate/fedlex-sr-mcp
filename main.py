from fastmcp import FastMCP
from fedlex_client import FedlexClient

# Initialize FastMCP server
mcp = FastMCP("Fedlex SR Systematic Law")

# Initialize Fedlex client
client = FedlexClient()

@mcp.tool()
def search_law(query: str) -> str:
    """
    Search for Swiss Federal Law (SR/RS) by keyword or citation.
    Supports:
    - Keywords: 'Stockwerkeigentum', 'OR 41', 'MWST'
    - Multi-language codes: 'CC 210', 'CO 1', 'CP 311.0', 'LP 281.1'
    - Detailed citations: 'Art. 41 OR', 'Art 1 ZGB'
    """
    client = FedlexClient()
    
    # 1. Try citation lookup (exact match for codes or SR)
    citation_res = client.fetch_law_by_citation(query)
    
    if citation_res:
        sr = citation_res.get("sr")
        article = citation_res.get("article")
        
        # If it's a specific article, get authoritative metadata
        if article:
            article_details = client.fetch_article_text(sr, article)
            if article_details:
                return (
                    f"### {article_details['title']}\n"
                    f"**SR Number:** {sr}\n"
                    f"**Authoritative Link:** {article_details['link']}\n\n"
                    f"> [!NOTE]\n"
                    f"> {article_details['text']}\n"
                    f"---\n"
                    f"Source: {article_details['source']}"
                )
        
        # General law result
        return (
            f"### {citation_res['title']}\n"
            f"**SR Number:** {sr}\n"
            f"**Link:** {citation_res['url']}\n\n"
            f"> [!TIP]\n"
            f"> Specify an article number (e.g. 'ZGB 712a' or 'CO 1') for specific article metadata."
        )
        
    # 2. Topical search (keyword search)
    topic_results = client.search_fedlex_topics(query)
    if topic_results:
        response = f"### Legal Results for '{query}'\n"
        response += f"Found {len(topic_results)} relevant laws:\n\n"
        for i, res in enumerate(topic_results, 1):
            response += f"{i}. **{res['title']}** (SR {res['sr']})\n"
            response += f"   - [Offizieller Link]({res['url']})\n"
        
        response += "\n> [!TIP]\n"
        response += "> Use specific abbreviations like 'ZGB', 'OR', 'CC', 'CO' for faster lookups."
        return response
    
    return f"No legislation found matching: '{query}'. Try the SR number (e.g. '210') or a broader keyword."

if __name__ == "__main__":
    mcp.run()
