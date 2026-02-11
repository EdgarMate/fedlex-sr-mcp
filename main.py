from fastmcp import FastMCP
from fedlex_client import FedlexClient

# Initialize FastMCP server
mcp = FastMCP("Fedlex SR Systematic Law")

# Initialize Fedlex client
client = FedlexClient()

@mcp.tool()
def search_law(query: str) -> str:
    """
    Search for Swiss legislation by citation (e.g., 'OR 41', 'ZGB 1, Abs. 1', 'Art. 52 lit. c', 'BV') or SR number (e.g., '210').
    
    Args:
        query: The law citation or SR number. Examples: 'OR 41, Abs. 2', 'Art. 52 Abs. 1 lit. c', 'ZGB 1', 'BV', '101', '210'.
    """
    result = client.fetch_law_by_citation(query)
    
    if not result:
        return f"No law or article found for query: {query}"
    
    title = result.get("title", "Unknown Title")
    url = result.get("url", "No URL available")
    sr = result.get("sr", "N/A")
    article = result.get("article")
    paragraph = result.get("paragraph")
    literal = result.get("literal")
    
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

if __name__ == "__main__":
    mcp.run()
