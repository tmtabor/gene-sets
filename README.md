# gene-sets

A toolkit for exporting MSigDB gene sets and generating static HTML pages for each gene set.

## Overview

This project provides three main tools for working with MSigDB gene sets:

1. **`export_genesets.py`** - Exports gene sets from MSigDB SQLite databases to YAML files
2. **`export_genesets_xml.py`** - Exports gene sets from MSigDB XML files to YAML files (alternative to SQLite-based export)
3. **`generate_pages.py`** - Generates static HTML pages from YAML gene set files

The typical workflow is:
1. Export gene sets from either SQLite databases or XML files to YAML format
2. Generate HTML pages from the YAML files for web presentation

## Installation

### Requirements

- Python 3.9 or higher
- PyYAML 6.0+
- Jinja2 3.0+
- lxml 4.6+ (optional, for better XML error handling)

### Install Dependencies

```bash
pip install -r requirements.txt
```

## export_genesets.py

Exports MSigDB gene sets from SQLite databases to structured YAML files. This is the primary export method for working with MSigDB database files.

### Description

This script reads gene set data from MSigDB SQLite database files and version history from XML files, then exports each gene set as a separate YAML file. The YAML files include comprehensive metadata such as gene members, descriptions, source publications, related gene sets, and version history.

### Usage

```bash
python export_genesets.py [OPTIONS]
```

### Command-Line Options

#### Species Selection

- **`--human`** - Export only human gene sets (from Hs database)
- **`--mouse`** - Export only mouse gene sets (from Mm database)
- If neither flag is specified, both human and mouse gene sets are exported

#### Processing Control

- **`--limit N`** - Limit the total number of gene sets to export across all species
  - Example: `--limit 100` exports up to 100 gene sets total
- **`--resume`** - Skip generating YAML files that already exist on disk
  - Useful for resuming interrupted exports or updating only new gene sets

#### Path Configuration

- **`--output PATH`** - Custom output directory for YAML files
  - Default: `outputs/`
  - YAML files are created in `{output}/human/` and `{output}/mouse/` subdirectories
- **`--input PATH`** - Custom input directory for database and XML files
  - Default: `inputs/`
- **`--hs-db PATH`** - Override path to human database file
  - Default: `inputs/msigdb_FULL_v2025.1.Hs.db`
- **`--mm-db PATH`** - Override path to mouse database file
  - Default: `inputs/msigdb_FULL_v2025.1.Mm.db`
- **`--hs-xml PATH`** - Override path to human XML history file
  - Default: `inputs/msigdb_history_v2025.1.Hs.xml`
- **`--mm-xml PATH`** - Override path to mouse XML history file
  - Default: `inputs/msigdb_history_v2025.1.Mm.xml`

### Examples

Export all gene sets (human and mouse):
```bash
python export_genesets.py
```

Export only human gene sets:
```bash
python export_genesets.py --human
```

Export only mouse gene sets:
```bash
python export_genesets.py --mouse
```

Export the first 500 gene sets:
```bash
python export_genesets.py --limit 500
```

Resume a previous export (skip existing files):
```bash
python export_genesets.py --resume
```

Export to a custom directory:
```bash
python export_genesets.py --output /path/to/output
```

Export with custom database paths:
```bash
python export_genesets.py --hs-db /path/to/human.db --mm-db /path/to/mouse.db
```

Export only 1000 mouse gene sets, resuming from where you left off:
```bash
python export_genesets.py --mouse --limit 1000 --resume
```

### Output Format

Each gene set is exported as a YAML file in `outputs/{species}/{GENE_SET_NAME}.yaml` containing:
- Standard and systematic names
- Brief and full descriptions
- Collection information
- Source species and publication details
- Authors and contributor information
- Related gene sets (from same publication and from same authors)
- Gene members with symbols and NCBI IDs
- Version history
- Dataset references
- External links (PubMed, etc.)

## export_genesets_xml.py

Exports MSigDB gene sets from XML files to structured YAML files. This is an alternative to `export_genesets.py` that works directly with XML source files instead of SQLite databases.

### Description

This script parses MSigDB XML files and exports each gene set as a separate YAML file. It includes advanced XML sanitization to handle malformed XML content, including invalid UTF-8 sequences and control characters. The script can process both the main gene set XML files and version history XML files.

### Usage

```bash
python export_genesets_xml.py [OPTIONS]
```

### Command-Line Options

#### Species Selection

- **`--human`** - Export only human gene sets (from Hs XML)
- **`--mouse`** - Export only mouse gene sets (from Mm XML)
- If neither flag is specified, both human and mouse gene sets are exported

#### Processing Control

- **`--limit N`** - Limit the total number of gene sets to export across all species
  - Example: `--limit 100` exports up to 100 gene sets total
- **`--resume`** - Skip generating YAML files that already exist on disk
  - Useful for resuming interrupted exports or updating only new gene sets

#### Path Configuration

- **`--output PATH`** - Custom output directory for YAML files
  - Default: `outputs/`
  - YAML files are created in `{output}/human-xml/` and `{output}/mouse-xml/` subdirectories
- **`--input PATH`** - Custom input directory for XML files
  - Default: `inputs/`
- **`--hs-xml PATH`** - Override path to human gene set XML file
  - Default: `inputs/msigdb_v2025.1.Hs.xml`
- **`--mm-xml PATH`** - Override path to mouse gene set XML file
  - Default: `inputs/msigdb_v2025.1.Mm.xml`
- **`--hs-history-xml PATH`** - Override path to human XML history file
  - Default: `inputs/msigdb_history_v2025.1.Hs.xml`
- **`--mm-history-xml PATH`** - Override path to mouse XML history file
  - Default: `inputs/msigdb_history_v2025.1.Mm.xml`

### Examples

Export all gene sets (human and mouse):
```bash
python export_genesets_xml.py
```

Export only human gene sets:
```bash
python export_genesets_xml.py --human
```

Export only mouse gene sets:
```bash
python export_genesets_xml.py --mouse
```

Export the first 500 gene sets:
```bash
python export_genesets_xml.py --limit 500
```

Resume a previous export (skip existing files):
```bash
python export_genesets_xml.py --resume
```

Export to a custom directory:
```bash
python export_genesets_xml.py --output /path/to/output
```

Export with custom XML paths:
```bash
python export_genesets_xml.py --hs-xml /path/to/human.xml --mm-xml /path/to/mouse.xml
```

Export only 1000 mouse gene sets with custom paths:
```bash
python export_genesets_xml.py --mouse --limit 1000 --mm-xml /path/to/mouse.xml
```

### Output Format

Each gene set is exported as a YAML file in `outputs/{species}-xml/{GENE_SET_NAME}.yaml` with the same structure as `export_genesets.py`:
- Standard and systematic names
- Brief and full descriptions
- Collection information
- Source species and publication details
- Authors and contributor information
- Related gene sets
- Gene members with symbols and NCBI IDs
- Version history
- Dataset references
- External links

### XML Sanitization

The script includes robust XML sanitization that:
- Handles invalid UTF-8 sequences
- Removes invalid XML control characters
- Processes malformed attribute values
- Creates sanitized temporary files when necessary
- Provides detailed error reporting

## generate_pages.py

Generates static HTML pages from YAML gene set files. Creates a complete website with individual pages for each gene set and collection index pages.

### Description

This script reads YAML gene set files (generated by either `export_genesets.py` or `export_genesets_xml.py`) and creates static HTML pages using Jinja2 templates. Each gene set gets its own HTML page with complete metadata, gene lists, related gene sets, and version history. Index pages are also generated to browse gene sets by collection.

**Note:** Index pages and links between gene sets use relative paths, so they work correctly regardless of where the files are deployed (subdirectory, different domain, etc.).

### Usage

```bash
python generate_pages.py [OPTIONS]
```

### Command-Line Options

#### Species Selection

- **`--human`** - Generate only human gene set pages
- **`--mouse`** - Generate only mouse gene set pages
- If neither flag is specified, both human and mouse pages are generated

#### Processing Control

- **`--limit N`** - Limit the total number of HTML pages to generate across all species
  - Example: `--limit 100` generates up to 100 pages total
- **`--resume`** - Skip generating HTML files that already exist on disk
  - Useful for resuming interrupted generation or updating only new pages
- **`--geneset NAME`** - Generate a specific gene set by name
  - Example: `--geneset ZNF320_TARGET_GENES`
  - Useful for testing or regenerating a single page
- **`--index`** - Generate index pages
  - When included, the overall index and all collection index pages are generated
  - When omitted, only individual gene set pages are generated (no indices)
  - Example: `--index` to generate all index pages

#### Path Configuration

- **`--input PATH`** - Custom input directory containing YAML files
  - Default: `outputs/`
  - The script expects subdirectories `{input}/human/` and `{input}/mouse/`
  - Example: `--input outputs/2025.1/`
- **`--output PATH`** - Custom output directory for HTML files
  - Default: `msigdb/`
  - HTML files are created in `{output}/human/geneset/` and `{output}/mouse/geneset/` subdirectories
- **`--link-prefix PREFIX`** - Prefix for external links (JSP pages, compendia, etc.)
  - Default: `` (empty string)
  - Example: `--link-prefix https://www.gsea-msigdb.org/`
  - Note: This only affects external links; internal links between gene sets and index pages always use relative paths
- **`--version TAG`** - Version tag to display on pages
  - Example: `--version v2025.1.Hs`

### Examples

Generate all gene set pages (human and mouse):
```bash
python generate_pages.py
```

Generate from a custom input directory:
```bash
python generate_pages.py --input outputs/2025.1/
```

Generate only human gene set pages:
```bash
python generate_pages.py --human
```

Generate only mouse gene set pages:
```bash
python generate_pages.py --mouse
```

Generate the first 100 pages:
```bash
python generate_pages.py --limit 100
```

Resume page generation (skip existing files):
```bash
python generate_pages.py --resume
```

Generate to a custom directory:
```bash
python generate_pages.py --output /var/www/html
```

Generate pages with link prefix for external resources:
```bash
python generate_pages.py --link-prefix https://www.gsea-msigdb.org/
```

Generate a single specific gene set:
```bash
python generate_pages.py --geneset HALLMARK_APOPTOSIS
```

Generate 500 mouse pages, resuming from where you left off:
```bash
python generate_pages.py --mouse --limit 500 --resume
```

Generate with custom input, output, and version tag:
```bash
python generate_pages.py \
  --input outputs/2025.1/ \
  --output msigdb/2025.1/ \
  --version v2025.1.Hs
```

Generate without index pages (gene set pages only):
```bash
python generate_pages.py --index false
```

### Output Structure

HTML pages are generated in the following structure:
```
{output}/
├── index.html                              # Overall index (relative links)
├── human/
│   ├── collection_C1.html                  # Collection indexes (relative links)
│   ├── collection_C2.html
│   ├── collection_C2_CGP.html
│   ├── collection_C2_CP.html
│   └── geneset/
│       ├── GENE_SET_1.html                # Individual gene set pages
│       ├── GENE_SET_2.html
│       └── ...
└── mouse/
    ├── collection_M1.html
    ├── collection_M2.html
    └── geneset/
        ├── GENE_SET_1.html
        └── ...
```

Each HTML page includes:
- Gene set name and description
- Collection and source information
- Complete gene member list with NCBI links
- Related gene sets (with relative links)
- Version history
- External links
- Formatted metadata tables

**Relative Links:** Links between gene sets and from index pages to gene sets use relative paths. This means the generated HTML files can be deployed to any location (subdirectory, CDN, etc.) and the internal navigation will continue to work correctly.

### Input Requirements

The script expects YAML files to exist in:
- `{input}/human/` for human gene sets (default: `outputs/human/`)
- `{input}/mouse/` for mouse gene sets (default: `outputs/mouse/`)

Run `export_genesets.py` or `export_genesets_xml.py` first to generate these YAML files.
