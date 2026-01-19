import os
from flask import Flask, request, jsonify
from flask_cors import CORS
from werkzeug.utils import secure_filename
from dotenv import load_dotenv

from services.pdf_service import PdfService
from services.ai_service import AiService

load_dotenv()

app = Flask(__name__)
CORS(app)

# Configuration
app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(__file__), 'uploads')
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB max

# Ensure upload folder exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Service instances
pdf_service = PdfService(app.config['UPLOAD_FOLDER'])
ai_service = AiService()


@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({'status': 'ok'})


# ==================== PDF Routes ====================

@app.route('/api/pdf/upload', methods=['POST'])
def upload_pdf():
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400

    if not file.filename.lower().endswith('.pdf'):
        return jsonify({'error': 'Only PDF files are allowed'}), 400

    try:
        result = pdf_service.save_and_process(file)
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/pdf/<pdf_id>/text', methods=['GET'])
def get_pdf_text(pdf_id):
    page = request.args.get('page', type=int)
    try:
        result = pdf_service.extract_text(pdf_id, page)
        return jsonify(result)
    except FileNotFoundError:
        return jsonify({'error': 'PDF not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/pdf/<pdf_id>/info', methods=['GET'])
def get_pdf_info(pdf_id):
    try:
        result = pdf_service.get_info(pdf_id)
        return jsonify(result)
    except FileNotFoundError:
        return jsonify({'error': 'PDF not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ==================== AI Routes ====================

@app.route('/api/ai/keywords', methods=['POST'])
def extract_keywords():
    data = request.get_json()
    pdf_id = data.get('pdfId')

    if not pdf_id:
        return jsonify({'error': 'pdfId is required'}), 400

    try:
        text = pdf_service.extract_text(pdf_id)['text']
        keywords = ai_service.extract_keywords(text)
        return jsonify({'keywords': keywords})
    except FileNotFoundError:
        return jsonify({'error': 'PDF not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/ai/summary', methods=['POST'])
def generate_summary():
    data = request.get_json()
    pdf_id = data.get('pdfId')

    if not pdf_id:
        return jsonify({'error': 'pdfId is required'}), 400

    try:
        text = pdf_service.extract_text(pdf_id)['text']
        summary = ai_service.generate_summary(text)
        return jsonify(summary)
    except FileNotFoundError:
        return jsonify({'error': 'PDF not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/ai/translate', methods=['POST'])
def translate_text():
    data = request.get_json()
    text = data.get('text')

    if not text:
        return jsonify({'error': 'text is required'}), 400

    try:
        translation = ai_service.translate(text)
        return jsonify(translation)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/ai/chat', methods=['POST'])
def chat():
    data = request.get_json()
    pdf_id = data.get('pdfId')
    message = data.get('message')
    history = data.get('history', [])

    if not pdf_id or not message:
        return jsonify({'error': 'pdfId and message are required'}), 400

    try:
        text = pdf_service.extract_text(pdf_id)['text']
        response = ai_service.chat(text, message, history)
        return jsonify(response)
    except FileNotFoundError:
        return jsonify({'error': 'PDF not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
