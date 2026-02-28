"""
Upload, processing status and PDF metadata endpoints.
"""
from pathlib import Path
from typing import Any, Dict, List, Tuple

from flask import Blueprint, request, jsonify, g, send_file, current_app

from core.security import jwt_required
from core.exceptions import NotFoundError
from core.logging import get_logger
from core.database import db
from repository.sql_repo import SQLRepository
from services.mineru_service import MinerUService
from utils import pdf_engine

logger = get_logger(__name__)

upload_bp = Blueprint('upload', __name__, url_prefix='/api/pdf')


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _bbox_to_xywh(raw_bbox: Any, page_w: float = 0.0, page_h: float = 0.0) -> Tuple[float, float, float, float]:
    """Normalize bbox to [x, y, w, h]. Supports xyxy/xywh with robust heuristics."""
    if not isinstance(raw_bbox, list) or len(raw_bbox) != 4:
        return 0.0, 0.0, 0.0, 0.0

    x0 = _safe_float(raw_bbox[0])
    y0 = _safe_float(raw_bbox[1])
    v2 = _safe_float(raw_bbox[2])
    v3 = _safe_float(raw_bbox[3])

    # Candidate A: treat as xyxy (order-agnostic).
    ax0 = min(x0, v2)
    ay0 = min(y0, v3)
    ax1 = max(x0, v2)
    ay1 = max(y0, v3)
    aw = max(ax1 - ax0, 0.0)
    ah = max(ay1 - ay0, 0.0)

    # Candidate B: treat as xywh (allow negative w/h).
    bx1 = x0 + v2
    by1 = y0 + v3
    bx0 = min(x0, bx1)
    by0 = min(y0, by1)
    bx1 = max(x0, bx1)
    by1 = max(y0, by1)
    bw = max(bx1 - bx0, 0.0)
    bh = max(by1 - by0, 0.0)

    def _overflow_score(px0: float, py0: float, px1: float, py1: float) -> float:
        score = 0.0
        if page_w > 0:
            score += max(0.0, px1 - page_w) / page_w
            score += max(0.0, -px0) / page_w
        if page_h > 0:
            score += max(0.0, py1 - page_h) / page_h
            score += max(0.0, -py0) / page_h
        return score

    # Prefer candidate with less page overflow; tie-break by smaller area.
    a_score = _overflow_score(ax0, ay0, ax1, ay1)
    b_score = _overflow_score(bx0, by0, bx1, by1)
    a_area = aw * ah
    b_area = bw * bh

    if (a_score < b_score) or (a_score == b_score and a_area <= b_area):
        return ax0, ay0, aw, ah
    return bx0, by0, bw, bh


def _normalize_layout_items(parsed: Dict[str, Any], dimensions: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Ensure every item has:
    - bbox: [x, y, w, h] absolute PDF coords
    - bboxNorm: {left, top, width, height} normalized to page size
    """
    normalized: Dict[str, Any] = {
        'page_count': parsed.get('page_count', 0),
        'paragraphs': [],
        'images': [],
        'tables': [],
        'formulas': [],
    }

    # First pass: convert all bboxes and infer real page extents from data.
    prepared: List[Tuple[str, Dict[str, Any], int, float, float, float, float]] = []
    inferred_extents: Dict[int, Tuple[float, float]] = {}

    for key in ('paragraphs', 'images', 'tables', 'formulas'):
        for item in parsed.get(key, []):
            page = int(item.get('page', 1) or 1)
            page_dim = dimensions[page - 1] if 0 <= (page - 1) < len(dimensions) else {}
            base_w = max(_safe_float(page_dim.get('width'), 1.0), 1.0)
            base_h = max(_safe_float(page_dim.get('height'), 1.0), 1.0)

            x, y, w, h = _bbox_to_xywh(item.get('bbox', []), base_w, base_h)
            prepared.append((key, item, page, x, y, w, h))

            max_x = max(x + w, base_w)
            max_y = max(y + h, base_h)
            old = inferred_extents.get(page)
            if old is None:
                inferred_extents[page] = (max_x, max_y)
            else:
                inferred_extents[page] = (max(old[0], max_x), max(old[1], max_y))

    # Document-level heuristic for square normalized canvas (commonly ~1000x1000).
    # Using per-page inferred extents can under-estimate on sparse pages and cause
    # consistent right/bottom drift. Prefer one document-level canvas when detected.
    global_max_x = 0.0
    global_max_y = 0.0
    for _p, (mx, my) in inferred_extents.items():
        global_max_x = max(global_max_x, mx)
        global_max_y = max(global_max_y, my)

    sample_dim = dimensions[0] if dimensions else {}
    sample_pdf_w = max(_safe_float(sample_dim.get('width'), 1.0), 1.0)
    sample_pdf_h = max(_safe_float(sample_dim.get('height'), 1.0), 1.0)
    sample_pdf_ratio = sample_pdf_w / sample_pdf_h

    use_doc_canvas = False
    doc_canvas_w = 0.0
    doc_canvas_h = 0.0
    if global_max_x > 0 and global_max_y > 0:
        global_ratio = global_max_x / global_max_y
        if (
            820.0 <= global_max_x <= 1200.0 and
            820.0 <= global_max_y <= 1200.0 and
            0.85 <= global_ratio <= 1.15 and
            abs(sample_pdf_ratio - global_ratio) >= 0.10
        ):
            # Prefer canonical 1000x1000 if values are around that range.
            if global_max_x <= 1050.0 and global_max_y <= 1050.0:
                doc_canvas_w, doc_canvas_h = 1000.0, 1000.0
            else:
                doc_canvas_w = max(global_max_x, 1.0)
                doc_canvas_h = max(global_max_y, 1.0)
            use_doc_canvas = True

    # Second pass: normalize using inferred extents / document canvas.
    for key, item, page, x, y, w, h in prepared:
        if use_doc_canvas:
            page_w, page_h = doc_canvas_w, doc_canvas_h
        else:
            page_w, page_h = inferred_extents.get(page, (1.0, 1.0))
            page_w = max(page_w, 1.0)
            page_h = max(page_h, 1.0)

        # Heuristic: some fallback bboxes are in a square 0..1000 canvas.
        # If extents look like ~1k square while PDF page ratio is non-square, use 1000x1000.
        page_dim = dimensions[page - 1] if 0 <= (page - 1) < len(dimensions) else {}
        pdf_w = max(_safe_float(page_dim.get('width'), 1.0), 1.0)
        pdf_h = max(_safe_float(page_dim.get('height'), 1.0), 1.0)
        inferred_ratio = page_w / page_h
        pdf_ratio = pdf_w / pdf_h
        if (
            820.0 <= page_w <= 1080.0 and
            820.0 <= page_h <= 1080.0 and
            0.90 <= inferred_ratio <= 1.10 and
            abs(pdf_ratio - inferred_ratio) >= 0.12
        ):
            page_w, page_h = 1000.0, 1000.0

        left = max(0.0, min(1.0, x / page_w))
        top = max(0.0, min(1.0, y / page_h))
        width = max(0.0, min(1.0 - left, w / page_w))
        height = max(0.0, min(1.0 - top, h / page_h))

        out = dict(item)
        out['bbox'] = [x, y, w, h]
        out['bboxNorm'] = {
            'left': left,
            'top': top,
            'width': width,
            'height': height,
        }
        normalized[key].append(out)

    return normalized


def _build_layout_from_db(pdf_id: str) -> Dict[str, Any]:
    """Fallback layout source when MinerU cache is unavailable."""
    repo = SQLRepository(db.session)

    paragraphs = []
    images = []
    tables = []
    formulas = []

    for p in repo.get_paragraphs(pdf_id):
        paragraphs.append({
            'page': p.page_number,
            'index': p.paragraph_index,
            'content': p.original_text,
            'bbox': p.bbox or [],
        })

    for img in repo.get_images(pdf_id):
        item = {
            'page': img.page_number,
            'index': img.image_index,
            'bbox': img.bbox or [],
            'path': img.image_path or '',
            'caption': img.caption or '',
        }
        if (img.caption or '').strip().startswith('[table]'):
            tables.append(item)
        else:
            images.append(item)

    for f in repo.get_formulas(pdf_id):
        formulas.append({
            'page': f.page_number,
            'index': f.formula_index,
            'bbox': f.bbox or [],
            'latex': f.latex_content or '',
        })

    return {
        'page_count': 0,
        'paragraphs': paragraphs,
        'images': images,
        'tables': tables,
        'formulas': formulas,
    }


@upload_bp.route('/', methods=['GET'])
@jwt_required()
def list_user_papers():
    page = request.args.get('page', 1, type=int)
    page_size = request.args.get('pageSize', 50, type=int)
    group = request.args.get('group')
    keyword = request.args.get('keyword')

    library_service = current_app.library_service
    result = library_service.get_user_papers(
        user_id=g.user_id,
        page=page,
        page_size=page_size,
        group_filter=group,
        keyword=keyword,
    )
    return jsonify(result)


@upload_bp.route('/upload', methods=['POST'])
@jwt_required()
def upload_pdf():
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400

    if not file.filename.lower().endswith('.pdf'):
        return jsonify({'error': 'Only PDF files are allowed'}), 400

    pdf_service = g.pdf_service
    user_id = g.user_id

    result = pdf_service.ingest_file(
        file_obj=file,
        filename=file.filename,
        user_id=user_id,
    )

    pdf_id = result['pdf_id']

    library_service = current_app.library_service
    library_service.bind_paper(
        user_id=user_id,
        pdf_id=pdf_id,
        title=file.filename,
    )

    response_data = {
        'pdfId': pdf_id,
        'taskId': result.get('task_id'),
        'status': result['status'],
        'pageCount': result.get('pageCount', 0),
        'filename': file.filename,
        'isNewUpload': result.get('is_new', True),
    }

    logger.info(
        f"[Upload] pdf_id={pdf_id}, "
        f"task_id={result.get('task_id')}, "
        f"status={result['status']}, "
        f"user={g.user_id_str}"
    )
    return jsonify(response_data)


@upload_bp.route('/<pdf_id>/status', methods=['GET'])
@jwt_required()
def get_task_status(pdf_id):
    from_page = request.args.get('from_page', 1, type=int)
    pdf_service = g.pdf_service
    result = pdf_service.get_process_status(pdf_id, from_page=from_page)
    return jsonify(result)


@upload_bp.route('/<pdf_id>/info', methods=['GET'])
@jwt_required()
def get_pdf_info(pdf_id):
    try:
        info = g.pdf_service.get_info(pdf_id)
        return jsonify(info)
    except FileNotFoundError:
        raise NotFoundError('PDF not found')


@upload_bp.route('/<pdf_id>/paragraphs', methods=['GET'])
@jwt_required()
def get_pdf_paragraphs(pdf_id):
    page = request.args.get('page', type=int)
    result = g.pdf_service.get_paragraph(pdf_id, pagenumber=page)
    return jsonify({'paragraphs': result})


@upload_bp.route('/<pdf_id>/source', methods=['GET'])
@jwt_required()
def get_pdf_source(pdf_id):
    try:
        file_obj = g.pdf_service.get_file_obj(pdf_id)
        return send_file(
            file_obj,
            mimetype='application/pdf',
            as_attachment=False,
            download_name=f'{pdf_id}.pdf',
        )
    except FileNotFoundError:
        raise NotFoundError('PDF file not found')


@upload_bp.route('/<pdf_id>/layout', methods=['GET'])
@jwt_required()
def get_pdf_layout(pdf_id):
    """Return normalized layout for frontend overlays."""
    try:
        upload_folder = Path(g.pdf_service.upload_folder)
    except Exception:
        raise NotFoundError('User upload folder not initialized')

    try:
        info = g.pdf_service.get_info(pdf_id)
        dimensions = info.get('dimensions') or []
    except Exception:
        dimensions = []

    cache_dir = upload_folder.parent / 'cache' / 'mineru' / pdf_id
    svc = MinerUService()
    content_json = svc._find_content_json(cache_dir)

    if content_json is not None:
        parsed = svc.parse_content_list(content_json, cache_dir)
    else:
        parsed = _build_layout_from_db(pdf_id)

    normalized = _normalize_layout_items(parsed, dimensions)
    return jsonify({'pdfId': pdf_id, 'layout': normalized})


@upload_bp.route('/<pdf_id>/image/<int:image_index>', methods=['GET'])
@jwt_required()
def get_pdf_image(pdf_id, image_index):
    try:
        image_id = pdf_engine.make_image_id(pdf_id, image_index)
        data = g.pdf_service.get_image_data(image_id)
        if not data:
            raise FileNotFoundError('Image not found')
        return jsonify({'id': image_id, 'mimeType': data.get('mimeType'), 'base64': data.get('base64')})
    except FileNotFoundError:
        raise NotFoundError('Image not found')
    except Exception as e:
        current_app.logger.error(f'Failed to get image {pdf_id}:{image_index} - {e}')
        return jsonify({'error': str(e)}), 500
