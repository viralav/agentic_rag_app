import os
from dotenv import find_dotenv, load_dotenv
from flask import Flask
import json

from app.config.set_logger import set_logger

from .api.bot_handler import bot_handler as core_blueprint



def create_app():

    app = Flask(__name__)

    app.register_blueprint(
        core_blueprint,
        url_prefix = '/api/v1/core'
    )

    return app