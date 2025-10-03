import dataclasses
from bioit_bigsdb_scripts.utils.sequence_typing_results import ListeriaSequenceTypingData, NeisseriaSequenceTypingData, SequenceTypingData
from psycopg.types.json import Jsonb
from bioit_bigsdb_scripts.utils.serotyping_results import NeisseriaSerotypingData, SerotypingData


class JsonMakerSummaryResults:
    """
    subclass used to create the html table for the sequence typîng fields
    """

    def __init__(self, st_data: SequenceTypingData, serotyping_data: SerotypingData | None = None) -> None:
        """
        :param data: SequenceTypingData object containing ST fields common to the different bacterial species
        :param additional_data: optional ListeriaSequenceTypingData or NeisseriaSequenceTypingData object containing species-specific ST fields
        """
        self.st_data = st_data
        if serotyping_data:
            self.serotype_data = serotyping_data

    def get_json_for_sequence_typing(self, additional_data: ListeriaSequenceTypingData | NeisseriaSequenceTypingData | None = None) -> JsonB:
        """
        additional_data: optional ListeriaSequenceTypingData or NeisseriaSequenceTypingData object containing species-specific ST fields
        :return: Json object containing the ST fields
        """
        json_dict = dataclasses.asdict(self.st_data)
        if additional_data:
            json_dict.update(dataclasses.asdict(additional_data))
        return Jsonb(json_dict)

    def get_json_for_serotyping(self, additional_data: NeisseriaSerotypingData | None = None ) -> Jsonb:
        """
        serotype_data: dictionary containing serotyping results
        :return: Json object containing the serotyping results
        """
        if not self.serotyping_data:
            raise ValueError("Serotyping data not provided to JsonMakerSummaryResults")
        json_dict = dataclasses.asdict(self.serotype_data)
        if additional_data:
            json_dict.update(dataclasses.asdict(additional_data))
        return Jsonb(json_dict)