from dotenv import load_dotenv, find_dotenv
import os

load_dotenv(find_dotenv())

from app.create_app import create_app


app = create_app()


@app.route('/health', methods=['GET'])
@app.route('/', methods=['GET'])
def status():
    return "Bot Backend Is Alive 🚀🚀🚀"

if __name__ == '__main__':
    app.run()