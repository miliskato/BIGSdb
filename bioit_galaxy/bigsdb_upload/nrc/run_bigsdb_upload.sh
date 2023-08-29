#!/bin/bash

# the DTAP of the VM is equivalent to DTAP of galaxy host used for upload ("dev" or "test")
galaxy_hn=$(hostname)
readarray -d - -t strarr <<<"$galaxy_hn"
DTAPVM_raw=${strarr[-1]}
DTAPVM="$(echo -e "${DTAPVM_raw}" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')"

# will make a shell script with positional arguments
# $1 tsvpath
# $2 user mail
# $3 output file
# $5 fastq-hash (can be in tsv) # not done yet

if grep -q $2 /db/galaxy_bigsdb_access/approved_users.txt; then :
else
  printf '%s\n' "${2} is not an approved user" >&2
  exit
fi

cd /scratch/galaxy/temp

# get species from tsv, two step process to be sure to have right line
speciesline=$(cat $1 | awk '{print $1}' | grep -nw pipeline_name | awk -F ':' '{print $1}')
species=$(cat $1 |  sed -n ${speciesline}p | awk '{print $2}' | tr '[:upper:]' '[:lower:]')

#if [ $species == "mycobacterium" ] || [ $species == "listeria" ] || [ $species == "neisseria" ] || [ $species == "stec" ] || [ $species == "salmonella" ]; then :
if [ $species == "neisseria" ]; then :
else
  printf '%s\n' "upload on nrc platform is only available for neisseria" >&2
  exit
fi

#get FQDN for bigsdb host
nrc_suffix=${species:0:3}
bigs_dns='bioit-nrc'${nrc_suffix}'-'${DTAPVM}
darwin_vm=${bigs_dns}'.darwinproject.be'
scien_vm=${bigs_dns}'.sciensano.be'

if (nslookup ${darwin_vm} | grep Name )
then
  bigs_fqdn=${darwin_vm}
elif (nslookup ${scien_vm} | grep Name )
then
  bigs_fqdn=${scien_vm}
else
  printf '%s\n' "cannot reach NRC platform by nslookup" >&2
  exit
fi

# get sample_name from tsv, two step process to be sure to have right line
nameline=$(cat $1 | awk '{print $1}' | grep -nw sample | awk -F ':' '{print $1}')
sample_name=$(cat $1 |  sed -n ${nameline}p | awk '{print $2}')

########### read "list_of_isolates.txt" on nrc host
#due to jail, /scratch/bigsupload/mongo/list_of_isolates.txt is readable from galaxy under mongo/list_of_isolates.txt only.
sftp -q -i /home/galaxy/.ssh/id_rsa_${nrc_suffix}_${DTAPVM} galaxy@${bigs_fqdn} <<< "get /mongo/list_of_isolates.txt"

if grep -q $sample_name list_of_isolates.txt; then
  printf '%s\n' "${sample_name} already exists in ${species} BIGSdb" >&2
  exit
fi

rm list_of_isolates.txt

# get html file and folder from tsv file name, by taking basename and doing -1
tsvfilenumber=$(basename "$1" .dat | awk -F '_' '{print $2}')
htmlfilenumber=$(( $tsvfilenumber - 1 ))
htmlfilename=$(echo $1 | sed "s/$tsvfilenumber/$htmlfilenumber/g")
if [ $(echo $htmlfilenumber | grep -o '...$') == 999 ]; then
  directorytsv="$(echo ${tsvfilenumber} |awk '{print substr($0,1, length($0)-3)}'| awk '{printf "%03d\n", $0;}')"
  directoryhtml=$(( directorytsv - 1 ))
  htmlfilename=$(echo $1 | sed "s/$tsvfilenumber/$htmlfilenumber/g" | sed "s\/$directorytsv/\/$directoryhtml/\g")
fi
htmlfilefolder=$(echo $htmlfilename | sed 's/\.dat/_files/g')

mkdir ${sample_name}

cp $1 ./${sample_name}/report.tsv
if test -f ${1}.json; then
  cp ${1}.json ./${sample_name}/report.json
fi
cp $htmlfilename ./${sample_name}/report.html
cp -r $htmlfilefolder/* ./${sample_name}/
touch ./${sample_name}/info.txt
echo "{'sample_name': '${sample_name}', 'species': '${species}', 'user': '$2'}" > ./${sample_name}/info.txt
tar -cf ${sample_name}.tar ./${sample_name}/
md5sum ${sample_name}.tar > ${sample_name}_md5.txt

if test -f ${1}.json; then
  sftp -q -i /home/galaxy/.ssh/id_rsa_${nrc_suffix}_${DTAPVM} galaxy@${bigs_fqdn} <<< "put ${sample_name}.tar mongo/"
  sftp -q -i /home/galaxy/.ssh/id_rsa_${nrc_suffix}_${DTAPVM} galaxy@${bigs_fqdn} <<< "put ${sample_name}_md5.txt mongo/"
else
  sftp -q -i /home/galaxy/.ssh/id_rsa_${nrc_suffix}_${DTAPVM} galaxy@${bigs_fqdn} <<< "put ${sample_name}.tar not_json/"
  sftp -q -i /home/galaxy/.ssh/id_rsa_${nrc_suffix}_${DTAPVM} galaxy@${bigs_fqdn} <<< "put ${sample_name}_md5.txt not_json/"
fi

echo "{user_mail: $2, sample_name: ${sample_name}, species: ${species}}" > $3

# todo need a check for pipeline name in tsv

rm -r ${sample_name} ${sample_name}_md5.txt ${sample_name}.tar
