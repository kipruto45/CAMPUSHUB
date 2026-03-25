"""
AI-Powered Document Summarization Service
"""

from typing import Optional
from django.conf import settings
import httpx


class SummarizationService:
    """Service for AI-powered document summarization"""
    
    def __init__(self):
        self.api_key = getattr(settings, 'OPENAI_API_KEY', None)
        self.model = getattr(settings, 'SUMMARIZATION_MODEL', 'gpt-3.5-turbo')
    
    async def summarize_text(
        self,
        text: str,
        max_length: int = 200,
        style: str = 'concise'
    ) -> str:
        """
        Summarize a long text/document
        
        Args:
            text: The text to summarize
            max_length: Maximum length of summary in words
            style: Summary style - 'concise', 'detailed', 'bullet_points'
        
        Returns:
            The summarized text
        """
        if not self.api_key:
            return self._fallback_summarize(text, max_length, style)
        
        style_instructions = {
            'concise': 'Provide a brief, to-the-point summary.',
            'detailed': 'Provide a comprehensive summary covering all key points.',
            'bullet_points': 'Summarize as bullet points for easy reading.'
        }
        
        prompt = f"""
        Summarize the following text. 
        Style: {style_instructions.get(style, style_instructions['concise'])}
        Maximum length: {max_length} words.
        
        Text to summarize:
        {text}
        
        Summary:
        """
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    'https://api.openai.com/v1/chat/completions',
                    headers={
                        'Authorization': f'Bearer {self.api_key}',
                        'Content-Type': 'application/json'
                    },
                    json={
                        'model': self.model,
                        'messages': [
                            {'role': 'user', 'content': prompt}
                        ],
                        'max_tokens': max_length * 4,
                        'temperature': 0.3
                    },
                    timeout=30.0
                )
                
                if response.status_code == 200:
                    data = response.json()
                    return data['choices'][0]['message']['content'].strip()
        except Exception as e:
            print(f"Summarization error: {e}")
        
        return self._fallback_summarize(text, max_length, style)
    
    def _fallback_summarize(self, text: str, max_length: int, style: str) -> str:
        """Fallback summarization using extractive method"""
        sentences = text.split('. ')
        
        if style == 'bullet_points':
            # Take first few sentences as bullets
            summary = sentences[:3]
            return '\n- '.join([s.strip() for s in summary])
        
        # Concise summary - take first portion
        words = text.split()[:max_length]
        return ' '.join(words) + ('...' if len(text.split()) > max_length else '')
    
    async def summarize_document(self, document_id: str) -> Optional[str]:
        """Summarize a document by ID"""
        from apps.resources.models import Resource
        
        try:
            resource = Resource.objects.get(id=document_id)
            if not resource.file:
                return None
            
            # In production, would extract text from file
            # For now, use description or metadata
            text = resource.description or ""
            
            if len(text) < 100:
                return "Document is too short to summarize."
            
            return await self.summarize_text(text)
        except Resource.DoesNotExist:
            return None
    
    async def generateLectureNotes(self, lecture_transcript: str) -> str:
        """Generate formatted lecture notes from transcript"""
        prompt = f"""
        Convert the following lecture transcript into well-structured study notes.
        Include:
        - Key topics covered
        - Important concepts (bold)
        - Key terms defined
        - Summary at the end
        
        Transcript:
        {lecture_transcript}
        
        Study Notes:
        """
        
        if not self.api_key:
            return self._fallback_summarize(lecture_transcript, 300, 'detailed')
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    'https://api.openai.com/v1/chat/completions',
                    headers={
                        'Authorization': f'Bearer {self.api_key}',
                        'Content-Type': 'application/json'
                    },
                    json={
                        'model': self.model,
                        'messages': [
                            {'role': 'user', 'content': prompt}
                        ],
                        'max_tokens': 2000,
                        'temperature': 0.3
                    },
                    timeout=30.0
                )
                
                if response.status_code == 200:
                    data = response.json()
                    return data['choices'][0]['message']['content'].strip()
        except Exception as e:
            print(f"Lecture notes error: {e}")
        
        return self._fallback_summarize(lecture_transcript, 300, 'detailed')
    
    async def extractKeyPoints(self, text: str, num_points: int = 5) -> list[str]:
        """Extract key points from text"""
        prompt = f"""
        Extract exactly {num_points} key points from the following text.
        Return as a JSON array of strings.
        
        Text:
        {text}
        
        Key Points:
        """
        
        if not self.api_key:
            sentences = text.split('. ')
            return [s.strip() for s in sentences[:num_points]]
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    'https://api.openai.com/v1/chat/completions',
                    headers={
                        'Authorization': f'Bearer {self.api_key}',
                        'Content-Type': 'application/json'
                    },
                    json={
                        'model': self.model,
                        'messages': [
                            {'role': 'user', 'content': prompt}
                        ],
                        'max_tokens': 500,
                        'temperature': 0.3
                    },
                    timeout=30.0
                )
                
                if response.status_code == 200:
                    data = response.json()
                    import json
                    content = data['choices'][0]['message']['content'].strip()
                    # Try to parse as JSON
                    try:
                        return json.loads(content)
                    except:
                        # Fallback to line parsing
                        return [line.strip() for line in content.split('\n') if line.strip()]
        except Exception as e:
            print(f"Key points extraction error: {e}")
        
        sentences = text.split('. ')
        return [s.strip() for s in sentences[:num_points]]


# Singleton instance
summarization_service = SummarizationService()
