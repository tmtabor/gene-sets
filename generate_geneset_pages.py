#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generate static HTML pages for gene sets from YAML files
"""

import yaml
import re
from pathlib import Path
import logging
import argparse
from jinja2 import Environment, FileSystemLoader, select_autoescape

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Initialize Jinja2 environment
template_dir = Path(__file__).parent / 'templates'
jinja_env = Environment(
    loader=FileSystemLoader(template_dir),
    autoescape=select_autoescape(['html', 'xml'])
)


def process_gene_links(text):
    """Add links to GeneID references in text"""
    if not text:
        return ''
    pattern = r'\[GeneID=(\d+)\]'
    replacement = r'<a href="http://www.ncbi.nlm.nih.gov/gene/\1">[GeneID=\1]</a>'
    return re.sub(pattern, replacement, text)


def build_related_gene_sets(related_gene_sets, species):
    """Build the related gene sets HTML section"""
    if not related_gene_sets:
        return ''

    html_parts = []

    from_pub = related_gene_sets.get('from_same_publication', [])
    if from_pub:
        count = len(from_pub)
        html_parts.append(f'''      
        
        
          
            <a href="javascript:toggleWithShowHide('relatedByPubMedId', 'showHideByPubMedId')">
              (<span id="showHideByPubMedId">show</span> {count} additional gene {'sets' if count > 1 else 'set'} from the source publication)
            </a>
            <br>
            <div id="relatedByPubMedId" style="display: none;">
              <br>
              ''')
        for geneset_name in from_pub:
            html_parts.append(f'''
                <a href="msigdb/{species}/geneset/{geneset_name}.html">{geneset_name}</a>
              ''')
        html_parts.append('''
            </div>
          ''')

    return ''.join(html_parts) if html_parts else ''


def build_version_history(version_history):
    """Build version history HTML"""
    if not version_history:
        return ''

    history_items = []
    for entry in version_history:
        version = entry.get('version', '')
        change = entry.get('change', '')
        history_items.append(f'''      
        
        {version}: {change}.
        ''')

    return ''.join(history_items)


def build_members_table(members):
    """Build the gene members table"""
    if not members:
        return ''

    rows = []
    for member in members:
        source_id = member.get('source_id', '')
        gene_symbol = member.get('gene_symbol')
        ncbi_gene_id = member.get('ncbi_gene_id')

        if gene_symbol is None or ncbi_gene_id is None:
            rows.append(f'''          
            <tr class="unmapped" title="original member source Id not mapped to a gene">
              <td valign="top">{source_id}</td>
              <td valign="top">&nbsp;</td>
              <td valign="top">&nbsp;</td>
              <td valign="top" width="100%">&nbsp;</td>
            </tr>
''')
        else:
            rows.append(f'''          
            <tr>
              <td valign="top">{source_id}</td>
              <td valign="top"><a target="_blank" href="http://view.ncbi.nlm.nih.gov/gene/{ncbi_gene_id}" title="view NCBI entry for Entrez gene id">{ncbi_gene_id}</a></td>
              <td valign="top"><a target="_blank" href="http://ensembl.org/Homo_sapiens/Gene/Summary?db=core;g={gene_symbol}" title="view Ensembl entry for gene symbol">{gene_symbol}</a></td>
              <td valign="top" width="100%">...</td>
            </tr>
''')

    table_html = f'''        <table border="0" cellpadding="0" cellspacing="0" align="left">
          <tbody><tr>
            <th valign="top" title="original member source identifier">Source<br>Id</th>
            <th valign="top" title="entrez gene id">NCBI&nbsp;(Entrez)<br>Gene&nbsp;Id</th>
            <th valign="top" title="human gene symbol equivalent">Gene<br>Symbol</th>
            <th valign="top" width="100%" title="description of the human gene">Gene<br>Description</th>
          </tr>
{''.join(rows)}        </tbody></table>'''

    return table_html


def build_overlap_links(standard_name, species, species_class):
    """Build compute overlaps section"""
    collections = [
        ('MH', 'Hallmark', []),
        ('M1', 'Positional', []),
        ('M2', 'Curated', [
            ('CGP', 'Chemical and Genetic Perturbations'),
            ('CP', 'Canonical Pathways', [
                ('CP:BIOCARTA', 'BioCarta Pathways'),
                ('CP:REACTOME', 'Reactome Pathways'),
                ('CP:WIKIPATHWAYS', 'WikiPathways'),
            ]),
        ]),
        ('M3', 'Regulatory Target', [
            ('GTRD', 'GTRD'),
            ('MIRDB', 'miRDB'),
        ]),
        ('M5', 'Ontology', [
            ('GO', 'Gene Ontology', [
                ('GO:BP', 'GO Biological Process'),
                ('GO:CC', 'GO Cellular Component'),
                ('GO:MF', 'GO Molecular Function'),
            ]),
            ('MPT', 'MP Tumor'),
        ]),
        ('M7', 'Immunologic Signature', []),
        ('M8', 'Cell Type Signature', []),
    ]

    html = f'''
      <a href="javascript:toggleWithShowHide('overlapCollections', 'showHideOverlapCollections')">
        (<span id="showHideOverlapCollections">show</span> collections to investigate for overlap with this gene set)
      </a>
      <br>
      <div id="overlapCollections" style="display:none;">
'''

    def build_collection_links(items, indent=0):
        result = []
        spaces = '&nbsp;' * (indent * 6)
        for item in items:
            if len(item) == 2:
                code, name = item
                subcollections = []
            elif len(item) == 3:
                code, name, subcollections = item
            else:
                continue

            prefix = '<br>\n' if indent == 0 and result else ''
            link_class = 'spanLink' if indent > 0 else ''
            class_attr = f' class="{link_class}"' if link_class else ''
            result.append(f'''{prefix}          {spaces}<a{class_attr} href="msigdb/{species}/compute_overlaps.jsp?geneSetName={standard_name}&amp;collection={code}"><nobr>{code}: {name}</nobr></a>
''')
            if subcollections:
                result.extend(build_collection_links(subcollections, indent + 1))
        return result

    html += ''.join(build_collection_links(collections))
    html += '''      </div>
      '''

    return html


def build_compendia_links(standard_name, species):
    """Build compendia expression profiles section"""
    if species == 'mouse':
        return f'''
      
      NG-CHM interactive heatmaps<br>
      (<i>Please note that clustering takes a few seconds</i>)<br>
      <a class="ext_link {species}" href="msigdb/{species}/ngchmCompendium.jsp?geneSetName={standard_name}&amp;compendiumId=mouseTranscriptomicBodyMap" target="_blank">
        <nobr>Mouse Transcriptomic BodyMap compendium</nobr>
      </a>
      <br><br>Legacy heatmaps (PNG)<br>
      <a href="msigdb/{species}/compendium.jsp?geneSetName={standard_name}&amp;compendiumId=mouseTranscriptomicBodyMap">
        <nobr>Mouse Transcriptomic BodyMap compendium</nobr>
      </a>
      '''
    else:
        return f'''
      
      NG-CHM interactive heatmaps<br>
      (<i>Please note that clustering takes a few seconds</i>)<br>
      <a class="ext_link {species}" href="msigdb/{species}/ngchmCompendium.jsp?geneSetName={standard_name}&amp;compendiumId=humanTranscriptomicBodyMap" target="_blank">
        <nobr>Human Transcriptomic BodyMap compendium</nobr>
      </a>
      <br><br>Legacy heatmaps (PNG)<br>
      <a href="msigdb/{species}/compendium.jsp?geneSetName={standard_name}&amp;compendiumId=humanTranscriptomicBodyMap">
        <nobr>Human Transcriptomic BodyMap compendium</nobr>
      </a>
      '''


def generate_html(data, species):
    """Generate HTML content from YAML data using Jinja2 template"""
    species_class = species
    species_title = 'Mouse' if species == 'mouse' else 'Human'

    standard_name = data.get('standard_name', '')
    systematic_name = data.get('systematic_name', '')
    brief_description = data.get('brief_description', '')
    full_description = data.get('full_description', '')
    collection = data.get('collection', {})
    source_publication = data.get('source_publication', {})
    exact_source = data.get('exact_source', '')
    related_gene_sets = data.get('related_gene_sets', {})
    source_species = data.get('source_species', '')
    contributed_by = data.get('contributed_by', '')
    contributor_org = data.get('contributor_organization', '')
    source_platform = data.get('source_platform', {})
    members = data.get('members', [])
    num_members = data.get('num_members', 0)
    num_genes_mapped = data.get('num_genes_mapped', 0)
    version_history = data.get('version_history', [])

    # Process brief description to add GeneID links
    brief_html = process_gene_links(brief_description)

    # Build sections
    related_html = build_related_gene_sets(related_gene_sets, species)
    version_history_html = build_version_history(version_history)
    members_html = build_members_table(members)
    overlap_links = build_overlap_links(standard_name, species, species_class)
    compendia_links = build_compendia_links(standard_name, species)

    # Cross-species info
    other_species = 'human' if species == 'mouse' else 'mouse'
    other_species_title = 'Human' if species == 'mouse' else 'Mouse'

    # Build publication link
    pmid = source_publication.get('pmid', '')
    authors_list = source_publication.get('authors', [])
    authors = ','.join(authors_list) if authors_list else ''
    pub_link = f'<a target="_blank" href="https://pubmed.ncbi.nlm.nih.gov/{pmid}">Pubmed {pmid}</a>&nbsp;&nbsp;&nbsp;Authors: {authors}' if pmid else ''

    # Build collection display
    collection_name = collection.get('name', '')
    collection_full = collection.get('full_name', '')
    if ':' in collection_name:
        main_col, sub_col = collection_name.split(':', 1)
        collection_display = f'{main_col}: Curated<br>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;{sub_col}: {collection_full}'
    else:
        collection_display = f'{collection_name}: {collection_full}'

    # Load and render template
    template = jinja_env.get_template('gene_set.html')

    return template.render(
        species=species,
        species_class=species_class,
        species_title=species_title,
        standard_name=standard_name,
        systematic_name=systematic_name,
        brief_html=brief_html,
        full_description=full_description,
        collection_display=collection_display,
        pub_link=pub_link,
        exact_source=exact_source,
        related_html=related_html,
        source_species=source_species,
        contributed_by=contributed_by,
        contributor_org=contributor_org,
        source_platform_name=source_platform.get('name', ''),
        overlap_links=overlap_links,
        compendia_links=compendia_links,
        num_genes_mapped=num_genes_mapped,
        num_members=num_members,
        members_html=members_html,
        version_history_html=version_history_html,
        other_species=other_species,
        other_species_title=other_species_title
    )


def main():
    """Main function to generate all gene set pages"""

    # Argument parser
    parser = argparse.ArgumentParser(description='Generate static HTML pages for gene sets from YAML files')
    parser.add_argument('--limit', type=int, help='Limit the number of files to process')
    parser.add_argument('--human', action='store_true', help='Generate only human gene sets')
    parser.add_argument('--mouse', action='store_true', help='Generate only mouse gene sets')
    parser.add_argument('--resume', action='store_true', help='Skip generating files that already exist')
    parser.add_argument('--output', type=str, help='Path to the output directory (default: msigdb)')
    args = parser.parse_args()

    # Determine which species to process
    process_human = args.human or not args.mouse  # Process human if --human or neither flag is set
    process_mouse = args.mouse or not args.human  # Process mouse if --mouse or neither flag is set

    # Define paths
    human_input_path = Path('outputs/human')
    mouse_input_path = Path('outputs/mouse')

    # Use custom output path if provided
    output_base = Path(args.output) if args.output else Path('msigdb')

    human_output_path = output_base / 'human' / 'geneset'
    mouse_output_path = output_base / 'mouse' / 'geneset'

    # Create output directories
    if process_human:
        human_output_path.mkdir(parents=True, exist_ok=True)
    if process_mouse:
        mouse_output_path.mkdir(parents=True, exist_ok=True)

    total_files = 0
    skipped_files = 0

    # Process human gene sets
    if process_human and human_input_path.exists():
        logger.info(f'Processing human gene sets from {human_input_path}')
        for yaml_file in human_input_path.glob('*.yaml'):
            with open(yaml_file, 'r') as f:
                data = yaml.safe_load(f)

            standard_name = data.get('standard_name', yaml_file.stem)
            output_file = human_output_path / f'{standard_name}.html'

            # Skip if file exists and --resume is set
            if args.resume and output_file.exists():
                skipped_files += 1
                continue

            html_content = generate_html(data, 'human')

            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(html_content)

            total_files += 1
            if args.limit and total_files >= args.limit:
                break
            if total_files % 100 == 0:
                logger.info(f'  Processed {total_files} files...')

    # Process mouse gene sets
    if process_mouse and mouse_input_path.exists() and (not args.limit or total_files < args.limit):
        logger.info(f'Processing mouse gene sets from {mouse_input_path}')
        for yaml_file in mouse_input_path.glob('*.yaml'):
            with open(yaml_file, 'r') as f:
                data = yaml.safe_load(f)

            standard_name = data.get('standard_name', yaml_file.stem)
            output_file = mouse_output_path / f'{standard_name}.html'

            # Skip if file exists and --resume is set
            if args.resume and output_file.exists():
                skipped_files += 1
                continue

            html_content = generate_html(data, 'mouse')

            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(html_content)

            total_files += 1
            if args.limit and total_files >= args.limit:
                break
            if total_files % 100 == 0:
                logger.info(f'  Processed {total_files} files...')

    logger.info(f'Successfully generated {total_files} HTML files')
    if args.resume and skipped_files > 0:
        logger.info(f'  Skipped {skipped_files} existing files')
    if process_human:
        logger.info(f'  Human gene sets: {human_output_path}')
    if process_mouse:
        logger.info(f'  Mouse gene sets: {mouse_output_path}')


if __name__ == '__main__':
    main()
