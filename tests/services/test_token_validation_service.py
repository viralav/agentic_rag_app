import os
import unittest
from unittest import mock
from unittest.mock import patch, MagicMock
from jwt.algorithms import RSAAlgorithm
from app.services.token_validation_service import TokenValidationService


class TestTokenValidationService(unittest.TestCase):

    @patch('requests.get')
    def test_fetch_azure_jkws_success(self, mock_get):
        # Mocking the requests.get method
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'keys': [{'kid': 'test_kid', 'kty': 'RSA', 'n': 'test_n', 'e': 'AQAB'}]}
        mock_get.return_value = mock_response

        # Setting up the test
        service = TokenValidationService(tenant_id='test_tenant_id')
        jwks = service.fetch_azure_jkws()

        # Assertions
        self.assertIsNotNone(jwks)
        self.assertIn('keys', jwks)
        self.assertEqual(len(jwks['keys']), 1)
        self.assertEqual(jwks['keys'][0]['kid'], 'test_kid')

    # def test_get_public_key_found(self):
    #     # Setting up a mock JWKS and kid
    #     mock_jwks = {'keys': [{'kid': 'test_kid', 'kty': 'RSA', 'n': 'test_n', 'e': 'AQAB'}]}
    #     service = TokenValidationService(tenant_id='test_tenant_id')

    #     # Calling the method
    #     public_key = service.get_public_key(mock_jwks, 'test_kid')

    #     # Assertions
    #     self.assertIsInstance(public_key, RSAAlgorithm)
    #     self.assertEqual(public_key.kid, 'test_kid')

    def test_get_public_key_not_found(self):
        # Setting up a mock JWKS and a non-existent kid
        mock_jwks = {'keys': [{'kid': 'test_kid', 'kty': 'RSA', 'n': 'test_n', 'e': 'AQAB'}]}
        service = TokenValidationService(tenant_id='test_tenant_id')

        # Calling the method with a non-existent kid
        public_key = service.get_public_key(mock_jwks, 'non_existent_kid')

        # Assertions
        self.assertIsNone(public_key)

if __name__ == '__main__':
    unittest.main()
