from flask import Flask, jsonify

from app.config import Config
from app.extensions import init_extensions
from app.database import init_app as init_database


def create_app(config_class=Config):

    app = Flask(__name__)

    app.config.from_object(config_class)

    init_extensions(app)

    init_database(app)
    
    from app.routes.main import main_bp
    from app.routes.auth import auth_bp
    from app.routes.events import events_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(events_bp)

     
    # 404 handler
    @app.errorhandler(404)
    def not_found(error):

        return jsonify({
            "error": "Resource not found"
        }), 404

    # 500 handler
    @app.errorhandler(500)
    def internal_error(error):

        app.logger.exception("Internal server error")

        return jsonify({
            "error": "Internal server error"
        }), 500

    return app