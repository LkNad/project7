from flask import Flask, render_template
import os

app = Flask(__name__)

template_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates')
static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')

app = Flask(__name__,
            template_folder=template_dir,
            static_folder=static_dir)

@app.route('/')
def index():
    return render_template('index.html')
