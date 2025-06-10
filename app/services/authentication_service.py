import requests
import jwt
from retrying import retry
from datetime import datetime
from app.config.set_logger import set_logger

logger = set_logger(name=__name__)

class AuthenticationService:
    def __init__(self, microsoft_tenant_id, microsoft_app_id, microsoft_app_secret, token_validation_service):
        self.token_store = {}
        self.microsoft_tenant_id = microsoft_tenant_id
        self.microsoft_app_id = microsoft_app_id
        self.microsoft_app_secret = microsoft_app_secret
        self.token_validation_service = token_validation_service
        logger.info("AuthenticationService initialized.")

    def is_jwt_token_expired(self, token):
        jkws = self.token_validation_service.fetch_azure_jkws()
        try:
            unverified_header = jwt.get_unverified_header(token)
            kid = unverified_header['kid']
            public_key = self.token_validation_service.get_public_key(jkws, kid)
            if public_key is None:
                logger.error("Public key not found in JWKS")
                raise Exception('Public key not found in JWKS')
            decoded_token = jwt.decode(token, public_key, algorithms=["RS256"], audience="https://api.botframework.com")
            if "exp" in decoded_token:
                expiration_timestamp = decoded_token["exp"]
                current_timestamp = datetime.utcnow().timestamp()
                if expiration_timestamp < current_timestamp:
                    logger.debug("Token has expired.")
                    return True
                else:
                    logger.debug("Token is still valid.")
                    return False
            else:
                logger.warning("JWT token does not contain 'exp' claim. Consider it as expired.")
                return True  # No 'exp' claim, token is considered not expired

        except jwt.ExpiredSignatureError:
            logger.debug("Token has expired due to ExpiredSignatureError.")
            return True

        except jwt.DecodeError as e:
            logger.error(f"Error decoding JWT token: {e}")
            return True  # Token cannot be decoded, considered expired

    def get_bearer_token(self):
        """
        Gets a bearer token from Azure AD.

        Returns:
            str: The bearer token.
        """
        url = f"https://login.microsoftonline.com/{self.microsoft_tenant_id}/oauth2/v2.0/token"
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        data = {
            "grant_type": "client_credentials",
            "client_id": f"{self.microsoft_app_id}",
            "client_secret": f"{self.microsoft_app_secret}",
            "scope": "https://api.botframework.com/.default",
        }

        try:
            response = requests.post(url, headers=headers, data=data)
            response.raise_for_status()
            response_data = response.json()
            bearer_token = response_data.get("access_token")
            if bearer_token:
                self.store_current_token(bearer_token)
                logger.info("Bearer token acquired and stored.")
                return bearer_token
            else:
                logger.error("Access token not found in the response.")
                raise ValueError("Access token not found in the response.")
        except requests.exceptions.RequestException as e:
            logger.exception(f"Request Exception: {e}")
        except ValueError as e:
            logger.exception(f"Value Error: {e}")
        except Exception as e:
            logger.exception(f"Unexpected Error: {e}")

        return None

    def get_current_token(self):
        return self.token_store.get("current_token")

    def store_current_token(self, token):
        self.token_store["current_token"] = token
        logger.debug("Token stored in token storage.")

    @retry(wait_exponential_multiplier=1000, wait_exponential_max=10000, stop_max_attempt_number=3)
    def get_token_with_retry(self):
        """Retry token fetch up to a maximum of 3 times starting at 1 second delay to a maximum of 10 second delay to retry token fetch"""
        logger.debug("Attempting to fetch token with retry.")
        return self.get_bearer_token()

    def refresh_token_if_needed(self):
        current_token = self.get_current_token()
        if current_token and self.is_jwt_token_expired(current_token):
            logger.debug("Existing token has expired! Creating a new token.")
            try:
                new_token = self.get_token_with_retry()  # Retry token acquisition
                if new_token:
                    self.store_current_token(new_token)
                    logger.debug("New token stored in token storage.")
            except Exception as e:
                logger.error(f"Failed to refresh token: {str(e)}")
        elif not current_token:
            logger.debug("No current token found, acquiring new token.")
            try:
                new_token = self.get_token_with_retry()  # Retry token acquisition for initial token
                if new_token:
                    self.store_current_token(new_token)
                    logger.debug("No current token so created a new token and stored it in token storage.")
            except Exception as e:
                logger.error(f"Failed to acquire initial token: {str(e)}")
