class UtilUrlGenerator:
    
    @staticmethod
    def create_open_ai_url(base_url, deployment_name):
        return f"{base_url}/openai/deployments/{deployment_name}"

