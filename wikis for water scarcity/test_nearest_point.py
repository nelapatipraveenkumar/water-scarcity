from app import app, db
from water_level_data import WaterLevelData

def test_nearest_point_calculation():
    with app.app_context():
        try:
            # Add test data points
            test_points = [
                WaterLevelData(latitude=40.7128, longitude=-74.0060, water_level=7.5),  # NYC
                WaterLevelData(latitude=40.7142, longitude=-74.0064, water_level=3.2),  # Near NYC
                WaterLevelData(latitude=34.0522, longitude=-118.2437, water_level=9.8),  # LA
            ]
            
            for point in test_points:
                db.session.add(point)
            db.session.commit()
            print('Test data points added successfully')
            
            # Test finding nearest point
            test_lat = 13.0220032  # Chennai, India
            test_lon = 80.2062336
            
            nearest = WaterLevelData.find_nearest_point(test_lat, test_lon)
            if nearest:
                print(f'Found nearest point:')
                print(f'Latitude: {nearest.latitude}')
                print(f'Longitude: {nearest.longitude}')
                print(f'Water Level: {nearest.water_level}')
                print(f'Scarcity Level: {WaterLevelData.get_scarcity_level(nearest.water_level)}')
                
                # Verify if the nearest point is the closest one (should be one of the NYC points)
                is_correct = abs(nearest.latitude - 40.7128) < 1 or abs(nearest.latitude - 40.7142) < 1
                print(f'Nearest point calculation is correct: {is_correct}')
            else:
                print('No nearest point found')
            
            # Cleanup
            for point in test_points:
                db.session.delete(point)
            db.session.commit()
            print('Test data cleaned up successfully')
            
            return True
            
        except Exception as e:
            print(f'Test Error: {str(e)}')
            db.session.rollback()
            return False

if __name__ == '__main__':
    test_nearest_point_calculation()