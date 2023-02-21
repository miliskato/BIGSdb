#!/bin/bash
# Checks whether new uploads are available from galaxy to bigsdb using the following cron command
# The cronjob is deployed using ansible in the bigsdb role (tasks/main.yml)
# */1 *   * * *   root    bash /home/bigsdb/BIGSdb/bioit_bigsdb_scripts/cron_startinsertion_mongo_implementation.sh

cd /home/galaxy/mongo

for file in /home/galaxy/mongo/*_md5.txt
do
  file_name=$(basename $file _md5.txt)
  if [ $(md5sum /home/galaxy/mongo/$file_name.tar | awk '{print $1}') == $(cat $file | awk '{print $1}') ]; then
    tar -xf /home/galaxy/mongo/$file_name.tar # else wait until md5sum same
    rm /home/galaxy/mongo/$file_name.tar
    rm $file
  fi
done

VENV_PYTHON_BIGSDB=/home/bigsdb/BIGSdb/3.9PythonVenv/bin/python3.9

for dir in /home/galaxy/mongo/*/
do
  species=$(cat $dir/info.txt | grep -oPw "(?<='species': ')[^']*")
  sample_name=$(cat $dir/info.txt | grep -oPw "(?<='sample_name': ')[^']*")
  uploader=$(cat $dir/info.txt | grep -oPw "(?<='user': ')[^']*")
  # todo uploader is unused here and in mainmongo atm, there is currently (6th jan 2022) a dummy in place in mainmongo: 'bioit'
  {
    mv $dir /reports/$species/bigsdb_json_upload/${sample_name}
    $VENV_PYTHON_BIGSDB /home/bigsdb/BIGSdb/bioit_bigsdb_scripts/htmltagger.py --htmlfilepath /reports/$species/bigsdb_json_upload/$sample_name/report.html --species $species
    $VENV_PYTHON_BIGSDB /home/bigsdb/BIGSdb/bioit_mongodb_scripts/mainmongo.py --reportdirectorypath /reports/$species/bigsdb_json_upload/${sample_name} --species ${species} --jsonfilepath /reports/$species/bigsdb_json_upload/${sample_name}/report.json --technical_id ${sample_name} --fastafilepath /reports/$species/bigsdb_json_upload/${sample_name}/assembly/${sample_name}_contigs.fasta --vcffilepath  /reports/$species/bigsdb_json_upload/${sample_name}/variant_filtering/${sample_name}-all.vcf --results_type new_isolate
    $VENV_PYTHON_BIGSDB /home/bigsdb/BIGSdb/bioit_mongodb_scripts/mongo_to_bigs.py --species ${species}
##    $VENV_PYTHON_BIGSDB /home/bigsdb/BIGSdb/bioit_bigsdb_scripts/cgmlst_similar_isolates.py --isolatename $sample_name --species $species
  } 2>&1 | tee /home/galaxy/mongo/$sample_name.mongodb_bigsdb_insertion.log
  mv /home/galaxy/mongo/$sample_name.mongodb_bigsdb_insertion.log /reports/$species/bigsdb_json_upload/$sample_name/
done
