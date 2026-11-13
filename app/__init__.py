from flask import Flask, jsonify

from app.config import Config
from app.extensions import init_extensions
from app.database import init_app as init_database

from app.routes.venues import venues_bp
from app.routes.attendance import attendance_bp
from app.routes.participants import participants_bp
from app.routes.analytics import analytics_bp
from app.routes.pages import pages_bp
from app.routes.venue_pages import venue_pages_bp
from app.routes.attendance_pages import attendance_pages_bp


def create_app(config_class=Config):
    app = Flask(__name__)

    app.config.from_object(config_class)

    init_extensions(app)
    init_database(app)

    from app.routes.main import main_bp
    from app.routes.auth import auth_bp
    from app.routes.events import events_bp
    from app.routes.registrations import registrations_bp


    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(events_bp)
    app.register_blueprint(registrations_bp)
    app.register_blueprint(venues_bp)
    app.register_blueprint(attendance_bp)
    app.register_blueprint(participants_bp)
    app.register_blueprint(analytics_bp)
    app.register_blueprint(pages_bp)
    app.register_blueprint(venue_pages_bp)
    app.register_blueprint(attendance_pages_bp)

    @app.errorhandler(404)
    def not_found(error):
        return jsonify({"error": "Resource not found"}), 404

    @app.errorhandler(500)
    def internal_error(error):
        app.logger.exception("Internal server error")
        return jsonify({"error": "Internal server error"}), 500

    return app
