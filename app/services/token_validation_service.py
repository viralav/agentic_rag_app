import requests
from jwt.algorithms import RSAAlgorithm

from app.config.set_logger import set_logger

logger = set_logger(name=__name__)

class TokenValidationService:
    def __init__(self, tenant_id):
        self.tenant_id = tenant_id

    def fetch_azure_jkws(self):
        oidc_config_url = f"https://login.microsoftonline.com/{self.tenant_id}/discovery/v2.0/keys"
        logger.info(f"Fetching Azure JWKs from {oidc_config_url}")
        try:
            response = requests.get(oidc_config_url)
            response.raise_for_status()
            logger.info("Successfully fetched Azure JWKs")
            return response.json()
        except requests.exceptions.RequestException as req_error:
            logger.error(f"Request error while fetching JWT public keys: {req_error}")
            raise
        except Exception as error:
            logger.error(f"Error in fetching JWT public keys: {error}")
            raise

    def get_public_key(self, jwks, kid):
        logger.info(f"Retrieving public key for kid: {kid}")
        try:
            for jwk in jwks['keys']:
                if jwk['kid'] == kid:
                    logger.info(f"Public key found for kid: {kid}")
                    return RSAAlgorithm.from_jwk(jwk)
            logger.warning(f"No public key found for kid: {kid}")
            return None
        except Exception as error:
            logger.error(f"Error retrieving public key: {error}")
            raise
