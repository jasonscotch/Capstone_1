from unittest import TestCase
# from sqlalchemy import exc

from models import db, User, Songs
from app import app, CURR_USER_KEY

app.config['SQLALCHEMY_DATABASE_URI'] = "postgresql:///datalens-test"
app.config['SQLALCHEMY_ECHO'] = False

app.config['TESTING'] = True

db.drop_all()
db.create_all()

SONG_DATA = {
    "id": "37",	
    "acousticness":	"0.398",
    "album": "Havana (Remix)",
    "analysis_ur": "https://api.spotify.com/v1/audio-analysis/3whrwq4DtvucphBPUogRuJ",	
    "artist": "Camila Cabello",	
    "popularity": "78",	
    "danceability":	"0.751",
    "duration_ms": "199095",	
    "energy": "0.579",	
    "spotify_id": "3whrwq4DtvucphBPUogRuJ",	
    "instrumentalness": "0.0000228",	
    "key": "2",	
    "liveness":	"0.133",
    "loudness":	"-4.036",
    "mode":	"1",
    "name":	"Havana - Remix",
    "release_date": "2017-11-12",
    "speechiness": "0.0321",	
    "tempo": "105.031",
    "time_signature": "4",
    "track_href": "https://api.spotify.com/v1/tracks/3whrwq4DtvucphBPUogRuJ",
    "spotify_type":	"audio_features",
    "uri": "spotify:track:3whrwq4DtvucphBPUogRuJ",
    "valence": "0.349",
    "genres": "dance pop,pop",	
    "played_at": "",	
    "user_id": "1"
}


class DataLensTestCase(TestCase):
    
    def setUp(self):
        """Create test client, add sample data."""
        db.drop_all()
        db.create_all()

        user1 = User.signup("Jason", "Scott", "1211113167", "mason.scotch@gmail.com","password")
        
        db.session.add(user1)
        
        user1 = User.query.get(user1.user_id)
        
        self.user1 = user1
        self.uid1 = user1.user_id
        
        self.client = app.test_client()
        
        song = Songs(**SONG_DATA)
        db.session.add(song)
        db.session.commit()
        
        self.song = song

    def tearDown(self):
        res = super().tearDown()
        db.session.rollback()
        return res
    
    def test_logged_in_pages(self):
        """Can you see the allowed pages if logged in?"""

        with self.client as c:
            with c.session_transaction() as sess:
                sess[CURR_USER_KEY] = self.uid1

            # Now, that session setting is saved, so we can have
            # the rest of ours test

            resp1 = c.get('/home')
            resp2 = c.get('/user/profile')
            resp3 = c.get('/user/profile/edit')
            
            self.assertEqual(resp1.status_code, 200)
            self.assertEqual(resp2.status_code, 200)
            self.assertEqual(resp3.status_code, 200)

    def test_logged_out_pages(self):
        """Can you not see the blocked pages if logged out"""
        resp1 = self.client.get('/home')
        resp2 = self.client.get('/user/profile')
        resp3 = self.client.get('/user/profile/edit')
            
        self.assertEqual(resp1.status_code, 401)
        self.assertEqual(resp2.status_code, 401)
        self.assertEqual(resp3.status_code, 401)
        
    # Tests that the dashboard is rendered correctly when the user is logged in and has saved songs
    def test_dashboard_with_songs(self):
        with self.client as c:
            with c.session_transaction() as sess:
                sess[CURR_USER_KEY] = self.uid1
                
            response = c.get('/dashboard')
            
            assert response.status_code == 200
            assert b'Energy vs Loudness' in response.data
            assert b'Popularity vs Loudness' in response.data
            assert b'Number of Songs per Year' in response.data
            assert b'Top 10 Artists' in response.data
            assert b'Genres' in response.data
            assert b'Heatmap' in response.data
            assert b'Popularity Distribution' in response.data
            assert b'Danceability vs Energy' in response.data
            assert b'Popularity Over Time' in response.data
            assert b'Loudness by Genre' in response.data