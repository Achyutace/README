"""
AI 服务 - 路线图生成和文档摘要

使用 OpenAI API 实现 AI 功能
"""

import os
import re
import json
from datetime import datetime

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

    def generate_roadmap(self, text: str) -> dict:
        """生成知识路线图"""
        if self.client:
            try:
                response = self.client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {
                            "role": "system",
                            "content": "You are a helpful assistant that extracts key concepts and creates a learning roadmap from academic papers. Return a JSON structure with 'nodes' (list of {id, label, data: {description, papers: [{title, link, year}]}}) and 'edges' (list of {id, source, target})."
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

        return self._demo_roadmap()

    def generate_summary(self, text: str) -> dict:
        """生成文档摘要"""
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

        return self._demo_summary()

    def _parse_bullets(self, content: str) -> list:
        """解析要点列表"""
        bullets = []
        for line in content.split('\n'):
            line = line.strip()
            if line and (line[0] in '-•*' or (line[0].isdigit() and '.' in line[:3])):
                cleaned = re.sub(r'^[\d\.\-\•\*]+\s*', '', line).strip()
                if cleaned:
                    bullets.append(cleaned)
        return bullets[:3] if bullets else [
            "This paper presents research on the given topic.",
            "The methodology involves analysis and experimentation.",
            "Future work may address current limitations."
        ]

    def _parse_json_roadmap(self, text: str) -> dict:
        """解析 JSON 路线图"""
        try:
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0].strip()
            elif "```" in text:
                text = text.split("```")[1].split("```")[0].strip()
            return json.loads(text)
        except:
            return self._demo_roadmap()

    def _demo_roadmap(self) -> dict:
        """演示模式路线图"""
        return {
            "nodes": [
                {"id": "1", "label": "Large Language Models", "data": {"label": "Large Language Models", "description": "Foundation models trained on vast amounts of data.", "papers": [{"title": "Language Models are Few-Shot Learners", "link": "https://arxiv.org/abs/2005.14165", "year": "2020"}]}, "position": {"x": 250, "y": 0}},
                {"id": "2", "label": "Chain-of-Thought", "data": {"label": "Chain-of-Thought", "description": "Generating intermediate reasoning steps.", "papers": [{"title": "Chain-of-Thought Prompting", "link": "https://arxiv.org/abs/2201.11903", "year": "2022"}]}, "position": {"x": 100, "y": 150}},
                {"id": "3", "label": "Self-Consistency", "data": {"label": "Self-Consistency", "description": "Sampling multiple reasoning paths.", "papers": []}, "position": {"x": 400, "y": 150}},
                {"id": "4", "label": "Prompt Engineering", "data": {"label": "Prompt Engineering", "description": "Techniques for designing inputs.", "papers": []}, "position": {"x": 250, "y": 300}}
            ],
            "edges": [
                {"id": "e1-2", "source": "1", "target": "2"},
                {"id": "e1-3", "source": "1", "target": "3"},
                {"id": "e2-3", "source": "2", "target": "3"},
                {"id": "e4-2", "source": "4", "target": "2"}
            ]
        }

    def _demo_summary(self) -> dict:
        """演示模式摘要"""
        return {
            'bullets': [
                '本文研究了相关主题的核心问题和方法。',
                '提出了创新性的解决方案和实验验证。',
                '讨论了研究的局限性和未来工作方向。'
            ],
            'generatedAt': datetime.now().isoformat()
        }
