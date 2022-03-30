
import flask

def main():
  print('Hello world!')
  app:flask.Flask = flask.Flask(__name__)
  app.route('/')(lambda:'Hello World!')
  app.run(host='0.0.0.0', port=5000)