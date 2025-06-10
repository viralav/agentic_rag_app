from werkzeug.exceptions import HTTPException

class OpenAILimitExceeded(HTTPException):
    type = 'OpenAILimitExceeded'
    status_code = 429
    description = "🧱 OpenAILimitExceeded 🧱"


    def __init__(self, description=None):
        if description:
            self.description = f"""{self.description}
            <br/><br/>
            <code>{description}</code>"""
        super().__init__()