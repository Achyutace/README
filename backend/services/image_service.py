"""
图片解析服务 - 提供图片提取和AI解析功能

功能：
1. 从PDF提取图片（Base64）
2. OCR文字识别
3. 图片内容AI解析
"""

import base64
import io
from typing import Dict, List, Optional
from pathlib import Path

from config import settings

try:
    import fitz  # PyMuPDF
    HAS_FITZ = True
except ImportError:
    HAS_FITZ = False

try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

try:
    from langchain_openai import ChatOpenAI
    from langchain.schema import HumanMessage, SystemMessage
    HAS_LANGCHAIN = True
except ImportError:
    HAS_LANGCHAIN = False


class ImageService:
    """
    图片解析服务

    - extract_images_from_pdf: 从PDF提取所有图片
    - get_image_base64: 获取图片的Base64编码
    - ocr_image: 对图片进行OCR识别
    - analyze_image: 使用AI分析图片内容
    """

    def __init__(self,
                 db=None,
                 cache_dir: str = None,
                 model: str = "gpt-4o-mini"):
        """
        Args:
            db: 数据库实例
            cache_dir: 图片缓存目录
            model: 用于图片分析的模型（需要支持vision）
        """
        self.db = db
        self.cache_dir = cache_dir
        self.model = model

        if cache_dir:
            Path(cache_dir).mkdir(parents=True, exist_ok=True)

        # 初始化 LLM（用于图片分析）
        if settings.has_openai_key and HAS_LANGCHAIN:
            llm_kwargs = {
                "model": model,
                "api_key": settings.openai.api_key
            }
            if settings.openai.api_base:
                llm_kwargs["base_url"] = settings.openai.api_base
            self.llm = ChatOpenAI(**llm_kwargs)
            self.has_llm = True
        else:
            self.llm = None
            self.has_llm = False

    def extract_images_from_pdf(self, pdf_path: str,
                                file_hash: str = None,
                                page_number: int = None) -> List[Dict]:
        """
        从PDF提取图片

        Args:
            pdf_path: PDF文件路径
            file_hash: 文件哈希（用于缓存）
            page_number: 指定页码（可选，不指定则提取所有页）

        Returns:
            图片列表 [
                {
                    'page': int,
                    'index': int,
                    'width': int,
                    'height': int,
                    'format': str,
                    'base64': str,
                    'bbox': [x0, y0, x1, y1]
                },
                ...
            ]
        """
        if not HAS_FITZ:
            return []

        images = []

        try:
            doc = fitz.open(pdf_path)

            pages_to_process = range(len(doc)) if page_number is None else [page_number - 1]

            for page_idx in pages_to_process:
                if page_idx < 0 or page_idx >= len(doc):
                    continue

                page = doc[page_idx]
                image_list = page.get_images(full=True)

                for img_idx, img_info in enumerate(image_list):
                    try:
                        xref = img_info[0]
                        base_image = doc.extract_image(xref)

                        if base_image:
                            image_data = base_image["image"]
                            image_ext = base_image["ext"]
                            width = base_image.get("width", 0)
                            height = base_image.get("height", 0)

                            # 转换为Base64
                            b64_data = base64.b64encode(image_data).decode('utf-8')

                            # 获取图片在页面上的位置
                            bbox = self._get_image_bbox(page, xref)

                            images.append({
                                'page': page_idx + 1,
                                'index': img_idx,
                                'width': width,
                                'height': height,
                                'format': image_ext,
                                'base64': b64_data,
                                'bbox': bbox,
                                'size': len(image_data)
                            })

                            # 保存到数据库
                            if self.db and file_hash:
                                # 保存图片到缓存
                                if self.cache_dir:
                                    img_filename = f"{file_hash}_p{page_idx + 1}_i{img_idx}.{image_ext}"
                                    img_path = os.path.join(self.cache_dir, img_filename)
                                    with open(img_path, 'wb') as f:
                                        f.write(image_data)

                                    self.db.add_image(
                                        file_hash=file_hash,
                                        page_number=page_idx + 1,
                                        image_index=img_idx,
                                        image_path=img_path,
                                        image_format=image_ext,
                                        width=width,
                                        height=height,
                                        file_size=len(image_data),
                                        bbox=bbox
                                    )

                    except Exception as e:
                        print(f"Error extracting image {img_idx} from page {page_idx + 1}: {e}")
                        continue

            doc.close()

        except Exception as e:
            print(f"Error processing PDF: {e}")

        return images

    def _get_image_bbox(self, page, xref) -> List[float]:
        """获取图片在页面上的边界框"""
        try:
            # 尝试从页面内容中找到图片位置
            for img in page.get_images(full=True):
                if img[0] == xref:
                    # 返回近似位置
                    rect = page.rect
                    return [0, 0, rect.width, rect.height]
        except:
            pass
        return [0, 0, 0, 0]

    def get_image_base64(self, file_hash: str, page_number: int,
                        image_index: int) -> Optional[Dict]:
        """
        获取指定图片的Base64编码

        Args:
            file_hash: 文件哈希
            page_number: 页码
            image_index: 图片索引

        Returns:
            {
                'base64': str,
                'format': str,
                'width': int,
                'height': int
            }
        """
        # 先尝试从缓存读取
        if self.db:
            images = self.db.get_images(file_hash, page_number)
            for img in images:
                if img['image_index'] == image_index:
                    img_path = img.get('image_path')
                    if img_path and os.path.exists(img_path):
                        with open(img_path, 'rb') as f:
                            image_data = f.read()
                        return {
                            'base64': base64.b64encode(image_data).decode('utf-8'),
                            'format': img.get('image_format', 'png'),
                            'width': img.get('width', 0),
                            'height': img.get('height', 0)
                        }

        return None

    def ocr_image(self, image_data: bytes = None, base64_data: str = None,
                  image_path: str = None) -> Dict:
        """
        对图片进行OCR识别

        Args:
            image_data: 图片二进制数据
            base64_data: 图片Base64编码
            image_path: 图片文件路径

        Returns:
            {
                'success': bool,
                'text': str,
                'confidence': float,
                'method': str  # 'tesseract' | 'vision'
            }
        """
        # 获取图片数据
        if base64_data:
            image_data = base64.b64decode(base64_data)
        elif image_path:
            with open(image_path, 'rb') as f:
                image_data = f.read()

        if not image_data:
            return {
                'success': False,
                'text': '',
                'error': 'No image data provided'
            }

        # 方法1：尝试使用 Tesseract OCR
        try:
            import pytesseract

            if HAS_PIL:
                image = Image.open(io.BytesIO(image_data))
                text = pytesseract.image_to_string(image, lang='eng+chi_sim')
                return {
                    'success': True,
                    'text': text.strip(),
                    'method': 'tesseract',
                    'confidence': 0.8
                }
        except ImportError:
            pass
        except Exception as e:
            print(f"Tesseract OCR error: {e}")

        # 方法2：使用 OpenAI Vision API
        if self.has_llm:
            try:
                b64 = base64.b64encode(image_data).decode('utf-8') if not base64_data else base64_data

                # 检测图片格式
                img_format = "png"
                if image_data[:8] == b'\x89PNG\r\n\x1a\n':
                    img_format = "png"
                elif image_data[:2] == b'\xff\xd8':
                    img_format = "jpeg"

                response = self.llm.invoke([
                    HumanMessage(content=[
                        {"type": "text", "text": "请识别这张图片中的所有文字。只输出识别到的文字内容，不要有其他说明。如果图片中没有文字，请回复'图片中没有文字'。"},
                        {"type": "image_url", "image_url": {"url": f"data:image/{img_format};base64,{b64}"}}
                    ])
                ])

                return {
                    'success': True,
                    'text': response.content.strip(),
                    'method': 'vision',
                    'confidence': 0.9
                }
            except Exception as e:
                print(f"Vision API OCR error: {e}")

        return {
            'success': False,
            'text': '',
            'error': 'No OCR method available'
        }

    def analyze_image(self, image_data: bytes = None, base64_data: str = None,
                     image_path: str = None, prompt: str = None,
                     analysis_type: str = "general") -> Dict:
        """
        使用AI分析图片内容

        Args:
            image_data: 图片二进制数据
            base64_data: 图片Base64编码
            image_path: 图片文件路径
            prompt: 自定义分析提示词
            analysis_type: 分析类型
                - 'general': 通用描述
                - 'figure': 图表分析
                - 'equation': 公式识别
                - 'table': 表格提取
                - 'diagram': 流程图/架构图分析

        Returns:
            {
                'success': bool,
                'analysis': str,
                'type': str,
                'details': {...}
            }
        """
        if not self.has_llm:
            return {
                'success': False,
                'analysis': '',
                'error': 'AI service not available. Please configure OPENAI_API_KEY.'
            }

        # 获取图片数据
        if base64_data:
            b64 = base64_data
            image_data = base64.b64decode(base64_data)
        elif image_path:
            with open(image_path, 'rb') as f:
                image_data = f.read()
            b64 = base64.b64encode(image_data).decode('utf-8')
        elif image_data:
            b64 = base64.b64encode(image_data).decode('utf-8')
        else:
            return {
                'success': False,
                'analysis': '',
                'error': 'No image data provided'
            }

        # 检测图片格式
        img_format = "png"
        if image_data[:8] == b'\x89PNG\r\n\x1a\n':
            img_format = "png"
        elif image_data[:2] == b'\xff\xd8':
            img_format = "jpeg"

        # 根据分析类型构建提示词
        if prompt:
            analysis_prompt = prompt
        else:
            prompts = {
                'general': "请详细描述这张图片的内容。如果是学术论文中的图片，请分析其含义和作用。",
                'figure': "这是一张学术论文中的图表。请分析：1) 图表类型 2) 展示的数据或信息 3) 主要发现或结论 4) 与研究的关系",
                'equation': "请识别并解释图片中的数学公式或方程。输出LaTeX格式的公式，并解释其含义。",
                'table': "请提取图片中的表格数据。以Markdown表格格式输出，并解释表格内容。",
                'diagram': "这是一张流程图、架构图或示意图。请分析：1) 图的类型 2) 各个组件及其关系 3) 整体流程或结构 4) 关键信息"
            }
            analysis_prompt = prompts.get(analysis_type, prompts['general'])

        try:
            response = self.llm.invoke([
                SystemMessage(content="你是一个专业的学术图片分析助手。请用中文回答。"),
                HumanMessage(content=[
                    {"type": "text", "text": analysis_prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/{img_format};base64,{b64}"}}
                ])
            ])

            return {
                'success': True,
                'analysis': response.content.strip(),
                'type': analysis_type,
                'details': {
                    'model': self.model,
                    'prompt_type': analysis_type
                }
            }

        except Exception as e:
            print(f"Image analysis error: {e}")
            return {
                'success': False,
                'analysis': '',
                'error': str(e)
            }

    def analyze_image_with_context(self, image_data: bytes = None,
                                   base64_data: str = None,
                                   context: str = None,
                                   question: str = None) -> Dict:
        """
        结合上下文分析图片

        Args:
            image_data: 图片数据
            base64_data: Base64编码
            context: 图片周围的文本上下文
            question: 用户的具体问题

        Returns:
            分析结果
        """
        prompt = f"""请分析这张图片。

上下文信息：
{context or '无'}

用户问题：
{question or '请描述这张图片的内容'}

请结合上下文信息回答用户的问题。"""

        return self.analyze_image(
            image_data=image_data,
            base64_data=base64_data,
            prompt=prompt,
            analysis_type='general'
        )