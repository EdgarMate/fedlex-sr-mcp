from fastmcp import FastMCP
from fedlex_client import FedlexClient

# Initialize FastMCP server
mcp = FastMCP("Fedlex SR Systematic Law")

# Initialize Fedlex client
client = FedlexClient()

@mcp.tool()
def search_law(query: str) -> str:
    """
    Authoritative search for Swiss Federal Law (SR/RS). 
    Use for specific articles (e.g., 'OR 41', 'ZGB 1, Abs. 1') OR broad topics (e.g., 'Verein Stimmrecht'). 
    Try this tool before any web search.
    
    Args:
        query: Specific citation (e.g. 'OR 41') or topic (e.g. 'Urheberrecht').
    """
    # Try specific citation fetch first
    result = client.fetch_law_by_citation(query)
    
    if result:
        title = result.get("title", "Unknown Title")
        url = result.get("url", "No URL available")
        sr = result.get("sr", "N/A")
        article = result.get("article")
        paragraph = result.get("paragraph")
        literal = result.get("literal")
        
        # If it's a specific article, try to fetch authoritative text/title metadata
        if article:
            article_details = client.fetch_article_text(sr, article)
            if article_details:
                return (
                    f"### {article_details['title']}\n"
                    f"**Gesetz:** {title} ({sr})\n"
                    f"**Link:** {article_details['link']}\n"
                    f"**Details:** {article_details['text']}\n\n"
                    f"*Quelle: {article_details['source']}*"
                )
        
        response = f"**{title}**\n"
        if article:
            text = f"Article {article}"
            if paragraph:
                text += f", Paragraph {paragraph}"
            if literal:
                text += f", Litera/Ziffer {literal}"
            response += f"Specific Location: {text}\n"
        response += f"SR Number: {sr}\n"
        response += f"Link: {url}"
        return response

    # Fallback to topical search
    topic_results = client.search_fedlex_topics(query)
    if topic_results:
        response = f"No specific citation found for '{query}'. Found {len(topic_results)} relevant laws/articles:\n\n"
        for i, res in enumerate(topic_results, 1):
            loc = f" ({res['sub_label']})" if res.get('sub_label') else ""
            response += f"{i}. **{res['title']}**{loc} (SR {res['sr']})\n   Link: {res['url']}\n"
        return response
    
    return f"No legislation or topics found matching query: {query}"

if __name__ == "__main__":
    mcp.run()
