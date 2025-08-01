from database import db
from sqlalchemy import func

class WaterLevelData(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)
    water_level = db.Column(db.Float, nullable=False)

    @staticmethod
    def get_scarcity_level(water_level):
        if 0 <= water_level <= 5:
            return 'low'
        elif 5 < water_level <= 10:
            return 'moderate'
        else:
            return 'high'

    @staticmethod
    def find_nearest_point(lat, lon):
        # Using Haversine formula to find nearest point
        earth_radius = 6371  # Earth's radius in kilometers
        
        # Ensure coordinates are within valid ranges
        if not (-90 <= lat <= 90) or not (-180 <= lon <= 180):
            return None
            
        try:
            # Calculate distance using simplified Haversine formula
            lat1_rad = db.func.radians(lat)
            lat2_rad = db.func.radians(WaterLevelData.latitude)
            delta_lat = db.func.radians(WaterLevelData.latitude - lat)
            delta_lon = db.func.radians(WaterLevelData.longitude - lon)
            
            # Calculate using Haversine formula components
            a = db.func.pow(db.func.sin(delta_lat / 2), 2) + \
                db.func.cos(lat1_rad) * db.func.cos(lat2_rad) * \
                db.func.pow(db.func.sin(delta_lon / 2), 2)
            
            c = 2 * db.func.asin(db.func.sqrt(a))
            distance = earth_radius * c
            
            return WaterLevelData.query.order_by(distance).first()
        except Exception as e:
            print(f'Error finding nearest point: {str(e)}')
            return None