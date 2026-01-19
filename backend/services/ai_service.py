import os
import re
from datetime import datetime

# Try to import OpenAI, but make it optional for demo mode
try:
    from openai import OpenAI
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False


class AiService:
    def __init__(self):
        self.client = None
        if HAS_OPENAI and os.getenv('OPENAI_API_KEY'):
            self.client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

    def extract_keywords(self, text: str) -> list:
        """Extract keywords from text."""
        if self.client:
            try:
                response = self.client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {
                            "role": "system",
                            "content": "You are a helpful assistant that extracts key academic terms from research papers. Return a JSON array of objects with 'term' and 'definition' fields."
                        },
                        {
                            "role": "user",
                            "content": f"Extract 5-10 key academic terms from this text and provide brief definitions:\n\n{text[:4000]}"
                        }
                    ],
                    temperature=0.3
                )
                # Parse response (simplified, in production use proper JSON parsing)
                content = response.choices[0].message.content
                return self._parse_keywords(content)
            except Exception as e:
                print(f"OpenAI error: {e}")

        # Fallback: Demo mode - extract common academic terms
        return self._demo_extract_keywords(text)

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
