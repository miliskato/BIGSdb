from bioit_bigsdb_scripts.components.python_utility_functions import get_bigsdb_config_data


class FailSafe:
    def __init__(self, results_type: str, isolatename: str):
        self._results_type = results_type
        self._isolatename = isolatename
        self._bigsdb_config_data = get_bigsdb_config_data()

    def ___make_flagfilepath(self) -> Path:
        """
        Returns the flag file path
        :return: flag file path
        """
        return Path(self._bigsdb_config_data['failsafe']['flag_dir']) / '.'.join([self._isolatename, self._bigsdb_config_data['failsafe']['flag_append']])

    def __fail_safe_mechanism(self, isolates_psql_tbl: TblIsolates) -> None:
        """
        Creates a flagfile if insertion is started and no flagfile is present.
        else insertion is started and flag file is present: remove highest version of sample and
        reinsert if multiple versions, if only one version, sample is reinserted in the main workflow below
        :param isolates_psql_tbl: isolates db isolates table/ connection instance for a given species
        :return: None
        """
        try:
            if not Path(self._bigsdb_config_data['failsafe']['flag_dir']).is_dir():
                Path(self._bigsdb_config_data['failsafe']['flag_dir']).mkdir(parents=True, exist_ok=True)
                Path(self._bigsdb_config_data['failsafe']['flag_dir']).chmod(0o755)
            flagfilepath = self.___make_flagfilepath()
            if flagfilepath.is_file() and not (self._results_type == 'reanalysis' or self._results_type == 'resequencing'):
                logging.warning(
                    f"fail safe mechanism detects that the bigsdb insertion for sample {self._isolatename} was started but did not finish. Removing {self._isolatename} from Bigsdb to be able to restart inserting.")
                isolates_psql_tbl.delete_isolate([self._isolatename])
                self._nominative_labtest_clinical_metadata_collection.update_one({'_id': self._isolatename},
                                                                                 {'$set': {'inserted_into_bigsdb': False}})
            else:
                flagfilepath.touch()
                flagfilepath.chmod(0o755)
                logging.info(f"flagfilepath {flagfilepath}")
        except Exception as exceptionmessage:
            send_email(f"{exceptionmessage}\n{traceback.format_exc()}",
                       f"{Path(__file__).name}: bigsdb upload fail safe mechanism fail on host {socket.gethostname()}")
            raise Exception(
                f"{Path(__file__).name}: bigsdb upload fail safe mechanism fail on host {socket.gethostname()}")

    def __delete_flagfile(self) -> None:
        """
        :return: None, Removes flagfile
        """
        flagfilepath: Path = self.___make_flagfilepath()
        try:
            flagfilepath.unlink()
        except Exception as exceptionmessage:
            send_email(f"{exceptionmessage}\n{traceback.format_exc()}",
                       f"{Path(__file__).name}: Could not remove flag file {flagfilepath} on host {socket.gethostname()}")
            raise Exception(
                f"{Path(__file__).name}: Could not remove flag file {flagfilepath} on host {socket.gethostname()}")

