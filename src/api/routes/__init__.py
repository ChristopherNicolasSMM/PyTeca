from .auth_routes import auth_bp
from .notifications_routes import notifications_bp
from .register import register_bp
from .book_routes import book_api_bp
# Lista de todos os blueprints do core (registro, notifications e auth)
all_blueprints = [register_bp, notifications_bp, auth_bp, book_api_bp]
