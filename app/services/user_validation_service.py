from flask import jsonify
import msal
import requests

from app.config.set_logger import set_logger

logger = set_logger(name=__name__)

class UserValidationService:
    def __init__(self, tenant_id, client_id, client_secret):
        self.tenant_id = tenant_id
        self.client_id = client_id
        self.client_secret = client_secret
        
        self.authority = f'https://login.microsoftonline.com/{self.tenant_id}'
        self.scope = ['https://graph.microsoft.com/.default']
        self.graph_api_endpoint = 'https://graph.microsoft.com/v1.0'
        logger.info(f"UserValidationService initialized with tenant_id: {tenant_id}")

    def validate_tenant_id(self, tenant_id):
        valid = tenant_id == self.tenant_id
        if valid:
            logger.info(f"Tenant ID {tenant_id} is valid.")
        else:
            logger.warning(f"Tenant ID {tenant_id} is invalid.")
        return valid

    def validate_user(self, user_aad_id):
        logger.info(f"Validating user with AAD ID: {user_aad_id}")
        self.token = self.get_access_token()
        if not self.token:
            logger.error("Could not get access token")
            return False

        user_exists = self.check_user_exists(user_aad_id)
        if user_exists:
            logger.info(f"User {user_aad_id} exists.")
        else:
            logger.warning(f"User {user_aad_id} does not exist.")
        return user_exists

    def get_access_token(self):
        logger.info("Acquiring access token from Azure AD")
        app = msal.ConfidentialClientApplication(
            self.client_id, authority=self.authority,
            client_credential=self.client_secret)

        result = app.acquire_token_for_client(scopes=self.scope)
        if "access_token" in result:
            logger.info("Access token acquired successfully")
            return result['access_token']
        else:
            logger.error(f"Could not acquire token: {result.get('error')}, {result.get('error_description')}")
            return None

    def check_user_exists(self, aad_id):
        logger.info(f"Checking if user {aad_id} exists in Microsoft Graph")
        headers = {
            'Authorization': f'Bearer {self.token}',
            'Content-Type': 'application/json'
        }
        query = f"{self.graph_api_endpoint}/users/{aad_id}"
        response = requests.get(query, headers=headers)

        if response.status_code == 200:
            logger.info(f"User {aad_id} found in Microsoft Graph")
            return True
        elif response.status_code == 404:
            logger.warning(f"User {aad_id} not found in Microsoft Graph")
            return False
        else:
            logger.error(f"Error querying Graph API: {response.status_code}, {response.text}")
            return False
