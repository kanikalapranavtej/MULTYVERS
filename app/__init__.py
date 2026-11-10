from flask import Flask, jsonify

from app.config import Config
from app.extensions import init_extensions
from app.database import init_app as init_database


def create_app(config_class=Config):

    # Create Flask application
    app = Flask(__name__)

    # Load configuration
    app.config.from_object(config_class)

    # Initialize extensions
    init_extensions(app)

    # Initialize database handling
    init_database(app)

    # Register application routes
    from app.routes.main import main_bp

    app.register_blueprint(main_bp)

    # Handle 404 errors
    @app.errorhandler(404)
    def not_found(error):

        return jsonify({
            "error": "Resource not found"
        }), 404

    # Handle internal server errors
    @app.errorhandler(500)
    def internal_error(error):

        app.logger.exception("Internal server error")

        return jsonify({
            "error": "Internal server error"
        }), 500

    return app