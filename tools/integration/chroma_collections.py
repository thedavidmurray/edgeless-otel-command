#!/usr/bin/env python3
"""
Chroma Collection Schema and Manager
Defines the standardized collections and metadata for the knowledge system
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime
from enum import Enum
import json


class SourceType(Enum):
    """Source systems for knowledge"""
    SERENA = "serena"
    OBSIDIAN = "obsidian"
    INGESTION = "ingestion"
    MANUAL = "manual"
    AUTOMATED = "automated"


class ContentType(Enum):
    """Types of content stored"""
    PATTERN = "pattern"
    SOLUTION = "solution"
    INSIGHT = "insight"
    ARCHITECTURE = "architecture"
    ERROR = "error"
    FUNCTION = "function"
    CLASS = "class"
    CONCEPT = "concept"


class ProjectName(Enum):
    """Active projects in the system"""
    MONTE_CARLO = "monte-carlo"
    ORG_INVENTORY = "refactored-org-inventory"
    TOTAL_SERIALISM = "total-serialism-art"
    BTC_TRADER = "btc-sentiment-trader"
    TOOLS = "tools"
    CROSS_PROJECT = "cross-project"
    AGENT_PLATFORM = "agent-platform"


@dataclass
class ChromaMetadata:
    """Standardized metadata schema for all embeddings"""
    source: SourceType
    project: ProjectName
    content_type: ContentType
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    related_files: List[str] = field(default_factory=list)
    obsidian_links: List[str] = field(default_factory=list)
    confidence_score: float = 1.0
    tags: List[str] = field(default_factory=list)
    language: Optional[str] = None
    complexity: Optional[str] = None
    usage_count: int = 0
    last_accessed: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for Chroma storage"""
        return {
            "source": self.source.value,
            "project": self.project.value,
            "content_type": self.content_type.value,
            "timestamp": self.timestamp,
            "related_files": json.dumps(self.related_files),
            "obsidian_links": json.dumps(self.obsidian_links),
            "confidence_score": self.confidence_score,
            "tags": json.dumps(self.tags),
            "language": self.language,
            "complexity": self.complexity,
            "usage_count": self.usage_count,
            "last_accessed": self.last_accessed
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ChromaMetadata':
        """Create from dictionary"""
        return cls(
            source=SourceType(data["source"]),
            project=ProjectName(data["project"]),
            content_type=ContentType(data["content_type"]),
            timestamp=data["timestamp"],
            related_files=json.loads(data.get("related_files", "[]")),
            obsidian_links=json.loads(data.get("obsidian_links", "[]")),
            confidence_score=data.get("confidence_score", 1.0),
            tags=json.loads(data.get("tags", "[]")),
            language=data.get("language"),
            complexity=data.get("complexity"),
            usage_count=data.get("usage_count", 0),
            last_accessed=data.get("last_accessed")
        )


class ChromaCollections:
    """Collection definitions for the knowledge system"""
    
    # Core collections
    CODE_PATTERNS = "code_patterns"
    PROJECT_KNOWLEDGE = "project_knowledge"
    LEARNING_INSIGHTS = "learning_insights"
    DEBUG_SOLUTIONS = "debug_solutions"
    ARCHITECTURAL_DECISIONS = "architectural_decisions"
    
    # Collection metadata
    COLLECTION_METADATA = {
        CODE_PATTERNS: {
            "description": "Reusable code patterns across projects",
            "embedding_model": "text-embedding-ada-002",
            "distance_metric": "cosine"
        },
        PROJECT_KNOWLEDGE: {
            "description": "Project-specific insights and knowledge",
            "embedding_model": "text-embedding-ada-002",
            "distance_metric": "cosine"
        },
        LEARNING_INSIGHTS: {
            "description": "Insights from ingested content and research",
            "embedding_model": "text-embedding-ada-002",
            "distance_metric": "cosine"
        },
        DEBUG_SOLUTIONS: {
            "description": "Error-solution pairs for debugging",
            "embedding_model": "text-embedding-ada-002",
            "distance_metric": "cosine"
        },
        ARCHITECTURAL_DECISIONS: {
            "description": "Design choices and architectural rationale",
            "embedding_model": "text-embedding-ada-002",
            "distance_metric": "cosine"
        }
    }
    
    @classmethod
    def get_all_collections(cls) -> List[str]:
        """Get list of all collection names"""
        return [
            cls.CODE_PATTERNS,
            cls.PROJECT_KNOWLEDGE,
            cls.LEARNING_INSIGHTS,
            cls.DEBUG_SOLUTIONS,
            cls.ARCHITECTURAL_DECISIONS
        ]
    
    @classmethod
    def get_collection_for_content(cls, content_type: ContentType) -> str:
        """Determine which collection to use based on content type"""
        mapping = {
            ContentType.PATTERN: cls.CODE_PATTERNS,
            ContentType.SOLUTION: cls.DEBUG_SOLUTIONS,
            ContentType.INSIGHT: cls.LEARNING_INSIGHTS,
            ContentType.ARCHITECTURE: cls.ARCHITECTURAL_DECISIONS,
            ContentType.ERROR: cls.DEBUG_SOLUTIONS,
            ContentType.FUNCTION: cls.CODE_PATTERNS,
            ContentType.CLASS: cls.CODE_PATTERNS,
            ContentType.CONCEPT: cls.PROJECT_KNOWLEDGE
        }
        return mapping.get(content_type, cls.PROJECT_KNOWLEDGE)


class MetadataValidator:
    """Validates metadata consistency across systems"""
    
    @staticmethod
    def validate(metadata: ChromaMetadata) -> List[str]:
        """Validate metadata and return list of issues"""
        issues = []
        
        # Check required fields
        if not metadata.source:
            issues.append("Source is required")
        if not metadata.project:
            issues.append("Project is required")
        if not metadata.content_type:
            issues.append("Content type is required")
            
        # Validate confidence score
        if not 0 <= metadata.confidence_score <= 1:
            issues.append("Confidence score must be between 0 and 1")
            
        # Validate timestamp format
        try:
            datetime.fromisoformat(metadata.timestamp)
        except ValueError:
            issues.append("Invalid timestamp format")
            
        # Check file paths
        for file_path in metadata.related_files:
            if not file_path.startswith("/"):
                issues.append(f"File path should be absolute: {file_path}")
                
        return issues
    
    @staticmethod
    def normalize(metadata: ChromaMetadata) -> ChromaMetadata:
        """Normalize metadata for consistency"""
        # Ensure lowercase tags
        metadata.tags = [tag.lower() for tag in metadata.tags]
        
        # Update last accessed
        metadata.last_accessed = datetime.now().isoformat()
        
        # Increment usage count
        metadata.usage_count += 1
        
        return metadata


# Example usage patterns
if __name__ == "__main__":
    # Create metadata for a code pattern
    pattern_metadata = ChromaMetadata(
        source=SourceType.SERENA,
        project=ProjectName.ORG_INVENTORY,
        content_type=ContentType.PATTERN,
        related_files=["/active-projects/refactored-org-inventory/Services/RoleIDGenerator.cs"],
        tags=["id-generation", "deduplication", "c#"],
        language="csharp",
        complexity="medium"
    )
    
    # Validate
    issues = MetadataValidator.validate(pattern_metadata)
    if issues:
        print(f"Validation issues: {issues}")
    else:
        print("Metadata is valid")
    
    # Get appropriate collection
    collection = ChromaCollections.get_collection_for_content(ContentType.PATTERN)
    print(f"Should store in collection: {collection}")
    
    # Convert to dict for storage
    storage_dict = pattern_metadata.to_dict()
    print(f"Storage format: {json.dumps(storage_dict, indent=2)}")