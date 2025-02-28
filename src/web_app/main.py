from flask import Flask, redirect, url_for
from ..database.database import init_app, init_db
from ..utils.config import get_settings
from .routes import aggregator_bp, reporting_bp, views_bp

settings = get_settings()

def create_app():
    app = Flask(__name__)
    
    # Initialize database
    init_app(app)
    
    # Register blueprints
    app.register_blueprint(aggregator_bp, url_prefix='/api/v1/aggregator')
    app.register_blueprint(reporting_bp, url_prefix='/api/v1/reports')
    app.register_blueprint(views_bp)
    
    # Create database tables
    init_db(app)
    
    @app.route('/')
    def root():
        return redirect(url_for('views.dashboard'))
    
    return app

if __name__ == '__main__':
    app = create_app()
    app.run(
        host=settings.APP_HOST,
        port=settings.APP_PORT,
        debug=settings.DEBUG
    ) 