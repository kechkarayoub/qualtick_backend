"""
Base repository for common data access operations.
"""
from typing import Any, Dict, List, Optional, Type
from django.db import models
from django.core.exceptions import ObjectDoesNotExist


class BaseRepository:
    """
    Base repository providing common CRUD operations.
    All specific repositories should inherit from this class.
    """
    
    model: Type[models.Model] = None
    
    @classmethod
    def get_by_id(cls, obj_id: int, db_alias: str = '') -> Optional[models.Model]:
        """
        Retrieve an object by its ID.
        
        Args:
            obj_id: The ID of the object
            db_alias: Database alias to use
            
        Returns:
            The model instance or None if not found
        """
        try:
            return cls.model.objects.using(db_alias or None).get(id=obj_id)
        except ObjectDoesNotExist:
            return None
    
    @classmethod
    def get_by_filter(cls, db_alias: str = '', **filters) -> Optional[models.Model]:
        """
        Retrieve a single object by filters.
        
        Args:
            db_alias: Database alias to use
            **filters: Django ORM filters
            
        Returns:
            The model instance or None if not found
        """
        try:
            return cls.model.objects.using(db_alias or None).get(**filters)
        except ObjectDoesNotExist:
            return None
    
    @classmethod
    def filter(cls, db_alias: str = '', **filters) -> models.QuerySet:
        """
        Retrieve multiple objects by filters.
        
        Args:
            db_alias: Database alias to use
            **filters: Django ORM filters
            
        Returns:
            QuerySet of matching objects
        """
        return cls.model.objects.using(db_alias or None).filter(**filters)
    
    @classmethod
    def all(cls, db_alias: str = '') -> models.QuerySet:
        """
        Retrieve all objects.
        
        Args:
            db_alias: Database alias to use
            
        Returns:
            QuerySet of all objects
        """
        return cls.model.objects.using(db_alias or None).all()
    
    @classmethod
    def create(cls, db_alias: str = '', **data) -> models.Model:
        """
        Create a new object.
        
        Args:
            db_alias: Database alias to use
            **data: Data for object creation
            
        Returns:
            The created model instance
        """
        instance = cls.model(**data)
        instance.save(using=db_alias or None)
        return instance
    
    @classmethod
    def update(cls, obj_id: int, db_alias: str = '', **data) -> Optional[models.Model]:
        """
        Update an existing object.
        
        Args:
            obj_id: The ID of the object
            db_alias: Database alias to use
            **data: Data to update
            
        Returns:
            The updated model instance or None if not found
        """
        obj = cls.get_by_id(obj_id, db_alias=db_alias)
        if obj:
            for key, value in data.items():
                setattr(obj, key, value)
            obj.save(using=db_alias or None)
        return obj
    
    @classmethod
    def delete(cls, obj_id: int, db_alias: str = '') -> bool:
        """
        Delete an object by ID.
        
        Args:
            obj_id: The ID of the object
            db_alias: Database alias to use
            
        Returns:
            True if deleted, False if not found
        """
        obj = cls.get_by_id(obj_id, db_alias=db_alias)
        if obj:
            obj.delete(using=db_alias or None)
            return True
        return False
    
    @classmethod
    def exists(cls, db_alias: str = '', **filters) -> bool:
        """
        Check if an object exists.
        
        Args:
            db_alias: Database alias to use
            **filters: Django ORM filters
            
        Returns:
            True if exists, False otherwise
        """
        return cls.model.objects.using(db_alias or None).filter(**filters).exists()
    
    @classmethod
    def count(cls, db_alias: str = '', **filters) -> int:
        """
        Count objects matching filters.
        
        Args:
            db_alias: Database alias to use
            **filters: Django ORM filters
            
        Returns:
            Count of matching objects
        """
        return cls.model.objects.using(db_alias or None).filter(**filters).count()
    
    @classmethod
    def bulk_create(cls, objects: List[Dict[str, Any]], db_alias: str = '') -> List[models.Model]:
        """
        Create multiple objects in a single query.
        
        Args:
            objects: List of dictionaries with object data
            db_alias: Database alias to use
            
        Returns:
            List of created model instances
        """
        instances = [cls.model(**obj) for obj in objects]
        return cls.model.objects.using(db_alias or None).bulk_create(instances)
    
    @classmethod
    def bulk_update(cls, objects: List[models.Model], fields: List[str], db_alias: str = '') -> int:
        """
        Update multiple objects in a single query.
        
        Args:
            objects: List of model instances to update
            fields: List of field names to update
            db_alias: Database alias to use
            
        Returns:
            Number of updated objects
        """
        return cls.model.objects.using(db_alias or None).bulk_update(objects, fields)
