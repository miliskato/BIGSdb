import dataclasses
from typing import Optional

from factories.main_results_factory import ListeriaSequenceTypingData, NeisseriaSequenceTypingData, SequenceTypingData
from factories.main_results_factory import NeisseriaSerotypingData, SerotypingData
from psycopg.types.json import Jsonb


class JsonMakerSummaryResults:
    """
    subclass used to create the html table for the sequence typîng fields
    """

    def __init__(self, sequence_typing_data: SequenceTypingData, serotyping_data: SerotypingData | None = None) -> None:
        """
        :param sequence_typing_data: SequenceTypingData object containing sequence typing related fields common to the different bacterial species
        :param serotyping_data: optional SerotypingData object containing serotyping related fields
        """
        self.sequence_typing_data = sequence_typing_data
        if serotyping_data:
            self.serotyping_data = serotyping_data

    def get_json_for_sequence_typing(self, additional_data: ListeriaSequenceTypingData | NeisseriaSequenceTypingData | None = None) -> dict:
        """
        additional_data: optional ListeriaSequenceTypingData or NeisseriaSequenceTypingData object containing species-specific ST fields
        :return: dict containing the ST fields
        """
        json_dict = dataclasses.asdict(self.sequence_typing_data)
        if additional_data:
            json_dict.update(dataclasses.asdict(additional_data))
        return json_dict

    def get_json_for_serotyping(self, additional_data: NeisseriaSerotypingData | None = None ) -> Optional[dict]:
        """
        serotype_data: dictionary containing serotyping results
        :return: dict containing the serotyping results
        """
        if not self.serotyping_data:
            return None
        json_dict = dataclasses.asdict(self.serotyping_data)
        if additional_data:
            json_dict.update(dataclasses.asdict(additional_data))
        return json_dict

    def create_binary_json(self, additional_sequencing_data: ListeriaSequenceTypingData | NeisseriaSequenceTypingData | None = None, additional_serotyping_data: NeisseriaSerotypingData | None = None) -> Jsonb:
        """
        Create the final json object containing all the sequencing results
        :param additional_sequencing_data: optional dictionary containing additional species specific sequencing results to be added to the json
        :param additional_serotyping_data: optional dictionary containing additional species specific serotyping results to be added to the json
        :return: Jsonb object containing all the sequencing results
        """
        st_results = self.get_json_for_sequence_typing(additional_sequencing_data)
        sg_results = self.get_json_for_serotyping(additional_serotyping_data)
        result_dict = {
                "st_results": st_results,
                **({"sg_results": sg_results} if sg_results is not None else {})
        }
        return Jsonb(result_dict)
