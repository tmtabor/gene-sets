#!/usr/bin/env python3
"""
Export MSigDB gene sets from XML files to YAML files.
Creates one YAML file per gene set in outputs/human-xml/ and outputs/mouse-xml/ directories.

This is an XML-based alternative to export_gene_sets.py which uses SQLite databases.
"""

import yaml
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List, Optional, Any
import time
from collections import defaultdict
import argparse
import re
import tempfile
import shutil

# Try to use lxml for better error handling with malformed XML
try:
    from lxml import etree as lxml_etree
    HAS_LXML = True
except ImportError:
    HAS_LXML = False


def sanitize_xml_content(content: str) -> str:
    """Remove invalid XML characters from content."""
    # XML 1.0 valid characters: #x9 | #xA | #xD | [#x20-#xD7FF] | [#xE000-#xFFFD] | [#x10000-#x10FFFF]
    # Remove control characters except tab, newline, carriage return
    def valid_xml_char(char):
        codepoint = ord(char)
        return (
            codepoint == 0x9 or
            codepoint == 0xA or
            codepoint == 0xD or
            (0x20 <= codepoint <= 0xD7FF) or
            (0xE000 <= codepoint <= 0xFFFD) or
            (0x10000 <= codepoint <= 0x10FFFF)
        )

    return ''.join(char for char in content if valid_xml_char(char))


def create_sanitized_xml_copy(xml_path: Path) -> Path:
    """Create a sanitized copy of the XML file if needed.

    Handles:
    - Invalid UTF-8 sequences
    - Invalid XML control characters
    - Unescaped <, >, and & characters inside GENESET attribute values
    - Unescaped quotes inside GENESET attribute values
    """
    print(f"  Checking XML file for invalid characters...")

    # Read the file in binary mode first to handle any encoding issues
    with open(xml_path, 'rb') as f:
        raw_content = f.read()

    # Decode with errors='replace' to handle any invalid UTF-8 sequences
    content = raw_content.decode('utf-8', errors='replace')

    # Count replacement characters that were added
    replacement_count = content.count('\ufffd')
    if replacement_count > 0:
        print(f"  Found {replacement_count} invalid UTF-8 sequences (replaced)")

    # Sanitize the content to remove any remaining invalid XML characters
    sanitized = sanitize_xml_content(content)

    removed_count = len(content) - len(sanitized)

    # Process GENESET elements specifically to escape special characters in attribute values
    # We use a regex-based approach to find GENESET elements and process their attributes

    result = []
    i = 0
    n = len(sanitized)
    escape_count = 0

    while i < n:
        # Look for GENESET element start
        if sanitized[i:i+8] == '<GENESET':
            # Found a GENESET element, copy the tag name
            result.append('<GENESET')
            i += 8

            # Process attributes until we hit /> or >
            while i < n:
                char = sanitized[i]

                # Check for end of element
                if sanitized[i:i+2] == '/>':
                    result.append('/>')
                    i += 2
                    break
                elif char == '>':
                    result.append('>')
                    i += 1
                    break

                # Check for attribute start (ATTR_NAME=")
                if char == '=' and i + 1 < n and sanitized[i + 1] == '"':
                    # Look back to verify we have an attribute name
                    j = len(result) - 1
                    while j >= 0 and (result[j].isalnum() or result[j] == '_'):
                        j -= 1

                    if j < len(result) - 1:  # Found attribute name
                        result.append('=')
                        result.append('"')
                        i += 2

                        # Process attribute value until closing quote
                        # The closing quote is followed by space+UPPERCASE or /> or >
                        while i < n:
                            c = sanitized[i]

                            if c == '"':
                                # Check if this is the real end of attribute
                                remaining = sanitized[i+1:i+25] if i+1 < n else ""

                                is_end = (
                                    not remaining or
                                    (remaining[0] == ' ' and len(remaining) > 1 and remaining[1].isupper()) or
                                    (remaining[0] == ' ' and len(remaining) > 1 and remaining[1] == '/') or
                                    remaining.startswith('/>') or
                                    remaining.startswith('>')
                                )

                                if is_end:
                                    result.append('"')
                                    i += 1
                                    break
                                else:
                                    # Embedded quote, escape it
                                    result.append('&quot;')
                                    escape_count += 1
                                    i += 1
                                    continue

                            # Handle ampersand - check if already escaped
                            if c == '&':
                                remaining = sanitized[i:i+10]
                                if (remaining.startswith('&lt;') or remaining.startswith('&gt;') or
                                    remaining.startswith('&amp;') or remaining.startswith('&quot;') or
                                    remaining.startswith('&apos;') or re.match(r'&#\d+;', remaining) or
                                    re.match(r'&#x[0-9a-fA-F]+;', remaining)):
                                    # Already escaped entity, copy as-is
                                    while i < n and sanitized[i] != ';':
                                        result.append(sanitized[i])
                                        i += 1
                                    if i < n:
                                        result.append(';')
                                        i += 1
                                    continue
                                else:
                                    # Unescaped &, escape it
                                    result.append('&amp;')
                                    escape_count += 1
                                    i += 1
                                    continue
                            elif c == '<':
                                result.append('&lt;')
                                escape_count += 1
                                i += 1
                                continue
                            elif c == '>':
                                result.append('&gt;')
                                escape_count += 1
                                i += 1
                                continue
                            else:
                                result.append(c)
                                i += 1
                    else:
                        result.append(char)
                        i += 1
                else:
                    result.append(char)
                    i += 1
        else:
            result.append(sanitized[i])
            i += 1

    sanitized = ''.join(result)

    if escape_count > 0:
        print(f"  Escaped {escape_count} special characters in attribute values")

    if removed_count > 0 or replacement_count > 0 or escape_count > 0:
        if removed_count > 0:
            print(f"  Found and removed {removed_count} invalid XML characters")
        # Always create a sanitized file when any changes were made
        temp_dir = Path(tempfile.gettempdir())
        sanitized_path = temp_dir / f"sanitized_{xml_path.name}"
        with open(sanitized_path, 'w', encoding='utf-8') as f:
            f.write(sanitized)
        print(f"  Created sanitized copy at: {sanitized_path}")
        return sanitized_path
    else:
        print(f"  No invalid characters found")
        return xml_path


# Mapping of collection codes to full names
COLLECTION_FULL_NAMES = {
    'C1': 'Positional gene sets',
    'C2': 'Curated gene sets',
    'C3': 'Regulatory target gene sets',
    'C4': 'Computational gene sets',
    'C5': 'Ontology gene sets',
    'C6': 'Oncogenic signature gene sets',
    'C7': 'Immunologic signature gene sets',
    'C8': 'Cell type signature gene sets',
    'H': 'Hallmark gene sets',
    'M1': 'Positional gene sets (mouse)',
    'M2': 'Curated gene sets (mouse)',
    'M3': 'Regulatory target gene sets (mouse)',
    'M5': 'Ontology gene sets (mouse)',
    'M8': 'Cell type signature gene sets (mouse)',
    'MH': 'Hallmark gene sets (mouse)',
}

# Mapping of sub-category codes to full names (for collection.full_name)
SUB_CATEGORY_FULL_NAMES = {
    'CGP': 'CGP',
    'CP': 'CP',
    'CP:BIOCARTA': 'BioCarta',
    'CP:KEGG': 'KEGG',
    'CP:PID': 'PID',
    'CP:REACTOME': 'Reactome',
    'CP:WIKIPATHWAYS': 'WikiPathways',
    'MIR:MIR_LEGACY': 'MIR_Legacy',
    'MIR:MIRDB': 'MIRDB',
    'TFT:GTRD': 'GTRD',
    'TFT:TFT_LEGACY': 'TFT_Legacy',
    'CGN': 'CGN',
    'CM': 'CM',
    'GO:BP': 'GO_BP',
    'GO:CC': 'GO_CC',
    'GO:MF': 'GO_MF',
    'HPO': 'HPO',
    'VAX': 'VAX',
}

# Mapping of platform/chip names to IDs (based on SQLite database namespace table)
PLATFORM_IDS = {
    'Human_Ensembl_Gene_ID': 4,
    'Mouse_Ensembl_Gene_ID': 5,
    'Human_NCBI_Gene_ID': 7,
    'Mouse_NCBI_Gene_ID': 8,
    'HUMAN_GENE_SYMBOL': 10,
    'MOUSE_GENE_SYMBOL': 11,
    'AFFY_HG_U133': 13,
    'AFFY_HG_U95': 14,
    'AFFY_HuGene': 15,
    'AFFY_MG_U74': 16,
    'AFFY_Mouse430': 17,
    'AFFY_MoGene': 18,
    'AFFY_Mu11K': 19,
    'AFFY_Rat230': 20,
    'AFFY_RG_U34': 21,
    'AFFY_RaGene': 22,
    'Human_AGILENT_Array': 23,
    'Mouse_AGILENT_Array': 24,
    'Human_ILLUMINA_Array': 26,
    'Mouse_ILLUMINA_Array': 27,
    'Operon_V1.1': 28,
    'HUMAN_SEQ_ACCESSION': 29,
    'MOUSE_SEQ_ACCESSION': 30,
    'Human_RefSeq': 32,
    'Mouse_RefSeq': 33,
    'Human_Image_Clone_ID': 35,
    'Mouse_Image_Clone_ID': 36,
    'Human_UniProt_ID': 38,
    'Mouse_UniProt_ID': 39,
    'UniGene_ID': 41,
    'Human_Gene_Namespace': 42,
    'Mouse_Gene_Namespace': 43,
    'AFFY_HTA_2.0': 44,
}

# Gene sets that the MSigDB website excludes from "related gene sets from same publication" lists
EXCLUDED_FROM_RELATED_GENE_SETS = set()


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description='Export MSigDB gene sets from XML files to YAML files.',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    # Species selection
    parser.add_argument('--human', action='store_true',
                        help='Generate only human gene sets')
    parser.add_argument('--mouse', action='store_true',
                        help='Generate only mouse gene sets')

    # Limit number of files
    parser.add_argument('--limit', type=int,
                        help='Limit the number of gene sets to export')

    # Resume functionality
    parser.add_argument('--resume', action='store_true',
                        help='Skip generating YAML files that already exist')

    # Path overrides
    parser.add_argument('--output', type=str,
                        help='Path to the output directory (default: outputs/)')
    parser.add_argument('--input', type=str,
                        help='Path to the inputs directory (default: inputs/)')
    parser.add_argument('--hs-xml', type=str,
                        help='Path to the human XML file')
    parser.add_argument('--mm-xml', type=str,
                        help='Path to the mouse XML file')
    parser.add_argument('--hs-history-xml', type=str,
                        help='Path to the human XML history file')
    parser.add_argument('--mm-history-xml', type=str,
                        help='Path to the mouse XML history file')

    return parser.parse_args()


def load_version_history(xml_file: Path) -> Dict[str, List[Dict[str, str]]]:
    """Load version history from XML file into a dictionary keyed by gene set name."""
    version_history = {}

    try:
        tree = ET.parse(xml_file)
        root = tree.getroot()

        for geneset in root.findall('.//GENESET'):
            standard_name = geneset.get('STANDARD_NAME')
            if standard_name:
                versions = []
                for version in geneset.findall('VERSION'):
                    versions.append({
                        'version': version.get('NUM', ''),
                        'change': version.get('CHANGE', '')
                    })
                if versions:
                    version_history[standard_name] = versions
    except Exception as e:
        print(f"Warning: Could not load version history: {e}")

    return version_history


def parse_members_mapping(mapping_str: str) -> List[Dict[str, Any]]:
    """Parse the MEMBERS_MAPPING attribute into a list of member dictionaries.

    Matches SQLite export format where:
    - gene_symbol is populated (kept even if same as source_id)
    - ncbi_gene_id is a string (to match SQLite format)
    """
    members = []
    if not mapping_str:
        return members

    for entry in mapping_str.split('|'):
        parts = entry.split(',')
        if len(parts) >= 3:
            source_id = parts[0]
            gene_symbol = parts[1]
            ncbi_gene_id = parts[2] if parts[2].isdigit() else None

            member = {
                'source_id': source_id,
                'gene_symbol': gene_symbol,  # Keep gene_symbol even if same as source_id
                'ncbi_gene_id': ncbi_gene_id  # Keep as string to match SQLite format
            }
            members.append(member)
        elif len(parts) == 2:
            member = {
                'source_id': parts[0],
                'gene_symbol': parts[1],
                'ncbi_gene_id': None
            }
            members.append(member)
        elif len(parts) == 1 and parts[0]:
            member = {
                'source_id': parts[0],
                'gene_symbol': None,
                'ncbi_gene_id': None
            }
            members.append(member)

    return members


def parse_datasets(dataset_str: str) -> List[Dict[str, str]]:
    """Parse dataset string (e.g., refinement or validation datasets)."""
    if not dataset_str:
        return []

    datasets = []
    for item in dataset_str.split(';'):
        item = item.strip()
        if ':' in item:
            dataset_id, description = item.split(':', 1)
            datasets.append({
                'dataset_id': dataset_id.strip(),
                'description': description.strip()
            })
        elif item:
            datasets.append({
                'dataset_id': item,
                'description': ''
            })
    return datasets


class XMLDataCache:
    """Cache for computing related gene sets from XML data."""

    def __init__(self):
        self.gene_sets_by_pmid = defaultdict(list)
        self.gene_sets_by_author = defaultdict(list)
        self.all_gene_sets = {}  # name -> {pmid, authors}

    def add_gene_set(self, name: str, pmid: str, authors: str):
        """Add a gene set to the cache for later relationship computation."""
        self.all_gene_sets[name] = {'pmid': pmid, 'authors': authors}

        if pmid:
            self.gene_sets_by_pmid[pmid].append(name)

        if authors:
            # Parse authors (they appear to be comma-separated or similar)
            for author in authors.split(','):
                author = author.strip()
                if author:
                    self.gene_sets_by_author[author].append(name)

    def get_related_by_publication(self, name: str) -> List[str]:
        """Get gene sets from same publication (excluding current gene set)."""
        info = self.all_gene_sets.get(name)
        if not info or not info['pmid']:
            return []

        related = [gs for gs in self.gene_sets_by_pmid[info['pmid']]
                   if gs != name and gs not in EXCLUDED_FROM_RELATED_GENE_SETS]
        return sorted(related)

    def get_related_by_authors(self, name: str) -> List[str]:
        """Get gene sets from same authors (excluding those from same publication)."""
        info = self.all_gene_sets.get(name)
        if not info or not info['authors']:
            return []

        current_pmid = info['pmid']
        related = set()

        for author in info['authors'].split(','):
            author = author.strip()
            if author:
                for gs_name in self.gene_sets_by_author[author]:
                    gs_info = self.all_gene_sets.get(gs_name)
                    # Exclude current gene set and those from same publication
                    if gs_name != name and gs_info and gs_info['pmid'] != current_pmid:
                        related.add(gs_name)

        return sorted(list(related))


def export_gene_set_to_yaml(geneset_elem: ET.Element, output_dir: Path,
                            version_history: Dict[str, List[Dict[str, str]]],
                            cache: XMLDataCache, resume: bool = False) -> Optional[str]:
    """Export a single gene set to a YAML file."""

    standard_name = geneset_elem.get('STANDARD_NAME', '')
    if not standard_name:
        return None

    # Check if file already exists when in resume mode
    output_file = output_dir / f"{standard_name}.yaml"
    if resume and output_file.exists():
        return None  # Skip this file

    # Extract attributes
    collection_code = geneset_elem.get('CATEGORY_CODE', '')
    sub_category = geneset_elem.get('SUB_CATEGORY_CODE', '')

    # Build collection name in SQLite format: CODE:SUB_CATEGORY (e.g., C3:MIR:MIR_LEGACY)
    if sub_category:
        collection_name = f"{collection_code}:{sub_category}"
        collection_full_name = SUB_CATEGORY_FULL_NAMES.get(sub_category, sub_category)
    else:
        collection_name = collection_code
        collection_full_name = COLLECTION_FULL_NAMES.get(collection_code)

    # Build the complete gene set data structure (matching SQLite format)
    gene_set_data = {
        'standard_name': standard_name,
        'systematic_name': geneset_elem.get('SYSTEMATIC_NAME', '') or None,
        'brief_description': geneset_elem.get('DESCRIPTION_BRIEF', '') or None,
        'full_description': geneset_elem.get('DESCRIPTION_FULL', '') or None,
        'collection': {
            'name': collection_name,
            'full_name': collection_full_name,
        },
        'source_species': geneset_elem.get('ORGANISM', '') or None,
        'contributed_by': geneset_elem.get('CONTRIBUTOR', '') or None,
        'contributor_organization': geneset_elem.get('CONTRIBUTOR_ORG', '') or None,
        'exact_source': geneset_elem.get('EXACT_SOURCE', '') or None,
        'license': 'CC-BY-4.0',
        'tags': geneset_elem.get('TAGS', '').split(',') if geneset_elem.get('TAGS') else [],
    }

    # Remove None values from collection
    gene_set_data['collection'] = {k: v for k, v in gene_set_data['collection'].items() if v is not None}

    # Add source platform if available (matching SQLite format with id and name)
    chip = geneset_elem.get('CHIP', '')
    if chip:
        platform_id = PLATFORM_IDS.get(chip)
        if platform_id:
            gene_set_data['source_platform'] = {
                'id': platform_id,
                'name': chip
            }
        else:
            gene_set_data['source_platform'] = {
                'name': chip
            }

    # Add external links
    external_links = []
    external_url = geneset_elem.get('EXTERNAL_DETAILS_URL', '')
    if external_url:
        external_links.append(external_url)
    listing_url = geneset_elem.get('GENESET_LISTING_URL', '')
    if listing_url:
        external_links.append(listing_url)
    if external_links:
        gene_set_data['external_links'] = external_links

    # Add publication information (limited - XML only has PMID and AUTHORS)
    pmid = geneset_elem.get('PMID', '')
    authors_str = geneset_elem.get('AUTHORS', '')
    if pmid or authors_str:
        pub_info = {}
        if pmid:
            pub_info['pmid'] = pmid
        if authors_str:
            pub_info['authors'] = [a.strip() for a in authors_str.split(',') if a.strip()]
        gene_set_data['source_publication'] = pub_info

    # Add related gene sets
    related = {}
    pub_related = cache.get_related_by_publication(standard_name)
    if pub_related:
        related['from_same_publication'] = pub_related

    author_related = cache.get_related_by_authors(standard_name)
    if author_related:
        related['from_same_authors'] = author_related

    if related:
        gene_set_data['related_gene_sets'] = related

    # Add filtered by similarity gene sets
    filtered = geneset_elem.get('FILTERED_BY_SIMILARITY', '')
    if filtered:
        gene_set_data['filtered_by_similarity'] = [f.strip() for f in filtered.split(',') if f.strip()]

    # Add dataset references
    datasets = []
    geo_id = geneset_elem.get('GEOID', '')
    if geo_id:
        datasets.append({
            'type': 'GEO',
            'id': geo_id
        })

    # Add hallmark datasets
    refinement_str = geneset_elem.get('REFINEMENT_DATASETS', '')
    for dataset in parse_datasets(refinement_str):
        datasets.append({
            'type': 'Hallmark Refinement',
            'id': dataset['dataset_id'],
            'description': dataset['description']
        })

    validation_str = geneset_elem.get('VALIDATION_DATASETS', '')
    for dataset in parse_datasets(validation_str):
        datasets.append({
            'type': 'Hallmark Validation',
            'id': dataset['dataset_id'],
            'description': dataset['description']
        })

    if datasets:
        gene_set_data['dataset_references'] = datasets

    # Add hallmark-specific information
    founder_names = geneset_elem.get('FOUNDER_NAMES', '')
    if founder_names:
        gene_set_data['hallmark_info'] = {
            'founder_gene_sets': [f.strip() for f in founder_names.split(',') if f.strip()]
        }

    # Add version history
    if standard_name in version_history:
        gene_set_data['version_history'] = version_history[standard_name]

    # Add gene members
    members_mapping = geneset_elem.get('MEMBERS_MAPPING', '')
    members = parse_members_mapping(members_mapping)

    gene_set_data['members'] = members
    gene_set_data['num_members'] = len(members)

    # Count mapped vs unmapped genes
    mapped_count = sum(1 for m in members if m['gene_symbol'] is not None)
    gene_set_data['num_genes_mapped'] = mapped_count

    # Clean up None values at top level, but keep full_description and tags even if null/empty
    # to match SQLite format exactly
    keys_to_always_keep = {'full_description', 'tags'}
    gene_set_data = {k: v for k, v in gene_set_data.items()
                     if k in keys_to_always_keep or (v is not None and v != [] and v != {})}

    # Write to YAML file
    with open(output_file, 'w') as f:
        yaml.dump(gene_set_data, f, default_flow_style=False, sort_keys=False, allow_unicode=True)

    return standard_name


def process_species(species_code: str, xml_path: str, history_xml_file: Path,
                    output_dir: Path, resume: bool = False, limit: Optional[int] = None):
    """Process gene sets for a single species from XML file."""

    print(f"\n{'='*60}")
    print(f"Processing {species_code.upper()} gene sets from XML")
    print(f"{'='*60}")

    overall_start = time.time()

    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Loading XML file: {xml_path}")

    # Sanitize the XML file to handle invalid characters
    sanitized_xml_path = create_sanitized_xml_copy(Path(xml_path))
    use_sanitized = str(sanitized_xml_path) != xml_path

    # Load version history from history XML file
    print(f"Loading version history from: {history_xml_file}")
    xml_start = time.time()
    version_history = load_version_history(history_xml_file)
    print(f"  Loaded version history for {len(version_history)} gene sets in {time.time() - xml_start:.2f}s")

    # First pass: build the cache for related gene sets
    print("  Building relationship cache...")
    cache_start = time.time()
    cache = XMLDataCache()

    context = ET.iterparse(str(sanitized_xml_path), events=('end',))
    gene_set_count = 0

    for event, elem in context:
        if elem.tag == 'GENESET':
            name = elem.get('STANDARD_NAME', '')
            pmid = elem.get('PMID', '')
            authors = elem.get('AUTHORS', '')
            cache.add_gene_set(name, pmid, authors)
            gene_set_count += 1
            elem.clear()

    print(f"  Cached {gene_set_count} gene sets in {time.time() - cache_start:.2f}s")

    # Second pass: export gene sets
    print("\nExporting gene sets...")
    export_start = time.time()
    exported_count = 0
    skipped_count = 0

    context = ET.iterparse(str(sanitized_xml_path), events=('end',))

    for event, elem in context:
        if elem.tag == 'GENESET':
            # Stop if we've reached the limit
            if limit and exported_count >= limit:
                elem.clear()
                break

            try:
                name = export_gene_set_to_yaml(elem, output_dir, version_history, cache, resume=resume)
                if name:
                    exported_count += 1
                    if exported_count % 500 == 0:
                        elapsed = time.time() - export_start
                        rate = exported_count / elapsed
                        remaining = (gene_set_count - exported_count - skipped_count) / rate if rate > 0 else 0
                        print(f"  Exported {exported_count}/{gene_set_count} gene sets... "
                              f"({rate:.1f}/sec, ~{remaining:.0f}s remaining)")
                elif resume:
                    skipped_count += 1
            except Exception as e:
                print(f"  Error exporting gene set {elem.get('STANDARD_NAME', 'unknown')}: {e}")

            elem.clear()

    # Clean up temporary file if we created one
    if use_sanitized and sanitized_xml_path.exists():
        sanitized_xml_path.unlink()

    total_time = time.time() - overall_start
    export_time = time.time() - export_start

    print(f"\n{species_code.upper()} Export complete!")
    print(f"  Total gene sets exported: {exported_count}")
    if resume and skipped_count > 0:
        print(f"  Skipped (already exist): {skipped_count}")
    if exported_count > 0:
        print(f"  Export time: {export_time:.2f}s ({exported_count/export_time:.1f} gene sets/sec)")
    else:
        print(f"  Export time: {export_time:.2f}s")
    print(f"  Total time: {total_time:.2f}s")
    print(f"  Output directory: {output_dir.absolute()}")

    return exported_count


def main():
    """Main function to export all gene sets for both human and mouse."""

    total_start = time.time()

    args = parse_args()

    # Determine directories
    output_dir = Path(args.output) if args.output else Path('outputs/')
    input_dir = Path(args.input) if args.input else Path('inputs/')

    # Calculate limit per species if both are being processed
    human_limit = None
    mouse_limit = None

    if args.limit:
        if args.human and not args.mouse:
            human_limit = args.limit
        elif args.mouse and not args.human:
            mouse_limit = args.limit
        else:
            human_limit = args.limit
            mouse_limit = args.limit

    # Process human gene sets if selected (or if no species specified, process both)
    if args.human or (not args.human and not args.mouse):
        human_count = process_species(
            species_code='human',
            xml_path=args.hs_xml if args.hs_xml else str(input_dir / 'msigdb_v2025.1.Hs.xml'),
            history_xml_file=Path(args.hs_history_xml) if args.hs_history_xml else input_dir / 'msigdb_history_v2025.1.Hs.xml',
            output_dir=output_dir / 'human-xml',
            resume=args.resume,
            limit=human_limit
        )
    else:
        human_count = 0

    # Process mouse gene sets if selected (or if no species specified, process both)
    if args.mouse or (not args.human and not args.mouse):
        mouse_count = process_species(
            species_code='mouse',
            xml_path=args.mm_xml if args.mm_xml else str(input_dir / 'msigdb_v2025.1.Mm.xml'),
            history_xml_file=Path(args.mm_history_xml) if args.mm_history_xml else input_dir / 'msigdb_history_v2025.1.Mm.xml',
            output_dir=output_dir / 'mouse-xml',
            resume=args.resume,
            limit=mouse_limit
        )
    else:
        mouse_count = 0

    total_time = time.time() - total_start

    print(f"\n{'='*60}")
    print(f"ALL EXPORTS COMPLETE!")
    print(f"{'='*60}")
    print(f"  Human gene sets exported: {human_count}")
    print(f"  Mouse gene sets exported: {mouse_count}")
    print(f"  Total gene sets exported: {human_count + mouse_count}")
    if human_count + mouse_count > 0:
        print(f"  Total time: {total_time:.2f}s ({(human_count + mouse_count)/total_time:.1f} gene sets/sec)")
    else:
        print(f"  Total time: {total_time:.2f}s")


if __name__ == '__main__':
    main()
