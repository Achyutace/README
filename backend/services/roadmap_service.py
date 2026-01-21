import os
import re
from datetime import datetime
import httpx
from openai import OpenAI

class AiService:
    def __init__(self):
        # 1. 尝试从环境变量获取代理设置
        # 如果你使用了代理（例如 v2ray, clash），请确保设置了 OPENAI_API_BASE 或 http_proxy
        
        # 2. 初始化 OpenAI 客户端
        # 注意: openai>=1.0.0 不再接受 proxies 参数
        # 它会自动读取系统的 HTTP_PROXY 和 HTTPS_PROXY 环境变量
        
        # 如果你需要显式指定代理（因为报错看起来像是内部创建 http_client 时出了问题）
        # 我们可以自定义一个 httpx.Client 传进去
        
        proxy_url = os.getenv("http_proxy") or os.getenv("https_proxy")
        
        if proxy_url:
            http_client = httpx.Client(proxies=proxy_url)
            self.client = OpenAI(
                api_key=os.getenv('OPENAI_API_KEY'),
                http_client=http_client
            )
        else:
            # 标准初始化
            self.client = OpenAI(
                api_key=os.getenv('OPENAI_API_KEY')
            )
            
    def generate_roadmap(self, text: str) -> dict:
        """Generate a concept roadmap from text."""
        if self.client:
            try:
                response = self.client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {
                            "role": "system",
                            "content": "You are a helpful assistant that extracts key concepts and creates a learning roadmap from academic papers. Return a JSON structure representing a graph of concepts. The output should contain 'nodes' (list of {id, label, data: {description, papers: [{title, link, year}]}}) and 'edges' (list of {id, source, target})."
                        },
                        {
                            "role": "user",
                            "content": f"Create a concept roadmap from this text. Identify 5-8 key concepts and their relationships:\n\n{text[:6000]}"
                        }
                    ],
                    temperature=0.3
                )
                content = response.choices[0].message.content
                return self._parse_json_roadmap(content)
            except Exception as e:
                print(f"OpenAI error: {e}")

        # Fallback: Demo mode
        return self._demo_roadmap()

    def generate_summary(self, text: str) -> dict:
        """Generate a 3-bullet summary of the text."""
        if self.client:
            try:
                response = self.client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {
                            "role": "system",
                            "content": "You are a helpful assistant that summarizes academic papers. Provide exactly 3 bullet points: 1) Core contribution, 2) Key innovations, 3) Limitations."
                        },
                        {
                            "role": "user",
                            "content": f"Summarize this paper in 3 bullet points:\n\n{text[:6000]}"
                        }
                    ],
                    temperature=0.5
                )
                content = response.choices[0].message.content
                bullets = self._parse_bullets(content)
                return {
                    'bullets': bullets,
                    'generatedAt': datetime.now().isoformat()
                }
            except Exception as e:
                print(f"OpenAI error: {e}")

        # Fallback: Demo mode
        return self._demo_summary()

    def translate(self, text: str) -> dict:
        """Translate text to Chinese."""
        if self.client:
            try:
                response = self.client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {
                            "role": "system",
                            "content": "You are a professional translator. Translate the following English text to Chinese. Keep technical terms accurate."
                        },
                        {
                            "role": "user",
                            "content": text
                        }
                    ],
                    temperature=0.3
                )
                translated = response.choices[0].message.content

                # Split into sentences
                sentences = self._split_sentences(text, translated)

                return {
                    'originalText': text,
                    'translatedText': translated,
                    'sentences': sentences
                }
            except Exception as e:
                print(f"OpenAI error: {e}")

        # Fallback: Demo mode
        return self._demo_translate(text)

    def chat(self, context: str, message: str, history: list) -> dict:
        """Chat with context from PDF."""
        if self.client:
            try:
                messages = [
                    {
                        "role": "system",
                        "content": f"You are a helpful assistant answering questions about a research paper. Use the following context to answer questions:\n\n{context[:8000]}"
                    }
                ]

                # Add history
                for h in history[-10:]:  # Last 10 messages
                    messages.append({
                        "role": h.get("role", "user"),
                        "content": h.get("content", "")
                    })

                messages.append({"role": "user", "content": message})

                response = self.client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=messages,
                    temperature=0.7
                )

                return {
                    'response': response.choices[0].message.content,
                    'citations': [{'pageNumber': 1, 'text': 'Referenced from document'}]
                }
            except Exception as e:
                print(f"OpenAI error: {e}")

        # Fallback: Demo mode
        return self._demo_chat(message)

    def _parse_keywords(self, content: str) -> list:
        """Parse keywords from AI response."""
        # Simple parsing - in production use proper JSON parsing
        keywords = []
        lines = content.split('\n')
        for line in lines:
            if ':' in line or '-' in line:
                parts = re.split(r'[:\-]', line, 1)
                if len(parts) == 2:
                    term = parts[0].strip().strip('*').strip('"').strip("'")
                    definition = parts[1].strip()
                    if term and definition:
                        keywords.append({
                            'term': term,
                            'definition': definition,
                            'occurrences': []
                        })
        return keywords[:10]

    def _parse_bullets(self, content: str) -> list:
        """Parse bullet points from AI response."""
        bullets = []
        lines = content.split('\n')
        for line in lines:
            line = line.strip()
            if line and (line.startswith('-') or line.startswith('•') or
                        line.startswith('1') or line.startswith('2') or
                        line.startswith('3')):
                # Clean the line
                cleaned = re.sub(r'^[\d\.\-\•\*]+\s*', '', line).strip()
                if cleaned:
                    bullets.append(cleaned)
        return bullets[:3] if bullets else [
            "This paper presents research on the given topic.",
            "The methodology involves analysis and experimentation.",
            "Future work may address current limitations."
        ]

    def _split_sentences(self, original: str, translated: str) -> list:
        """Split text into aligned sentence pairs."""
        # Simple sentence splitting
        orig_sentences = re.split(r'(?<=[.!?])\s+', original)
        trans_sentences = re.split(r'(?<=[。！？])', translated)

        sentences = []
        for i, (orig, trans) in enumerate(zip(orig_sentences, trans_sentences)):
            sentences.append({
                'index': i + 1,
                'original': orig.strip(),
                'translated': trans.strip()
            })

        return sentences

    def _demo_extract_keywords(self, text: str) -> list:
        """Demo mode: return sample keywords."""
        return [
            {'term': 'Machine Learning', 'definition': '机器学习是一种人工智能方法', 'occurrences': []},
            {'term': 'Neural Network', 'definition': '神经网络是一种计算模型', 'occurrences': []},
            {'term': 'Deep Learning', 'definition': '深度学习是机器学习的一个分支', 'occurrences': []},
        ]

    def _parse_json_roadmap(self, text: str) -> dict:
        import json
        try:
            # Try to find JSON block
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0].strip()
            elif "```" in text:
                text = text.split("```")[1].split("```")[0].strip()
            return json.loads(text)
        except:
             return self._demo_roadmap()

    def _demo_roadmap(self) -> dict:
        return {
            "nodes": [
                { "id": "1", "label": "Large Language Models", "data": { "label": "Large Language Models", "description": "Foundation models trained on vast amounts of data.", "papers": [{ "title": "Language Models are Few-Shot Learners", "link": "https://arxiv.org/abs/2005.14165", "year": "2020" }] }, "position": { "x": 250, "y": 0 } },
                { "id": "2", "label": "Chain-of-Thought", "data": { "label": "Chain-of-Thought", "description": "Generating intermediate reasoning steps.", "papers": [{ "title": "Chain-of-Thought Prompting Elicits Reasoning in Large Language Models", "link": "https://arxiv.org/abs/2201.11903", "year": "2022" }] }, "position": { "x": 100, "y": 150 } },
                { "id": "3", "label": "Self-Consistency", "data": { "label": "Self-Consistency", "description": "Sampling multiple reasoning paths and choosing the most consistent answer.", "papers": [{ "title": "Self-Consistency Improves Chain of Thought Reasoning in Language Models", "link": "https://arxiv.org/abs/2203.11171", "year": "2022" }] }, "position": { "x": 400, "y": 150 } },
                { "id": "4", "label": "Prompt Engineering", "data": { "label": "Prompt Engineering", "description": "Techniques for designing inputs to get optimal outputs.", "papers": [] }, "position": { "x": 250, "y": 300 } }
            ],
            "edges": [
                { "id": "e1-2", "source": "1", "target": "2", "label": "enabled by" },
                { "id": "e1-3", "source": "1", "target": "3", "label": "improved by" },
                { "id": "e2-3", "source": "2", "target": "3", "label": "extends" },
                { "id": "e4-2", "source": "4", "target": "2", "label": "includes" }
            ]
        }

    def _demo_summary(self) -> dict:
        """Demo mode: return sample summary."""
        return {
            'bullets': [
                '本文研究了相关主题的核心问题和方法。',
                '提出了创新性的解决方案和实验验证。',
                '讨论了研究的局限性和未来工作方向。'
            ],
            'generatedAt': datetime.now().isoformat()
        }

    def _demo_translate(self, text: str) -> dict:
        """Demo mode: return placeholder translation."""
        return {
            'originalText': text,
            'translatedText': f'[演示翻译] {text[:100]}...',
            'sentences': [
                {'index': 1, 'original': text, 'translated': f'[演示翻译] {text[:100]}...'}
            ]
        }

    def _demo_chat(self, message: str) -> dict:
        """Demo mode: return placeholder response."""
        responses = {
            '这篇文章的核心是什么': '这篇文章主要探讨了研究领域的关键问题，提出了创新性的方法和解决方案。',
            '有什么创新点': '主要创新点包括新的方法论、实验设计和发现。',
            '有什么局限性': '研究的局限性包括数据规模、方法适用范围等方面。'
        }

        for key, value in responses.items():
            if key in message:
                return {'response': value, 'citations': [{'pageNumber': 1, 'text': '参考段落'}]}

        return {
            'response': f'关于"{message}"，这是一个很好的问题。基于文档内容，我的理解是这涉及到研究的核心方面...',
            'citations': [{'pageNumber': 1, 'text': '参考段落'}]
        }
