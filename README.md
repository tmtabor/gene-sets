# gene-sets

A toolkit for exporting MSigDB gene sets and generating static HTML pages for each gene set.

## Overview

This project provides two main tools:

1. **`export_gene_sets.py`** - Exports gene sets from MSigDB SQLite databases to YAML files
2. **`generate_geneset_pages.py`** - Generates static HTML pages from YAML gene set files

## Requirements

- Python 3.9 or higher
- PyYAML 6.0+

Install dependencies:
```bash
pip install -r requirements.txt
```

## Quick Start

### 1. Export Gene Sets from Database

Export all gene sets to YAML files:
```bash
python3 export_gene_sets.py
```

Export only the first 100 gene sets:
```bash
python3 export_gene_sets.py --limit 100
```

Export only human gene sets:
```bash
python3 export_gene_sets.py --human
```

### 2. Generate HTML Pages

Generate HTML pages for all gene sets:
```bash
python3 generate_geneset_pages.py
```

Generate pages for only the first 1000 gene sets:
```bash
python3 generate_geneset_pages.py --limit 1000
```

Generate only mouse gene set pages:
```bash
python3 generate_geneset_pages.py --mouse
```

## Project Structure

```
gene-sets/
├── export_gene_sets.py          # Export gene sets from SQLite to YAML
├── generate_geneset_pages.py    # Generate HTML pages from YAML files
├── requirements.txt              # Python dependencies
├── inputs/                       # Input databases and XML files
│   ├── msigdb_FULL_v2025.1.Hs.db.sqlite
│   ├── msigdb_FULL_v2025.1.Mm.db.sqlite
│   ├── msigdb_history_v2025.1.Hs.xml
│   └── msigdb_history_v2025.1.Mm.xml
├── outputs/                      # Generated YAML files
│   ├── human/                    # Human gene sets (YAML)
│   └── mouse/                    # Mouse gene sets (YAML)
└── msigdb/                       # Generated HTML pages
    ├── human/geneset/            # Human gene set pages
    └── mouse/geneset/            # Mouse gene set pages
```

## export_gene_sets.py

Exports MSigDB gene sets from SQLite databases to structured YAML files.

### Usage

```bash
python3 export_gene_sets.py [OPTIONS]
```

### Options

#### Species Selection
- `--human` - Export only human gene sets
- `--mouse` - Export only mouse gene sets
- (default: exports both species)

#### Processing Control
- `--limit N` - Limit the number of gene sets to export
- `--resume` - Skip generating YAML files that already exist

#### Path Configuration
- `--output PATH` - Custom output directory (default: `outputs/`)
- `--input PATH` - Custom input directory (default: `inputs/`)
- `--hs-db PATH` - Path to human database file
- `--mm-db PATH` - Path to mouse database file
- `--hs-xml PATH` - Path to human XML history file
- `--mm-xml PATH` - Path to mouse XML history file

### Examples

Export only human gene sets:
```bash
python3 export_gene_sets.py --human
```

Export the first 500 gene sets total:
```bash
python3 export_gene_sets.py --limit 500
```

Resume a previous export (skip existing files):
```bash
python3 export_gene_sets.py --resume
```

Export to a custom directory:
```bash
python3 export_gene_sets.py --output /path/to/output
```

Export only mouse gene sets, limited to 1000:
```bash
python3 export_gene_sets.py --mouse --limit 1000
```

### Output Format

Each gene set is exported as a YAML file containing:
- Standard and systematic names
- Brief and full descriptions
- Collection information
- Source publication and authors
- Related gene sets
- Gene members with symbols and NCBI IDs
- Version history
- Dataset references
- External links

Example YAML structure:
```yaml
standard_name: ABBUD_LIF_SIGNALING_1_DN
systematic_name: MM623
brief_description: Genes down-regulated in AtT20 cells...
collection:
  name: M2:CGP
  full_name: Chemical and Genetic Perturbations
source_species: Mus musculus
members:
  - source_id: AA657044
    gene_symbol: Ahnak
    ncbi_gene_id: 66395
  # ... more members
```

## generate_geneset_pages.py

Generates static HTML pages from YAML gene set files.

### Usage

```bash
python3 generate_geneset_pages.py [OPTIONS]
```

### Options

#### Species Selection
- `--human` - Generate only human gene set pages
- `--mouse` - Generate only mouse gene set pages
- (default: generates both species)

#### Processing Control
- `--limit N` - Limit the number of HTML pages to generate
- `--resume` - Skip generating files that already exist

#### Path Configuration
- `--output PATH` - Custom output directory (default: `msigdb/`)

### Examples

Generate only human gene set pages:
```bash
python3 generate_geneset_pages.py --human
```

Generate the first 100 pages:
```bash
python3 generate_geneset_pages.py --limit 100
```

Resume page generation (skip existing files):
```bash
python3 generate_geneset_pages.py --resume
```

Generate to a custom directory:
```bash
python3 generate_geneset_pages.py --output /var/www/html
```

Generate 500 mouse pages, resuming from where you left off:
```bash
python3 generate_geneset_pages.py --mouse --limit 500 --resume
```

### Output

HTML pages are generated in the following structure:
- Human pages: `msigdb/human/geneset/{GENE_SET_NAME}.html`
- Mouse pages: `msigdb/mouse/geneset/{GENE_SET_NAME}.html`
