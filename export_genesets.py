#!/usr/bin/env python3
"""
Export MSigDB gene sets from SQLite database to YAML files.
Creates one YAML file per gene set in outputs/human/ and outputs/mouse/ directories.
"""

import sqlite3
import yaml
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List, Optional, Any
import time
from collections import defaultdict
import argparse


# Gene sets that the MSigDB website excludes from "related gene sets from same publication" lists
# These are specific M3:GTRD mouse gene sets that appear to be filtered out on the website
EXCLUDED_FROM_RELATED_GENE_SETS = {
    # 'AEBP2_TARGET_GENES',
    # 'ARID1A_TARGET_GENES',
    # 'BRWD1_TARGET_GENES',
    # 'CARM1_TARGET_GENES',
    # 'HOXA13_TARGET_GENES',
    # 'IRF7_TARGET_GENES',
    # 'NFIL3_TARGET_GENES',
    # 'POU3F1_TARGET_GENES',
    # 'USP7_TARGET_GENES',
    # 'ZFP992_TARGET_GENES',
}


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description='Export MSigDB gene sets from SQLite database to YAML files.',
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
    parser.add_argument('--hs-db', type=str,
                        help='Path to the human database file')
    parser.add_argument('--mm-db', type=str,
                        help='Path to the mouse database file')
    parser.add_argument('--hs-xml', type=str,
                        help='Path to the human XML history file')
    parser.add_argument('--mm-xml', type=str,
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


class DataCache:
    """Cache for frequently accessed database lookups."""

    def __init__(self, cursor):
        self.cursor = cursor
        self.species_cache = {}
        self.collection_cache = {}
        self.namespace_cache = {}
        self.publication_cache = {}
        self.external_links_cache = {}
        self.filtered_similarity_cache = {}
        self.hallmark_cache = {}
        self.gene_sets_by_publication = defaultdict(list)
        self.gene_sets_by_author = defaultdict(list)

    def preload_all(self):
        """Preload all cacheable data."""
        print("  Preloading reference data...")
        start = time.time()

        self._preload_species()
        self._preload_collections()
        self._preload_namespaces()
        self._preload_publications()
        self._preload_external_links()
        self._preload_filtered_similarity()
        self._preload_hallmarks()
        self._preload_publication_relationships()
        self._preload_author_relationships()

        print(f"  Preloading complete in {time.time() - start:.2f}s")

    def _preload_species(self):
        """Load all species into cache."""
        self.cursor.execute("SELECT species_code, species_name FROM species")
        for row in self.cursor.fetchall():
            self.species_cache[row[0]] = row[1]

    def _preload_collections(self):
        """Load all collections into cache."""
        self.cursor.execute("SELECT collection_name, full_name FROM collection")
        for row in self.cursor.fetchall():
            self.collection_cache[row[0]] = row[1]

    def _preload_namespaces(self):
        """Load all namespaces into cache."""
        self.cursor.execute("SELECT id, label FROM namespace")
        for row in self.cursor.fetchall():
            self.namespace_cache[row[0]] = row[1]

    def _preload_publications(self):
        """Load all publications with authors."""
        # Load publication info
        self.cursor.execute("""
            SELECT id, PMID, title, DOI, URL
            FROM publication
        """)
        for row in self.cursor.fetchall():
            pub_id = row[0]
            self.publication_cache[pub_id] = {
                'pmid': row[1],
                'title': row[2],
                'doi': row[3],
                'url': row[4],
                'authors': []
            }

        # Load authors for each publication
        self.cursor.execute("""
            SELECT pa.publication_id, a.display_name
            FROM publication_author pa
            JOIN author a ON pa.author_id = a.id
            ORDER BY pa.publication_id, pa.author_order
        """)
        for row in self.cursor.fetchall():
            pub_id = row[0]
            if pub_id in self.publication_cache:
                self.publication_cache[pub_id]['authors'].append(row[1])

    def _preload_external_links(self):
        """Load all external links."""
        self.cursor.execute("SELECT term, external_name FROM external_term")
        for row in self.cursor.fetchall():
            term = row[0]
            if term not in self.external_links_cache:
                self.external_links_cache[term] = []
            if row[1]:
                self.external_links_cache[term].append(row[1])

    def _preload_filtered_similarity(self):
        """Load all filtered similarity relationships."""
        self.cursor.execute("""
            SELECT gene_set_id, term
            FROM external_term_filtered_by_similarity
            ORDER BY gene_set_id, term
        """)
        for row in self.cursor.fetchall():
            gene_set_id = row[0]
            if gene_set_id not in self.filtered_similarity_cache:
                self.filtered_similarity_cache[gene_set_id] = []
            self.filtered_similarity_cache[gene_set_id].append(row[1])

    def _preload_hallmarks(self):
        """Load all hallmark information."""
        self.cursor.execute("""
            SELECT gene_set_id, founder_names, validation_datasets, refinement_datasets
            FROM hallmark
        """)
        for row in self.cursor.fetchall():
            gene_set_id = row[0]
            founder_names = row[1].split(',') if row[1] else []

            def parse_datasets(dataset_str):
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
                return datasets

            self.hallmark_cache[gene_set_id] = {
                'founder_gene_sets': founder_names,
                'validation_datasets': parse_datasets(row[2]),
                'refinement_datasets': parse_datasets(row[3])
            }

    def _preload_publication_relationships(self):
        """Preload gene sets grouped by publication."""
        self.cursor.execute("""
            SELECT gsd.publication_id, gs.id, gs.standard_name
            FROM gene_set gs
            JOIN gene_set_details gsd ON gs.id = gsd.gene_set_id
            WHERE gsd.publication_id IS NOT NULL
            ORDER BY gsd.publication_id, gs.standard_name
        """)
        for row in self.cursor.fetchall():
            pub_id = row[0]
            self.gene_sets_by_publication[pub_id].append({
                'id': row[1],
                'name': row[2]
            })

    def _preload_author_relationships(self):
        """Preload gene sets grouped by author."""
        self.cursor.execute("""
            SELECT pa.author_id, gs.id, gs.standard_name, gsd.publication_id
            FROM gene_set gs
            JOIN gene_set_details gsd ON gs.id = gsd.gene_set_id
            JOIN publication_author pa ON gsd.publication_id = pa.publication_id
            WHERE gsd.publication_id IS NOT NULL
            ORDER BY pa.author_id, gs.standard_name
        """)
        for row in self.cursor.fetchall():
            author_id = row[0]
            self.gene_sets_by_author[author_id].append({
                'id': row[1],
                'name': row[2],
                'pub_id': row[3]
            })

    def get_species(self, species_code: str) -> Optional[str]:
        """Get species name from cache."""
        return self.species_cache.get(species_code)

    def get_collection_name(self, collection_code: str) -> Optional[str]:
        """Get collection full name from cache."""
        return self.collection_cache.get(collection_code)

    def get_namespace_label(self, namespace_id: int) -> Optional[str]:
        """Get namespace label from cache."""
        return self.namespace_cache.get(namespace_id)

    def get_publication(self, publication_id: int) -> Optional[Dict[str, Any]]:
        """Get publication info from cache."""
        return self.publication_cache.get(publication_id)

    def get_external_links(self, gene_set_name: str) -> List[str]:
        """Get external links from cache."""
        return self.external_links_cache.get(gene_set_name, [])

    def get_filtered_similarity(self, gene_set_id: int) -> List[str]:
        """Get filtered similarity gene sets from cache."""
        return self.filtered_similarity_cache.get(gene_set_id, [])

    def get_hallmark_info(self, gene_set_id: int) -> Optional[Dict[str, Any]]:
        """Get hallmark info from cache."""
        return self.hallmark_cache.get(gene_set_id)

    def get_related_by_publication(self, gene_set_id: int, publication_id: int) -> List[str]:
        """Get gene sets from same publication (excluding current gene set)."""
        if not publication_id or publication_id not in self.gene_sets_by_publication:
            return []
        return [gs['name'] for gs in self.gene_sets_by_publication[publication_id]
                if gs['id'] != gene_set_id and gs['name'] not in EXCLUDED_FROM_RELATED_GENE_SETS]

    def get_related_by_authors(self, gene_set_id: int, publication_id: int) -> List[str]:
        """Get gene sets from same authors (excluding those from same publication)."""
        if not publication_id or publication_id not in self.publication_cache:
            return []

        # Get author IDs for this publication
        author_ids = []
        self.cursor.execute("""
            SELECT author_id FROM publication_author WHERE publication_id = ?
        """, (publication_id,))
        author_ids = [row[0] for row in self.cursor.fetchall()]

        if not author_ids:
            return []

        # Collect all gene sets by these authors
        related = set()
        for author_id in author_ids:
            if author_id in self.gene_sets_by_author:
                for gs in self.gene_sets_by_author[author_id]:
                    # Exclude current gene set and those from same publication
                    if gs['id'] != gene_set_id and gs['pub_id'] != publication_id:
                        related.add(gs['name'])

        return sorted(list(related))


def get_gene_set_basic_info(cursor, gene_set_id: int, cache: DataCache) -> Dict[str, Any]:
    """Get basic gene set information."""
    cursor.execute("""
        SELECT gs.standard_name, gs.collection_name, gs.tags, gs.license_code,
               gsd.systematic_name, gsd.description_brief, gsd.description_full,
               gsd.exact_source, gsd.external_details_URL, gsd.contributor,
               gsd.contrib_organization, gsd.source_species_code,
               gsd.publication_id, gsd.GEO_id, gsd.primary_namespace_id
        FROM gene_set gs
        LEFT JOIN gene_set_details gsd ON gs.id = gsd.gene_set_id
        WHERE gs.id = ?
    """, (gene_set_id,))

    row = cursor.fetchone()
    if not row:
        return {}

    collection_name = row[1]
    namespace_id = row[14]

    return {
        'standard_name': row[0],
        'collection_name': collection_name,
        'collection_full_name': cache.get_collection_name(collection_name) if collection_name else None,
        'tags': row[2],
        'license_code': row[3],
        'systematic_name': row[4],
        'description_brief': row[5],
        'description_full': row[6],
        'exact_source': row[7],
        'external_details_url': row[8],
        'contributor': row[9],
        'contributor_organization': row[10],
        'source_species_code': row[11],
        'source_species': cache.get_species(row[11]) if row[11] else None,
        'publication_id': row[12],
        'geo_id': row[13],
        'namespace_id': namespace_id,
        'namespace_label': cache.get_namespace_label(namespace_id) if namespace_id else None,
    }


def get_gene_members(cursor, gene_set_id: int) -> List[Dict[str, Any]]:
    """Get all gene members with source IDs, symbols, and descriptions."""
    try:
        cursor.execute("""
            SELECT sm.source_id, 
                   gs.symbol, 
                   gs.NCBI_id
            FROM gene_set_source_member gssm
            JOIN source_member sm ON gssm.source_member_id = sm.id
            LEFT JOIN gene_symbol gs ON sm.gene_symbol_id = gs.id
            WHERE gssm.gene_set_id = ?
            ORDER BY sm.source_id
        """, (gene_set_id,))

        members = []
        for row in cursor.fetchall():
            member = {
                'source_id': row[0],
                'gene_symbol': row[1],
                'ncbi_gene_id': row[2]
            }
            members.append(member)

        return members
    except Exception as e:
        print(f"    Warning: Could not get gene members: {e}")
        return []


def export_gene_set_to_yaml(cursor, gene_set_id: int, output_dir: Path,
                            version_history: Dict[str, List[Dict[str, str]]],
                            cache: DataCache, resume: bool = False) -> Optional[str]:
    """Export a single gene set to a YAML file."""

    # Get basic information (now includes cached lookups)
    info = get_gene_set_basic_info(cursor, gene_set_id, cache)
    if not info:
        return None

    standard_name = info['standard_name']

    # Check if file already exists when in resume mode
    output_file = output_dir / f"{standard_name}.yaml"
    if resume and output_file.exists():
        return None  # Skip this file

    # Build the complete gene set data structure
    gene_set_data = {
        'standard_name': standard_name,
        'systematic_name': info['systematic_name'],
        'brief_description': info['description_brief'],
        'full_description': info['description_full'],
        'collection': {
            'name': info['collection_name'],
            'full_name': info['collection_full_name']
        },
        'source_species': info['source_species'],
        'contributed_by': info['contributor'],
        'contributor_organization': info['contributor_organization'],
        'exact_source': info['exact_source'],
        'license': info['license_code'],
        'tags': info['tags'].split(',') if info['tags'] else []
    }

    # Add source platform if available
    if info['namespace_id']:
        gene_set_data['source_platform'] = {
            'id': info['namespace_id'],
            'name': info['namespace_label']
        }

    # Add external links (from cache + details URL)
    external_links = []
    if info['external_details_url']:
        external_links.append(info['external_details_url'])
    external_links.extend(cache.get_external_links(standard_name))
    if external_links:
        gene_set_data['external_links'] = external_links

    # Add publication information (from cache)
    pub_info = cache.get_publication(info['publication_id'])
    if pub_info:
        gene_set_data['source_publication'] = pub_info

    # Add related gene sets (from cache)
    related = {}
    pub_related = cache.get_related_by_publication(gene_set_id, info['publication_id'])
    if pub_related:
        related['from_same_publication'] = pub_related

    author_related = cache.get_related_by_authors(gene_set_id, info['publication_id'])
    if author_related:
        related['from_same_authors'] = author_related

    if related:
        gene_set_data['related_gene_sets'] = related

    # Add filtered by similarity gene sets (from cache)
    filtered = cache.get_filtered_similarity(gene_set_id)
    if filtered:
        gene_set_data['filtered_by_similarity'] = filtered

    # Add dataset references
    datasets = []
    if info['geo_id']:
        datasets.append({
            'type': 'GEO',
            'id': info['geo_id']
        })

    # Add hallmark datasets if applicable (from cache, only fetch once)
    hallmark_info = cache.get_hallmark_info(gene_set_id)
    if hallmark_info:
        for dataset in hallmark_info.get('refinement_datasets', []):
            datasets.append({
                'type': 'Hallmark Refinement',
                'id': dataset['dataset_id'],
                'description': dataset['description']
            })
        for dataset in hallmark_info.get('validation_datasets', []):
            datasets.append({
                'type': 'Hallmark Validation',
                'id': dataset['dataset_id'],
                'description': dataset['description']
            })

    if datasets:
        gene_set_data['dataset_references'] = datasets

    # Add hallmark-specific information if applicable
    if hallmark_info and hallmark_info['founder_gene_sets']:
        gene_set_data['hallmark_info'] = {
            'founder_gene_sets': hallmark_info['founder_gene_sets']
        }

    # Add version history
    if standard_name in version_history:
        gene_set_data['version_history'] = version_history[standard_name]

    # Add gene members
    members = get_gene_members(cursor, gene_set_id)
    gene_set_data['members'] = members
    gene_set_data['num_members'] = len(members)

    # Count mapped vs unmapped genes
    mapped_count = sum(1 for m in members if m['gene_symbol'] is not None)
    gene_set_data['num_genes_mapped'] = mapped_count

    # Write to YAML file
    with open(output_file, 'w') as f:
        yaml.dump(gene_set_data, f, default_flow_style=False, sort_keys=False, allow_unicode=True)

    return standard_name


def process_species(species_code: str, db_path: str, xml_history_file: Path, output_dir: Path, resume: bool = False, limit: Optional[int] = None):
    """Process gene sets for a single species."""

    print(f"\n{'='*60}")
    print(f"Processing {species_code.upper()} gene sets")
    print(f"{'='*60}")

    overall_start = time.time()

    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Connecting to database: {db_path}")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Get all gene set IDs, excluding those with THRESHOLD_EXCLUDED archive policy
    cursor.execute("""
        SELECT id FROM gene_set 
        WHERE id NOT IN (
            SELECT gene_set_id FROM gene_set_archive_policy 
            WHERE policy_code = 'THRESHOLD_EXCLUDED'
        )
        ORDER BY id
    """)
    gene_set_ids = [row[0] for row in cursor.fetchall()]

    print(f"Found {len(gene_set_ids)} gene sets to export")

    # Also report how many were excluded
    cursor.execute("""
        SELECT COUNT(*) FROM gene_set_archive_policy 
        WHERE policy_code = 'THRESHOLD_EXCLUDED'
    """)
    excluded_count = cursor.fetchone()[0]
    if excluded_count > 0:
        print(f"  Excluded {excluded_count} gene sets with THRESHOLD_EXCLUDED archive policy")

    if limit:
        print(f"  Limiting to {limit} gene sets")
    if resume:
        print("  Resume mode: skipping existing files")

    # Load version history from XML file
    print(f"Loading version history from: {xml_history_file}")
    xml_start = time.time()
    version_history = load_version_history(xml_history_file)
    print(f"  Loaded version history for {len(version_history)} gene sets in {time.time() - xml_start:.2f}s")

    # Preload all cacheable data
    cache = DataCache(cursor)
    cache.preload_all()

    # Export each gene set
    print("\nExporting gene sets...")
    export_start = time.time()
    exported_count = 0
    skipped_count = 0
    for i, gene_set_id in enumerate(gene_set_ids, 1):
        # Stop if we've reached the limit
        if limit and exported_count >= limit:
            break

        try:
            name = export_gene_set_to_yaml(cursor, gene_set_id, output_dir, version_history, cache, resume=resume)
            if name:
                exported_count += 1
                if exported_count % 500 == 0:
                    elapsed = time.time() - export_start
                    rate = exported_count / elapsed
                    remaining = (len(gene_set_ids) - exported_count - skipped_count) / rate if rate > 0 else 0
                    print(f"  Exported {exported_count}/{len(gene_set_ids)} gene sets... "
                          f"({rate:.1f}/sec, ~{remaining:.0f}s remaining)")
            elif resume:
                skipped_count += 1
        except Exception as e:
            print(f"  Error exporting gene set {gene_set_id}: {e}")
            continue

    conn.close()

    total_time = time.time() - overall_start
    export_time = time.time() - export_start

    print(f"\n{species_code.upper()} Export complete!")
    print(f"  Total gene sets exported: {exported_count}")
    if resume and skipped_count > 0:
        print(f"  Skipped (already exist): {skipped_count}")
    print(f"  Export time: {export_time:.2f}s ({exported_count/export_time:.1f} gene sets/sec)" if exported_count > 0 else "  Export time: {export_time:.2f}s")
    print(f"  Total time: {total_time:.2f}s")
    print(f"  Output directory: {output_dir.absolute()}")

    return exported_count


def main():
    """Main function to export all gene sets for both human and mouse."""

    total_start = time.time()

    args = parse_args()

    # Determine output directory
    output_dir = Path(args.output) if args.output else Path('outputs/')
    input_dir = Path(args.input) if args.input else Path('inputs/')

    # Calculate limit per species if both are being processed
    human_limit = None
    mouse_limit = None

    if args.limit:
        # If only processing one species, give it the full limit
        if args.human and not args.mouse:
            human_limit = args.limit
        elif args.mouse and not args.human:
            mouse_limit = args.limit
        else:
            # If processing both, split the limit
            human_limit = args.limit
            mouse_limit = max(0, args.limit)  # Mouse gets remaining after human

    # Process human gene sets if selected (or if no species specified, process both)
    if args.human or (not args.human and not args.mouse):
        human_count = process_species(
            species_code='human',
            db_path=args.hs_db if args.hs_db else str(input_dir / 'msigdb_FULL_v2025.1.Hs.db'),
            xml_history_file=Path(args.hs_xml) if args.hs_xml else input_dir / 'msigdb_history_v2025.1.Hs.xml',
            output_dir=output_dir / 'human',
            resume=args.resume,
            limit=human_limit
        )

        # Adjust mouse limit if processing both species
        if args.limit and mouse_limit is not None and not args.human:
            mouse_limit = max(0, args.limit - human_count)
    else:
        human_count = 0

    # Process mouse gene sets if selected (or if no species specified, process both)
    if args.mouse or (not args.human and not args.mouse):
        mouse_count = process_species(
            species_code='mouse',
            db_path=args.mm_db if args.mm_db else str(input_dir / 'msigdb_FULL_v2025.1.Mm.db'),
            xml_history_file=Path(args.mm_xml) if args.mm_xml else input_dir / 'msigdb_history_v2025.1.Mm.xml',
            output_dir=output_dir / 'mouse',
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
