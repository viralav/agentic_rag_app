import os
import unittest
from unittest import mock
import requests
from unittest.mock import patch, MagicMock
from app.services.user_validation_service import UserValidationService

class TestUserValidationService(unittest.TestCase):
    def setUp(self):
        self.mock_client_id = 'mock_client_id'
        self.mock_client_secret = 'mock_client_secret'
        self.mock_tenant_id = 'mock_tenant_id'  # Invalid tenant ID causing the issue
        self.mock_aad_id = 'mock_aad_id'
        self.mock_user_endpoint = f'https://graph.microsoft.com/v1.0/users/{self.mock_aad_id}'
        self.mock_token = 'mock_access_token'

        # Mock get_access_token to prevent actual authentication
        self.mock_get_access_token = patch.object(UserValidationService, 'get_access_token', return_value='mock_access_token')
        self.mock_get_access_token.start()

        # Mock requests.get for validating user existence
        self.mock_get = patch('requests.get', side_effect=self.mock_requests_get)
        self.mock_get.start()

        # Initialize the service
        self.service = UserValidationService(
            self.mock_tenant_id, self.mock_client_id, self.mock_client_secret)

    def tearDown(self):
        self.mock_get_access_token.stop()
        self.mock_get.stop()

    def mock_requests_get(self, url, headers=None):
        # Mock the response from requests.get for user existence check
        if url == self.mock_user_endpoint:
            mock_response = MagicMock()
            if headers.get('Authorization') == f'Bearer {self.service.token}':
                mock_response.status_code = 200
                mock_response.text = '{"id": "mock_aad_id"}'
            else:
                mock_response.status_code = 401
            return mock_response
        elif url == 'https://graph.microsoft.com/v1.0/users/non_existing_aad_id':
            mock_response = MagicMock()
            mock_response.status_code = 404
            return mock_response
        elif url == 'https://graph.microsoft.com/v1.0/users/invalid_json_aad_id':
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.text = '{"invalid_json"'
            return mock_response  # Invalid JSON intentionally returned
        else:
            return MagicMock()


    @patch.object(UserValidationService, 'get_access_token', return_value='mock_access_token')
    def test_validate_tenant_id(self, mock_get_access_token):
        self.assertTrue(self.service.validate_tenant_id(self.mock_tenant_id))
        self.assertFalse(self.service.validate_tenant_id('invalid_tenant_id'))

    @patch('requests.get')
    def test_validate_user_exists(self, mock_get):
        # Mocking a successful response for user existence
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        self.assertTrue(self.service.validate_user(self.mock_aad_id))

        # Verify that requests.get was called with the correct endpoint and headers
        mock_get.assert_called_once_with(self.mock_user_endpoint, headers={
            'Authorization': f'Bearer {self.mock_token}',
            'Content-Type': 'application/json'
        })

    @patch('requests.get')
    def test_validate_user_not_exists(self, mock_get):
        # Mocking a 404 response for user non-existence
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response

        self.assertFalse(self.service.validate_user(self.mock_aad_id))

        # Verify that requests.get was called with the correct endpoint and headers
        mock_get.assert_called_once_with(self.mock_user_endpoint, headers={
            'Authorization': f'Bearer {self.mock_token}',
            'Content-Type': 'application/json'
        })

    @patch('requests.get')
    def test_validate_user_server_error(self, mock_get):
        # Mocking a server error response
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_get.return_value = mock_response

        self.assertFalse(self.service.validate_user(self.mock_aad_id))

        # Verify that requests.get was called with the correct endpoint and headers
        mock_get.assert_called_once_with(self.mock_user_endpoint, headers={
            'Authorization': f'Bearer {self.mock_token}',
            'Content-Type': 'application/json'
        })

    @patch('requests.get')
    def test_validate_user_unexpected_status_code(self, mock_get):

        # Mocking an unexpected status code
        mock_response = MagicMock()
        mock_response.status_code = 403  # Example of an unexpected status code
        mock_get.return_value = mock_response

        self.assertFalse(self.service.validate_user(self.mock_aad_id))

        # Verify that requests.get was called with the correct endpoint and headers
        mock_get.assert_called_once_with(self.mock_user_endpoint, headers={
            'Authorization': f'Bearer {self.mock_token}',
            'Content-Type': 'application/json'
        })

    # @patch.object(UserValidationService, 'get_access_token', return_value=None)
    # def test_validate_user_no_token(self, mock_get_access_token):
    #     self.assertFalse(self.service.validate_user(self.mock_aad_id))

    def test_validate_user_request_exception(self):
        # Test validate_user for a scenario where a request exception occurs
        self.assertFalse(self.service.validate_user('connection_error_aad_id'))

    @patch('requests.get')
    def test_validate_user_invalid_json(self, mock_get):
        self.assertFalse(self.service.validate_user('invalid_json_aad_id'))

    def test_validate_user_timeout(self):
        self.assertFalse(self.service.validate_user('timeout_aad_id'))


    # Additional test cases can be added to cover more edge cases, such as malformed URL, network errors, etc.

if __name__ == '__main__':
    unittest.main()

