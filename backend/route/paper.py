"""
论文管理路由

功能：
1. 上传论文
2. 获取论文列表
3. 删除论文
4. 图片提取和分析
"""

from flask import Blueprint, request, jsonify, g

paper_bp = Blueprint('paper', __name__, url_prefix='/api/paper')


def init_paper_routes(db, pdf_service_getter, rag_service, image_service=None):
    """
    初始化论文路由

    Args:
        db: 数据库实例
        pdf_service_getter: 获取PDF服务的函数
        rag_service: RAG服务实例
        image_service: 图片服务实例（可选）
    """

    @paper_bp.route('/list', methods=['GET'])
    def list_papers():
        """
        获取论文列表

        返回：
        {
            "papers": [
                {
                    "id": "PDF ID",
                    "filename": "文件名",
                    "pageCount": 页数,
                    "uploadTime": "上传时间",
                    "indexed": true/false
                },
                ...
            ]
        }
        """
        try:
            pdf_service = pdf_service_getter(g.user_id)
            papers = pdf_service.list_pdfs()

            # 检查是否已索引
            for paper in papers:
                try:
                    filepath = pdf_service.get_filepath(paper['id'])
                    from services.rag_service import RAGService
                    file_hash = RAGService.calculate_file_hash(filepath)
                    # 这里可以查询数据库检查索引状态
                    paper['indexed'] = True
                except:
                    paper['indexed'] = False

            return jsonify({'papers': papers})
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @paper_bp.route('/<pdf_id>', methods=['DELETE'])
    def delete_paper(pdf_id):
        """
        删除论文

        返回：
        {
            "success": true
        }
        """
        try:
            pdf_service = pdf_service_getter(g.user_id)

            # 从RAG中删除
            try:
                rag_service.delete_paper(pdf_id, g.user_id)
            except:
                pass  # 可能未索引

            # 删除文件
            pdf_service.delete_pdf(pdf_id)

            return jsonify({'success': True})
        except FileNotFoundError:
            return jsonify({'error': 'PDF not found'}), 404
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @paper_bp.route('/<pdf_id>/reindex', methods=['POST'])
    def reindex_paper(pdf_id):
        """
        重新索引论文到RAG

        返回：
        {
            "success": true,
            "chunks": 索引的块数
        }
        """
        try:
            pdf_service = pdf_service_getter(g.user_id)
            filepath = pdf_service.get_filepath(pdf_id)

            result = rag_service.index_paper(
                pdf_path=filepath,
                paper_id=pdf_id,
                user_id=g.user_id
            )

            return jsonify({
                'success': True,
                'chunks': result.get('chunks_created', 0)
            })
        except FileNotFoundError:
            return jsonify({'error': 'PDF not found'}), 404
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    # ==================== 图片相关路由 ====================

    @paper_bp.route('/<pdf_id>/images', methods=['GET'])
    def get_images(pdf_id):
        """
        获取论文中的图片列表

        查询参数：
        - page: 页码（可选）

        返回：
        {
            "images": [
                {
                    "page": int,
                    "index": int,
                    "width": int,
                    "height": int,
                    "format": str,
                    "base64": str（如果不太大）
                },
                ...
            ]
        }
        """
        if not image_service:
            return jsonify({'error': 'Image service not available'}), 503

        page_number = request.args.get('page', type=int)

        try:
            pdf_service = pdf_service_getter(g.user_id)
            filepath = pdf_service.get_filepath(pdf_id)

            from services.rag_service import RAGService
            file_hash = RAGService.calculate_file_hash(filepath)

            images = image_service.extract_images_from_pdf(
                filepath, file_hash, page_number
            )

            # 移除过大的base64数据，只保留预览
            for img in images:
                if img.get('size', 0) > 100000:  # 大于100KB
                    img['base64'] = None
                    img['hasFullImage'] = True

            return jsonify({'images': images})
        except FileNotFoundError:
            return jsonify({'error': 'PDF not found'}), 404
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @paper_bp.route('/<pdf_id>/images/<int:page>/<int:index>', methods=['GET'])
    def get_image(pdf_id, page, index):
        """
        获取指定图片的Base64数据

        返回：
        {
            "base64": str,
            "format": str,
            "width": int,
            "height": int
        }
        """
        if not image_service:
            return jsonify({'error': 'Image service not available'}), 503

        try:
            pdf_service = pdf_service_getter(g.user_id)
            filepath = pdf_service.get_filepath(pdf_id)

            from services.rag_service import RAGService
            file_hash = RAGService.calculate_file_hash(filepath)

            result = image_service.get_image_base64(file_hash, page, index)

            if result:
                return jsonify(result)
            else:
                # 如果没有缓存，重新提取
                images = image_service.extract_images_from_pdf(filepath, file_hash, page)
                for img in images:
                    if img['index'] == index:
                        return jsonify({
                            'base64': img['base64'],
                            'format': img['format'],
                            'width': img['width'],
                            'height': img['height']
                        })
                return jsonify({'error': 'Image not found'}), 404

        except FileNotFoundError:
            return jsonify({'error': 'PDF not found'}), 404
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @paper_bp.route('/<pdf_id>/images/analyze', methods=['POST'])
    def analyze_image(pdf_id):
        """
        分析图片内容

        请求体：
        {
            "page": 页码,
            "index": 图片索引,
            "type": "general" | "figure" | "equation" | "table" | "diagram",
            "prompt": "自定义提示（可选）",
            "method": "ocr" | "vision"  // 可选，默认vision
        }

        返回：
        {
            "success": true,
            "analysis": "分析结果",
            "type": "分析类型"
        }
        """
        if not image_service:
            return jsonify({'error': 'Image service not available'}), 503

        data = request.get_json()
        page = data.get('page')
        index = data.get('index')
        analysis_type = data.get('type', 'general')
        prompt = data.get('prompt')
        method = data.get('method', 'vision')

        if page is None or index is None:
            return jsonify({'error': 'page and index are required'}), 400

        try:
            pdf_service = pdf_service_getter(g.user_id)
            filepath = pdf_service.get_filepath(pdf_id)

            from services.rag_service import RAGService
            file_hash = RAGService.calculate_file_hash(filepath)

            # 获取图片数据
            img_data = image_service.get_image_base64(file_hash, page, index)

            if not img_data:
                # 重新提取
                images = image_service.extract_images_from_pdf(filepath, file_hash, page)
                for img in images:
                    if img['index'] == index:
                        img_data = {
                            'base64': img['base64'],
                            'format': img['format']
                        }
                        break

            if not img_data:
                return jsonify({'error': 'Image not found'}), 404

            # 根据方法选择分析方式
            if method == 'ocr':
                result = image_service.ocr_image(base64_data=img_data['base64'])
                return jsonify({
                    'success': result.get('success', False),
                    'analysis': result.get('text', ''),
                    'type': 'ocr',
                    'method': result.get('method', 'unknown')
                })
            else:
                result = image_service.analyze_image(
                    base64_data=img_data['base64'],
                    prompt=prompt,
                    analysis_type=analysis_type
                )
                return jsonify(result)

        except FileNotFoundError:
            return jsonify({'error': 'PDF not found'}), 404
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @paper_bp.route('/images/analyze-upload', methods=['POST'])
    def analyze_uploaded_image():
        """
        分析上传的图片

        请求：multipart/form-data
        - image: 图片文件
        - type: 分析类型（可选）
        - prompt: 自定义提示（可选）
        - method: ocr | vision（可选）

        返回：
        {
            "success": true,
            "analysis": "分析结果"
        }
        """
        if not image_service:
            return jsonify({'error': 'Image service not available'}), 503

        if 'image' not in request.files:
            return jsonify({'error': 'No image provided'}), 400

        file = request.files['image']
        if file.filename == '':
            return jsonify({'error': 'No image selected'}), 400

        analysis_type = request.form.get('type', 'general')
        prompt = request.form.get('prompt')
        method = request.form.get('method', 'vision')

        try:
            image_data = file.read()

            if method == 'ocr':
                result = image_service.ocr_image(image_data=image_data)
                return jsonify({
                    'success': result.get('success', False),
                    'analysis': result.get('text', ''),
                    'type': 'ocr'
                })
            else:
                result = image_service.analyze_image(
                    image_data=image_data,
                    prompt=prompt,
                    analysis_type=analysis_type
                )
                return jsonify(result)

        except Exception as e:
            return jsonify({'error': str(e)}), 500

    return paper_bp
