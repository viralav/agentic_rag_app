from dotenv import find_dotenv, load_dotenv
import requests
from azure.storage.blob import BlobServiceClient, generate_blob_sas, BlobSasPermissions
import uuid
from datetime import datetime
from dateutil.relativedelta import relativedelta
from app.config.set_logger import set_logger

logger = set_logger(name=__name__)

class AzureBlobService:
    def __init__(self, blob_account_name, blob_account_key, blob_container_name):
        self.blob_account_name = blob_account_name
        self.blob_account_key = blob_account_key
        self.blob_container_name = blob_container_name
        
        # Create the BlobServiceClient object which will be used to create a container client
        self.blob_service_client = BlobServiceClient(
            account_url=f"https://{self.blob_account_name}.blob.core.windows.net",
            credential=self.blob_account_key
        )
        
        # Ensure the container exists
        self.container_client = self.blob_service_client.get_container_client(self.blob_container_name)
        logger.info(f"AzureBlobService initialized for account: {self.blob_account_name} and container: {self.blob_container_name}")

    def upload_file(self, file_url):
        try:
            blob_name = str(uuid.uuid4()) + '.png'
            logger.debug(f"Generated blob name: {blob_name}")

            # Download the file from the URL
            response = requests.get(file_url)
            response.raise_for_status()  # Check if the request was successful
            logger.info(f"Downloaded file from URL: {file_url}")

            # Create a blob client using the blob name
            blob_client = self.container_client.get_blob_client(blob_name)
            logger.debug(f"Created blob client for blob: {blob_name}")

            # Upload the file content
            blob_client.upload_blob(response.content, overwrite=True)
            logger.info(f"Uploaded file to blob: {blob_name}")
            return blob_name

        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to download the file from URL: {e}")
        except Exception as ex:
            logger.exception(f"An error occurred while uploading file: {ex}")
    
    def generate_sas_url(self, blob_name):
        try:
            # Generate SAS token with read permission and 1 month expiry
            sas_token = generate_blob_sas(
                account_name=self.blob_account_name,
                container_name=self.blob_container_name,
                blob_name=blob_name,
                account_key=self.blob_account_key,
                permission=BlobSasPermissions(read=True),
                expiry=datetime.now() + relativedelta(months=1)
            )
            blob_url_with_sas = f"https://{self.blob_account_name}.blob.core.windows.net/{self.blob_container_name}/{blob_name}?{sas_token}"
            logger.info(f"Generated SAS URL for blob: {blob_name}")
            return blob_url_with_sas

        except Exception as ex:
            logger.exception(f"Failed to generate SAS token for blob: {blob_name} - {ex}")
