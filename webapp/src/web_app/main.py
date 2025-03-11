from flask import Flask
from src.database.database import init_db
from src.utils.logging_config import get_logger
from src.utils.config import config
from src.web_app.routes import views, aggregator

logger = get_logger('web_app')

def create_app():
    """Create and configure the Flask application."""
    logger.info("Creating Flask application")
    
    app = Flask(__name__)
    
    # Configure the app
    app.config['SECRET_KEY'] = config.web.secret_key
    app.config['SQLALCHEMY_DATABASE_URI'] = config.get_database_url()
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    # Register blueprints
    app.register_blueprint(views.views_bp)
    app.register_blueprint(aggregator.aggregator_bp, url_prefix='/api/v1/aggregator')
    
    # Initialize database
    logger.info("Initializing database")
    init_db(app)
    
    return app

if __name__ == '__main__':
    app = create_app()
    web_config = config.get_web_config()
    logger.info(f"Starting web server on {web_config['host']}:{web_config['port']}")
    app.run(
        host=web_config['host'],
        port=web_config['port'],
        debug=web_config['debug']
    ) 