from fastmcp import FastMCP
from fedlex_client import FedlexClient

# Initialize FastMCP server
mcp = FastMCP("Fedlex SR Systematic Law")

# Initialize Fedlex client
client = FedlexClient()

@mcp.tool()
def fetch_legislation(sr_number: str) -> str:
    """
    Fetch Swiss legislation details (Title and URL) by its Systematic Law (SR) number.
    
    Args:
        sr_number: The Systematic Law number (e.g., '210' for Civil Code, '101' for Federal Constitution).
    """
    result = client.fetch_article_by_sr(sr_number)
    
    if not result:
        return f"No legislation found for SR number: {sr_number}"
    
    title = result.get("title", "Unknown Title")
    url = result.get("url", "No URL available")
    
    return f"**Title:** {title}\n**URL:** {url}\n**SR Number:** {sr_number}"

if __name__ == "__main__":
    mcp.run()
