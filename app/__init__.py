from werkzeug.middleware.proxy_fix import ProxyFix
from flask import Flask
from app.config import Config
from app.routes_scan import scan_bp
from app.routes_admin import admin_bp

def create_app():
    Config.validate()
    app = Flask(__name__, template_folder="../templates", static_folder="../static")
    # Behind kts-proxy the app is served under a path prefix (X-Forwarded-Prefix).
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)
    app.config.from_object(Config)

    app.register_blueprint(scan_bp)
    app.register_blueprint(admin_bp)

    return app
