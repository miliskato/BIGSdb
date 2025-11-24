# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]
### Added:
- Warning reasons to the submissions page
- Alert system for Influenza based on the hosts of the reference sequence (reference selection)
- Reference database for Influenza to the galaxy report section of the isolate page
- Krona report to the Analysis section of the isolate page
- InternalReferenceSampleID field to the nominative metadata for Influenza

### Changed:
- Order nominative metadata Influenza

### Fixed:
- Assigning FluA_SubtypeNAPCR when NA lab test info is present

## [4.3.0]
### Added:
- Added task in ANSIBLE to remove the first version of the bigsdb-insertion.service (if present on the VM)
- HtmlAntiviralMutationsTableBuilder and HtmlAntiviralMutationsTableBuilder classes 
- Integration in BIGSdb of two assays for Influenza: the "Antiviral resistances" and the "Reference selection"

### Changed
- For Influenza, html tags are used but using the section tags of the original report
- Changes in the naming of pcr related fields for Influenza
- Adapt import for get_bigsdb_config_data
- Adapt core QC thresholds influenza
- Include warning reasons in MongoDB document to be inserted
- Include contamination check and input type in rejected document (MongoDB)

### Fixed
- Creation of temp file in "rejected_isolates.py"
- Reanalysis (reanalysis submission + html report + html replacer + html tagger)
- influenza missing reference segment info in core qc checks
- Correct count of pseudonymisation in nrc integration

## [4.2.0]
### Added:
- Ability to support deployment for multiple species databases on the same VM
- Enterococcus faecalis and Enterococcus faecium related assays ('MLST_Bezdicek', 'LRE-Finder')
- Method to validate Literal object and value passed to this one
- "manual_validation_of_good_qc.py" to validate the good qc isolates submitted into BIGSdb (historical collection)
- Influenza CLIN LAB DCD integration
- Field 'detected_lineage' in eav_text to filter query based on snp lineage

### Changed
- Method to get relevant info from the mongoDB config file
- Content of the mongoDB config file (bioit_mongodb_scripts/config/config.yml)
- Migration files for the "isolates" DB are now moved to a extra subfolder (bigsdb_isolates_v/bigsdb_{{ species }}_isolates) to avoid overlap of the migrations files after the first deployment (one deployment/species)
- log files for the bigsdb-insertion-{species}.service are moved to /var/log/bigsdb_insertions_service/ folder 
- Reworked SFTPConnection class to be able to be used in with statements for cleaner exiting
- snp lineage is now stored as eav_text data with two fields (one for the html table and the other to help filtering queries)

### Fixed
- Issue with rotation of the logs for bigsdb-insertion-{species}.service
- Literal accepting silently wrong values
- missing snp_lineage results due to changes in the "mongo key" of the assay after updating to pipeline 1.3


### Removed:
- some batch of unused files + stec related functions

## [4.1.1]
### Added
- "manual_validation_of_good_qc.py" to validate the good qc isolates submitted into BIGSdb (historical collection)

### Fixed
- bug in coreqc for influenza: duplication due to not deepcopying

## [4.1.0]
### Added:
- nominative fields for MTB

### Changed:
- Remove spoligotyping from query results in BIGSdb
- Only store in BIGSdb hsp65 lineage found in the collection

### Fixed:
- hsp65 fields was not inserted as boolean which makes the search on this field not possible
- failure to insert the 51SNP scheme results

### Removed:
- cron job to insert reports from galaxy in the local mongoDB

## [4.0.1]
### Changed:
- version of AMRFinder int the tagger_config.yml file (for Neisseria, Listeria and Enterococcus spp.)

### Fixed:
- The html that are used in the bigsdb config are now corresponding to those used in the report (in the tagger_config) except for AMRFinder, we stick to #amr as the anchor #amrfinder was not present in the report
- The url link to the report which was used in Mob-Suite html table is now working
- Insertion of cgMLST diffs clustering into classification schemes table of salmonella isolates database
- Bad layout of the html tables for genedetection schemes handled by the genedetection generic builder

## [4.0.0]
### Changed:
- AMRFinder tool and database version
- Insertion of viral technical metadata

## [3.1.0]
### Changed:
- Added AMRFinder for Neisseria
- Added AMRFinder for Salmonella

### Fixed:
- Added mic_resistances fields again in both sql and db xml. They were accidentally removed from sql previously. Also added serogroup_pheno field 
  in neisseria again which was also accidentally removed during splitting up of all sql columns in isolates database by pathogen.

## [3.0.0] 
### Added:
- rMLST scheme
- ResFinder4
- AMRFinder
- MOB-Suite
- gMATS
- MenDeVar
- Azure service bus to handle the insertion of isolates in BIGSdb
- Service "bigsdb-insertion.service" to replace the cron job mongo_to_bigs_hourly
- check for presence of cgMLST scheme members and for presence of mv_scheme_x table in seqdef before trying a 
  cache update of the scheme. 
- Added Listeria & Influenza output DCD's to NRC integration
- Added core QC page and core quality metrics checking for both Illumina & ONT
- Enterococcus is supported
- Listeria CLIN LAB DCD integration

### Changed
- All Jammy existing assays to bigsdb for neisseria listeria salmonella mycobacterium influenza.
- Adaptations done in 2.1.1 to avoid the usage of hard link to the mount were exported in this version.
- Insertion of gene detection schemes
- Insertion of sequence typing schemes
- Validation of good quality isolates + exporting of JSON reports to /output_reports
- All Jammy existing assays to bigsdb for neisseria listeria salmonella mycobacterium influenza.
- Upgrade from python 3.9 to python 3.12
- Rework integration SFTP flow 11 to send genomic indicators to ODS instead of DWH, remove mapping table flow to ODS
- Simplification of html generation azure script
- Updated NRC integration according to latest DCD's:
  - Salmonella CLIN v1.0.5-draft7
  - Salmonella LAB v1.0.6-draft5
  - Salmonella genomic 1.0.1-draft4
  - Listeria genomic 1.0.1-draft3
  - Influenza genomic 1.0.1-draft3
- Modified pseudonymization slightly to be able to rename resequencing files in Azure so that they do not cause issues during the archival.
- Simplification of html tagger and html update merger scripts (renamed to html replacer) + creation of general html report class
- Update of tagger config to account for the jammy changes
- Update of reanalysis and reanalysis configs to account for the jammy changes
- Upgrade from psycopg2 to psycopg3
- Upgrade of BIGSdb to v1.51.1
- Unique mreact acc host and token that needs to be defined in the host_vars

### Fixed:
- Mykrobe scheme : typo in two AB names
- issue if PubMLST add some extra blank lines at the end of the profiles.tsv files
- Bugfix reanalysis influenza

### Removed:
- PointFinder, ResFinder, NCBI AMR, PlasmidFinder
- Ability to support stec species
- Ability to recompute gene_detection (removal, recalculation and reinsertion of alleles designations disabled)
- cron job to target insertion from MongoDB Atlas to BIGSdb

## [2.1.1 - support/2.1.0]
### Changed:
- remove mount of the local db catalog. Only keep the Azure one and named the mount ".bioit_database" instead of ".bioit_database_azure"
  (this part is handle on the ANSIBLE side)
- use the /db folder instead of the /.bioit_database path in the project (in order to use the symlinks and not the mount directly)

## [2.1.0]
### Added
- Possibility to handle insertion for viral species that come without any scheme to insert in seqdef
- Nominative metadata for Influenza 
- Configuration for Influenza DBs (xml)

### Changed
- List of authorized species in mongo config
- Microreact can run without selecting a scheme
- A part of the eav fields are available for selection in the dropdown list of Microreact plugin
- cpanm is used instead of cpan to install perl packages
- Ansible was updated to 2.18.1
- The bioit-bigsdb.yml playbook includes extra roles in order to skip the manual run of the bioit-db.yml and bioit-filedb.yml
  playbooks during the deployment of the platform.

### Fixed
- Insertion of assembly is now using the "fasta_path" from mongo instead of reconstructing a path based on the "report_dir" field.
- Insertion of nominative data (broken in 2.0.1)
- Fix in mongo_to_bigs in the code handling comparison of cgst in case of reanalysis (600a28e4051574fb7d38bb68d44d3b68b2771d48)
- ANSIBLE 2.18.1 - fix community.general.cpan module

## [2.0.2] - 2025-01-20 (myc dev and test)
### Fixed
- insertion of reanalysed badqc isolates (bug: removing of the validated badqc from BIGSdb before reinserting its new results was not done)
- fix a type issue in a condition during the cgst reevaluation

## [2.0.1] - 2024-12-02
### Added
- cron job to ensure that badqcs stored in MongoDB are all well inserted into BIGSdb submission system
- Utility script for the validation of all badqcs submitted in BIGSdb

### Fixed
- Insertion of clustering/nominative data and alert computation is disabled when BIGSdb is still empty
- Fix access rights on /home/bigsdb/BIGSdb
- Fix the lockfile command configuration to avoid simultaneous connections to the matrix file in AZURE. 
- Avoid duplicated primary key in "classification_group_profile_history" if clustering change the same day
- Badqc not selected for submission in BIGSdb if their creation date in Mongo coincides with the start of the cron job 
  for mongo_to_bigs.py
- Issue due to new cgMLST selected for insertion between the last update of temporary alleles and the next new run for the temp_id_replacer
- Unexpected deletion of isolates from BIGSdb if a failure happens during the insertion of their reanalysis results.

### Changed
- Update of "snp_lineage" scheme (mycobacterium)
- "mongo_to_bigs_hourly" cron job is running every 5 minutes
- Introduce new fields to get info on various updates in MongoDB Atlas
- deprecated "datetime.utcnow()" is replaced by "datetime.now(timezone.utc)"
- Fail-safe mechanism (flagfile) is only used for new isolates (not anymore used for reseq/reanalysis)
- Cache update of cgmlst scheme in BIGSdb is now performed using the incremental method. 
  In case of reanalysis, the isolate will firstly be removed from the temp_isolates_scheme_fields_x table

## [2.0.0] - 2024-10-28

### Added
- SciensanoReportPage.pm to download the report directly from BIGSdb as previous solution was not working under 
  BIGSdb 1.48

### Changed
- Reports are not stored on the local VM, they need to be called from AZURE api
- Computation of the cgmlst matrix is done on AZURE
- html tagger is running on AZURE
- BIGSdb was upload from V1.36 -> V1.47
- Local MongoDB hosts the mapping table for pseudonymization and the other collections are stored in MongoDB Atlas

### Fixed
- API call for Download/visualisation of the html reports 
- Sequence bin plugin in BIGSdb

### Removed
- Uploading of the pipeline's reports directly from galaxy
- Possibility to accept resequencing (disabled for now)

## [1.0.0] - 2024-04-27 
- Local version of the NRC platform as deployed on nrcnei-prod

## [0.0.0]
- Local earliest developments of the NRC platform not deployed on any prod instance