from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, abort
from sqlalchemy.exc import SQLAlchemyError
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta
from flask_wtf import CSRFProtect
from flask_wtf.csrf import CSRFProtect, generate_csrf
import os
from dotenv import load_dotenv
from database import db, init_db

app = Flask(__name__)
csrf = CSRFProtect(app)

load_dotenv()

app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-key-please-change')
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///wiki.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = os.path.join(app.root_path, 'static', 'uploads')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

init_db(app)

@app.errorhandler(413)
def too_large(e):
    return "File is too large", 413

@app.errorhandler(404)
def not_found(e):
    return render_template('404.html'), 404

@app.errorhandler(500)
def server_error(e):
    return render_template('500.html'), 500
app.config['TINYMCE_API_KEY'] = os.getenv('TINYMCE_API_KEY')
app.config['UPLOAD_EXTENSIONS'] = ['.png', '.jpg', '.jpeg', '.gif', '.mp4', '.webm']

# Create upload folder if it doesn't exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'mp4', 'webm'}

# Environment configuration
ENV = os.getenv('FLASK_ENV', 'development')
DEBUG = ENV == 'development'

# Import models
from water_level_data import WaterLevelData

# Configure logging based on environment
if ENV == 'production':
    import logging
    from logging.handlers import RotatingFileHandler
    logging_handler = RotatingFileHandler('app.log', maxBytes=10000, backupCount=3)
    logging_handler.setLevel(logging.WARNING)
    app.logger.addHandler(logging_handler)
    app.logger.setLevel(logging.WARNING)

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS and \
           os.path.splitext(filename)[1].lower() in app.config['UPLOAD_EXTENSIONS']

def validate_file_content(file):
    try:
        header = file.read(512)  # Read first 512 bytes
        file.seek(0)  # Reset file pointer
        
        # Check file size
        file.seek(0, 2)  # Seek to end
        size = file.tell()
        file.seek(0)  # Reset pointer
        
        if size > app.config['MAX_CONTENT_LENGTH']:
            app.logger.warning(f'File size {size} exceeds limit of {app.config["MAX_CONTENT_LENGTH"]} bytes')
            return False
            
        # Image validation
        if file.filename.lower().endswith(('.jpg', '.jpeg', '.png', '.gif')):
            if not (header.startswith(b'\xff\xd8') or  # JPEG
                    header.startswith(b'\x89PNG') or  # PNG
                    header.startswith(b'GIF')):       # GIF
                app.logger.warning(f'Invalid image format for file {file.filename}')
                return False
        
        # Video validation
        elif file.filename.lower().endswith(('.mp4', '.webm')):
            if not (header.startswith(b'\x00\x00\x00') or  # MP4
                    header.startswith(b'\x1a\x45\xdf\xa3')):  # WebM
                app.logger.warning(f'Invalid video format for file {file.filename}')
                return False
        
        return True
    except Exception as e:
        app.logger.error(f'File validation error: {str(e)}')
        return False

from water_level_data import WaterLevelData
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128))
    wikis = db.relationship('Wiki', backref='author', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class WikiMedia(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), nullable=False)
    file_type = db.Column(db.String(10), nullable=False)  # 'image' or 'video'
    wiki_id = db.Column(db.Integer, db.ForeignKey('wiki.id'), nullable=False)

class Wiki(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    content = db.Column(db.Text, nullable=False)
    date_posted = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    media_files = db.relationship('WikiMedia', backref='wiki', lazy=True, cascade='all, delete-orphan')
    water_scarcity_level = db.Column(db.String(20), nullable=False)  # 'low', 'moderate', 'high'
    category = db.Column(db.String(20), nullable=False)  # 'agriculture', 'domestic', 'business'

    def delete(self):
        for media in self.media_files:
            try:
                os.remove(os.path.join(app.config['UPLOAD_FOLDER'], media.filename))
            except OSError:
                pass
        db.session.delete(self)
        db.session.commit()

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route('/')
def home():
    wikis = Wiki.query.order_by(Wiki.date_posted.desc()).all()
    return render_template('home.html', wikis=wikis)

@app.route('/wiki/<int:wiki_id>')
def view_wiki(wiki_id):
    wiki = Wiki.query.get_or_404(wiki_id)
    return render_template('view_wiki.html', wiki=wiki)

@app.route('/create_wiki', methods=['GET', 'POST'])
@login_required
def create_wiki():
    if request.method == 'POST':
        try:
            if not request.form.get('title') or not request.form.get('content') or not request.form.get('water_scarcity_level') or not request.form.get('category'):
                flash('Title, content, water scarcity level, and category are required!')
                return redirect(url_for('create_wiki'))

            water_scarcity_level = request.form['water_scarcity_level']
            category = request.form['category']

            title = request.form['title']
            content = request.form['content']
            wiki = Wiki(title=title, content=content, author=current_user, water_scarcity_level=water_scarcity_level, category=category)
            
            # Handle media file uploads
            media_files = request.files.getlist('media')
            for file in media_files:
                if not file or file.filename == '':
                    continue
                    
                if not allowed_file(file.filename):
                    flash(f'File type not allowed for {file.filename}. Allowed types: {", ".join(ALLOWED_EXTENSIONS)}')
                    continue
                    
                try:
                    if not validate_file_content(file):
                        flash(f'Invalid file content or size for {file.filename}')
                        continue

                    base_filename = secure_filename(file.filename)
                    filename = base_filename
                    counter = 1
                    while os.path.exists(os.path.join(app.config['UPLOAD_FOLDER'], filename)):
                        name, ext = os.path.splitext(base_filename)
                        filename = f"{name}_{counter}{ext}"
                        counter += 1

                    file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                    file_type = 'image' if file.filename.rsplit('.', 1)[1].lower() in {'png', 'jpg', 'jpeg', 'gif'} else 'video'
                    media = WikiMedia(filename=filename, file_type=file_type, wiki=wiki)
                    db.session.add(media)
                except IOError as e:
                    app.logger.error(f'File save error for {file.filename}: {str(e)}')
                    flash(f'Error saving file {file.filename}. Please try again.')
                    continue
                except Exception as e:
                    app.logger.error(f'Unexpected error during file upload for {file.filename}: {str(e)}')
                    flash(f'Unexpected error uploading {file.filename}')
                    continue

            db.session.add(wiki)
            db.session.commit()
            flash('Your wiki has been created!')
            return redirect(url_for('home'))
        except Exception as e:
            db.session.rollback()
            app.logger.error(f'Create wiki error: {str(e)}')
            flash('An error occurred while creating the wiki')
            return redirect(url_for('create_wiki'))

    return render_template('create_wiki.html')

@app.route('/edit_wiki/<int:wiki_id>', methods=['GET', 'POST'])
@login_required
def edit_wiki(wiki_id):
    wiki = Wiki.query.get_or_404(wiki_id)
    if not wiki:
        abort(404)
    if wiki.author != current_user:
        flash('You do not have permission to edit this wiki')
        return redirect(url_for('home'))
    if request.method == 'POST':
        try:
            wiki.title = request.form['title']
            wiki.content = request.form['content']

            # Handle media file deletions
            media_to_delete = request.form.getlist('delete_media')
            for media_id in media_to_delete:
                media = WikiMedia.query.get(int(media_id))
                if media and media.wiki_id == wiki.id:
                    try:
                        os.remove(os.path.join(app.config['UPLOAD_FOLDER'], media.filename))
                    except OSError:
                        pass  # File might not exist
                    db.session.delete(media)

            # Handle media file uploads
            media_files = request.files.getlist('media')
            for file in media_files:
                if file and allowed_file(file.filename):
                    try:
                        filename = secure_filename(file.filename)
                        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                        file_type = 'image' if file.filename.rsplit('.', 1)[1].lower() in {'png', 'jpg', 'jpeg', 'gif'} else 'video'
                        media = WikiMedia(filename=filename, file_type=file_type, wiki=wiki)
                        db.session.add(media)
                    except Exception as e:
                        flash(f'Error uploading file {file.filename}')
                        continue

            db.session.commit()
            flash('Your wiki has been updated!')
            return redirect(url_for('home'))
        except Exception as e:
            db.session.rollback()
            flash('An error occurred while updating the wiki')
            return redirect(url_for('edit_wiki', wiki_id=wiki_id))
    return render_template('create_wiki.html', wiki=wiki)

@app.route('/search')
def search():
    try:
        query = request.args.get('query', '')
        use_location = request.args.get('use_location', type=bool)
        category = request.args.get('category', '')

        app.logger.info(f'Search request - Query: {query}, Category: {category}, Use Location: {use_location}')

        # Start with base query
        wikis = Wiki.query

        # Apply category filter if specified
        if category and category.strip():
            app.logger.info(f'Applying category filter: {category}')
            try:
                # Use exact match for category since it's a controlled field
                wikis = wikis.filter(Wiki.category == category.strip().lower())
                app.logger.info('Category filter applied successfully')
            except SQLAlchemyError as e:
                app.logger.error(f'Error applying category filter: {str(e)}')
                flash('An error occurred while filtering by category')
                return redirect(url_for('home'))

        # Handle location-based filtering
        if use_location and request.args.get('use_location') == 'true':
            lat = request.args.get('latitude', type=float)
            lon = request.args.get('longitude', type=float)
            
            if lat is not None and lon is not None:
                try:
                    if not (-90 <= lat <= 90) or not (-180 <= lon <= 180):
                        flash('Invalid coordinates detected')
                        return redirect(url_for('home'))

                    nearest_point = WaterLevelData.find_nearest_point(lat, lon)
                    if not nearest_point:
                        flash('No water level data found for your location')
                        return redirect(url_for('home'))

                    scarcity_level = WaterLevelData.get_scarcity_level(nearest_point.water_level)
                    wikis = wikis.filter_by(water_scarcity_level=scarcity_level)
                except (ValueError, SQLAlchemyError) as e:
                    app.logger.error(f'Error processing location data: {str(e)}')
                    flash('An error occurred while processing location data')
                    return redirect(url_for('home'))

        # Apply search query filter if specified
        if query and query.strip():
            try:
                wikis = wikis.filter(
                    db.or_(
                        Wiki.title.ilike(f'%{query.strip()}%'),
                        Wiki.content.ilike(f'%{query.strip()}%')
                    )
                )
            except SQLAlchemyError as e:
                app.logger.error(f'Error applying search query filter: {str(e)}')
                flash('An error occurred while processing your search query')
                return redirect(url_for('home'))

        try:
            # Execute query and get results
            results = wikis.order_by(Wiki.date_posted.desc()).all()
            app.logger.info(f'Search results count: {len(results)}')

            # Prepare template parameters
            template_params = {
                'wikis': results,
                'search_query': query,
                'category': category
            }

            # Add water level info if location-based search was used
            if use_location and 'nearest_point' in locals():
                template_params['water_level'] = nearest_point.water_level
                
            return render_template('home.html', **template_params)

        except SQLAlchemyError as e:
            app.logger.error(f'Error executing search query: {str(e)}')
            flash('An error occurred while processing your search')
            return redirect(url_for('home'))

    except Exception as e:
        app.logger.error(f'Unexpected error in search route: {str(e)}')
        flash('An unexpected error occurred')
        return redirect(url_for('home'))
        
    except Exception as e:
        app.logger.error(f'Search error: {str(e)}')
        flash('An error occurred while processing your search')
        return redirect(url_for('home'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        if not request.form.get('username') or not request.form.get('email') or not request.form.get('password'):
            flash('All fields are required!')
            return redirect(url_for('register'))
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        
        if User.query.filter_by(username=username).first():
            flash('Username already exists')
            return redirect(url_for('register'))
            
        if User.query.filter_by(email=email).first():
            flash('Email already registered')
            return redirect(url_for('register'))
            
        user = User(username=username, email=email)
        user.set_password(password)
        db.session.add(user)
        try:
            db.session.commit()
            flash('Registration successful!')
            return redirect(url_for('login'))
        except SQLAlchemyError as e:
            db.session.rollback()
            flash('An error occurred during registration')
            return redirect(url_for('register'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if not request.form.get('username') or not request.form.get('password'):
            flash('Username and password are required!')
            return redirect(url_for('login'))
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        
        if user and user.check_password(password):
            login_user(user)
            return redirect(url_for('home'))
        flash('Invalid username or password')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('home'))

@app.route('/import-data')
@login_required
def import_data():
    try:
        excel_file_path = os.getenv('EXCEL_FILE_PATH')
        if not excel_file_path:
            return jsonify({'error': 'Excel file path not configured'}), 400

        if not os.path.exists(excel_file_path):
            return jsonify({'error': 'Excel file not found'}), 404

        # Clear existing data
        if not clear_water_level_data():
            return jsonify({'error': 'Failed to clear existing data'}), 500

        # Import new data
        result = import_excel_data(excel_file_path)
        
        if result['success']:
            app.logger.info(f'Successfully imported {result["imported_count"]} records')
            return jsonify({
                'success': True,
                'message': f'Successfully imported {result["imported_count"]} records',
                'errors': result['error_rows']
            })
        else:
            app.logger.error(f'Import failed: {result["error"]}')
            return jsonify({
                'success': False,
                'error': result['error'],
                'errors': result['error_rows']
            }), 400
            
    except Exception as e:
        app.logger.error(f'Data import error: {str(e)}')
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/upload_media', methods=['POST'])
@login_required
def upload_media():
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file part'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No selected file'}), 400

        if file and allowed_file(file.filename):
            base_filename = secure_filename(file.filename)
            filename = base_filename
            counter = 1
            # Generate unique filename to prevent overwriting
            while os.path.exists(os.path.join(app.config['UPLOAD_FOLDER'], filename)):
                name, ext = os.path.splitext(base_filename)
                filename = f"{name}_{counter}{ext}"
                counter += 1

            try:
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                return jsonify({
                    'location': url_for('static', filename=f'uploads/{filename}')
                })
            except Exception as e:
                app.logger.error(f'File upload error: {str(e)}')
                return jsonify({'error': 'Failed to save file'}), 500
        
        return jsonify({'error': 'File type not allowed'}), 400
    except Exception as e:
        app.logger.error(f'Upload media error: {str(e)}')
        return jsonify({'error': 'Internal server error'}), 500

# Enhanced security configurations
app.config['SESSION_COOKIE_SECURE'] = True
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=7)

# Configure CSRF protection
csrf.init_app(app)

# Configure file upload settings with additional security
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
app.config['UPLOAD_EXTENSIONS'] = ['.jpg', '.png', '.gif', '.mp4', '.webm']
app.config['UPLOAD_PATH'] = 'uploads'

# Enhanced error handling for database operations
@app.errorhandler(SQLAlchemyError)
def handle_db_error(error):
    db.session.rollback()
    app.logger.error(f'Database error: {str(error)}')
    return 'Database error occurred', 500

# Add request logging
@app.before_request
def log_request_info():
    if not request.path.startswith('/static'):
        app.logger.info(f'Request: {request.method} {request.path}')

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)