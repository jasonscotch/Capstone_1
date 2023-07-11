from flask_bcrypt import Bcrypt
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin

bcrypt = Bcrypt()
db = SQLAlchemy()


class User(db.Model, UserMixin):
    """Users in the system"""

    __tablename__ = 'users'

    user_id = db.Column(
        db.Integer,
        primary_key=True,
    )

    email = db.Column(
        db.String(100),
        nullable=False,
        unique=True,
    )

    username = db.Column(
        db.String(100),
        nullable=False,
        unique=True,
    )

    first_name = db.Column(
        db.String(100),
        nullable=False,
    )

    last_name = db.Column(
        db.String(100),
        nullable=False,
    )

    password = db.Column(
        db.Text,
        nullable=False,
    )
    
    songs = db.relationship('Songs', backref='user', cascade='all, delete-orphan')
    dashboards = db.relationship('UserFavoriteDashboards', backref='user', cascade='all, delete-orphan')

    def __repr__(self):
        return f"<User #{self.user_id}: {self.username}, {self.email}>"
    
    def is_active(self):
        return True

    def get_id(self):
        return str(self.user_id)

    def is_authenticated(self):
        return True

    def is_anonymous(self):
        return False

    @classmethod
    def signup(cls, first_name, last_name, username, email, password):
        """Sign up user. Hashes password and adds user to system.
        """

        hashed_pwd = bcrypt.generate_password_hash(password).decode('UTF-8')

        user = User(
            first_name=first_name,
            last_name=last_name,
            username=username,
            email=email,
            password=hashed_pwd,
        )

        db.session.add(user)
        return user
    
    @classmethod
    def authenticate(cls, username, password):
        """Find user with `username` and `password`. If can't find matching user (or if password is wrong), returns False."""

        user = cls.query.filter_by(username=username).first()

        if user:
            is_auth = bcrypt.check_password_hash(user.password, password)
            if is_auth:
                return user

        return False
    
    
class UserFavoriteDashboards(db.Model):
    """Maps user favorites to """
    
    __tablename__ = 'userfavoritedashboards'
    
    id = db.Column(
        db.Integer,
        primary_key=True,
        autoincrement=True
    )
    
    dash_name = db.Column(
        db.String,
        unique=True,
        nullable=False
    )
    
    kpi_1 = db.Column(
        db.String
    )
    
    kpi_2 = db.Column(
        db.String
    )
    
    kpi_3 = db.Column(
        db.String
    )
    
    kpi_4 = db.Column(
        db.String
    )
    
    viz_1 = db.Column(
        db.String
    )
    
    viz_2 = db.Column(
        db.String
    )
    
    viz_3 = db.Column(
        db.String
    )
    
    viz_4 = db.Column(
        db.String
    )
    
    user_id = db.Column(
        db.Integer,
        db.ForeignKey('users.user_id', ondelete='CASCADE'),
        nullable=False
    )
    

class Songs(db.Model):
    """Songs table, saves all of a users favorite songs for later access"""
    
    __tablename__ = 'songs'
    
    id = db.Column(
        db.Integer, 
        primary_key=True
    )
    acousticness = db.Column(
        db.Float
    )
    album = db.Column(
        db.String
    )
    analysis_url = db.Column(
        db.String
    )
    artist = db.Column(
        db.String,
        nullable=False
    )
    popularity = db.Column(
        db.Integer
    )
    danceability = db.Column(
        db.Float
    )
    duration_ms = db.Column(
        db.Float
    )
    energy = db.Column(
        db.Float
    )
    spotify_id = db.Column(
        db.String
    )
    instrumentalness = db.Column(
        db.Float
    )
    key = db.Column(
        db.Integer
    )
    liveness = db.Column(
        db.Float
    )
    loudness = db.Column(
        db.Float
    )
    mode = db.Column(
        db.Integer
    )
    name = db.Column(
        db.String,
        nullable=False
    )
    release_date = db.Column(
        db.String
    )
    speechiness = db.Column(
        db.Float
    )
    tempo = db.Column(
        db.Float
    )
    time_signature = db.Column(
        db.Integer
    )
    track_href = db.Column(
        db.String
    )
    spotify_type = db.Column(
        db.String
    )
    uri = db.Column(
        db.String
    )
    valence = db.Column(
        db.Float
    )
    genres = db.Column(
        db.String
    )
    played_at = db.Column(
        db.String,
    )
    user_id = db.Column(
        db.Integer,
        db.ForeignKey('users.user_id', ondelete='CASCADE'),
        nullable=False
    )
   
    
def connect_db(app):
    """Connect this database to provided Flask app."""

    db.app = app
    db.init_app(app)
    return db