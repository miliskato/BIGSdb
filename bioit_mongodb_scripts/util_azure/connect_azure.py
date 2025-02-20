from datetime import datetime, timedelta, timezone

from azure import batch
from azure.common.credentials import ServicePrincipalCredentials
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient
from azure.storage.blob import AccountSasPermissions, BlobServiceClient, generate_account_sas, ResourceTypes


class ConnectAzure:
    """
    This class is used to connect to the keyvault, the batch service, the blob storage, and the fileshare of a
    specific environment.
    """
    def __init__(self, dtap: str) -> None:
        """
        Initialises this class for a given environment and opens the connection to the keyvault if required.
        :param dtap: environment; dev, test, acc, or prod
        :return: None
        """
        self._dtap = dtap

    def _connect_to_keyvault(self) -> None:
        """
        Connects to keyvault.
        :return: None
        """
        self.credential = DefaultAzureCredential()  # this should take the Managed Identity (which needs to have 'Keyvault secrets user' permissions)
        self.keyvault_client = SecretClient(vault_url=f"https://keyv-weu-{self._dtap}.vault.azure.net",
                                            credential=self.credential)

    def connect_to_batch_client(self) -> batch.BatchServiceClient:
        """
        Connects to batch service.
        :return: Batch service client
        """
        batch_url = f"https://baweu{self._dtap}herawgs.westeurope.batch.azure.com"

        # # Specify Batch account and service principal account credentials
        # Where to get the client secret and id: https://success.myshn.net/Skyhigh_CASB/Skyhigh_CASB_Sanctioned_Apps/Skyhigh_CASB_for_Office_365/Service_Principal_with_a_Secret_Key_and_Azure_API_Integration
        # Initialize the Batch client with Azure AD authentication
        creds = ServicePrincipalCredentials(
            client_id=self.get_secret_value('SP-HERA-SHRD-AZURE-CLIENT-ID'),
            secret=self.get_secret_value('SP-HERA-SHRD-AZURE-CLIENT-SECRET'),
            tenant=self.get_secret_value('TENANT-ID'),
            resource="https://batch.core.windows.net/"
        )
        # Managed identity in defaultcredential can not be used to authenticate to BatchServiceClient yet.
        # The error it gives is: AttributeError: 'ManagedIdentityCredential' object has no attribute 'signed_session'
        batch_client = batch.BatchServiceClient(creds, batch_url)
        return batch_client

    def connect_to_storages(self) -> BlobServiceClient:
        """
        Connects to the blob storage, which is needed to access the files.
        :return: blob service client
        """
        # Instantiate a BlobServiceClient
        input_storage_connection_string = self.get_secret_value(
            'AZURE-STORAGE-CONNECTION-STRING-INPUT')
        blob_service_client_input = BlobServiceClient.from_connection_string(input_storage_connection_string)
        return blob_service_client_input

    def get_secret_value(self, secret_key: str) -> str:
        """
        Returns the secret value of the keyvault for the given secret key.
        :return: str
        """
        secret_value = self.keyvault_client.get_secret(secret_key).value
        return secret_value

    @property
    def sas_token_blobstorage_input(self) -> str:
        """
        Generates a sas token for the input blob storage
        :return: str
        """
        # SAS = shared access signatures
        return generate_account_sas(account_name=self.connect_to_storages().account_name,
                                    account_key=self.connect_to_storages().credential.account_key,
                                    resource_types=ResourceTypes(service=True, container=True, object=True),
                                    permission=AccountSasPermissions(read=True, write=True),
                                    expiry=datetime.now(timezone.utc) + timedelta(weeks=2))
        # Issue: the 48 h here is a bottleneck, but any nr of hrs will be a bottleneck
