# Fedlex SR MCP Server

A powerful Model Context Protocol (MCP) server for searching and deep-linking Swiss Federal Law (Classified Compilation - SR/RS) using the official Fedlex SPARQL endpoint.

## Features

- **SR Number Search**: Find any Swiss law by its Systematic Law number (e.g., `210`, `101`, `0.312.11`).
- **Comprehensive Abbreviation Support**: Search using over 1,600 official law abbreviations (e.g., `OR`, `ZGB`, `BV`, `StGB`, `SchKG`).
- **Deep Linking (Subdivisions)**: Automatically generates direct links to specific subdivisions using URL fragments:
  - **Articles**: `OR 41` -> `#art_41`
  - **Paragraphs (Absatz)**: `OR 41 Abs. 2` -> `#art_41/para_2`
  - **Letters (Litera)**: `Art. 52 Abs. 1 lit. c` -> `#art_52/para_1/lbl_c`
  - **Numbers (Ziffer)**: `Art. 1 Ziff. 1` -> `#art_1/lbl_1`
- **Full Text Retrieval**: Automatically fetches the **authoritative article wording** from the official Fedlex mirror (GitHub), bypassing portal restrictions.
- **Flexible Syntax**: Recognizes various labels like `Art.`, `Abs.`, `Absatz`, `lit.`, `Buchstabe`, `Ziff.`, and `Ziffer` regardless of whether they are provided.

## Installation

### Prerequisites
- Python 3.10+
- `pip`

### Dependencies
Install the required packages:
pip install httpx fastmcp beautifulsoup4
```

## Setup

1. **Clone the repository**:
   ```bash
   git clone https://github.com/EdgarMate/fedlex-sr-mcp.git
   cd fedlex-sr-mcp
   ```

2. **Generate/Refresh Mapping** (Optional):
   The repository comes with a pre-generated `abbreviation_mapping.json`. To refresh it from the Fedlex SPARQL endpoint:
   ```bash
   python build_mapping.py
   ```

## Usage

### Running the Server
You can run the server using `fastmcp`:

```bash
fastmcp dev main.py
```

### Tool: `search_law`
The server exposes a single tool `search_law` that accepts a `query` string.

**Example Queries:**
- `OR 41, Abs. 2`
- `Art. 52 Abs. 1 lit. c`
- `ZGB 1`
- `Bundesverfassung` (via abbreviation `BV`)
- `210` (SR number for ZGB)

## Technical Architecture

- **SPARQL Endpoint**: Queries `https://fedlex.data.admin.ch/sparqlendpoint` to resolve SR numbers and abbreviations to `ConsolidationAbstract` and `Expression` URIs.
- **FastMCP**: Implements the Model Context Protocol for seamless integration with AI assistants.
- **Deep Linking Strategy**: Uses ELI-compatible URL fragments (`#art_N`, `/para_N`, `/lbl_X`) to provide direct content access.

## Data Source
Data provided by the Swiss Federal Chancellery via [Fedlex](https://fedlex.data.admin.ch/).

## Created with Antigravity

This project was built with **Antigravity**, an agentic AI coding assistant by Google DeepMind.

## Contribution and Feedback

Contributions are welcome! If you have ideas for improvements, new features, or find any issues, please feel free to:
- Open an issue or pull request.
- Reach out with suggestions or feedback.
- Use and adapt this project for your own needs.

Your input is highly valued as we continue to improve tools for accessing Swiss legislation!

## License
MIT
