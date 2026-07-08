from flask import Flask, render_template
from routes.api import api_bp
import os

def create_app():
    app = Flask(__name__)
    
    # Register blueprints
    app.register_blueprint(api_bp)
    
    @app.route('/')
    def index():
        return render_template('index.html')
        
    return app

app = create_app()

if __name__ == '__main__':
    app.run(host='localhost', debug=True, port=5000)
