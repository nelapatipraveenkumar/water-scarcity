import pandas as pd
from database import db
from flask import current_app as app
from water_level_data import WaterLevelData
from dotenv import load_dotenv
import os

load_dotenv()

def validate_data(row):
    """Validate a single row of data from Excel."""
    try:
        # Clean and convert values, handling potential NaN or empty cells
        lat = pd.to_numeric(row['latitude'], errors='coerce')
        lon = pd.to_numeric(row['longitude'], errors='coerce')
        water_level = pd.to_numeric(str(row['water_level']).strip(), errors='coerce')
        
        # Check for NaN values after conversion
        if pd.isna(lat) or pd.isna(lon) or pd.isna(water_level):
            return False, "Missing or invalid data in row"
        
        if not (-90 <= lat <= 90):
            return False, f"Invalid latitude value: {lat}"
        if not (-180 <= lon <= 180):
            return False, f"Invalid longitude value: {lon}"
        if water_level < 0:
            return False, f"Invalid water level value: {water_level}"
            
        return True, None
    except Exception as e:
        return False, str(e)

def import_excel_data(file_path):
    """Import water level data from Excel file."""
    try:
        # Read Excel file
        df = pd.read_excel(file_path)
        
        # Clean column names by removing extra whitespace and newlines
        df.columns = df.columns.str.strip().str.replace('\n', '')
        
        # Check required columns
        required_columns = ['latitude', 'longitude', 'water_level']
        if not all(col in df.columns for col in required_columns):
            missing = [col for col in required_columns if col not in df.columns]
            raise ValueError(f"Missing required columns: {', '.join(missing)}")
        
        # Process each row
        success_count = 0
        error_rows = []
        
        for index, row in df.iterrows():
            is_valid, error_msg = validate_data(row)
            
            if is_valid:
                # Create new water level data entry
                water_data = WaterLevelData(
                    latitude=float(row['latitude']),
                    longitude=float(row['longitude']),
                    water_level=float(row['water_level'])
                )
                db.session.add(water_data)
                success_count += 1
            else:
                error_rows.append({
                    'row': index + 2,  # Excel row number (1-based + header)
                    'error': error_msg
                })
        
        # Commit changes if there were any successful imports
        if success_count > 0:
            db.session.commit()
        
        return {
            'success': True,
            'imported_count': success_count,
            'error_rows': error_rows
        }
        
    except Exception as e:
        db.session.rollback()
        return {
            'success': False,
            'error': str(e),
            'imported_count': 0,
            'error_rows': []
        }

def clear_water_level_data():
    """Clear all existing water level data."""
    try:
        WaterLevelData.query.delete()
        db.session.commit()
        return True
    except Exception:
        db.session.rollback()
        return False