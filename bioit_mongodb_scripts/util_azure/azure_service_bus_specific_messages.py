from bioit_mongodb_scripts.util_azure.azure_message_base import AzureMessageBase


class AzureServiceBusMessage(AzureMessageBase):
    """
    This class contains methods to handle a single Azure service bus message.
    """
    def __init__(self, pseudo_id: str, collection: str):
        """
        This method initialises this class
        :param pseudo_id: the pseudo id of the isolate
        :param collection: the collection that the isolate has been inserted in
        """
        self.pseudo_id = pseudo_id
        self.collection = collection


class AzureServiceBusSubmissionMessage(AzureMessageBase):
    """
    This class contains methods to handle a single Azure service bus submission message.
    """

    def __init__(self, species: str):
        """
        This method initialises this class
        :param species: the species for which a submission was processed by batch
        """
        self.species = species
