import argparse
import json
import logging
import tempfile
from pathlib import Path
from urllib.parse import urljoin

import shutil
import requests
import yaml
import psycopg2
import subprocess

from camel.app.camel import Camel
from camel.app.command.command import Command

import smtplib
from email.message import EmailMessage

def _parse_arguments() -> argparse.Namespace:
    """
    Parses the command line arguments.
    :return: Parsed arguments
    """
    parser = argparse.ArgumentParser()
    parser.add_argument('--host-url', type=str, required=True, help='URL for the bigsdb instance')
    parser.add_argument('--species', type=str, required=True, help='Species to re-analyze')
    # parser.add_argument('--dir-fastq', type=Path, required=True, help='Directory containing FASTQ files')
    parser.add_argument('--config', type=Path, required=True, help='Configuration file')
    parser.add_argument('--threads', type=int, default=8, help='Number of threads to use')
    return parser.parse_args()

# --host-url
# http://bioit-bigs-dev.sciensano.be
# --species
# mycobacterium
# --dir-fastq
# /testdata/camel/pipelines/
# --config
# /home/bebogaerts/PycharmProjects/CamelTemp/camel/scripts/reanalysis/config.yml
# --threads
# 4

def send_email(subject: str, content: str, config: dict) -> None:
    """
    Sends an email.
    :param subject: Mail subject
    :param content: Content of the message
    :return: None
    """
    message = EmailMessage()
    message['Subject'] = subject
    message['From'] = config['from']
    message['To'] = config['to']
    message.set_content(content)
    with smtplib.SMTP(config['host']) as s:
        s.send_message(message)

if __name__ == '__main__':
    # Initialize logging
    Camel.get_instance()

    # Parse arguments
    args = _parse_arguments()

    # Read the config
    with open(args.config, encoding='utf-8') as handle:
        config_data = yaml.safe_load(handle)

    # Retrieve isolates that need to be re-analyzed
    url_full = ''.join([args.host_url, f':5000/db/bigsdb_{args.species}_isolates/isolates'])
    response = requests.get(url_full)
    response_data = json.loads(response.content.decode('utf-8'))
    logging.info(f"{len(response_data['isolates'])} isolates parsed")

    # ! For testing, you can specify isolates manually here
    # response_data = {'isolates': ['Myco-DRR041783-ds']}

    # Re-analyze the isolates (can be parallelized with a Snakemake workflow)
    # e.g. response_data['isolates'] : "isolates":["http://bioit-bigs-dev.sciensano.be:5000/db/bigsdb_listeria_isolates/isolates/3","http://bioit-bigs-dev.sciensano.be:5000/db/bigsdb_listeria_isolates/isolates/4","http://bioit-bigs-dev.sciensano.be:5000/db/bigsdb_listeria_isolates/isolates/5"]
    for isolate_url in response_data['isolates']:

        isolate_id = isolate_url.split('/')[-1]

        # if the isolate contains an assembly, a reanalysis can be done
        url_assembly = urljoin(args.host_url, f"cgi-bin/bigsdb/bigsdb.pl?db=bigsdb_{args.species}_isolates&page=plugin&name=Contigs&format=text&isolate_id={isolate_id}&match=1&pc_untagged=0&min_length=&header=1")
        fasta = requests.get(url_assembly).content.decode('utf-8')
        if '>' in fasta:

            logging.info(f"{isolate_id} contains an assembly")
            # Get sample_name
            url_sample = ''.join([args.host_url, f':5000/db/bigsdb_{args.species}_isolates/isolates/{isolate_id}'])
            sample_name = json.loads((requests.get(url_sample)).content.decode('utf-8'))['provenance']['isolate']
            # Create new sample name with date for report dir uniqueness
            import datetime
            new_sample_name = '_'.join([sample_name, str(datetime.date.today())])
            logging.info(f"new sample name: {new_sample_name}")
            # Get original uploader
            uploader = json.loads(requests.get(url_sample).content.decode('utf-8'))['provenance']['uploader']

            # Get a temporary working directory
            with Path(tempfile.mkdtemp(None, 're_analysis_', Camel.get_instance().config['temp_dir'])) as dir_temp:

                # Get the species-specific configuration
                config_species = config_data['species'][args.species]

                # Determine the output file paths
                dir_out = dir_temp / new_sample_name
                dir_out.mkdir(exist_ok=True, parents=True)
                tsv_out = dir_out / 'report.tsv'
                html_out = dir_out / 'report.html'

                # Create the fasta file from copied from the Bigs Rest API above
                fasta_input = open(dir_out / f"{sample_name}.fasta", "w")
                fasta_input.write(fasta)
                fasta_input.close()

                # Create the command to re-analyze the datasets
                base_command = ' '.join([
                    f"module load {config_species['lmod']};",
                    f"{config_species['main_script']}",
                    f'--fasta {dir_out / f"{sample_name}.fasta"}',
                    f'--output-dir {dir_out}',
                    f"--output-html {html_out}",
                    f'--output-tsv {tsv_out}',
                    f'--working-dir {dir_temp}',
                    *config_species['options'],
                    f'--threads {args.threads}'
                ])
                command = Command(base_command)
                if args.species == 'mycobacterium':
                    # if this vcf doesnt exist then pipeline will fail during execution and send a mail just like with any other error
                    command = Command(' '.join([base_command, f'--vcf-unfiltered /reports/{args.species}/{sample_name}/report/variant_calling/variants-{sample_name}-all.vcf']))
                command.run(dir_temp)
                if command.returncode != 0:
                    # if pipeline fails, send mail and continue to next sample
                    send_email(f'Error executing automatic reanalysis pipeline on {args.species}, {sample_name} on host {args.host_url}', command.stderr, config_data['mail'])
                    # raise RuntimeError(f"Error executing pipeline: {command.stderr}")
                else:
                    logging.info(f"Re-analysis for isolate '{sample_name}' completed")
                # if 1+1==3:
                #     continue
                # else:
                #     sample_name = 'S22BD01406'
                #     new_sample_name = 'S22BD01406_2022-06-21'
                #     uploader = 'mikeltestauto'
                #     dir_out = Path("/scratch/temp/re_analysis_nnrjhl_9/S22BD01406_2022-06-21")

                    # Adding the new sample version to the database and
                    con = psycopg2.connect(database=f"bigsdb_{args.species}_isolates", user='apache', password='remote',
                                           host='127.0.0.1', port='')
                    con.autocommit = True
                    cur = con.cursor()
                    cur.execute(f"INSERT INTO isolates(id, isolate, sender, curator, date_entered, datestamp, uploader) "
                                f"VALUES((SELECT CASE WHEN (SELECT(SELECT MAX(id) FROM isolates)+1) IS NULL THEN 1 "
                                f"ELSE (SELECT(SELECT MAX(id) FROM isolates)+1) END), '{sample_name}', 1, 1, "
                                f"(SELECT CURRENT_DATE),(SELECT CURRENT_DATE), '{uploader}')")
                    cur.execute(f"UPDATE isolates SET new_version=(SELECT MAX(id) FROM isolates WHERE isolate='{sample_name}') "
                                f"WHERE isolate='{sample_name}' AND new_version IS NULL AND id!=(SELECT MAX(id) "
                                f"FROM isolates WHERE isolate='{sample_name}')")

                    # Executing the BIGSdb python scripts to move the reports and insert all the results
                    handle = open(f"{new_sample_name}.log", 'w+')
                    def run_subprocess(custom_command):
                        result = subprocess.run(
                                custom_command,
                                stdout=handle,
                                stderr=handle,
                                shell=True,
                                executable='/bin/bash')
                        if result.returncode != 0:
                            send_email(
                                f'Error handling output of automatic reanalysis pipeline on {args.species}, {sample_name} on host {args.host_url}', f"look in file /reports/{args.species}/{new_sample_name}/{new_sample_name}.log", config_data['mail'])
                    # moving the report
                    run_subprocess(f"/home/BIGSdb/3.9PythonVenv/bin/python3.9 /home/BIGSdb/bioit_custom_scripts/reportmover.py --reportdirectory {dir_out} --species {args.species}")
                    # tag the html report
                    run_subprocess(f"/home/BIGSdb/3.9PythonVenv/bin/python3.9 /home/BIGSdb/bioit_custom_scripts/htmltagger.py --htmlfilepath /reports/{args.species}/{new_sample_name}/report.html --species {args.species}")
                    # insert the results
                    run_subprocess(f"/home/BIGSdb/3.9PythonVenv/bin/python3.9 /home/BIGSdb/bioit_custom_scripts/isolate_{args.species}_typing_results.py --tsvfilepath /reports/{args.species}/{new_sample_name}/report.tsv --isolatename {sample_name} --uploadermailadress {uploader}")
                    # insert the assembly and remove the assembly file
                    run_subprocess(f"/home/BIGSdb/3.9PythonVenv/bin/python3.9 /home/BIGSdb/bioit_custom_scripts/insert_assemblies.py --fastafilepath /reports/{args.species}/{new_sample_name}/{sample_name}.fasta --isolatename {sample_name} --species {args.species}")
                    # Move the subprocess log file
                    shutil.move(f"./{new_sample_name}.log", f"/reports/{args.species}/{new_sample_name}/{new_sample_name}.log")

                    # Removing the temporary working dir and the remaining files that were not kept
                    shutil.rmtree(dir_temp)
                    # If mycobacterium and if salmonella, copy specific assays
                    if args.species == 'mycobacterium':
                        cur.execute(f"INSERT INTO eav_text(isolate_id, "
                                    f"field, value)"
                                    f"VALUES((SELECT MAX(id) FROM isolates WHERE isolate='{sample_name}'),"
                                    f"'gyrB_group', (SELECT value FROM eav_text WHERE field = 'gyrB_group' AND isolate_id = (SELECT MIN(id) FROM isolates WHERE isolate='{sample_name}'))) ")
                        cur.execute(f"INSERT INTO eav_text(isolate_id, "
                                    f"field, value)"
                                    f"VALUES((SELECT MAX(id) FROM isolates WHERE isolate='{sample_name}'),"
                                    f"'Genetic_group', (SELECT value FROM eav_text WHERE field = 'Genetic_group' AND isolate_id = (SELECT MIN(id) FROM isolates WHERE isolate='{sample_name}'))) ")
                        cur.execute(f"INSERT INTO eav_text(isolate_id, "
                                    f"field, value)"
                                    f"VALUES((SELECT MAX(id) FROM isolates WHERE isolate='{sample_name}'),"
                                    f"'SCG', (SELECT value FROM eav_text WHERE field = 'SCG' AND isolate_id = (SELECT MIN(id) FROM isolates WHERE isolate='{sample_name}'))) ")
                        cur.execute(f"INSERT INTO eav_text(isolate_id, "
                                    f"field, value)"
                                    f"VALUES((SELECT MAX(id) FROM isolates WHERE isolate='{sample_name}'),"
                                    f"'spoligotype_binary', (SELECT value FROM eav_text WHERE field = 'spoligotype_binary' AND isolate_id = (SELECT MIN(id) FROM isolates WHERE isolate='{sample_name}'))) ")
                        cur.execute(f"INSERT INTO eav_text(isolate_id, "
                                    f"field, value)"
                                    f"VALUES((SELECT MAX(id) FROM isolates WHERE isolate='{sample_name}'),"
                                    f"'spoligotype_octal', (SELECT value FROM eav_text WHERE field = 'spoligotype_octal' AND isolate_id = (SELECT MIN(id) FROM isolates WHERE isolate='{sample_name}'))) ")
                        cur.execute(f"INSERT INTO allele_designations(locus, isolate_id, "
                                    f"allele_id, status, method, sender, "
                                    f"curator, date_entered, datestamp) "
                                    f"SELECT locus, (SELECT MAX(id) FROM isolates WHERE isolate='{sample_name}'), "
                                    f"allele_id, status, method, sender, "
                                    f"curator, (SELECT CURRENT_DATE),(SELECT CURRENT_DATE) "
                                    f"FROM allele_designations WHERE isolate_id = (SELECT MIN(id) FROM isolates WHERE isolate='{sample_name}') "
                                    f"AND locus IN (SELECT locus FROM scheme_members WHERE scheme_id IN (SELECT id FROM schemes WHERE name = 'csb_RD' OR name = 'Spoligotyping'))")
                    elif args.species == 'salmonella':
                        cur.execute(f"INSERT INTO allele_designations(locus, isolate_id, "
                                    f"allele_id, status, method, sender, "
                                    f"curator, date_entered, datestamp) "
                                    f"SELECT locus, (SELECT MAX(id) FROM isolates WHERE isolate='{sample_name}'), "
                                    f"allele_id, status, method, sender, "
                                    f"curator, (SELECT CURRENT_DATE),(SELECT CURRENT_DATE) "
                                    f"FROM allele_designations WHERE isolate_id = (SELECT MIN(id) FROM isolates WHERE isolate='{sample_name}') "
                                    f"AND locus IN (SELECT locus FROM scheme_members WHERE scheme_id IN (SELECT id FROM schemes WHERE name = 'Genotyphi' OR name = 'seqsero2_allele' OR name = 'seqsero2_kmerread' OR name = 'spifinder_fastq'))")


        else:
            continue

###
# Shell script for Cron
###

# #!/bin/bash
#
# export MODULEPATH=/etc/lmod/modules
# source /etc/profile.d/lmod.sh
#
# cd /temp/scratch
# export PYTHONPATH=/home/BIGSdb/automated-reanalysis
# source /home/BIGSdb/3.9PythonVenv/bin/activate
# for species in listeria neisseria stec mycobacterium salmonella
# do
#   python /home/BIGSdb/automated-reanalysis/camel/scripts/reanalysis/reanalysis.py --host-url http://$HOSTNAME.sciensano.be --species $species --config /home/BIGSdb/automated-reanalysis/camel/scripts/reanalysis/config.yml --threads 4
# done
