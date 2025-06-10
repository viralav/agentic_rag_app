class HelperMethods:
    
    @staticmethod
    def add_logging_context(data):
        try:
            return {'custom_dimensions' : {'user_id' : data['from']['aadObjectId']}}
        except KeyError:
            return {'custom_dimensions' : {'user_id' : ''}}
