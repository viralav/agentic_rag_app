from os import environ, path

class BaseConfig(object):
    '''Base configuration'''

    APP_NAME = environ.get('APP_NAME') or 'BOT_BACKEND'
    DEBUG = True

class Development(BaseConfig):
    ''' Development configuration '''
    DEBUG = True
    ENV = 'development'


class Staging(BaseConfig):
    ''' Staging configuration '''
    DEBUG = True
    ENV = 'staging'

class Production(BaseConfig):
    ''' Production configuration '''
    DEBUG = False
    ENV = 'production'

config = {
    'development': Development,
    'staging': Staging,
    'production': Production,
}


def get_environment():
    return environ.get('APPLICATION_ENV') or 'development'