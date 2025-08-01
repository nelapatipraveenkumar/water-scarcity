from app import app, db
from water_level_data import WaterLevelData

def test_database():
    with app.app_context():
        try:
            # Test database connection
            db.session.execute('SELECT 1')
            print('Database connection successful!')
            
            # Test model operations
            test_data = WaterLevelData(latitude=40.7128, longitude=-74.0060, water_level=7.5)
            db.session.add(test_data)
            db.session.commit()
            print('Successfully added test water level data')
            
            # Query test
            result = WaterLevelData.query.filter_by(latitude=40.7128).first()
            print(f'Retrieved test data - Water Level: {result.water_level}')
            
            # Cleanup
            db.session.delete(result)
            db.session.commit()
            print('Test data cleaned up successfully')
            return True
        except Exception as e:
            print(f'Database Error: {str(e)}')
            return False

if __name__ == '__main__':
    test_database()