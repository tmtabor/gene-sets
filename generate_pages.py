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


def build_related_gene_sets(related_gene_sets, species, link_prefix=''):
    """Build the related gene sets HTML section"""
    if not related_gene_sets:
        return '''      
        &nbsp;
        '''

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
                <a href="{link_prefix}msigdb/{species}/geneset/{geneset_name}.html">{geneset_name}</a>
              ''')
        html_parts.append('''
            </div>
          
          
          ''')

    from_authors = related_gene_sets.get('from_same_authors', [])
    if from_authors:
        count = len(from_authors)
        html_parts.append(f'''
            <a href="javascript:toggleWithShowHide('relatedByAuthors', 'showHideByAuthors')">
              (<span id="showHideByAuthors">show</span> {count} gene {'sets' if count > 1 else 'set'} from any of these authors)
            </a>
            <br>
            <div id="relatedByAuthors" style="display: none;">
              <br>
              ''')
        for geneset_name in from_authors:
            html_parts.append(f'''
                <a href="{link_prefix}msigdb/{species}/geneset/{geneset_name}.html">{geneset_name}</a>
              ''')
        html_parts.append('''
            </div>
          ''')

    return ''.join(html_parts) if html_parts else '''      
        &nbsp;
        '''


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


def build_overlap_links(standard_name, species, species_class, link_prefix=''):
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
        for i, item in enumerate(items):
            if len(item) == 2:
                code, name = item
                subcollections = []
            elif len(item) == 3:
                code, name, subcollections = item
            else:
                continue

            link_class = 'spanLink' if indent > 0 else ''
            class_attr = f' class="{link_class}"' if link_class else ''
            result.append(f'''          {spaces}<a{class_attr} href="{link_prefix}msigdb/{species}/compute_overlaps.jsp?geneSetName={standard_name}&amp;collection={code}"><nobr>{code}: {name}</nobr></a><br>
''')
            if subcollections:
                result.extend(build_collection_links(subcollections, indent + 1))
        return result

    html += ''.join(build_collection_links(collections))
    html += '''      </div>
      '''

    return html


def build_compendia_links(standard_name, species, link_prefix=''):
    """Build compendia expression profiles section"""
    if species == 'mouse':
        return f'''
      
      NG-CHM interactive heatmaps<br>
      (<i>Please note that clustering takes a few seconds</i>)<br>
      <a class="ext_link {species}" href="{link_prefix}msigdb/{species}/ngchmCompendium.jsp?geneSetName={standard_name}&amp;compendiumId=mouseTranscriptomicBodyMap" target="_blank">
        <nobr>Mouse Transcriptomic BodyMap compendium</nobr>
      </a>
      <br><br>Legacy heatmaps (PNG)<br>
      <a href="{link_prefix}msigdb/{species}/compendium.jsp?geneSetName={standard_name}&amp;compendiumId=mouseTranscriptomicBodyMap">
        <nobr>Mouse Transcriptomic BodyMap compendium</nobr>
      </a>
      '''
    else:
        # Human has 4 compendia
        return f'''
      
      NG-CHM interactive heatmaps<br>
      (<i>Please note that clustering takes a few seconds</i>)<br>
      <a class="ext_link" href="{link_prefix}msigdb/{species}/ngchmCompendium.jsp?geneSetName={standard_name}&amp;compendiumId=gtex" target="_blank">
        <nobr>GTEx compendium</nobr>
      </a><br>
      <a class="ext_link" href="{link_prefix}msigdb/{species}/ngchmCompendium.jsp?geneSetName={standard_name}&amp;compendiumId=novartisHuman" target="_blank">
        <nobr>Human tissue compendium (Novartis)</nobr>
      </a><br>
      <a class="ext_link" href="{link_prefix}msigdb/{species}/ngchmCompendium.jsp?geneSetName={standard_name}&amp;compendiumId=cancerTissues" target="_blank">
        <nobr>Global Cancer Map (Broad Institute)</nobr>
      </a><br>
      <a class="ext_link" href="{link_prefix}msigdb/{species}/ngchmCompendium.jsp?geneSetName={standard_name}&amp;compendiumId=cancerCellLines" target="_blank">
        <nobr>NCI-60 cell lines (National Cancer Institute)</nobr>
      </a>
      <br><br>Legacy heatmaps (PNG)<br>
      <a href="{link_prefix}msigdb/{species}/compendium.jsp?geneSetName={standard_name}&amp;compendiumId=gtex">
        <nobr>GTEx compendium</nobr>
      </a><br>
      <a href="{link_prefix}msigdb/{species}/compendium.jsp?geneSetName={standard_name}&amp;compendiumId=novartisHuman">
        <nobr>Human tissue compendium (Novartis)</nobr>
      </a><br>
      <a href="{link_prefix}msigdb/{species}/compendium.jsp?geneSetName={standard_name}&amp;compendiumId=cancerTissues">
        <nobr>Global Cancer Map (Broad Institute)</nobr>
      </a><br>
      <a href="{link_prefix}msigdb/{species}/compendium.jsp?geneSetName={standard_name}&amp;compendiumId=cancerCellLines">
        <nobr>NCI-60 cell lines (National Cancer Institute)</nobr>
      </a>
      '''


def build_dataset_references(dataset_references):
    """Build dataset references HTML section"""
    if not dataset_references:
        return '''      &nbsp;
      
      
      '''

    count = len(dataset_references)
    html = f'''      <a href="javascript:javascript:toggleWithShowHide('datasets', 'showHideDatasets')">
            (<span id="showHideDatasets">show</span> {count} dataset{'s' if count > 1 else ''})
        </a>
      <br>
      <div id="datasets" style="display: none;"><br>'''

    dataset_links = []
    for dataset in dataset_references:
        dataset_type = dataset.get('type', '')
        dataset_id = dataset.get('id', '')

        if dataset_type == 'GEO':
            url = f'http://www.ncbi.nlm.nih.gov/projects/geo/query/acc.cgi?acc={dataset_id}'
            dataset_links.append(f'<a href="{url}" target="_blank">{dataset_id}</a>')
        else:
            dataset_links.append(dataset_id)

    html += '<br>'.join(dataset_links)
    html += '</div>\n'

    return html


def generate_html(data, species, link_prefix='', other_species_gene_sets=None):
    """Generate HTML content from YAML data using Jinja2 template"""
    species_class = species
    species_title = 'Mouse' if species == 'mouse' else 'Human'

    standard_name = data.get('standard_name', '')
    systematic_name = data.get('systematic_name', '')
    brief_description = data.get('brief_description', '')
    full_description = data.get('full_description', '')

    # Normalize collection - handle both string and dict formats
    collection_raw = data.get('collection', {})
    if isinstance(collection_raw, dict):
        collection_name = collection_raw.get('name', '')
        collection_full = collection_raw.get('full_name', '')
    elif isinstance(collection_raw, str):
        collection_name = collection_raw
        collection_full = ''
    else:
        collection_name = ''
        collection_full = ''

    source_publication = data.get('source_publication', {})
    exact_source = data.get('exact_source', '')
    # Handle None or empty exact_source - leave blank instead of showing "None"
    if exact_source is None or exact_source == 'None':
        exact_source = ''
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
    related_html = build_related_gene_sets(related_gene_sets, species, link_prefix)
    version_history_html = build_version_history(version_history)
    members_html = build_members_table(members)
    overlap_links = build_overlap_links(standard_name, species, species_class, link_prefix)
    compendia_links = build_compendia_links(standard_name, species, link_prefix)
    dataset_references = build_dataset_references(data.get('dataset_references', []))

    # Cross-species info
    other_species = 'human' if species == 'mouse' else 'mouse'
    other_species_title = 'Human' if species == 'mouse' else 'Mouse'

    # Check if corresponding gene set exists in other species
    has_other_species_geneset = False
    if other_species_gene_sets is not None:
        has_other_species_geneset = standard_name in other_species_gene_sets

    # Build publication link
    pmid = source_publication.get('pmid', '')
    authors_list = source_publication.get('authors', [])
    authors = ','.join(authors_list) if authors_list else ''
    pub_link = f'<a target="_blank" href="https://pubmed.ncbi.nlm.nih.gov/{pmid}">Pubmed {pmid}</a>&nbsp;&nbsp;&nbsp;Authors: {authors}' if pmid else '&nbsp;'

    # Build collection display - handle full 3-level hierarchy
    if not collection_name:
        collection_display = '&nbsp;'
    else:
        parts = collection_name.split(':')

        # Map of collection codes to names
        collection_map = {
            # Human collections
            'C1': 'Positional',
            'C2': 'Curated',
            'C3': 'Regulatory Target',
            'C5': 'Ontology',
            'C7': 'Immunologic Signature',
            'C8': 'Cell Type Signature',
            'CH': 'Hallmark',
            # Mouse collections
            'M1': 'Positional',
            'M2': 'Curated',
            'M3': 'Regulatory Target',
            'M5': 'Ontology',
            'M7': 'Immunologic Signature',
            'M8': 'Cell Type Signature',
            'MH': 'Hallmark',
            # Subcollections
            'CP': 'Canonical Pathways',
            'CGP': 'Chemical and Genetic Perturbations',
            'GO': 'Gene Ontology',
            'MIR': 'microRNA Targets',
            'TFT': 'Transcription Factor Targets',
            'GTRD': 'GTRD',
            'MIRDB': 'miRDB',
            # GO subcollections
            'GO:BP': 'GO Biological Process',
            'GO:CC': 'GO Cellular Component',
            'GO:MF': 'GO Molecular Function',
            # CP subcollections
            'CP:BIOCARTA': 'BioCarta Pathways',
            'CP:KEGG': 'KEGG Pathways',
            'CP:KEGG_MEDICUS': 'KEGG Medicus',
            'CP:PID': 'PID Pathways',
            'CP:REACTOME': 'Reactome Pathways',
            'CP:WIKIPATHWAYS': 'WikiPathways',
            # MIR subcollections
            'MIR:MIR_LEGACY': 'MIR_Legacy',
            'MIR:MIRDB': 'miRDB',
            # TFT subcollections
            'TFT:GTRD': 'GTRD',
            'TFT:TFT_LEGACY': 'TFT_Legacy',
            # Other
            'MPT': 'MP Tumor',
        }

        if len(parts) == 1:
            # Simple collection: "C2"
            collection_display = f'{parts[0]}: {collection_map.get(parts[0], collection_full)}'
        elif len(parts) == 2:
            # Two-level: "C2:CGP" or "M3:GTRD"
            main_name = collection_map.get(parts[0], parts[0])
            sub_name = collection_map.get(parts[1], collection_full)
            collection_display = f'{parts[0]}: {main_name}<br>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;{parts[1]}: {sub_name}'
        else:
            # Three-level: "C2:CP:KEGG_MEDICUS" or "C3:MIR:MIR_LEGACY"
            main_name = collection_map.get(parts[0], parts[0])
            mid_name = collection_map.get(parts[1], parts[1])
            full_sub = ':'.join(parts[1:])
            collection_display = f'{parts[0]}: {main_name}<br>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;{parts[1]}: {mid_name}<br>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;{full_sub}: {collection_full}'

    # Build external links
    external_links = data.get('external_links', [])
    external_links_html = ''
    if external_links:
        links = []
        for url in external_links:
            links.append(f'<a target="_blank" href="{url}">{url}</a>')
        links.append('<a target="_blank" href=""></a>')
        external_links_html = '<br>'.join(links)
    else:
        external_links_html = '<a target="_blank" href=""></a>'

    # Build contributor display - show organization in parentheses if different
    if contributed_by and contributor_org and contributed_by != contributor_org:
        contributor_display = f'{contributed_by} ({contributor_org})'
    elif contributed_by:
        contributor_display = contributed_by
    elif contributor_org:
        contributor_display = contributor_org
    else:
        contributor_display = '&nbsp;'

    # Load and render template
    template = jinja_env.get_template('gene_set.html')

    return template.render(
        species=species,
        species_class=species_class,
        species_title=species_title,
        standard_name=standard_name,
        systematic_name=systematic_name,
        brief_html=brief_html,
        full_description=full_description if full_description else '&nbsp;',
        collection_display=collection_display,
        pub_link=pub_link,
        exact_source=exact_source,
        related_html=related_html,
        external_links_html=external_links_html,
        source_species=source_species,
        contributor_display=contributor_display,
        source_platform_name=source_platform.get('name', ''),
        overlap_links=overlap_links,
        compendia_links=compendia_links,
        dataset_references=dataset_references,
        num_genes_mapped=num_genes_mapped,
        num_members=num_members,
        members_html=members_html,
        version_history_html=version_history_html,
        other_species=other_species,
        other_species_title=other_species_title,
        has_other_species_geneset=has_other_species_geneset,
        link_prefix=link_prefix
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
    parser.add_argument('--geneset', type=str, help='Generate a specific gene set by name (e.g., ZNF320_TARGET_GENES)')
    parser.add_argument('--link-prefix', type=str, default='', help='Prefix for all links (e.g., https://www.gsea-msigdb.org/)')

    args = parser.parse_args()

    # Normalize link prefix - ensure it ends with / if provided
    link_prefix = args.link_prefix
    if link_prefix and not link_prefix.endswith('/'):
        link_prefix += '/'

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

    # Build index of gene sets for cross-species checking
    human_gene_sets = set()
    mouse_gene_sets = set()

    for yaml_file in human_input_path.glob('*.yaml'):
        human_gene_sets.add(yaml_file.stem)
    for yaml_file in mouse_input_path.glob('*.yaml'):
        mouse_gene_sets.add(yaml_file.stem)

    total_files = 0
    skipped_files = 0

    # Process human gene sets
    # If --geneset is specified, process only that specific gene set
    if args.geneset:
        geneset_name = args.geneset

        # Process human gene set if applicable
        if process_human:
            yaml_file = human_input_path / f'{geneset_name}.yaml'
            if yaml_file.exists():
                logger.info(f'Processing human gene set: {geneset_name}')
                with open(yaml_file, 'r') as f:
                    data = yaml.safe_load(f)

                standard_name = data.get('standard_name', geneset_name)
                output_file = human_output_path / f'{standard_name}.html'

                html_content = generate_html(data, 'human', link_prefix, mouse_gene_sets)

                with open(output_file, 'w', encoding='utf-8') as f:
                    f.write(html_content)

                logger.info(f'Generated: {output_file}')
                total_files += 1
            elif process_human:
                logger.warning(f'Human gene set not found: {yaml_file}')

        # Process mouse gene set if applicable
        if process_mouse:
            yaml_file = mouse_input_path / f'{geneset_name}.yaml'
            if yaml_file.exists():
                logger.info(f'Processing mouse gene set: {geneset_name}')
                with open(yaml_file, 'r') as f:
                    data = yaml.safe_load(f)

                standard_name = data.get('standard_name', geneset_name)
                output_file = mouse_output_path / f'{standard_name}.html'

                html_content = generate_html(data, 'mouse', link_prefix, human_gene_sets)

                with open(output_file, 'w', encoding='utf-8') as f:
                    f.write(html_content)

                logger.info(f'Generated: {output_file}')
                total_files += 1
            elif process_mouse:
                logger.warning(f'Mouse gene set not found: {yaml_file}')

        if total_files == 0:
            logger.error(f'Gene set "{geneset_name}" not found for the specified species')
        return


    logger.info(f'Successfully generated {total_files} HTML files')
    if args.resume and skipped_files > 0:
        logger.info(f'  Skipped {skipped_files} existing files')
    if process_human:
        logger.info(f'  Human gene sets: {human_output_path}')
    if process_mouse:
        logger.info(f'  Mouse gene sets: {mouse_output_path}')


if __name__ == '__main__':
    main()
