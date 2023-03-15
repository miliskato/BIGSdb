# bioit_bigsdb_scripts overview

See also the bioit wiki page that describes how to add new species to bigsdb: https://bioit.sciensano.be/wiki/adding-new-species-bigsdb

## ansible

All bigsdb_*.sql scripts are used by ansible to deploy a species.

upgrade_isolates.sql and upgrade_seqdef.sql are used to upgrade the sql database from dev to master.
Correspondingly, when merging dev into master, the files should be emptied.

The following scripts are executed by ansible upon deployment, and except for Typing_loci_intopsql.py all scripts are added as a weekly cron job.
genedetection_intopsql.py
Typing_loci_intopsql.py
Typing_alleles_intopsql.py
Typing_schemeprofiles_intopsql.py
The order for the typing scripts is important, because alleles can not be inserted when loci do not exist, and profiles can not be inserted without alleles.

the file requirements.txt is used to install python dependencies in the virtual environment for the bigs scripts, created by ansible.


## psql

In order to separate psql from python and to have organized psql code:
- all psql queries are grouped in components/psql/psql_queries.py
- there is a single class components/psql/databaseconnection.py that connects to the databases in a safe way and handles query sanitization (google psycopg2 sanitization)
- all psql tables are separated in individual classes inheriting from the DatabaseConnection class. Every class has functions which are one on one connections with single queries from components/psql/psql_queries.py
- The class json_superclass in components groups tables/queries into higher level functions that recur in json_genedetectionresultsinserter.py and json_typingresultsinserter.py .

## result insertion

the script main_results_inserter.py is the actual production script that will insert results into bigsdb for a new sample or a new version of a sample.
It uses all of the scripts in components, most importantly the scripts maininserter.py, json_genedetectionresultsinserter.py and json_typingresultsinserter.py .

