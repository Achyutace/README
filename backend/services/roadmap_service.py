import os
import re
from datetime import datetime
import httpx
from openai import OpenAI

from core.config import settings
from core.llm_provider import resolve_llm_profile, create_openai_client


class MapService:
    def __init__(self):
        # 1. 解析配置
        self.profile = resolve_llm_profile(scene="roadmap")

        # 2. 初始化客户端
        if self.profile.is_available:
            self.client = create_openai_client(self.profile)
        else:
            self.client = None
            
    def generate_roadmap(self, text: str) -> dict:
        """Generate a concept roadmap from text."""
        if self.client:
            try:
        
                response = self.client.chat.completions.create(
                    model=self.profile.model,
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