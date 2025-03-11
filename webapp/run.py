import os
import sys
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Add the project root directory to the Python path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

from src.web_app.main import create_app
from src.utils.logging_config import get_logger

logger = get_logger('main')

if __name__ == '__main__':
    app = create_app()
    from src.utils.config import config
    web_config = config.get_web_config()
    logger.info(f"Starting web server on {web_config['host']}:{web_config['port']}")
    app.run(
        host=web_config['host'],
        port=web_config['port'],
        debug=web_config['debug']
    ) 