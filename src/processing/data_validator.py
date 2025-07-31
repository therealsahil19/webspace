"""
Data validator for launch information using Pydantic schemas.
"""
import logging
from typing import Dict, List, Optional, Any, Union
from datetime import datetime
from pydantic import ValidationError

from src.models.schemas import LaunchData, SourceData, ConflictData, LaunchStatus

logger = logging.getLogger(__name__)


class DataValidationError(Exception):
    """Custom exception for data validation errors."""
    pass


class LaunchDataValidator:
    """Validates launch data using Pydantic schemas."""
    
    def __init__(self):
        """Initialize the validator."""
        self.validation_errors = []
        self.warnings = []
    
    def validate_launch_data(self, raw_data: Dict[str, Any]) -> Optional[LaunchData]:
        """
        Validate raw launch data against LaunchData schema.
        
        Args:
            raw_data: Raw dictionary data to validate
            
        Returns:
            LaunchData object if validation succeeds, None if it fails
            
        Raises:
            DataValidationError: If critical validation fails
        """
        try:
            # Clean and prepare data
            cleaned_data = self._clean_raw_data(raw_data)
            
            # Validate using Pydantic model
            launch_data = LaunchData(**cleaned_data)
            
            # Additional business logic validation
            self._validate_business_rules(launch_data)
            
            logger.info(f"Successfully validated launch data for: {launch_data.mission_name}")
            return launch_data
            
        except ValidationError as e:
            error_msg = f"Pydantic validation failed for {raw_data.get('mission_name', 'unknown')}: {e}"
            logger.error(error_msg)
            self.validation_errors.append(error_msg)
            return None
            
        except Exception as e:
            error_msg = f"Unexpected validation error for {raw_data.get('mission_name', 'unknown')}: {e}"
            logger.error(error_msg)
            self.validation_errors.append(error_msg)
            return None
    
    def validate_source_data(self, raw_data: Dict[str, Any]) -> Optional[SourceData]:
        """
        Validate source data against SourceData schema.
        
        Args:
            raw_data: Raw dictionary data to validate
            
        Returns:
            SourceData object if validation succeeds, None if it fails
        """
        try:
            source_data = SourceData(**raw_data)
            logger.debug(f"Successfully validated source data: {source_data.source_name}")
            return source_data
            
        except ValidationError as e:
            error_msg = f"Source data validation failed: {e}"
            logger.error(error_msg)
            self.validation_errors.append(error_msg)
            return None
    
    def validate_conflict_data(self, raw_data: Dict[str, Any]) -> Optional[ConflictData]:
        """
        Validate conflict data against ConflictData schema.
        
        Args:
            raw_data: Raw dictionary data to validate
            
        Returns:
            ConflictData object if validation succeeds, None if it fails
        """
        try:
            conflict_data = ConflictData(**raw_data)
            logger.debug(f"Successfully validated conflict data for field: {conflict_data.field_name}")
            return conflict_data
            
        except ValidationError as e:
            error_msg = f"Conflict data validation failed: {e}"
            logger.error(error_msg)
            self.validation_errors.append(error_msg)
            return None
    
    def validate_batch(self, raw_data_list: List[Dict[str, Any]]) -> List[LaunchData]:
        """
        Validate a batch of launch data.
        
        Args:
            raw_data_list: List of raw data dictionaries
            
        Returns:
            List of validated LaunchData objects (excludes failed validations)
        """
        validated_data = []
        
        for i, raw_data in enumerate(raw_data_list):
            try:
                launch_data = self.validate_launch_data(raw_data)
                if launch_data:
                    validated_data.append(launch_data)
                else:
                    logger.warning(f"Skipping invalid data at index {i}")
            except Exception as e:
                logger.error(f"Failed to validate data at index {i}: {e}")
                continue
        
        logger.info(f"Validated {len(validated_data)} out of {len(raw_data_list)} records")
        return validated_data
    
    def _clean_raw_data(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Clean and normalize raw data before validation.
        
        Args:
            raw_data: Raw data dictionary
            
        Returns:
            Cleaned data dictionary
        """
        cleaned = raw_data.copy()
        
        # Normalize status values
        if 'status' in cleaned and cleaned['status']:
            status_mapping = {
                'success': LaunchStatus.SUCCESS,
                'successful': LaunchStatus.SUCCESS,
                'failure': LaunchStatus.FAILURE,
                'failed': LaunchStatus.FAILURE,
                'upcoming': LaunchStatus.UPCOMING,
                'scheduled': LaunchStatus.UPCOMING,
                'in_flight': LaunchStatus.IN_FLIGHT,
                'in-flight': LaunchStatus.IN_FLIGHT,
                'aborted': LaunchStatus.ABORTED,
                'cancelled': LaunchStatus.ABORTED,
                'canceled': LaunchStatus.ABORTED,
            }
            status_lower = str(cleaned['status']).lower().strip()
            cleaned['status'] = status_mapping.get(status_lower, status_lower)
        
        # Clean string fields
        string_fields = ['slug', 'mission_name', 'vehicle_type', 'orbit', 'details']
        for field in string_fields:
            if field in cleaned and cleaned[field]:
                cleaned[field] = str(cleaned[field]).strip()
                if not cleaned[field]:  # Empty after stripping
                    cleaned[field] = None
        
        # Clean numeric fields
        if 'payload_mass' in cleaned and cleaned['payload_mass'] is not None:
            try:
                cleaned['payload_mass'] = float(cleaned['payload_mass'])
            except (ValueError, TypeError):
                logger.warning(f"Invalid payload_mass value: {cleaned['payload_mass']}")
                cleaned['payload_mass'] = None
        
        # Clean datetime fields
        if 'launch_date' in cleaned and cleaned['launch_date']:
            if isinstance(cleaned['launch_date'], str):
                try:
                    # Try to parse common datetime formats
                    for fmt in ['%Y-%m-%dT%H:%M:%S%z', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d']:
                        try:
                            cleaned['launch_date'] = datetime.strptime(cleaned['launch_date'], fmt)
                            break
                        except ValueError:
                            continue
                    else:
                        logger.warning(f"Could not parse launch_date: {cleaned['launch_date']}")
                        cleaned['launch_date'] = None
                except Exception as e:
                    logger.warning(f"Error parsing launch_date: {e}")
                    cleaned['launch_date'] = None
        
        # Generate slug if missing
        if not cleaned.get('slug') and cleaned.get('mission_name'):
            cleaned['slug'] = self._generate_slug(cleaned['mission_name'])
        
        return cleaned
    
    def _generate_slug(self, mission_name: str) -> str:
        """
        Generate a URL-friendly slug from mission name.
        
        Args:
            mission_name: Mission name to convert
            
        Returns:
            URL-friendly slug
        """
        import re
        
        # Convert to lowercase and replace spaces/special chars with hyphens
        slug = re.sub(r'[^\w\s-]', '', mission_name.lower())
        slug = re.sub(r'[-\s]+', '-', slug)
        slug = slug.strip('-')
        
        return slug
    
    def _validate_business_rules(self, launch_data: LaunchData) -> None:
        """
        Apply additional business logic validation.
        
        Args:
            launch_data: Validated LaunchData object
            
        Raises:
            DataValidationError: If business rules are violated
        """
        # Check for reasonable launch date ranges
        if launch_data.launch_date:
            current_year = datetime.now().year
            if launch_data.launch_date.year > current_year + 10:
                warning = f"Launch date seems too far in future: {launch_data.launch_date}"
                logger.warning(warning)
                self.warnings.append(warning)
        
        # Validate status consistency with launch date
        if launch_data.status == LaunchStatus.UPCOMING and launch_data.launch_date:
            if launch_data.launch_date < datetime.now():
                warning = f"Launch marked as upcoming but date is in past: {launch_data.mission_name}"
                logger.warning(warning)
                self.warnings.append(warning)
        
        # Check for reasonable payload mass
        if launch_data.payload_mass and launch_data.payload_mass > 100000:  # 100 tons
            warning = f"Payload mass seems unusually high: {launch_data.payload_mass}kg"
            logger.warning(warning)
            self.warnings.append(warning)
    
    def get_validation_summary(self) -> Dict[str, Any]:
        """
        Get summary of validation results.
        
        Returns:
            Dictionary with validation statistics
        """
        return {
            'errors': self.validation_errors,
            'warnings': self.warnings,
            'error_count': len(self.validation_errors),
            'warning_count': len(self.warnings)
        }
    
    def clear_results(self) -> None:
        """Clear validation results for next batch."""
        self.validation_errors.clear()
        self.warnings.clear()