class ResponseFunctionDictionary:
    def __init__(self, response_dict):
        self.response_dict = response_dict
    
    def __getattr__(self, name):
        if name in self.response_dict:
            return self.response_dict[name]
        else:
            raise AttributeError(f"'{type(self).__name__}' object has no attribute '{name}'")