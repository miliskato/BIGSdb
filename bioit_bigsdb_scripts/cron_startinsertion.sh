#!/bin/bash
# Checks whether new uploads are available from galaxy to bigsdb using the following cron command
# The cronjob is deployed using ansible in the bigsdb role (tasks/main.yml)
# */1 *   * * *   root    bash /home/bigsdb/BIGSdb/bioit_bigsdb_scripts/cron_startinsertion.sh

cd /home/galaxy

for file in /home/galaxy/*_md5.txt
do
  file_name=$(basename $file _md5.txt)
  if [ $(md5sum /home/galaxy/$file_name.tar | awk '{print $1}') == $(cat $file | awk '{print $1}') ]; then
    tar -xf /home/galaxy/$file_name.tar  # else wait until md5sum same
    rm /home/galaxy/$file_name.tar
    rm $file
  fi
done

VENV_PYTHON_BIGSDB=/home/bigsdb/BIGSdb/3.9PythonVenv/bin/python3.9

for dir in /home/galaxy/*/
do
  species=$(cat $dir/info.txt | grep -oPw "(?<='species': ')[^']*")
  sample_name=$(cat $dir/info.txt | grep -oPw "(?<='sample_name': ')[^']*")
  uploader=$(cat $dir/info.txt | grep -oPw "(?<='user': ')[^']*")
  {
    mv $dir /reports/$species/$sample_name
    $VENV_PYTHON_BIGSDB /home/bigsdb/BIGSdb/bioit_bigsdb_scripts/htmltagger.py --htmlfilepath /reports/$species/$sample_name/report.html --species $species
    $VENV_PYTHON_BIGSDB /home/bigsdb/BIGSdb/bioit_bigsdb_scripts/main_results_inserter.py --tsvfilepath /reports/$species/$sample_name/report.tsv --isolatename $sample_name --uploadermailadress $uploader --species $species --results_type new_isolate
    $VENV_PYTHON_BIGSDB /home/bigsdb/BIGSdb/bioit_bigsdb_scripts/insert_assembly.py --fastafilepath /reports/$species/$sample_name/assembly/${sample_name}_contigs.fasta --isolatename $sample_name --species $species
##    $VENV_PYTHON_BIGSDB /home/bigsdb/BIGSdb/bioit_bigsdb_scripts/cgmlst_similar_isolates.py --isolatename $sample_name --species $species
  } 2>&1 | tee /home/galaxy/$sample_name.bigsdb_insertion.log
  mv /home/galaxy/$sample_name.bigsdb_insertion.log /reports/$species/$sample_name/
done
