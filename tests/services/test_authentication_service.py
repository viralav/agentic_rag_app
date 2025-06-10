import os
import unittest
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta
import requests

from app.services.authentication_service import AuthenticationService

class TestAuthenticationService(unittest.TestCase):

    def setUp(self):
        self.microsoft_tenant_id = "tenant_id"
        self.microsoft_app_id = "app_id"
        self.microsoft_app_secret = "app_secret"
        self.mock_token_validation_service = MagicMock()
        self.auth_service = AuthenticationService(
            self.microsoft_tenant_id,
            self.microsoft_app_id,
            self.microsoft_app_secret,
            self.mock_token_validation_service
        )
    
    @patch('jwt.decode')
    @patch('jwt.get_unverified_header')
    def test_is_jwt_token_expired_valid_token(self, mock_get_unverified_header, mock_decode):
        token = "valid_token"
        mock_get_unverified_header.return_value = {'kid': 'valid_kid'}
        self.mock_token_validation_service.get_public_key.return_value = 'public_key'
        mock_decode.return_value = {'exp': (datetime.utcnow() + timedelta(hours=1)).timestamp()}
        
        result = self.auth_service.is_jwt_token_expired(token)
        
        self.assertFalse(result)
        self.mock_token_validation_service.get_public_key.assert_called_once_with(self.mock_token_validation_service.fetch_azure_jkws(), 'valid_kid')
        mock_decode.assert_called_once_with(token, 'public_key', algorithms=["RS256"], audience="https://api.botframework.com")
    
    @patch('jwt.decode')
    @patch('jwt.get_unverified_header')
    def test_is_jwt_token_expired_expired_token(self, mock_get_unverified_header, mock_decode):
        token = "expired_token"
        mock_get_unverified_header.return_value = {'kid': 'valid_kid'}
        self.mock_token_validation_service.get_public_key.return_value = 'public_key'
        mock_decode.return_value = {'exp': (datetime.utcnow() - timedelta(hours=1)).timestamp()}
        
        result = self.auth_service.is_jwt_token_expired(token)
        
        self.assertTrue(result)
    
    @patch('requests.post')
    def test_get_bearer_token_success(self, mock_post):
        response_mock = MagicMock()
        response_mock.json.return_value = {'access_token': 'test_token'}
        response_mock.raise_for_status.return_value = None
        mock_post.return_value = response_mock
        
        result = self.auth_service.get_bearer_token()
        
        self.assertEqual(result, 'test_token')
        self.assertEqual(self.auth_service.get_current_token(), 'test_token')
    
    @patch('requests.post')
    def test_get_bearer_token_failure(self, mock_post):
        mock_post.side_effect = requests.exceptions.RequestException
        
        result = self.auth_service.get_bearer_token()
        
        self.assertIsNone(result)
    
    @patch('requests.post')
    @patch('jwt.decode')
    @patch('jwt.get_unverified_header')
    def test_refresh_token_if_needed_expired_token(self, mock_get_unverified_header, mock_decode, mock_post):
        expired_token = "expired_token"
        new_token = "new_token"
        self.auth_service.store_current_token(expired_token)
        
        mock_get_unverified_header.return_value = {'kid': 'valid_kid'}
        self.mock_token_validation_service.get_public_key.return_value = 'public_key'
        mock_decode.return_value = {'exp': (datetime.utcnow() - timedelta(hours=1)).timestamp()}
        
        response_mock = MagicMock()
        response_mock.json.return_value = {'access_token': new_token}
        response_mock.raise_for_status.return_value = None
        mock_post.return_value = response_mock
        
        self.auth_service.refresh_token_if_needed()
        
        self.assertEqual(self.auth_service.get_current_token(), new_token)
    
    @patch('requests.post')
    @patch('jwt.decode')
    @patch('jwt.get_unverified_header')
    def test_refresh_token_if_needed_no_current_token(self, mock_get_unverified_header, mock_decode, mock_post):
        new_token = "new_token"
        
        response_mock = MagicMock()
        response_mock.json.return_value = {'access_token': new_token}
        response_mock.raise_for_status.return_value = None
        mock_post.return_value = response_mock
        
        self.auth_service.refresh_token_if_needed()
        
        self.assertEqual(self.auth_service.get_current_token(), new_token)

if __name__ == '__main__':
    unittest.main()
