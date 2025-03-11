from flask import Flask

app = Flask(__name__)

@app.route('/')
def hello():
    return 'Hello, World! Server is running.'

@app.route('/api/v1/aggregator/register', methods=['POST'])
def register():
    return {'status': 'success', 'message': 'Device registered successfully'}

if __name__ == '__main__':
    print("Starting test server on 0.0.0.0:8000")
    app.run(host='0.0.0.0', port=8000, debug=True) 