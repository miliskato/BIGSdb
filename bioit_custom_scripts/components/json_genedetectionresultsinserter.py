from pathlib import Path
import json
import logging

from .json_superclass import JsonSuperClass

class JsonGeneDetectionResultsInserter(JsonSuperClass):
    """
    Class containing definition to insert gene detection results
    """

    def __init__(self, isolatename, species, cur_isolates, cur_seqdef, outputjsondict):
        JsonSuperClass.__init__(self, isolatename, species, cur_isolates, cur_seqdef, outputjsondict)

    def insert_genedetection_results(self, genedetectiondict):
        if genedetectiondict is not None:
            for scheme in genedetectiondict:
                if scheme in self.outputjsondict.keys():
                    # create current clusterdict with names and current cluster
                    clusterdict, ncbi_ab_class_dict = self._create_clusterdict_current_db_version(scheme, genedetectiondict)
                    # Get hits
                    listofhits = self.outputjsondict[scheme]['loci']
                    # this might look something like this currently: "ncbi_amr": {"loci": [{"DB_cluster": "Cluster_973", "Locus": "fosA7.4", "% Identity": "96.07", "HSP/Locus length": "280/423", "Contig": "NODE_3_length_348793_cov_29.301727", "Position in contig": "289059..289338", "Antibiotic(s)": "Fosfomycin", "Accession": "NG_067230.1"}]
                    if listofhits != []:
                        # Storing snapshot Clusters in eav_text_hidden to be used in periodical GeneCluster recalculation
                        for index, hit in enumerate(listofhits):
                            for k,v in hit.items():
                                listofhits[index][k] = v.replace("'","")
                        listofhits_json = json.dumps(listofhits)
                        self.cur_isolates.execute(f"INSERT INTO eav_text_hidden(isolate_id, "
                                             f"field, value)"
                                             f"VALUES((SELECT MAX(id) FROM isolates WHERE isolate='{self.isolatename}'),"
                                             f"'{genedetectiondict[scheme]['schemename_bigsdb']}', '{listofhits_json}') ")
                        eavhtmltable = '<table class="data"><tr><th>GeneCluster</th><th>Locus</th></tr>'
                        clusterhitlist = []  # in case loci that were in different clusters at some point get in the same cluster
                        for hit in listofhits:
                            # allele is always position 1 and accession is always last position (-1)
                            hit['Locus'] = hit['Locus'].replace("'", "")
                            hit_name = '_'.join([hit['Accession'], hit['Locus']])
                            try:
                                clusterhit = clusterdict[hit_name]
                            except:
                                raise RuntimeError('provided input is probably to old compared to current database')
                            # append Cluster
                            eavhtmltable = eavhtmltable + ''.join(
                                ['<tr><td>', ''.join(['GeneCluster', clusterhit.split('Cluster')[1]]), '</td>'])
                            # append Locus
                            if not scheme.endswith('vfdbcore'):
                                eavhtmltable = eavhtmltable + ''.join(
                                    [f'<td><a href="/galaxyreports/{self.species}/', self.isolatename, '/report.html#',
                                     genedetectiondict[scheme]['schemename_html'], '" target="_blank">',
                                     hit['Locus'], '</a></td></tr>'])
                            else:
                                eavhtmltable = eavhtmltable + ''.join(
                                    [f'<td><a href="/galaxyreports/{self.species}/', self.isolatename, '/report.html#',
                                     genedetectiondict[scheme]['schemename_html'], '" target="_blank">',
                                     hit['Gene'], '</a></td></tr>'])

                            if clusterhit not in clusterhitlist:
                                self._insert_allele_designation(clusterhit, 1)
                            clusterhitlist.append(clusterhit)

                            # Part 2 for the AB schemes
                            if genedetectiondict[scheme]['schemename_bigsdb'] == 'NCBI_AMR':
                                ncbi_class = ncbi_ab_class_dict[hit_name]
                                genehit = hit['Locus'].replace('.', '_').replace(' ', '_')
                                self._insert_locus_if_needed(ncbi_class, 'NCBI_AMR_AB_CLASS')
                                self._assign_schememember_if_needed(ncbi_class, 'NCBI_AMR_AB_CLASS')
                                self._insert_dummy_sequence_if_needed(ncbi_class, genehit)
                                self._insert_AD_if_needed(ncbi_class, genehit)

                                for antibiotic in hit['Antibiotic(s)'].split('/'):
                                    ABhit = '_'.join(['NCBI_AMR', antibiotic.upper().replace(' ', '_')])
                                    self._insert_locus_if_needed(ABhit, 'NCBI_AMR_AB')
                                    self._assign_schememember_if_needed(ABhit, 'NCBI_AMR_AB')
                                    self._insert_dummy_sequence_if_needed(ABhit, genehit)
                                    self._insert_AD_if_needed(ABhit, genehit)

                            elif genedetectiondict[scheme]['schemename_bigsdb'] == 'ResFinder':
                                genehit = hit['Locus'].replace('.', '_').replace(' ', '_')
                                for antibiotic in hit['Antibiotic(s)'].split('/'):
                                    ABhit = '_'.join(['ResFinder', antibiotic.upper().replace(' ', '_')])
                                    self._insert_locus_if_needed(ABhit, 'ResFinder_AB')
                                    self._insert_dummy_sequence_if_needed(ABhit, genehit)
                                    self._insert_AD_if_needed(ABhit, genehit)

                        eavhtmltable = eavhtmltable + '</table>'
                        self._insert_metadata(genedetectiondict[scheme]['schemename_bigsdb'], eavhtmltable)
                else:
                    logging.warning(f"scheme {scheme} not present in json file")
            self.cur_isolates.execute(f"INSERT INTO history(isolate_id, timestamp, action, curator)"
                                 f"VALUES((SELECT MAX(id) FROM isolates WHERE isolate='{self.isolatename}'),(SELECT NOW()::TIMESTAMP), 'Gene detection results inserted', 1)")
            logging.info('Gene detection insertion succesful')

    def _create_clusterdict_current_db_version(self, scheme, genedetectiondict):
        # first create a cluster content list
        sequencefile = json.load(open(Path(genedetectiondict[scheme]['metadatafile']), 'r'))
        sequencenamedict = {}
        ncbi_ab_class_dict = {}
        for x in list(sequencefile):
            # sequencename becomes accession concatenated with allele because in e.g. Resfinder, multiple accessions are not unique.
            # sequencefile looks like this: {'seq_0': {'accession': 'NG_047553.1', 'antibiotic': 'Bleomycin', 'allele': '1567214_ble', 'gene': '1567214_ble', 'product': 'BLMA family bleomycin binding protein', 'header_orig': 'NG_047553.1_1567214_ble', 'cluster': 'Cluster_881'}, 'seq_1': {'accession': 'NG_047554.1', 'antibiotic': 'Bleomycin', 'allele': '1567214_ble', 'gene': '1567214_ble', 'product': 'BLMA family bleomycin binding protein', 'header_orig': 'NG_047554.1_1567214_ble', 'cluster': 'Cluster_881'}, 'seq_2': {'accession': 'NG_056058.1', 'antibiotic': 'Carbapenem', 'allele': 'BcII', 'gene': 'BcII', 'product': 'BcII family subclass B1 metallo-beta-lactamase', 'header_orig': 'NG_056058.1_BcII', 'cluster': 'Cluster_561'}, 'seq_3': {'accession': 'NG_047221.1', 'antibiotic': 'Carbapenem', 'allele': 'BcII', 'gene': 'BcII', 'product': 'BcII family subclass B1 metallo-beta-lactamase', 'header_orig': 'NG_047221.1_BcII', 'cluster': 'Cluster_561'}}
            # in VFDB, there are accessions with name "null", this breaks the script, therefore an empty space is added, and the allele should be enough to find.
            if sequencefile[x]['accession'] is None:
                sequencefile[x]['accession'] = "-"
            sequencenamedict[x] = '_'.join(
                [(sequencefile[x]['accession']), (sequencefile[x]['allele']).replace("'", "")])
            if genedetectiondict[scheme]['schemename_bigsdb'] == 'NCBI_AMR':
                ncbi_ab_class_dict['_'.join(
                    [(sequencefile[x]['accession']), (sequencefile[x]['allele']).replace("'", "")])] = '_'.join(
                    ['NCBI_AMR', sequencefile[x]['class'].upper().replace(' ', '_')])

        clusterfile = open(Path(genedetectiondict[scheme]['clusteredfasta']), 'r').readlines()
        clusterdict = {}
        for line in clusterfile:
            # line looks like this: >0__Cluster_0__seq_4648__seq_4648
            if line.startswith('>'):
                # key is sequencename from previous dict, value is cluster
                clusterdict[sequencenamedict[line.split('__')[2]]] = '_'.join(
                    [genedetectiondict[scheme]['schemename_bigsdb'], ''.join(['Gene', line.split('__')[1]])])
                # e.g. sequencenamedict['NG_047553.11567214_ble'] = 'NCBI_AMR_GeneCluster_0'
        return clusterdict, ncbi_ab_class_dict
