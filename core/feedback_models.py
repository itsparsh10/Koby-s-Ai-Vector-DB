"""
MongoDB Models for User Feedback and Contributions
This module handles user-contributed knowledge and feedback storage
"""

from mongoengine import Document, StringField, DateTimeField, IntField, FloatField, ListField, DictField
from datetime import datetime
import re
from typing import List, Dict, Any


class UserContribution(Document):
    """
    MongoDB model for storing user contributions and feedback
    """
    # Basic fields
    question = StringField(required=True, max_length=1000)
    original_question = StringField(max_length=1000)  # The original training question if applicable
    answer = StringField(required=True, max_length=5000)
    question_type = StringField(required=True, max_length=100)
    
    # User information
    user_id = StringField(max_length=100)
    user_email = StringField(max_length=255)
    
    # Metadata
    timestamp = DateTimeField(default=datetime.utcnow)
    rating = FloatField(default=0.0, min_value=0.0, max_value=5.0)
    usage_count = IntField(default=0)
    improvement_type = StringField(max_length=50, default="enhancement")  # enhancement, correction, clarification
    
    # Search optimization
    similarity_keywords = ListField(StringField(max_length=50))
    question_hash = StringField(max_length=64)  # For quick duplicate detection
    
    # Additional metadata
    source_type = StringField(default="user_contribution", max_length=50)
    is_approved = StringField(default="pending", max_length=20)  # pending, approved, rejected
    
    meta = {
        'collection': 'user_contributions',
        'indexes': [
            'question',
            'question_type',
            'similarity_keywords',
            'timestamp',
            'rating',
            'question_hash'
        ]
    }
    
    def save(self, *args, **kwargs):
        """Override save to automatically generate keywords and hash"""
        if not self.similarity_keywords:
            self.similarity_keywords = self._extract_keywords(self.question)
        
        if not self.question_hash:
            self.question_hash = self._generate_question_hash(self.question)
        
        super().save(*args, **kwargs)
    
    def _extract_keywords(self, text: str) -> List[str]:
        """Extract keywords from question text for similarity matching"""
        # Convert to lowercase and remove special characters
        clean_text = re.sub(r'[^\w\s]', ' ', text.lower())
        
        # Split into words and filter out common stop words
        stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'is', 'are', 'was', 'were', 'be', 'been', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could', 'should', 'may', 'might', 'can', 'what', 'how', 'when', 'where', 'why', 'who'}
        
        words = [word for word in clean_text.split() if word not in stop_words and len(word) > 2]
        
        # Return unique keywords (limit to 10 most relevant)
        return list(set(words))[:10]
    
    def _generate_question_hash(self, text: str) -> str:
        """Generate a hash for quick duplicate detection"""
        import hashlib
        # Normalize text for consistent hashing
        normalized = re.sub(r'\s+', ' ', text.lower().strip())
        return hashlib.md5(normalized.encode()).hexdigest()
    
    def increment_usage(self):
        """Increment usage count when this contribution is used"""
        self.usage_count += 1
        self.save()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses"""
        return {
            'id': str(self.id),
            'question': self.question,
            'original_question': self.original_question,
            'answer': self.answer,
            'question_type': self.question_type,
            'user_id': self.user_id,
            'user_email': self.user_email,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'rating': self.rating,
            'usage_count': self.usage_count,
            'improvement_type': self.improvement_type,
            'similarity_keywords': self.similarity_keywords,
            'source_type': self.source_type,
            'is_approved': self.is_approved
        }


class FeedbackAnalytics(Document):
    """
    MongoDB model for tracking feedback analytics and system improvements
    """
    question_type = StringField(required=True, max_length=100)
    total_contributions = IntField(default=0)
    average_rating = FloatField(default=0.0)
    most_common_questions = ListField(DictField())
    
    # Store actual questions and answers for analytics
    questions_and_answers = ListField(DictField())  # Store Q&A pairs
    top_rated_qa = ListField(DictField())  # Store top-rated Q&A pairs
    recent_contributions = ListField(DictField())  # Store recent contributions
    
    last_updated = DateTimeField(default=datetime.utcnow)
    
    meta = {
        'collection': 'feedback_analytics',
        'indexes': ['question_type', 'last_updated']
    }
    
    def update_analytics(self, contribution: UserContribution):
        """Update analytics when a new contribution is added"""
        self.total_contributions += 1
        
        # Update average rating
        if self.total_contributions == 1:
            self.average_rating = contribution.rating
        else:
            # Calculate new average
            total_rating = self.average_rating * (self.total_contributions - 1) + contribution.rating
            self.average_rating = total_rating / self.total_contributions
        
        # Store the actual question and answer
        qa_pair = {
            'question': contribution.question,
            'answer': contribution.answer,
            'rating': contribution.rating,
            'user_id': contribution.user_id,
            'timestamp': contribution.timestamp.isoformat() if contribution.timestamp else None,
            'contribution_id': str(contribution.id),
            'improvement_type': contribution.improvement_type
        }
        
        # Add to questions_and_answers list
        if not self.questions_and_answers:
            self.questions_and_answers = []
        self.questions_and_answers.append(qa_pair)
        
        # Keep only last 50 Q&A pairs to avoid document size issues
        if len(self.questions_and_answers) > 50:
            self.questions_and_answers = self.questions_and_answers[-50:]
        
        # Update top-rated Q&A (keep top 10)
        if not self.top_rated_qa:
            self.top_rated_qa = []
        
        # Add current contribution to top-rated list
        self.top_rated_qa.append(qa_pair)
        
        # Sort by rating and keep only top 10
        self.top_rated_qa.sort(key=lambda x: x.get('rating', 0), reverse=True)
        self.top_rated_qa = self.top_rated_qa[:10]
        
        # Update recent contributions (keep last 20)
        if not self.recent_contributions:
            self.recent_contributions = []
        
        self.recent_contributions.append(qa_pair)
        
        # Sort by timestamp and keep only last 20
        self.recent_contributions.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
        self.recent_contributions = self.recent_contributions[:20]
        
        self.last_updated = datetime.utcnow()
        self.save()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses"""
        return {
            'question_type': self.question_type,
            'total_contributions': self.total_contributions,
            'average_rating': self.average_rating,
            'most_common_questions': self.most_common_questions,
            'questions_and_answers': self.questions_and_answers or [],
            'top_rated_qa': self.top_rated_qa or [],
            'recent_contributions': self.recent_contributions or [],
            'last_updated': self.last_updated.isoformat() if self.last_updated else None
        }
    
    def get_questions_by_rating(self, min_rating: float = 0.0) -> List[Dict[str, Any]]:
        """Get questions and answers filtered by minimum rating"""
        if not self.questions_and_answers:
            return []
        
        return [qa for qa in self.questions_and_answers if qa.get('rating', 0) >= min_rating]
    
    def get_questions_by_keyword(self, keyword: str) -> List[Dict[str, Any]]:
        """Get questions and answers containing a specific keyword"""
        if not self.questions_and_answers:
            return []
        
        keyword_lower = keyword.lower()
        return [
            qa for qa in self.questions_and_answers 
            if keyword_lower in qa.get('question', '').lower() or 
               keyword_lower in qa.get('answer', '').lower()
        ]
    
    def get_recent_questions(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent questions and answers"""
        if not self.recent_contributions:
            return []
        
        return self.recent_contributions[:limit]
    
    def get_top_rated_questions(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get top-rated questions and answers"""
        if not self.top_rated_qa:
            return []
        
        return self.top_rated_qa[:limit]
    
    def search_questions(self, search_term: str) -> List[Dict[str, Any]]:
        """Search questions and answers by search term"""
        if not self.questions_and_answers:
            return []
        
        search_lower = search_term.lower()
        results = []
        
        for qa in self.questions_and_answers:
            question = qa.get('question', '').lower()
            answer = qa.get('answer', '').lower()
            
            if search_lower in question or search_lower in answer:
                results.append(qa)
        
        # Sort by rating (highest first)
        results.sort(key=lambda x: x.get('rating', 0), reverse=True)
        
        return results
