from MongoDB.config import HIERCC_CONFIG
import subprocess
import logging
import hashlib
import shutil


class MongoInitHierCCClustering:
    def __init__(self, species: str):
        self.species = species

    def run_initial_clustering(self):
        logging.getLogger().setLevel(logging.INFO)
        logging.info(f"Running HierCC tool for clustering")
        self.__run_hiercc()
        logging.info(f"Running of HierCC finished")
        shutil.copyfile(HIERCC_CONFIG[self.species]['initial_clustering'], HIERCC_CONFIG[self.species]['running_clustering'])


    def __run_hiercc(self) -> None:
        """
        Runs the HierCC clustering tool in command line.
        :return:
        """
        command = f"module load phiercc;" \
                  f" pHierCC -p {HIERCC_CONFIG[self.species]['running_st']} " \
                  f"-o {HIERCC_CONFIG[self.species]['initial_clustering'].replace('.HierCC.gz', '')} "
        out = subprocess.run(
            command,
            shell=True,
            executable='/bin/bash')
        try:
            check_file_after_run = hashlib.md5(open(HIERCC_CONFIG[self.species]['npz_file'], 'rb').read()).hexdigest()
        except:
            raise RuntimeError("HierCC doesn't seem to have run as the npz file is not present. Check for exceptions!")
