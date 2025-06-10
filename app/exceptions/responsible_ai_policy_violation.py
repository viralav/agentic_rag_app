from werkzeug.exceptions import HTTPException

class ResponsibleAIPolicyViolation(HTTPException):
    type = 'ResponsibleAIPolicyViolation'
    status_code = 400
    description = "⛔️ ResponsibleAIPolicyViolation ⛔️"


    def __init__(self, description=None, query=""):
        if description:
            self.description = f"""{self.description}
            <br/><br/>
            <code>{query}</code>
            <br/><br/>
            prompt input is blocked by safety system.


{description}"""
        super().__init__()