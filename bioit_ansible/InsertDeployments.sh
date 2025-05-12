#!/bin/bash

SPECIES=$1
DTAP=$2
COMMIT_SHA=$3
BRANCH=$4
GIT_TAG=$5
ANSIBLE_TAGS=$6
ANSIBLE_SKIP_TAGS=$7
WHO=$8
FILE="$SPECIES.json"

TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

if [[ ! -f "$FILE" ]]; then
    echo "[]" > "$FILE"
    echo "$FILE created."
fi

# Remove the last closing bracket
sed -i '$ s/]$//' "$FILE"
# Replace the last } with },
sed -i ':a;N;$!ba;s/}\s*$/},/' "$FILE"

# Append the new entry
echo "    {" >> "$FILE"
echo "        \"dtap\": \"$DTAP\"," >> "$FILE"
echo "        \"branch\": \"$BRANCH\"," >> "$FILE"
echo "        \"commitSha\": \"$COMMIT_SHA\"," >> "$FILE"
echo "        \"tag\": \"$GIT_TAG\"," >> "$FILE"
echo "        \"ansibleTags\": \"$ANSIBLE_TAGS\"," >> "$FILE"
echo "        \"ansibleSkipTags\": \"$ANSIBLE_SKIP_TAGS\"," >> "$FILE"
echo "        \"when\": \"$TIMESTAMP\"," >> "$FILE"
echo "        \"who\": \"$WHO\"" >> "$FILE"
echo "    }" >> "$FILE"

# Close the JSON array
echo "]" >> "$FILE"

echo "Deployment info added to $FILE"