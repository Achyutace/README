from flask import Blueprint, jsonify, request

roadmap_bp = Blueprint('roadmap', __name__, url_prefix='/api/roadmap')

@roadmap_bp.route('/ping', methods=['GET'])
def ping():
    return jsonify({"message": "pong"})
