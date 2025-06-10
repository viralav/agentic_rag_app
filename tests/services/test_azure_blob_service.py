import os
import unittest
from unittest import mock
from unittest.mock import MagicMock, patch
import requests
from azure.storage.blob import BlobServiceClient, BlobClient, ContainerClient
from app.services.azure_blob_service import AzureBlobService  # Replace 'mymodule' with the actual module name where AzureBlobService is defined

class TestAzureBlobService(unittest.TestCase):

    @patch('app.services.azure_blob_service.BlobServiceClient')
    def setUp(self, MockBlobServiceClient):
        # Mock BlobServiceClient and ContainerClient
        self.mock_blob_service_client = MockBlobServiceClient.return_value
        self.mock_container_client = MagicMock()
        self.mock_blob_service_client.get_container_client.return_value = self.mock_container_client

        # Initialize AzureBlobService with dummy parameters
        self.azure_blob_service = AzureBlobService(
            blob_account_name="dummy_account_name",
            blob_account_key="dummy_account_key",
            blob_container_name="dummy_container_name"
        )

    @patch('app.services.azure_blob_service.requests.get')
    def test_upload_file_success(self, mock_requests_get):
        # Arrange
        file_url = "http://example.com/test.png"
        blob_name = "dummy_blob.png"
        mock_response = MagicMock()
        mock_response.content = b"dummy_content"
        mock_response.raise_for_status = MagicMock()
        mock_requests_get.return_value = mock_response
        
        mock_blob_client = MagicMock()
        self.mock_container_client.get_blob_client.return_value = mock_blob_client

        # Act
        result = self.azure_blob_service.upload_file(file_url)

        # Assert
        self.assertTrue(result.endswith('.png'))
        mock_requests_get.assert_called_once_with(file_url)
        mock_response.raise_for_status.assert_called_once()
        mock_blob_client.upload_blob.assert_called_once_with(mock_response.content, overwrite=True)

    @patch('app.services.azure_blob_service.requests.get')
    def test_upload_file_request_exception(self, mock_requests_get):
        # Arrange
        file_url = "http://example.com/test.png"
        mock_requests_get.side_effect = requests.exceptions.RequestException("Request failed")

        # Act
        result = self.azure_blob_service.upload_file(file_url)

        # Assert
        self.assertIsNone(result)
        mock_requests_get.assert_called_once_with(file_url)

    @patch('app.services.azure_blob_service.generate_blob_sas')
    def test_generate_sas_url_success(self, mock_generate_blob_sas):
        # Arrange
        blob_name = "dummy_blob.png"
        sas_token = "dummy_sas_token"
        mock_generate_blob_sas.return_value = sas_token

        # Act
        result = self.azure_blob_service.generate_sas_url(blob_name)

        # Assert
        expected_url = f"https://dummy_account_name.blob.core.windows.net/dummy_container_name/{blob_name}?{sas_token}"
        self.assertEqual(result, expected_url)
        mock_generate_blob_sas.assert_called_once()

    @patch('app.services.azure_blob_service.generate_blob_sas')
    def test_generate_sas_url_exception(self, mock_generate_blob_sas):
        # Arrange
        blob_name = "dummy_blob.png"
        mock_generate_blob_sas.side_effect = Exception("SAS generation failed")

        # Act
        result = self.azure_blob_service.generate_sas_url(blob_name)

        # Assert
        self.assertIsNone(result)
        mock_generate_blob_sas.assert_called_once()

if __name__ == '__main__':
    unittest.main()
