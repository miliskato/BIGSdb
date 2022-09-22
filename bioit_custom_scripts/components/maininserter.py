import logging


class MainInserter:
    """
    Class containing all queries for Mongo
    """

    def __init__(self):
        pass

    def insert_main(self, isolatename, species, cur_isolates, outputtsvdict):
        reportlink = f'<p><a href="/galaxyreports/{species}/{isolatename}/report.html" target="_blank"> html report</a></p>'
        cur_isolates.execute(f"INSERT INTO eav_text(isolate_id, "
                    f"field, value)"
                    f"VALUES((SELECT MAX(id) FROM isolates WHERE isolate='{isolatename}'),"
                    f"'html', '{reportlink}') ")
        cur_isolates.execute(f"INSERT INTO eav_text(isolate_id, "
                    f"field, value)"
                    f"VALUES((SELECT MAX(id) FROM isolates WHERE isolate='{isolatename}'),"
                    f"'tsv', '{reportlink.replace('html', 'tsv')}') ")
        self._insert_species_specific(isolatename, species, cur_isolates, outputtsvdict)
        logging.info('Metadata insertion succesful')
    
    def _insert_species_specific(self, isolatename, species, cur_isolates, outputtsvdict):
        if species == 'mycobacterium':
            if '51SNP-gyrB_group' in outputtsvdict:
                cur_isolates.execute(f"INSERT INTO eav_text(isolate_id, "
                            f"field, value)"
                            f"VALUES((SELECT MAX(id) FROM isolates WHERE isolate='{isolatename}'),"
                            f"'gyrB_group', '{outputtsvdict['51SNP-gyrB_group']}') ")
                cur_isolates.execute(f"INSERT INTO eav_text(isolate_id, "
                            f"field, value)"
                            f"VALUES((SELECT MAX(id) FROM isolates WHERE isolate='{isolatename}'),"
                            f"'Genetic_group', '{outputtsvdict['51SNP-genetic_group']}') ")
                cur_isolates.execute(f"INSERT INTO eav_text(isolate_id, "
                            f"field, value)"
                            f"VALUES((SELECT MAX(id) FROM isolates WHERE isolate='{isolatename}'),"
                            f"'SCG', '{outputtsvdict['51SNP-scg']}') ")
            cur_isolates.execute(f"INSERT INTO eav_text(isolate_id, "
                        f"field, value)"
                        f"VALUES((SELECT MAX(id) FROM isolates WHERE isolate='{isolatename}'),"
                        f"'snpit_species', '{outputtsvdict['snpit_species']}') ")
            cur_isolates.execute(f"INSERT INTO eav_text(isolate_id, "
                        f"field, value)"
                        f"VALUES((SELECT MAX(id) FROM isolates WHERE isolate='{isolatename}'),"
                        f"'snpit_lineage', '{outputtsvdict['snpit_lineage']}') ")
            cur_isolates.execute(f"INSERT INTO eav_text(isolate_id, "
                        f"field, value)"
                        f"VALUES((SELECT MAX(id) FROM isolates WHERE isolate='{isolatename}'),"
                        f"'snpit_sublineage', '{outputtsvdict['snpit_sublineage']}') ")
        elif species == 'stec':
            cur_isolates.execute(f"INSERT INTO eav_text(isolate_id, "
                        f"field, value)"
                        f"VALUES((SELECT MAX(id) FROM isolates WHERE isolate='{isolatename}'),"
                        f"'Serotype', '{outputtsvdict['serotype']}') ")