import os
from flask import Flask
from ..database.database import db
from ..utils.logging_config import setup_logger
from .routes.views import views_bp
from .routes.metrics import metrics_bp
from .routes.aggregator import aggregator_bp
from .routes.reporting import reporting_bp
from .routes.stocks import stocks_bp

logger = setup_logger('web_app')

def create_app(test_config=None):
    # Create and configure the app
    app = Flask(__name__, instance_relative_config=True)
    
    # Configure the app
    app.config.from_mapping(
        SECRET_KEY='dev',
        SQLALCHEMY_DATABASE_URI=os.environ.get('DATABASE_URL', 'sqlite:///metrics.db'),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
    )

    if test_config is None:
        # Load the instance config, if it exists, when not testing
        app.config.from_pyfile('config.py', silent=True)
    else:
        # Load the test config if passed in
        app.config.from_mapping(test_config)

    # Ensure the instance folder exists
    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass

    # Initialize the database
    db.init_app(app)
    with app.app_context():
        db.create_all()

    # Register blueprints
    app.register_blueprint(views_bp)
    app.register_blueprint(metrics_bp)
    app.register_blueprint(aggregator_bp)
    app.register_blueprint(reporting_bp)
    app.register_blueprint(stocks_bp)  # Register the stocks blueprint

    return app 