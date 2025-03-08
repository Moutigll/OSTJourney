import json
import os
import re
from datetime import datetime, timedelta
import requests
import subprocess

from dotenv import load_dotenv
from flask import Flask, render_template, url_for, request, redirect, flash, session, send_from_directory, make_response, jsonify, abort
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_mail import Mail, Message
from itsdangerous import URLSafeTimedSerializer
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import desc, func
from werkzeug.security import generate_password_hash, check_password_hash

from app_utils import *

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY')

base_dir = os.path.dirname(os.path.abspath(__file__))
songs_dir = os.path.join(base_dir, "songs")

serializer = URLSafeTimedSerializer(app.secret_key)

# Footer information
BUILD = "dev 1.0.12"
REPO_OWNER = "Moutigll"
COPYRIGHT = "© 2025 - Moutig"
REPO_NAME = "OSTJourney"
REPO_URL = f"https://github.com/{REPO_OWNER}/{REPO_NAME}"
BRANCH = "main"

def get_commit_from_github():
	try:
		local_commit_hash = subprocess.check_output(["git", "rev-parse", "HEAD"]).strip().decode('utf-8')
		url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/commits/{local_commit_hash}"
		response = requests.get(url)
		response.raise_for_status()
		
		return response.json()
	except Exception as e:
		print(f"Erreur API GitHub: {e}")
		return None

commit_data = get_commit_from_github()

email_enabled = os.getenv('EMAIL_ENABLED', 'false').lower() == 'true'
if email_enabled:
	app.config['MAIL_SERVER'] = os.getenv('MAIL_SERVER')
	app.config['MAIL_PORT'] = os.getenv('MAIL_PORT')
	app.config['MAIL_DEFAULT_SENDER'] = os.getenv('MAIL_DEFAULT_SENDER')


mail = Mail(app)

limiter = Limiter(
	key_func=get_real_ip,
	app=app,
	default_limits=[]
)

app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('SQLALCHEMY_DATABASE_URI')
binds = os.getenv('SQLALCHEMY_BINDS', '{}')
app.config['SQLALCHEMY_BINDS'] = json.loads(binds) if binds else {}
db = SQLAlchemy(app)

class Songs(db.Model):
	id = db.Column(db.Integer, primary_key=True)
	title = db.Column(db.String(200), nullable=False)
	artist = db.Column(db.String(200), nullable=False)
	duration = db.Column(db.Float)
	tags = db.Column(db.Text)
	path = db.Column(db.String(500))
	album = db.Column(db.String(200))
	cover = db.Column(db.String(200))

	def __repr__(self):
		return f'<Song {self.id}: {self.title} by {self.artist}>'

class User(db.Model):
	__bind_key__ = 'users'
	id = db.Column(db.Integer, primary_key=True)
	username = db.Column(db.String(150), unique=True, nullable=False)
	email = db.Column(db.String(150), unique=True, nullable=False)
	password = db.Column(db.String(200), nullable=False)
	created_at = db.Column(db.DateTime, default=datetime.utcnow)

	total_duration = db.Column(db.Float, default=0)
	total_songs = db.Column(db.Integer, default=0)

	listening_history = db.relationship('ListeningHistory', back_populates='user', lazy='dynamic')
	listening_sessions = db.relationship('ListeningSession', back_populates='user', lazy='dynamic')

	def __repr__(self):
		return f'<User {self.username}>'

class ListeningHistory(db.Model):
	__bind_key__ = 'users'
	id = db.Column(db.Integer, primary_key=True)
	user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
	song_id = db.Column(db.Integer, nullable=False)
	listen_time = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
	duration_seconds = db.Column(db.Integer, nullable=True)

	user = db.relationship('User', back_populates='listening_history')

	def __repr__(self):
		return f'<ListeningHistory {self.id}: User {self.user_id} listened to Song {self.song_id} at {self.listen_time}>'

class ListeningSession(db.Model):
	__bind_key__ = 'users'
	id = db.Column(db.Integer, primary_key=True)
	user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
	song_id = db.Column(db.Integer, nullable=False)
	start_time = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
	expiration_time = db.Column(db.DateTime, nullable=False)

	user = db.relationship('User', back_populates='listening_sessions')

	def __repr__(self):
		return f'<ListeningSession {self.id}: User {self.user_id} Song {self.song_id}>'
	
class UserActivity(db.Model):
	__bind_key__ = 'users'
	id = db.Column(db.Integer, primary_key=True)
	user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
	date = db.Column(db.Date, nullable=False)
	total_duration = db.Column(db.Float, default=0)
	total_songs = db.Column(db.Integer, default=0)

	user = db.relationship('User', backref=db.backref('user_activity', lazy=True))

	def __repr__(self):
		return f'<UserActivity {self.user_id} on {self.date}>'

class ListeningStatistics(db.Model):
	__bind_key__ = 'users'
	id = db.Column(db.Integer, primary_key=True)
	user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
	hour = db.Column(db.Integer, nullable=False)
	listen_count = db.Column(db.Integer, default=0, nullable=False)

	user = db.relationship('User', backref=db.backref('listening_statistics', lazy=True))

	def __repr__(self):
		return f'<ListeningStatistics User {self.user_id} Hour {self.hour}: {self.listen_count} listens>'

class BlacklistedIP(db.Model):
	__bind_key__ = 'users'
	id = db.Column(db.Integer, primary_key=True)
	ip_address = db.Column(db.String(45), unique=True, nullable=False)
	banned_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

	def __repr__(self):
		return f'<BlacklistedIP {self.ip_address}>'

@app.before_request
def check_blacklist():
	ip_address = get_real_ip()
	blacklisted_ip = BlacklistedIP.query.filter_by(ip_address=ip_address).first()

	if blacklisted_ip:
		return render_template('banned.html', ip_address=ip_address, banned_at=blacklisted_ip.banned_at, ban_id=blacklisted_ip.id)

@app.route('/')
def index():
	song_id = request.args.get("song")
	listened_count = None

	if not song_id:
		return render_template('index.html')
	if song_id:
		song = Songs.query.get(song_id)
		if not song:
			return render_template('index.html', error="Chanson non trouvée.")
		user_id = session.get('user_id')
		if user_id:
			listened_count = db.session.query(func.count(ListeningHistory.id)).filter_by(
				user_id=user_id,
				song_id=song_id
			).scalar()

	if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
		return render_template('song.html', song=song, listened_count=listened_count)
	else:
		return render_template('base.html', content=render_template('song.html', song=song, listened_count=listened_count))

@app.route('/robots.txt')
def robots():
	return send_from_directory('static', 'robots.txt')

@app.route('/sitemap.xml')
def sitemap():
	return send_from_directory('static', 'sitemap.xml')

@app.route('/nav')
def nav():
	if request.headers.get('X-Requested-With') != 'XMLHttpRequest':
		abort(404)
	return render_template('nav.html')

@app.route('/footer')
def footer():
	if request.headers.get('X-Requested-With') != 'XMLHttpRequest':
		abort(404)
	return render_template('footer.html', commit_data=commit_data, build=BUILD, repo_owner=REPO_OWNER, repo_name=REPO_NAME, repo_url=REPO_URL, branch=BRANCH, copy_right=COPYRIGHT)

@app.route('/register', methods=['GET', 'POST'])
def register():
	if 'user' in session:
		return redirect(url_for('profile'))
	
	if request.method == 'POST':
		username = request.form.get('username').strip()
		email = request.form.get('email').strip()
		password = request.form.get('password')
		confirm_password = request.form.get('confirm_password')

		username_pattern = r'^[a-zA-Z0-9_]{3,20}$'
		if not re.match(username_pattern, username):
			return render_template('register.html', error="Invalid username.", username=username, email=email, currentUrl="/register")

		if password != confirm_password:
			return render_template('register.html', error="Passwords do not match.", username=username, email=email, currentUrl="/register")

		password_pattern = r'^(?=.*\d)(?=.*[a-z])(?=.*[A-Z])(?=.*[!@#$%^&*()_+\-=\[\]{};\'\\|,.<>\/?]).{8,40}$'
		if not re.match(password_pattern, password):
			return render_template('register.html', error="Invalid password.", username=username, email=email, currentUrl="/register")

		email_pattern = r'([-!#-\'*+/-9=?A-Z^-~]+(\.[-!#-\'*+/-9=?A-Z^-~]+)*|"([]!#-[^-~ \t]|(\\[\t -~]))+")@[0-9A-Za-z]([0-9A-Za-z-]{0,61}[0-9A-Za-z])?(\.[0-9A-Za-z]([0-9A-Za-z-]{0,61}[0-9A-Za-z])?)+'
		if not re.match(email_pattern, email):
			return render_template('register.html', error="Invalid email.", username=username, email=email, currentUrl="/register")

		existing_user = User.query.filter(func.lower(User.username) == username.lower()).first()
		if existing_user:
			return render_template('register.html', error="Username already exists.", email=email, currentUrl="/register")

		existing_email = User.query.filter_by(email=email).first()
		if existing_email:
			return render_template('register.html', error="Email already exists.", username=username, currentUrl="/register")

		hashed_password = generate_password_hash(password, method='pbkdf2:sha256', salt_length=8)
		new_user = User(username=username, email=email, password=hashed_password)
		db.session.add(new_user)
		db.session.commit()

		return render_template('login.html', success="Account created successfully. Please login.", email=email, currentUrl="/login")

	if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
		return render_template('register.html', currentUrl="/register")
	else:
		return render_template('base.html', content=render_template('register.html'), currentUrl="/register", title="Register")

@app.route('/login', methods=['GET', 'POST'])
def login():
	if 'user' in session:
		return redirect(url_for('profile'))
	if request.method == 'POST':
		email = request.form.get('email').strip()
		password = request.form.get('password')

		if not email or not password:
			return render_template('login.html', error="Please fill in all fields.", email=email, currentUrl="/login", email_enabled=email_enabled)

		user = User.query.filter_by(email=email).first()
		if user and check_password_hash(user.password, password):
			session['user_id'] = user.id
			session['user'] = user.username
			session['email'] = user.email
			session['created_at'] = user.created_at

			token = serializer.dumps({'user_id': user.id})
			response = make_response(redirect(url_for('profile')))
			response.set_cookie('session_token', token, max_age=30*24*3600, httponly=True)

			return response
		elif user:
			return render_template('login.html', error="Invalid password.", email=email, currentUrl="/login", email_enabled=email_enabled)
		else:
			return render_template('login.html', error="Invalid email.", email=email, currentUrl="/login", email_enabled=email_enabled)
	
	if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
		return render_template('login.html', currentUrl="/login", email_enabled=email_enabled)
	else:
		return render_template('base.html', content=render_template('login.html', email_enabled=email_enabled), currentUrl="/login", title="Login")

@app.route('/logout')
def logout():
	session.clear()
	response = make_response(redirect(url_for('login')))
	response.delete_cookie('session_token')
	return response

@app.route("/reset_password_request", methods=["POST"])
@limiter.limit("5 per hour")
def reset_password_request():
	if not email_enabled:
		return jsonify({"success": False, "error": "Email is not enabled, please contact support@ostjourney.xyz."}), 400
	
	data = request.get_json()
	email = data.get("email")

	if not email:
		return jsonify({"success": False, "error": "Email is required."}), 400

	user = User.query.filter_by(email=email).first()
	if not user:
		return jsonify({"success": False, "error": "This email is not registered."}), 404

	token = generate_reset_token(email)
	reset_url = url_for("reset_password", token=token, _external=True)

	if email_enabled:
		msg = Message("Password Reset Request", recipients=[email])
		msg.body = (
			"Hello,\n\n"
			"We have received a request to reset the password for your OSTJourney account.\n\n"
			"If you made this request, please click the link below to reset your password:\n"
			f"{reset_url}\n\n"
			"This link is valid for a limited time. If you did not request a password reset, please ignore this email.\n\n"
			"For any questions or assistance, feel free to contact our support team at support@ostjourney.xyz.\n\n"
			"Thank you,\n"
			"The OSTJourney Team"
		)
		mail.send(msg)
	
	return jsonify({"success": True}), 200

@app.route("/test/<token>")
def test(token):
	return render_template('base.html', content=render_template('reset_password.html', token=token, currentUrl="/reset_password"))


@app.route("/reset_password/<token>", methods=["GET", "POST"])
@limiter.limit("3 per hour", methods=["POST"])
def reset_password(token):
	email = verify_reset_token(token)
	if not email or 'user' in session:
		return render_template('base.html', content=render_template('login.html', currentUrl="/login", error="Already logged or invalid/expired token."))

	if request.method == "POST":
		form_token = request.form.get("token")
		if form_token != token:
			return render_template('base.html', content=render_template('reset_password.html', token=token, error="Invalid token."))

		password = request.form.get("password").strip()
		confirm_password = request.form.get("confirm_password").strip()

		if password != confirm_password:
			return render_template('base.html', content=render_template('reset_password.html', token=token, error="Passwords do not match."))

		password_pattern = r'^(?=.*\d)(?=.*[a-z])(?=.*[A-Z])(?=.*[!@#$%^&*()_+\-=\[\]{};\'\\|,.<>\/?]).{8,40}$'
		if not re.match(password_pattern, password):
			return render_template('base.html', content=render_template('reset_password.html', token=token, error="Invalid password format. Password must contain at least one number, one uppercase letter, one lowercase letter, and one special character."))

		user = User.query.filter_by(email=email).first()
		if user:
			hashed_password = generate_password_hash(password, method='pbkdf2:sha256', salt_length=8)
			user.password = hashed_password
			db.session.commit()
			return render_template('login.html', success="Password reset successfully. Please login.", email=email, currentUrl="/login")
		else:
			return render_template('base.html', content=render_template('login.html', currentUrl="/login", error="Invalid email."))

	return render_template('base.html', content=render_template('reset_password.html', token=token, currentUrl="/reset_password"))

@app.route('/settings')
def settings():
	if 'user' not in session:
		if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
			return render_template('login.html', currentUrl="/login")
		return render_template('base.html', content=render_template('login.html', currentUrl="/login"))

	token = request.cookies.get('session_token')
	if not token:
		return redirect(url_for('index'))

	try:
		user_data = serializer.loads(token)
		user_id = user_data.get('user_id')
	except:
		return redirect(url_for('logout'))
	
	if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
		return render_template('settings.html', currentUrl="/settings")
	return render_template('base.html', content=render_template('settings.html'), currentUrl="/settings", title="Settings")
	


@app.route('/profile')
def profile():
	if 'user' not in session:
		if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
			return render_template('login.html', currentUrl="/login")
		return render_template('base.html', content=render_template('login.html', currentUrl="/login"))

	token = request.cookies.get('session_token')
	if not token:
		return redirect(url_for('index'))

	try:
		user_data = serializer.loads(token)
		user_id = user_data.get('user_id')
	except:
		return redirect(url_for('logout'))

	user = User.query.get(user_id)
	if not user:
		return redirect(url_for('index'))

	total_listened = user.total_songs
	total_duration_seconds = user.total_duration
	listening_history = ListeningHistory.query.filter_by(user_id=user_id).order_by(desc(ListeningHistory.listen_time)).limit(25).all()

	songs_list = []
	for history in listening_history:
		song = Songs.query.get(history.song_id)
		if song:
			songs_list.append({
				'song_id': song.id,
				'title': song.title,
				'artist': song.artist,
				'duration': format_duration(song.duration),
				'cover': song.cover
			})

	load_button = len(songs_list) == 25
	total_duration = format_duration(total_duration_seconds)
	total_hours = round(total_duration_seconds / 3600, 2)

	if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
		return render_template(
			'profile.html',
			username=user.username,
			email=user.email,
			created_at=user.created_at,
			user_id=user.id,
			total_duration=total_duration,
			total_listened=total_listened,
			songs_list=songs_list,
			load_button=load_button,
			total_hours=total_hours,
			currentUrl="/profile"
		)

	return render_template(
		'base.html',
		content=render_template(
			'profile.html',
			username=user.username,
			email=user.email,
			created_at=user.created_at,
			user_id=user.id,
			total_duration=total_duration,
			total_listened=total_listened,
			songs_list=songs_list,
			load_button=load_button,
			total_hours=total_hours,
			currentUrl="/profile"
		)
	)

@app.route('/api/user_activity', methods=['GET'])
def get_user_activity():
	if 'user' in session:
		token = request.cookies.get('session_token')
		if not token:
			return {'status': 'error', 'message': 'User not logged in'}

		try:
			user_data = serializer.loads(token)
			user_id = user_data['user_id']
		except:
			return {'status': 'error', 'message': 'Invalid session token'}

		activities = UserActivity.query.filter_by(user_id=user_id).all()

		activity_by_date = {}
		for activity in activities:
			date = activity.date
			year = date.year
			date_str = date.strftime('%Y-%m-%d')
			if year not in activity_by_date:
				activity_by_date[year] = {}
			activity_by_date[year][date_str] = {
				'total_duration': activity.total_duration,
				'total_songs': activity.total_songs
			}

		year_data = {}
		for year, year_activities in activity_by_date.items():
			year_data[year] = {
				'data': {},
				'min_duration': float('inf'),
				'max_duration': float('-inf'),
				'min_songs': float('inf'),
				'max_songs': float('-inf')
			}
			for month in range(1, 13):
				for day in range(1, 32):
					try:
						current_date = datetime(year, month, day).date()
						current_date_str = current_date.strftime('%Y-%m-%d')
					except ValueError:
						continue

					if current_date_str in year_activities:
						day_data = year_activities[current_date_str]
						formatted_duration = format_duration(day_data['total_duration'])
						day_data['formatted_duration'] = formatted_duration

						if day_data['total_duration'] > 0:
							year_data[year]['min_duration'] = min(year_data[year]['min_duration'], day_data['total_duration'])
							year_data[year]['max_duration'] = max(year_data[year]['max_duration'], day_data['total_duration'])
						if day_data['total_songs'] > 0:
							year_data[year]['min_songs'] = min(year_data[year]['min_songs'], day_data['total_songs'])
							year_data[year]['max_songs'] = max(year_data[year]['max_songs'], day_data['total_songs'])
					else:
						day_data = {'total_duration': 0, 'total_songs': 0, 'formatted_duration': '00:00:00'}

					year_data[year]['data'][current_date_str] = day_data

			if year_data[year]['min_duration'] == float('inf'):
				year_data[year]['min_duration'] = 0
			if year_data[year]['min_songs'] == float('inf'):
				year_data[year]['min_songs'] = 0

			if year_data[year]['max_duration'] == float('-inf'):
				year_data[year]['max_duration'] = 0
			if year_data[year]['max_songs'] == float('-inf'):
				year_data[year]['max_songs'] = 0

		return {'status': 'success', 'year_data': year_data}

	return {'status': 'error', 'message': 'User not logged in'}

@app.route('/profile/history')
def load_more_history():
	if 'user' in session:
		offset = int(request.args.get('offset', 0))
		token = request.cookies.get('session_token')
		if not token:
			return jsonify({'error': 'Unauthorized'}), 401

		try:
			user_data = serializer.loads(token)
			user_id = user_data['user_id']
		except:
			return jsonify({'error': 'Unauthorized'}), 401

		listening_history = ListeningHistory.query.filter_by(user_id=user_id)\
			.order_by(desc(ListeningHistory.listen_time))\
			.offset(offset)\
			.limit(25)\
			.all()

		songs_list = []
		for history in listening_history:
			song = Songs.query.get(history.song_id)
			if song:
				songs_list.append({
					'song_id': song.id,
					'title': song.title,
					'artist': song.artist,
					'duration': format_duration(song.duration),
					'cover': song.cover
				})

		if not songs_list:
			return jsonify({'songs': []})

		return jsonify({'songs': songs_list})

	return jsonify({'error': 'Unauthorized'}), 401

@app.route('/profile/history/24h')
def hourly_history():
	if 'user' in session:
		user_id = session.get('user_id')

		data = db.session.query(
			ListeningStatistics.hour,
			ListeningStatistics.listen_count
		).filter_by(user_id=user_id).all()

		hourly_counts = {i: 0 for i in range(24)}

		for hour, count in data:
			hourly_counts[hour] = count

		return jsonify({'hourly_counts': hourly_counts})

	return jsonify({'error': 'Unauthorized'}), 401

@app.route('/latest', methods=['GET'])
def get_latest_session():
	if 'user_id' in session:
		user_id = session['user_id']

		latest_session = ListeningSession.query.filter_by(user_id=user_id).order_by(ListeningSession.start_time.desc()).first()
		
		if latest_session:
			return jsonify({'latest_session_id': latest_session.song_id})
		else:
			return jsonify({'error': 'No listening session found for the user'}), 404
	else:
		return jsonify({'error': 'Unauthorized'}), 401


@app.route('/api/songs/<int:id>', methods=['GET'])
def get_song(id):
	song = Songs.query.get_or_404(id)
	return {
		'id': song.id,
		'title': song.title,
		'artist': song.artist,
		'album': song.album,
		'cover': song.cover,
		'duration': song.duration,
		'path': song.path,
		'tags': song.tags
}

@app.route('/api/songs', methods=['GET'])
def get_songs():
	song_count = Songs.query.count()

	return jsonify({
		'song_count': song_count
})

@app.route('/songs/<path:filename>')
def media(filename):
	return send_from_directory(songs_dir, filename)

@app.route('/api/music/start', methods=['POST'])
def start_music():
	data = request.get_json()
	song_id = data.get('song_id')

	if not song_id:
		return {'status': 'error', 'message': 'Song ID is required'}

	token = request.cookies.get('session_token')
	if not token:
		return {'status': 'error', 'message': 'User not logged in'}

	try:
		user_data = serializer.loads(token)
		user_id = user_data['user_id']
	except Exception:
		return {'status': 'error', 'message': 'Invalid or expired session token'}

	song = db.session.get(Songs, song_id)
	if not song:
		return {'status': 'error', 'message': 'Song not found'}

	existing_session = ListeningSession.query.filter_by(user_id=user_id, song_id=song_id).first()
	if existing_session:
		db.session.delete(existing_session)
		db.session.commit()

	active_sessions = ListeningSession.query.filter_by(user_id=user_id).all()
	
	if len(active_sessions) >= 3:
		active_sessions.sort(key=lambda s: s.start_time)
		for session in active_sessions[:-2]:
			db.session.delete(session)
		db.session.commit()

	max_duration = min(song.duration * 5, 86400)

	new_session = ListeningSession(
		user_id=user_id,
		song_id=song_id,
		start_time=datetime.now(),
		expiration_time=datetime.now() + timedelta(seconds=max_duration)
	)

	db.session.add(new_session)
	db.session.commit()

	return {'status': 'success', 'message': 'Music started and listening session recorded'}

@app.route('/api/music/end', methods=['POST'])
def end_music():
	data = request.get_json()
	song_id = data.get('song_id')

	if not song_id:
		return {'status': 'error', 'message': 'Song ID is required'}

	token = request.cookies.get('session_token')
	if not token:
		return {'status': 'error', 'message': 'User not logged in'}

	try:
		user_data = serializer.loads(token)
		user_id = user_data['user_id']
	except Exception:
		return {'status': 'error', 'message': 'Invalid or expired session token'}

	listening_session = ListeningSession.query.filter_by(user_id=user_id, song_id=song_id).first()
	if not listening_session:
		return {'status': 'error', 'message': 'Listening session not found'}

	song = db.session.query(Songs).get(song_id)
	if not song:
		return {'status': 'error', 'message': 'Song not found'}

	if listening_session.expiration_time and datetime.now() > listening_session.expiration_time:
		db.session.delete(listening_session)
		db.session.commit()
		return {'status': 'error', 'message': 'Listening session has expired'}

	if datetime.now() < listening_session.start_time + timedelta(seconds=song.duration - 3):
		db.session.delete(listening_session)
		db.session.commit()
		return {'status': 'error', 'message': 'Listening session is too short'}

	duration_seconds = song.duration

	listening_history = ListeningHistory(
		user_id=user_id,
		song_id=song_id,
		listen_time=listening_session.start_time,
		duration_seconds=duration_seconds
	)

	db.session.add(listening_history)

	user = db.session.query(User).get(user_id)
	user.total_songs += 1
	user.total_duration += duration_seconds

	current_date = datetime.now().date()
	activity = UserActivity.query.filter_by(user_id=user_id, date=current_date).first()

	if not activity:
		activity = UserActivity(user_id=user_id, date=current_date)
		db.session.add(activity)

	activity.total_duration = (activity.total_duration or 0) + duration_seconds
	activity.total_songs = (activity.total_songs or 0) + 1

	start_hour = listening_session.start_time.hour
	listening_stat = ListeningStatistics.query.filter_by(user_id=user_id, hour=start_hour).first()

	if not listening_stat:
		listening_stat = ListeningStatistics(user_id=user_id, hour=start_hour, listen_count=0)
		db.session.add(listening_stat)

	listening_stat.listen_count += 1

	db.session.delete(listening_session)
	db.session.commit()

	return {'status': 'success', 'message': 'Listening session ended and data updated'}

@app.errorhandler(429)
def ratelimit_error(e):
	ip_address = get_real_ip()
	blacklisted_ip = BlacklistedIP.query.filter_by(ip_address=ip_address).first()

	if not blacklisted_ip:
		blacklisted_ip = BlacklistedIP(ip_address=ip_address, banned_at=datetime.utcnow())
		db.session.add(blacklisted_ip)
		db.session.commit()

	return jsonify({"success": False, "error": "Too many requests. Try again later."}), 429

@app.errorhandler(404)
def page_not_found(error):
	return render_template('404.html'), 404

if __name__ == '__main__':
	with app.app_context():
		db.create_all()

	ssl_cert_path = os.getenv('SSL_CERT_PATH')
	ssl_key_path = os.getenv('SSL_KEY_PATH')
	flask_env = os.getenv('FLASK_ENV')
	flask_port = os.getenv('FLASK_PORT', 5000) 

	if flask_env == 'production' and ssl_cert_path and ssl_key_path:
		app.run(debug=False, host='0.0.0.0', port=int(flask_port), ssl_context=(ssl_cert_path, ssl_key_path))
	else:
		app.run(debug=True, host='127.0.0.1', port=int(flask_port))