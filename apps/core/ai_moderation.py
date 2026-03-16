"""
AI-Powered Content Moderation Service
Provides automated content analysis and moderation for resources
"""

import re
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional, Dict, Any
from django.conf import settings


class ModerationLevel(Enum):
    """Content moderation risk levels."""
    SAFE = "safe"
    LOW_RISK = "low_risk"
    MEDIUM_RISK = "medium_risk"
    HIGH_RISK = "high_risk"
    BLOCKED = "blocked"


class ModerationCategory(Enum):
    """Categories of content that can be flagged."""
    INAPPROPRIATE = "inappropriate"
    SPAM = "spam"
    COPYRIGHT = "copyright"
    MISINFORMATION = "misinformation"
    HARASSMENT = "harassment"
    VIOLENCE = "violence"
    ADULT = "adult"
    SENSITIVE = "sensitive"
    NONE = "none"


@dataclass
class ModerationResult:
    """Result of content moderation analysis."""
    is_safe: bool
    risk_level: ModerationLevel
    categories: List[ModerationCategory]
    confidence_score: float
    flagged_words: List[str]
    recommendation: str
    details: Dict[str, Any]


class AIContentModerationService:
    """
    AI-powered content moderation service.
    
    This service analyzes content for potentially inappropriate material
    and provides risk assessments. In production, this would integrate
    with actual AI services like Google Perspective API, AWS Rekognition,
    or Azure Content Safety.
    """

    # Sensitive keywords for different categories (simplified for demo)
    INAPPROPRIATE_KEYWORDS = [
        'inappropriate', 'offensive', 'explicit', 'nsfw',
    ]
    
    SPAM_KEYWORDS = [
        'spam', 'clickbait', 'free money', 'buy now', 'limited offer',
        'act now', 'urgent', 'winner', 'prize', 'congratulations',
    ]
    
    COPYRIGHT_KEYWORDS = [
        'copyright', 'pirated', 'torrent', 'cracked', 'serial key',
    ]
    
    VIOLENCE_KEYWORDS = [
        'violence', 'harm', 'attack', 'threat', 'weapon',
    ]
    
    HARASSMENT_KEYWORDS = [
        'harass', 'bully', 'hate', 'discriminate', 'threaten',
    ]
    
    ADULT_KEYWORDS = [
        'adult', 'explicit', 'nsfw', '18+', 'nude',
    ]

    # Risk weight configuration
    CATEGORY_WEIGHTS = {
        ModerationCategory.INAPPROPRIATE: 0.8,
        ModerationCategory.SPAM: 0.5,
        ModerationCategory.COPYRIGHT: 0.7,
        ModerationCategory.MISINFORMATION: 0.6,
        ModerationCategory.HARASSMENT: 0.9,
        ModerationCategory.VIOLENCE: 0.9,
        ModerationCategory.ADULT: 0.95,
        ModerationCategory.SENSITIVE: 0.4,
    }

    @classmethod
    def analyze_content(
        cls,
        title: str,
        description: str = "",
        content_text: str = "",
    ) -> ModerationResult:
        """
        Analyze content for inappropriate material.
        
        Args:
            title: Resource title
            description: Resource description
            content_text: Full text content of the resource
            
        Returns:
            ModerationResult with risk assessment
        """
        # Combine all text for analysis
        full_text = f"{title} {description} {content_text}".lower()
        
        # Track flagged words by category
        flagged_by_category: Dict[ModerationCategory, List[str]] = {
            cat: [] for cat in ModerationCategory
        }
        
        # Check each category
        for keyword in cls.INAPPROPRIATE_KEYWORDS:
            if keyword in full_text:
                flagged_by_category[ModerationCategory.INAPPROPRIATE].append(keyword)
                
        for keyword in cls.SPAM_KEYWORDS:
            if keyword in full_text:
                flagged_by_category[ModerationCategory.SPAM].append(keyword)
                
        for keyword in cls.COPYRIGHT_KEYWORDS:
            if keyword in full_text:
                flagged_by_category[ModerationCategory.COPYRIGHT].append(keyword)
                
        for keyword in cls.VIOLENCE_KEYWORDS:
            if keyword in full_text:
                flagged_by_category[ModerationCategory.VIOLENCE].append(keyword)
                
        for keyword in cls.HARASSMENT_KEYWORDS:
            if keyword in full_text:
                flagged_by_category[ModerationCategory.HARASSMENT].append(keyword)
                
        for keyword in cls.ADULT_KEYWORDS:
            if keyword in full_text:
                flagged_by_category[ModerationCategory.ADULT].append(keyword)
        
        # Calculate risk score
        risk_score = 0.0
        categories_found = []
        all_flagged_words = []
        
        for category, words in flagged_by_category.items():
            if words:
                categories_found.append(category)
                all_flagged_words.extend(words)
                weight = cls.CATEGORY_WEIGHTS.get(category, 0.5)
                # Calculate category risk (more keywords = higher risk)
                category_risk = min(len(words) * 0.2, 1.0) * weight
                risk_score = max(risk_score, category_risk)
        
        # Determine risk level
        if risk_score >= 0.9:
            risk_level = ModerationLevel.BLOCKED
        elif risk_score >= 0.7:
            risk_level = ModerationLevel.HIGH_RISK
        elif risk_score >= 0.4:
            risk_level = ModerationLevel.MEDIUM_RISK
        elif risk_score >= 0.2:
            risk_level = ModerationLevel.LOW_RISK
        else:
            risk_level = ModerationLevel.SAFE
        
        # Determine if safe
        is_safe = risk_level in [ModerationLevel.SAFE, ModerationLevel.LOW_RISK]
        
        # Generate recommendation
        if risk_level == ModerationLevel.BLOCKED:
            recommendation = "Content has been automatically blocked due to severe policy violations."
        elif risk_level == ModerationLevel.HIGH_RISK:
            recommendation = "Content requires immediate manual review by a moderator."
        elif risk_level == ModerationLevel.MEDIUM_RISK:
            recommendation = "Content should be reviewed by a moderator."
        elif risk_level == ModerationLevel.LOW_RISK:
            recommendation = "Content appears acceptable but may warrant review."
        else:
            recommendation = "Content approved for publication."
        
        return ModerationResult(
            is_safe=is_safe,
            risk_level=risk_level,
            categories=categories_found if categories_found else [ModerationCategory.NONE],
            confidence_score=1.0 - (risk_score * 0.1),  # Higher risk = lower confidence
            flagged_words=all_flagged_words,
            recommendation=recommendation,
            details={
                'risk_score': risk_score,
                'word_count': len(full_text.split()),
                'flagged_count': len(all_flagged_words),
            }
        )

    @classmethod
    def analyze_resource(cls, resource) -> ModerationResult:
        """
        Analyze a Resource model for moderation.
        
        Args:
            resource: Resource model instance
            
        Returns:
            ModerationResult with risk assessment
        """
        title = getattr(resource, 'title', '') or ''
        description = getattr(resource, 'description', '') or ''
        
        # Get content text if available
        content_text = ''
        if hasattr(resource, 'file'):
            # For file-based resources, we could extract text
            # This is a placeholder
            pass
        
        return cls.analyze_content(title, description, content_text)

    @classmethod
    def batch_analyze(cls, resources) -> List[ModerationResult]:
        """
        Analyze multiple resources.
        
        Args:
            resources: QuerySet or list of Resource models
            
        Returns:
            List of ModerationResult
        """
        results = []
        for resource in resources:
            result = cls.analyze_resource(resource)
            results.append(result)
        return results

    @classmethod
    def get_moderation_stats(cls, resources) -> Dict[str, Any]:
        """
        Get moderation statistics for a set of resources.
        
        Args:
            resources: QuerySet or list of Resource models
            
        Returns:
            Dictionary with statistics
        """
        results = cls.batch_analyze(resources)
        
        stats = {
            'total': len(results),
            'safe': 0,
            'low_risk': 0,
            'medium_risk': 0,
            'high_risk': 0,
            'blocked': 0,
            'by_category': {cat.value: 0 for cat in ModerationCategory if cat != ModerationCategory.NONE},
        }
        
        for result in results:
            if result.risk_level == ModerationLevel.SAFE:
                stats['safe'] += 1
            elif result.risk_level == ModerationLevel.LOW_RISK:
                stats['low_risk'] += 1
            elif result.risk_level == ModerationLevel.MEDIUM_RISK:
                stats['medium_risk'] += 1
            elif result.risk_level == ModerationLevel.HIGH_RISK:
                stats['high_risk'] += 1
            elif result.risk_level == ModerationLevel.BLOCKED:
                stats['blocked'] += 1
            
            for cat in result.categories:
                if cat != ModerationCategory.NONE:
                    stats['by_category'][cat.value] = stats['by_category'].get(cat.value, 0) + 1
        
        return stats


class ModerationQueueService:
    """
    Service for managing the content moderation queue.
    """

    @staticmethod
    def get_pending_resources():
        """Get resources pending moderation."""
        from apps.resources.models import Resource
        
        return Resource.objects.filter(
            moderation_status='pending'
        ).select_related('uploaded_by', 'faculty', 'department')

    @staticmethod
    def get_flagged_resources():
        """Get resources that have been flagged for review."""
        from apps.resources.models import Resource
        
        return Resource.objects.filter(
            moderation_status='flagged'
        ).select_related('uploaded_by', 'faculty', 'department')

    @staticmethod
    def auto_moderate_resources():
        """
        Automatically moderate pending resources using AI.
        
        Returns:
            Dictionary with moderation results
        """
        pending = ModerationQueueService.get_pending_resources()
        
        results = {
            'auto_approved': 0,
            'auto_flagged': 0,
            'auto_blocked': 0,
            'details': [],
        }
        
        for resource in pending:
            result = AIContentModerationService.analyze_resource(resource)
            
            if result.risk_level == ModerationLevel.BLOCKED:
                resource.moderation_status = 'blocked'
                resource.moderation_notes = f"Auto-blocked: {result.recommendation}"
                results['auto_blocked'] += 1
            elif result.risk_level in [ModerationLevel.HIGH_RISK, ModerationLevel.MEDIUM_RISK]:
                resource.moderation_status = 'flagged'
                resource.moderation_notes = f"AI Flagged: {result.recommendation}"
                results['auto_flagged'] += 1
            else:
                resource.moderation_status = 'approved'
                resource.moderation_notes = f"Auto-approved: {result.recommendation}"
                results['auto_approved'] += 1
            
            # Store moderation result as JSON
            import json
            resource.ai_moderation_result = json.dumps({
                'risk_level': result.risk_level.value,
                'categories': [c.value for c in result.categories],
                'confidence_score': result.confidence_score,
                'flagged_words': result.flagged_words,
            })
            
            resource.save()
            
            results['details'].append({
                'resource_id': resource.id,
                'title': resource.title,
                'result': result.risk_level.value,
            })
        
        return results
