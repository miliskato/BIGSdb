#!/bin/bash
# Checks whether new uploads are available from galaxy to bigsdb using the following cron command
# The cronjob is deployed using ansible in the bigsdb role (tasks/main.yml)
# */1 *   * * *   root    bash /home/bigsdb/BIGSdb/bioit_bigsdb_scripts/cron_startinsertion_mongo_implementation.sh

cd /scratch/bigsupload/mongo

for file in /scratch/bigsupload/mongo/*_md5.txt
do
  file_name=$(basename $file _md5.txt)
  if [ $(md5sum /scratch/bigsupload/mongo/$file_name.tar | awk '{print $1}') == $(cat $file | awk '{print $1}') ]; then
    tar -xf /scratch/bigsupload/mongo/$file_name.tar # else wait until md5sum same
    rm /scratch/bigsupload/mongo/$file_name.tar
    rm $file
  fi
done

VENV_PYTHON_BIGSDB=/home/bigsdb/BIGSdb/3.9PythonVenv/bin/python3.9

for dir in /scratch/bigsupload/mongo/*/
do
  species=$(cat $dir/info.txt | grep -oPw "(?<='species': ')[^']*")
  sample_name=$(cat $dir/info.txt | grep -oPw "(?<='sample_name': ')[^']*")
  uploader=$(cat $dir/info.txt | grep -oPw "(?<='user': ')[^']*")
  insert_date=$(date +%m-%d-%Y_%H:%M:%S)
  {
    mv $dir /reports/$species/${sample_name}_${insert_date}
    $VENV_PYTHON_BIGSDB /home/bigsdb/BIGSdb/bioit_bigsdb_scripts/htmltagger.py --htmlfilepath /reports/$species/${sample_name}_${insert_date}/report.html --species $species
    $VENV_PYTHON_BIGSDB /home/bigsdb/BIGSdb/bioit_mongodb_scripts/mainmongo.py --reportdirectorypath /reports/$species/${sample_name}_${insert_date} --species ${species} --uploader_mail_address ${uploader} --jsonfilepath /reports/$species/${sample_name}_${insert_date}/report.json --technical_id ${sample_name} --fastafilepath /reports/$species/${sample_name}_${insert_date}/assembly/${sample_name}_contigs.fasta --vcffilepath  /reports/$species/${sample_name}_${insert_date}/variant_calling/variants-${sample_name}-all.vcf --results_type new_isolate
    $VENV_PYTHON_BIGSDB /home/bigsdb/BIGSdb/bioit_mongodb_scripts/mongo_to_bigs.py --species ${species} --uploader_mail_address ${uploader} --single_sample_id ${sample_name}
##    $VENV_PYTHON_BIGSDB /home/bigsdb/BIGSdb/bioit_bigsdb_scripts/cgmlst_similar_isolates.py --isolatename $sample_name --species $species
  } 2>&1 | tee /scratch/bigsupload/mongo/$sample_name.mongodb_bigsdb_insertion.log
  mv /scratch/bigsupload/mongo/$sample_name.mongodb_bigsdb_insertion.log /reports/$species/${sample_name}_${insert_date}/
done
