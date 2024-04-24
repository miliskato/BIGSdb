#!/bin/bash
# Stop commands upon failure
set -o errexit

# Define default values
sample_name=""
fq_fw=""
fq_fw_name=""
fq_rev=""
fq_rev_name=""
species=""
isolation_date=""
uploader_mail_address=""


# Function to display usage
usage() {
    echo "Usage: $0 --sample-name <value> --fq-fw <value> --fq-fw-name <value> --fq-rev <value> --fq-rev-name <value> --species <value> --isolation-date <value> --uploader-mail-address <value>"
    exit 1
}

# Parse arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        --sample-name)
            sample_name=$2
            shift 2
            ;;
        --fq-fw)
            fq_fw=$2
            shift 2
            ;;
        --fq-fw_name)
            fq_fw_name=$2
            shift 2
            ;;
        --fq-rev)
            fq_rev=$2
            shift 2
            ;;
        --fq-rev-name)
            fq_rev_name=$2
            shift 2
            ;;
        --species)
            species=$2
            shift 2
            ;;
        --isolation-date)
            isolation_date=$2
            shift 2
            ;;
        --uploader-mail-address)
            uploader_mail_address=$2
            shift 2
            ;;
        *)
            echo "Error: Unknown option: $1"
            usage
            ;;
    esac
done

# Check if all required arguments are provided (and not empty = -z)
if [[ -z $sample_name || -z $fq_fw || -z $fq_fw_name || -z $fq_rev || -z $fq_rev_name || -z $species || -z $isolation_date || -z $uploader_mail_address ]]; then
    echo "Error: All variables are required."
    usage
fi

# Check whether input isolation_date matches the requested format
date_pattern="^[0-9]{2}-[0-9]{2}-[0-9]{4}$"
if [[ ! $isolation_date =~  $date_pattern ]]; then
    echo "Invalid date format"
    exit 1
fi

# the DTAP of the VM is equivalent to DTAP of galaxy host used for upload ("dev" or "test")
galaxy_hn=$(hostname)
readarray -d - -t strarr <<<"$galaxy_hn"
DTAPVM_raw=${strarr[-1]}
DTAPVM="$(echo -e "${DTAPVM_raw}" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')"

# Check whether user has permission to upload samples
if grep -q $uploader_mail_address /db/galaxy_bigsdb_access/approved_users.txt; then :
else
  printf '%s\n' "${uploader_mail_address} is not an approved user" >&2
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

cd /scratch/galaxy/temp

touch ${sample_name}_to_azure.json
# todo add all variables to json file below
echo "{'sample_name': '${sample_name}', 'species': '${species}', 'user': '$2'}" > ${sample_name}_to_azure.json

# todo md5sum here?
# todo check whether fq are gzipped or not using e.g. if [[ $string == *gz ]], gzip if not
#md5sum ${sample_name}.tar > ${sample_name}_md5.txt

# todo scp the fq files (to sample_name_1.fastq.gz etc) and the json file

sftp -q -i /home/galaxy/.ssh/id_rsa_${nrc_suffix}_${DTAPVM} galaxy@${bigs_fqdn} <<< "put ${sample_name}_to_azure.json.tar mongo/"
sftp -q -i /home/galaxy/.ssh/id_rsa_${nrc_suffix}_${DTAPVM} galaxy@${bigs_fqdn} <<< "put ${sample_name}_md5.txt mongo/"




rm ${sample_name}_to_azure.json

# todo create cronjob on bigsdb side that uses template for fastq (does not exist yet) and converts species names to HD species names using dict and then sftp's everything to Azure (sftp to be set up too)