import os
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials

from dotenv import load_dotenv
from datetime import datetime
import re
import collections

from flask import Flask, render_template, flash, redirect, session, g, url_for, jsonify
from flask_login import LoginManager, login_user, logout_user, login_required 
from sqlalchemy.exc import IntegrityError

import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
from collections import Counter

from forms import UserAddForm, LoginForm, UserEditForm
from models import db, connect_db, User, Songs, UserFavoriteDashboards

import dash
from dash import dcc
from dash import html

from dash.dependencies import Input, Output, State

load_dotenv()

client_id = os.getenv("CLIENT_ID")
client_secret = os.getenv("CLIENT_SECRET")

CURR_USER_KEY = "curr_user"
SPOTIFY_TOKEN_KEY = 'spotify_token'
TOKEN_INFO_KEY = 'token_info'

app = Flask(__name__)
app.app_context().push()

# Create and configure the login manager
login_manager = LoginManager()
login_manager.init_app(app)

app.config['SQLALCHEMY_DATABASE_URI'] = (
    os.environ.get('DATABASE_URL', 'postgresql:///datalens'))

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ECHO'] = False
app.config.from_pyfile('config.py')

app.config['ERROR_404_HELP'] = False

connect_db(app)
# db.drop_all()
db.create_all()

dash_app = dash.Dash(__name__, server=app, url_base_pathname='/dash/')
dash_app.config.suppress_callback_exceptions = True
dash_app.scripts.config.serve_locally = True
dash_app.css.config.serve_locally = True
# dash_app.run_server(debug=True)


if __name__ == "__main__":
    app.run()
    
    
# User signup/login/logout
@app.before_request
def add_user_to_g():
    """If we're logged in, add curr user to Flask global."""
    
    if CURR_USER_KEY in session:
        g.user = User.query.get(session[CURR_USER_KEY])

    else:
        g.user = None


def do_login(user):
    """Log in user."""
    
    session[CURR_USER_KEY] = user.user_id
    login_user(user)


def do_logout():
    """Logout user."""
    if CURR_USER_KEY in session:
        del session[CURR_USER_KEY]    
   
    logout_user()
    session.clear()

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(user_id)


@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404


@app.route('/signup', methods=["GET", "POST"])
def signup():
    """Handles user signup."""
    # session.clear()
    form = UserAddForm()

    if form.is_submitted() and form.validate():
        try:
            user = User.signup(
                first_name=form.first_name.data,
                last_name=form.last_name.data,
                username=form.username.data,
                email=form.email.data,
                password=form.password.data
            )
            db.session.commit()

        except IntegrityError:
            flash("Username already taken", 'danger')
            return render_template('users/signup.html', form=form)

        do_login(user)

        return redirect("/home")

    else:
        return render_template('users/signup.html', form=form)


@app.route('/login', methods=["GET", "POST"])
def login():
    """Handle user login."""
    # session.clear()
    form = LoginForm()
    
    if form.is_submitted() and form.validate():
        user = User.authenticate(form.username.data,
                                 form.password.data)

        if user:
            do_login(user)
            flash(f"Hello, {user.first_name}!", "success")
            return redirect("/home")

        flash("Invalid credentials.", 'danger')

    return render_template('users/login.html', form=form)


@app.route('/logout')
def logout():
    """Handle logout of user."""
    
    # token_info = session.get(SPOTIFY_TOKEN_KEY)
    # if token_info:
    #     access_token = token_info['access_token']
    #     revoke_url = 'https://accounts.spotify.com/api/token/revoke'
    #     headers = {'Authorization': 'Bearer ' + access_token}
    #     requests.post(revoke_url, headers=headers)
    
    do_logout()
    session.clear()
    
    flash('Goodbye!', 'success')
    return redirect('/login')
 
    
@app.route('/')
def index():

    return redirect(url_for('login', _external=True))


@app.route('/home')
@login_required
def homepage():
    user_id = session[CURR_USER_KEY]
    dashboards = UserFavoriteDashboards.query.filter_by(user_id=user_id).all()
    
    return render_template('home.html', dashboards=dashboards)


@app.route('/gettracks')
@login_required
def gettracks():
 
    user = User.query.get(session[CURR_USER_KEY])
    auth_manager = SpotifyClientCredentials(client_id, client_secret)
    sp = spotipy.Spotify(auth_manager=auth_manager)
    playlists = sp.user_playlists(user.username)

    # Collect unique Spotify IDs of existing songs
    existing_spotify_ids_subquery = db.session.query(Songs.spotify_id).filter(Songs.user_id == user.user_id).subquery()
    existing_spotify_ids = {row[0] for row in db.session.query(existing_spotify_ids_subquery).with_entities(existing_spotify_ids_subquery.c.spotify_id).all()}


    # Collect data for new songs
    songs_to_add = []
    track_ids = []

    for playlist in playlists['items']:
        if playlist['owner']['id'] == user.username:
            playlist_id = playlist['id']
            results = sp.playlist(playlist_id, fields="tracks,next")
            tracks = results['tracks']

            while tracks:
                for item in tracks['items']:
                    track = item['track']
                    spotify_id = track['id']

                    if not spotify_id or spotify_id in existing_spotify_ids:
                        continue

                    track_ids.append(spotify_id)
                    audio_features = sp.audio_features(track_ids)

                    for audio_feature in audio_features:
                        release_date = sp.album(track['album']['id'])['release_date']
                        artist = sp.artist(track['artists'][0]['uri'])
                        popularity = artist['popularity']
                        genres = [re.sub(r'[{}"]', '', genre).strip() for genre in artist['genres'] if genre.strip()]
                        genres_string = ",".join(genres)

                        track_with_features = {
                            **track,
                            **audio_feature,
                            'release_date': release_date,
                            'popularity': popularity,
                            'genres': genres_string
                        }

                        songs_to_add.append(track_with_features)

                    track_ids = []

                if tracks['next']:
                    tracks = sp.next(tracks)
                else:
                    tracks = None

    # Add new songs to the database
    songs = [
        Songs(
            acousticness=track['acousticness'],
            album=track['album']['name'],
            analysis_url=track['analysis_url'],
            artist=track['artists'][0]['name'],
            popularity=track['popularity'],
            danceability=track['danceability'],
            duration_ms=track['duration_ms'],
            energy=track['energy'],
            spotify_id=track['id'],
            instrumentalness=track['instrumentalness'],
            key=track['key'],
            liveness=track['liveness'],
            loudness=track['loudness'],
            mode=track['mode'],
            name=track['name'],
            release_date=track['release_date'],
            speechiness=track['speechiness'],
            tempo=track['tempo'],
            time_signature=track['time_signature'],
            track_href=track['track_href'],
            spotify_type=track['type'],
            uri=track['uri'],
            valence=track['valence'],
            genres=track['genres'],
            user_id=user.user_id
        )
        for track in songs_to_add
    ]

    db.session.bulk_save_objects(songs)
    db.session.commit()

    return jsonify({'message': 'Tracks added successfully'})


@app.route('/dashboard')
@login_required
def dashboard():
    user_id = session[CURR_USER_KEY]
    dashboards = UserFavoriteDashboards.query.filter_by(user_id=user_id).all()
    
    all_songs = Songs.query.filter_by(user_id=user_id).all()

    energy_loudness_plot = create_energy_loudness_plot(all_songs)
    popularity_loudness_plot = create_popularity_loudness_plot(all_songs)
    num_songs_per_year_plot = create_num_songs_per_year(all_songs)
    top_10_artists_plot = create_top_artists_plot(all_songs)
    genres_plot = create_genres_plot(all_songs)
    heatmap_plot = create_heatmap_plot(all_songs)
    histo_popularity_plot = create_histo_popularity(all_songs)
    danceability_energy_plot = create_danceability_energy_plot(all_songs)
    popularity_over_time_plot = create_populartity_over_time_plot(all_songs)
    loudness_by_genre_plot = create_loudness_by_genre_plot(all_songs)
    
    return render_template('dashboard.html', dashboards=dashboards, energy_loudness_plot=energy_loudness_plot.to_html(full_html=True), popularity_loudness_plot=popularity_loudness_plot.to_html(full_html=True), num_songs_per_year_plot=num_songs_per_year_plot.to_html(full_html=True), top_10_artists_plot=top_10_artists_plot.to_html(full_html=True), genres_plot=genres_plot.to_html(full_html=True), heatmap_plot=heatmap_plot.to_html(full_html=True), histo_popularity_plot=histo_popularity_plot.to_html(full_html=True), danceability_energy_plot=danceability_energy_plot.to_html(full_html=True), popularity_over_time_plot=popularity_over_time_plot.to_html(full_html=True), loudness_by_genre_plot=loudness_by_genre_plot.to_html(full_html=True))
 
 
@app.route('/dash')
@login_required
def dash_route():
    create_dash_application()
    user_id = session[CURR_USER_KEY]
    dashboards = UserFavoriteDashboards.query.filter_by(user_id=user_id).all()
    return render_template('dash.html', dashboards=dashboards, content=dash_app.index())


@app.route('/dash/<int:dash_id>')
@login_required
def saved_dash_route(dash_id):
    saved_dash_application(dash_id)
    user_id = session[CURR_USER_KEY]
    dashboards = UserFavoriteDashboards.query.filter_by(user_id=user_id).all()
    return render_template('saveddash.html', dashboards=dashboards, content=dash_app.index())

    
# Viz Creation
def create_energy_loudness_plot(songs):
    song_data = []
    for song in songs:
        song_data.append({
            'name': song.name,
            'energy': song.energy,
            'loudness': song.loudness
        })
    
    # Create the regression plot using Plotly Express
    fig = px.scatter(
        song_data, 
        x=[song['energy'] for song in song_data],
        y=[song['loudness'] for song in song_data],
        trendline='ols',
        color='energy',
        color_continuous_scale='viridis'
    )
    fig.update_traces(
        hovertemplate="<b>Name:</b> %{text}<br>"
                      "<b>Energy:</b> %{x}<br>"
                      "<b>Loudness:</b> %{y}",
        text=[song['name'] for song in song_data]
    )
    fig.update_layout(
        title="Energy vs Loudness",
        xaxis_title="Energy",
        yaxis_title="Loudness",
        template='plotly_dark'
    )
    
    return fig


def create_popularity_loudness_plot(songs):
    song_data = []
    for song in songs:
        song_data.append({
            'name': song.name,
            'popularity': song.popularity,
            'loudness': song.loudness
        })
    
    # Create the regression plot using Plotly Express
    fig = px.scatter(
        song_data,
        x=[song['popularity'] for song in song_data],
        y=[song['loudness'] for song in song_data],
        trendline='ols',
        color='popularity',  
        color_continuous_scale='viridis'
    )
    fig.update_traces(
        hovertemplate="<b>Name:</b> %{text}<br>"
                      "<b>Energy:</b> %{x}<br>"
                      "<b>Loudness:</b> %{y}",
        text=[song['name'] for song in song_data]
    )
    fig.update_layout(
        title="Popularity vs Loudness",
        xaxis_title="Popularity",
        yaxis_title="Loudness",
        template='plotly_dark'
    )
    
    return fig


def create_num_songs_per_year(songs):
    song_data = []
    for song in songs:
        release_date = song.release_date

        if len(release_date) == 7:
            year = int(release_date[:4])
        
        elif len(release_date) == 4:
            year = int(release_date)
        else:
            year = datetime.strptime(release_date, "%Y-%m-%d").year
        
        song_data.append(year)
        count_per_year = dict(collections.Counter(song_data))
    
    # Create the histogram plot using Plotly Express
    fig = go.Figure(data=go.Histogram(
        x=list(count_per_year.keys()),
        hovertext=list(count_per_year.values()),
        hovertemplate="Count: %{hovertext}<br>Year: %{x}",
        marker=dict(color='rgb(42, 120, 142)')
    ))
    
    fig.update_layout(
        title="Number of Songs per Year",
        xaxis_title="Year",
        yaxis_title="Count",
        template='plotly_dark'
    )
    return fig


def create_top_artists_plot(songs):
    artist_counts = Counter(song.artist for song in songs)
    top_10_artists = artist_counts.most_common(10)
    
    # Create the bar plot using Plotly Express
    fig = go.Figure(data=go.Bar(
        x=[artist for artist, count in top_10_artists],
        y=[count for artist, count in top_10_artists],
        marker=dict(color='rgb(40, 168, 131)')
    ))
    
    fig.update_layout(
        title="Top 10 Artists",
        xaxis_title="Artist",
        yaxis_title="Count",
        template='plotly_dark'
    )
    
    return fig


def create_genres_plot(songs):
    genre_counts = Counter()

    # Extract genre strings from each song and count their occurrences
    for song in songs:
        genres = song.genres.split(",")
        genre_counts.update(genres)

    # Select the top 10 most common genres
    top_10_genres = genre_counts.most_common(10)

    # Create the treemap chart using Plotly Express
    labels = [genre for genre, count in top_10_genres]
    values = [count for genre, count in top_10_genres]

    fig = go.Figure(go.Treemap(
        labels=labels,
        parents=[""] * len(labels),
        values=values,
        texttemplate="%{label}<br>Count: %{value}",
        textinfo="label+value+percent parent",
        marker=dict(
            colorscale="Viridis",
            colors=values,
            showscale=True
        )
    ))

    fig.update_layout(
        title="Top 10 Genres (Treemap)",
        margin=dict(l=0, r=0, t=30, b=0),
        template='plotly_dark'
    )
    
    return fig


def create_heatmap_plot(songs):
    df = pd.DataFrame({
        'popularity': [song.popularity for song in songs],
        'danceability': [song.danceability for song in songs],
        'energy': [song.energy for song in songs],
        'loudness': [song.loudness for song in songs],
        'speechiness': [song.speechiness for song in songs],
        'acousticness': [song.acousticness for song in songs],
        'instrumentalness': [song.instrumentalness for song in songs],
        'liveness': [song.liveness for song in songs],
        'valence': [song.valence for song in songs]
    })

    # Compute the correlation matrix
    corr = df.corr()

    # Create the heatmap trace
    data = go.Heatmap(
        z=corr.values,
        x=corr.columns,
        y=corr.index,
        colorscale='viridis'
    )

    # Create the annotations
    annotations = []
    for i, row in enumerate(corr.values):
        for j, value in enumerate(row):
            annotations.append(dict(
                x=corr.columns[j],
                y=corr.index[i],
                text=f'{value:.2f}',
                showarrow=False
            ))

    # Create the layout
    layout = go.Layout(
        title="Correlation Heatmap Between Variables",
        xaxis=dict(title='Features'),
        yaxis=dict(title='Features'),
        annotations=annotations,
        template='plotly_dark'
    )

    # Create the figure
    fig = go.Figure(data=data, layout=layout)

    return fig


def create_histo_popularity(songs):
    popularity_values = [song.popularity for song in songs]

    # Create the histogram
    fig = go.Figure(data=go.Histogram(x=popularity_values))
    
    fig.update_layout(
        title="Popularity Distribution", 
        xaxis_title="Popularity", 
        yaxis_title="Count",
        template='plotly_dark'
    )

    return fig
        

def create_danceability_energy_plot(songs):
    song_data = []
    for song in songs:
        song_data.append({
            'name': song.name,
            'danceability': song.danceability,
            'energy': song.energy
        })
    
    # Create the regression plot using Plotly Express
    fig = px.scatter(
        song_data, 
        x=[song['danceability'] for song in song_data],
        y=[song['energy'] for song in song_data],
        trendline='ols',
        color='energy',
        color_continuous_scale='viridis'
    )
    fig.update_traces(
        hovertemplate="<b>Name:</b> %{text}<br>"
                      "<b>Danceability:</b> %{x}<br>"
                      "<b>Energy:</b> %{y}",
        text=[song['name'] for song in song_data]
    )
    fig.update_layout(
        title="Dancibility vs Energy",
        xaxis_title="Danceability",
        yaxis_title="Energy",
        template='plotly_dark'
    )
    
    return fig


def create_populartity_over_time_plot(songs):
    df_songs = pd.DataFrame({
        'release_date': [song.release_date for song in songs],
        'popularity': [song.popularity for song in songs]
    })

    df_songs['release_date'] = pd.to_datetime(df_songs['release_date'])

    # Group songs by release date and calculate average popularity
    release_date_groups = df_songs.groupby(['release_date'])['popularity'].mean().reset_index()

    # Create the line chart
    fig = px.line(
        release_date_groups, 
        x="release_date", 
        y="popularity",
        color_discrete_sequence=px.colors.qualitative.Dark2
    )

    fig.update_layout(
        title="Popularity Over Time", 
        xaxis_title="Date", 
        yaxis_title="Popularity",
        template='plotly_dark'
    )

    return fig


def create_loudness_by_genre_plot(songs):
    song_data = []
    
    for song in songs:
        genres = song.genres.split(",")
        for genre in genres:
            song_data.append({
                'genre': genre,
                'loudness': song.loudness
            })
    
    df = pd.DataFrame(song_data)

    fig = px.box(
        df, 
        x='genre', 
        y='loudness', 
        points="all",
        color_discrete_sequence=px.colors.qualitative.D3
    )

    fig.update_layout(
        title="Loudness by Genre", 
        xaxis_title="Genres", 
        yaxis_title="Loudness",
        template='plotly_dark'
    )

    return fig
    
    
def total_artists(songs):
    artist_count = len(set(song.artist for song in songs))
    
    fig = go.Figure(go.Indicator(
        mode="number",
        value=artist_count,
        title={'text': 'Artist Count'}
        ))
    
    fig.update_layout(template='plotly_dark', height=225)
    
    return fig


def total_songs(songs):
    song_count = len(set(song.name for song in songs))
    
    fig = go.Figure(go.Indicator(
        mode="number",
        value=song_count,
        title={'text': 'Song Count'}
    ))
    
    fig.update_layout(template='plotly_dark', height=225)
    
    return fig


def total_genres(songs):
    song_data = []
    
    for song in songs:
        genres = song.genres.split(",")
        for genre in genres:
            song_data.append({
                'genre': genre
            })
    genre_count = len(set(song['genre'] for song in song_data))
    
    fig = go.Figure(go.Indicator(
        mode="number",
        value=genre_count,
        title={'text': 'Genre Count'}
    ))
    
    fig.update_layout(template='plotly_dark', height=225)
    
    return fig


def total_albums(songs):
    album_count = len(set(song.album for song in songs))
    
    fig = go.Figure(go.Indicator(
        mode="number",
        value=album_count,
        title={'text': 'Album Count'}
    ))
    
    fig.update_layout(template='plotly_dark', height=225)
    
    return fig


@dash_app.callback(Output('dash-container1', 'children'), [Input('viz-dropdown1', 'value')])
def update_dashboard_1(selected_viz):
    user_id = session[CURR_USER_KEY]
    all_songs = Songs.query.filter_by(user_id=user_id).all()

    energy_loudness_plot = create_energy_loudness_plot(all_songs)
    popularity_loudness_plot = create_popularity_loudness_plot(all_songs)
    num_songs_per_year_plot = create_num_songs_per_year(all_songs)
    top_10_artists_plot = create_top_artists_plot(all_songs)
    genres_plot = create_genres_plot(all_songs)
    heatmap_plot = create_heatmap_plot(all_songs)
    histo_popularity_plot = create_histo_popularity(all_songs)
    danceability_energy_plot = create_danceability_energy_plot(all_songs)
    popularity_over_time_plot = create_populartity_over_time_plot(all_songs)
    loudness_by_genre_plot = create_loudness_by_genre_plot(all_songs)
    
    if selected_viz == 'energy_loudness':
        return html.Div(dcc.Graph(figure=energy_loudness_plot))
    elif selected_viz == 'popularity_loudness':
        return html.Div(dcc.Graph(figure=popularity_loudness_plot))
    elif selected_viz == 'songs_per_year':
        return html.Div(dcc.Graph(figure=num_songs_per_year_plot))
    elif selected_viz == 'top_10_artists':
        return html.Div(dcc.Graph(figure=top_10_artists_plot))
    elif selected_viz == 'genres':
        return html.Div(dcc.Graph(figure=genres_plot))
    elif selected_viz == 'heatmap':
        return html.Div(dcc.Graph(figure=heatmap_plot))
    elif selected_viz == 'popularity_histogram':
        return html.Div(dcc.Graph(figure=histo_popularity_plot))
    elif selected_viz == 'danceability_energy':
        return html.Div(dcc.Graph(figure=danceability_energy_plot))
    elif selected_viz == 'popularity_over_time':
        return html.Div(dcc.Graph(figure=popularity_over_time_plot))
    elif selected_viz == 'loudness_by_genre':
        return html.Div(dcc.Graph(figure=loudness_by_genre_plot))
    elif selected_viz == 'none':
        return None
    
    # Default case if no visualization is selected
    return None


@dash_app.callback(Output('dash-container2', 'children'), [Input('viz-dropdown2', 'value')])
def update_dashboard_2(selected_viz):
    user_id = session[CURR_USER_KEY]
    all_songs = Songs.query.filter_by(user_id=user_id).all()

    energy_loudness_plot = create_energy_loudness_plot(all_songs)
    popularity_loudness_plot = create_popularity_loudness_plot(all_songs)
    num_songs_per_year_plot = create_num_songs_per_year(all_songs)
    top_10_artists_plot = create_top_artists_plot(all_songs)
    genres_plot = create_genres_plot(all_songs)
    heatmap_plot = create_heatmap_plot(all_songs)
    histo_popularity_plot = create_histo_popularity(all_songs)
    danceability_energy_plot = create_danceability_energy_plot(all_songs)
    popularity_over_time_plot = create_populartity_over_time_plot(all_songs)
    loudness_by_genre_plot = create_loudness_by_genre_plot(all_songs)
    
    if selected_viz == 'energy_loudness':
        return html.Div(dcc.Graph(figure=energy_loudness_plot))
    elif selected_viz == 'popularity_loudness':
        return html.Div(dcc.Graph(figure=popularity_loudness_plot))
    elif selected_viz == 'songs_per_year':
        return html.Div(dcc.Graph(figure=num_songs_per_year_plot))
    elif selected_viz == 'top_10_artists':
        return html.Div(dcc.Graph(figure=top_10_artists_plot))
    elif selected_viz == 'genres':
        return html.Div(dcc.Graph(figure=genres_plot))
    elif selected_viz == 'heatmap':
        return html.Div(dcc.Graph(figure=heatmap_plot))
    elif selected_viz == 'popularity_histogram':
        return html.Div(dcc.Graph(figure=histo_popularity_plot))
    elif selected_viz == 'danceability_energy':
        return html.Div(dcc.Graph(figure=danceability_energy_plot))
    elif selected_viz == 'popularity_over_time':
        return html.Div(dcc.Graph(figure=popularity_over_time_plot))
    elif selected_viz == 'loudness_by_genre':
        return html.Div(dcc.Graph(figure=loudness_by_genre_plot))
    elif selected_viz == 'none':
        return None
    
    # Default case if no visualization is selected
    return None


@dash_app.callback(Output('dash-container3', 'children'), [Input('viz-dropdown3', 'value')])
def update_dashboard_3(selected_viz):
    user_id = session[CURR_USER_KEY]
    all_songs = Songs.query.filter_by(user_id=user_id).all()

    energy_loudness_plot = create_energy_loudness_plot(all_songs)
    popularity_loudness_plot = create_popularity_loudness_plot(all_songs)
    num_songs_per_year_plot = create_num_songs_per_year(all_songs)
    top_10_artists_plot = create_top_artists_plot(all_songs)
    genres_plot = create_genres_plot(all_songs)
    heatmap_plot = create_heatmap_plot(all_songs)
    histo_popularity_plot = create_histo_popularity(all_songs)
    danceability_energy_plot = create_danceability_energy_plot(all_songs)
    popularity_over_time_plot = create_populartity_over_time_plot(all_songs)
    loudness_by_genre_plot = create_loudness_by_genre_plot(all_songs)
    
    if selected_viz == 'energy_loudness':
        return html.Div(dcc.Graph(figure=energy_loudness_plot))
    elif selected_viz == 'popularity_loudness':
        return html.Div(dcc.Graph(figure=popularity_loudness_plot))
    elif selected_viz == 'songs_per_year':
        return html.Div(dcc.Graph(figure=num_songs_per_year_plot))
    elif selected_viz == 'top_10_artists':
        return html.Div(dcc.Graph(figure=top_10_artists_plot))
    elif selected_viz == 'genres':
        return html.Div(dcc.Graph(figure=genres_plot))
    elif selected_viz == 'heatmap':
        return html.Div(dcc.Graph(figure=heatmap_plot))
    elif selected_viz == 'popularity_histogram':
        return html.Div(dcc.Graph(figure=histo_popularity_plot))
    elif selected_viz == 'danceability_energy':
        return html.Div(dcc.Graph(figure=danceability_energy_plot))
    elif selected_viz == 'popularity_over_time':
        return html.Div(dcc.Graph(figure=popularity_over_time_plot))
    elif selected_viz == 'loudness_by_genre':
        return html.Div(dcc.Graph(figure=loudness_by_genre_plot))
    elif selected_viz == 'none':
        return None
    
    # Default case if no visualization is selected
    return None


@dash_app.callback(Output('dash-container4', 'children'), [Input('viz-dropdown4', 'value')])
def update_dashboard_4(selected_viz):
    user_id = session[CURR_USER_KEY]
    all_songs = Songs.query.filter_by(user_id=user_id).all()

    energy_loudness_plot = create_energy_loudness_plot(all_songs)
    popularity_loudness_plot = create_popularity_loudness_plot(all_songs)
    num_songs_per_year_plot = create_num_songs_per_year(all_songs)
    top_10_artists_plot = create_top_artists_plot(all_songs)
    genres_plot = create_genres_plot(all_songs)
    heatmap_plot = create_heatmap_plot(all_songs)
    histo_popularity_plot = create_histo_popularity(all_songs)
    danceability_energy_plot = create_danceability_energy_plot(all_songs)
    popularity_over_time_plot = create_populartity_over_time_plot(all_songs)
    loudness_by_genre_plot = create_loudness_by_genre_plot(all_songs)
    
    if selected_viz == 'energy_loudness':
        return html.Div(dcc.Graph(figure=energy_loudness_plot))
    elif selected_viz == 'popularity_loudness':
        return html.Div(dcc.Graph(figure=popularity_loudness_plot))
    elif selected_viz == 'songs_per_year':
        return html.Div(dcc.Graph(figure=num_songs_per_year_plot))
    elif selected_viz == 'top_10_artists':
        return html.Div(dcc.Graph(figure=top_10_artists_plot))
    elif selected_viz == 'genres':
        return html.Div(dcc.Graph(figure=genres_plot))
    elif selected_viz == 'heatmap':
        return html.Div(dcc.Graph(figure=heatmap_plot))
    elif selected_viz == 'popularity_histogram':
        return html.Div(dcc.Graph(figure=histo_popularity_plot))
    elif selected_viz == 'danceability_energy':
        return html.Div(dcc.Graph(figure=danceability_energy_plot))
    elif selected_viz == 'popularity_over_time':
        return html.Div(dcc.Graph(figure=popularity_over_time_plot))
    elif selected_viz == 'loudness_by_genre':
        return html.Div(dcc.Graph(figure=loudness_by_genre_plot))
    elif selected_viz == 'none':
        return None
    
    # Default case if no visualization is selected
    return None


@dash_app.callback(Output('dash-container5', 'children'), [Input('viz-dropdown5', 'value')])
def update_dashboard_5(selected_viz):
    user_id = session[CURR_USER_KEY]
    all_songs = Songs.query.filter_by(user_id=user_id).all()
    
    artist_count = total_artists(all_songs)
    song_count = total_songs(all_songs)
    genre_count = total_genres(all_songs)
    album_count = total_albums(all_songs)
    
    if selected_viz == 'artist_count':
        return html.Div(dcc.Graph(figure=artist_count))
    elif selected_viz == 'song_count':
        return html.Div(dcc.Graph(figure=song_count))
    elif selected_viz == 'genre_count':
        return html.Div(dcc.Graph(figure=genre_count))
    elif selected_viz == 'album_count':
        return html.Div(dcc.Graph(figure=album_count))
    elif selected_viz == 'none':
        return None
    
    # Default case if no visualization is selected
    return None


@dash_app.callback(Output('dash-container6', 'children'), [Input('viz-dropdown6', 'value')])
def update_dashboard_6(selected_viz):
    user_id = session[CURR_USER_KEY]
    all_songs = Songs.query.filter_by(user_id=user_id).all()
    
    artist_count = total_artists(all_songs)
    song_count = total_songs(all_songs)
    genre_count = total_genres(all_songs)
    album_count = total_albums(all_songs)
    
    if selected_viz == 'artist_count':
        return html.Div(dcc.Graph(figure=artist_count))
    elif selected_viz == 'song_count':
        return html.Div(dcc.Graph(figure=song_count))
    elif selected_viz == 'genre_count':
        return html.Div(dcc.Graph(figure=genre_count))
    elif selected_viz == 'album_count':
        return html.Div(dcc.Graph(figure=album_count))
    elif selected_viz == 'none':
        return None
    
    # Default case if no visualization is selected
    return None


@dash_app.callback(Output('dash-container7', 'children'), [Input('viz-dropdown7', 'value')])
def update_dashboard_7(selected_viz):
    user_id = session[CURR_USER_KEY]
    all_songs = Songs.query.filter_by(user_id=user_id).all()
    
    artist_count = total_artists(all_songs)
    song_count = total_songs(all_songs)
    genre_count = total_genres(all_songs)
    album_count = total_albums(all_songs)
    
    if selected_viz == 'artist_count':
        return html.Div(dcc.Graph(figure=artist_count))
    elif selected_viz == 'song_count':
        return html.Div(dcc.Graph(figure=song_count))
    elif selected_viz == 'genre_count':
        return html.Div(dcc.Graph(figure=genre_count))
    elif selected_viz == 'album_count':
        return html.Div(dcc.Graph(figure=album_count))
    elif selected_viz == 'none':
        return None
    
    # Default case if no visualization is selected
    return None


@dash_app.callback(Output('dash-container8', 'children'), [Input('viz-dropdown8', 'value')])
def update_dashboard_8(selected_viz):
    user_id = session[CURR_USER_KEY]
    all_songs = Songs.query.filter_by(user_id=user_id).all()
    
    artist_count = total_artists(all_songs)
    song_count = total_songs(all_songs)
    genre_count = total_genres(all_songs)
    album_count = total_albums(all_songs)
    
    if selected_viz == 'artist_count':
        return html.Div(dcc.Graph(figure=artist_count))
    elif selected_viz == 'song_count':
        return html.Div(dcc.Graph(figure=song_count))
    elif selected_viz == 'genre_count':
        return html.Div(dcc.Graph(figure=genre_count))
    elif selected_viz == 'album_count':
        return html.Div(dcc.Graph(figure=album_count))
    elif selected_viz == 'none':
        return None
    
    # Default case if no visualization is selected
    return None


def create_dash_application():
    layout = html.Div([
        dcc.Location(id='url', refresh=True),
        html.Div(className='container-fluid', children=[
            html.Div(className='row', children=[
                html.Div(className='col-md-6', children=[
                    dcc.Input(
                        id='text-input',
                        type='text',
                        placeholder='Enter a Title...',
                        className='form-control form-control-lg'
                    )
                ]),
                html.Div(className='col-md-6 text-md-end', children=[
                    html.Button('Save', className='btn btn-custom btn-lg', id='save-button', n_clicks=0),
                    html.A(id='redirect-link', href='/dashboard', children='Back to All', className='btn btn-secondary btn-lg'),
                    html.Div(id='flash-message', className='row', style={'margin': '10px', 'color': 'white', 'justify-content': 'flex-end'})
                ])
            ]),
            html.Div(className='row', children=[
                html.Div(className='col-md-3', children=[
                    dcc.Dropdown(
                        id='viz-dropdown5',
                        options=[
                            {'label': 'Artist Count', 'value': 'artist_count'},
                            {'label': 'Song Count', 'value': 'song_count'},
                            {'label': 'Genre Count', 'value': 'genre_count'},
                            {'label': 'Album Count', 'value': 'album_count'},
                            {'label': 'None', 'value': 'none'}
                        ],
                        value=None,  # Set default value to None
                        placeholder='Select a visualization',
                        style={'margin-bottom': '10px'}
                    ),
                    html.Div(id='dash-container5')
                ]),
                html.Div(className='col-md-3', children=[
                    dcc.Dropdown(
                        id='viz-dropdown6',
                        options=[
                            {'label': 'Artist Count', 'value': 'artist_count'},
                            {'label': 'Song Count', 'value': 'song_count'},
                            {'label': 'Genre Count', 'value': 'genre_count'},
                            {'label': 'Album Count', 'value': 'album_count'},
                            {'label': 'None', 'value': 'none'}
                        ],
                        value=None,  # Set default value to None
                        placeholder='Select a visualization',
                        style={'margin-bottom': '10px'}
                    ),
                    html.Div(id='dash-container6')
                ]),
                html.Div(className='col-md-3', children=[
                    dcc.Dropdown(
                        id='viz-dropdown7',
                        options=[
                            {'label': 'Artist Count', 'value': 'artist_count'},
                            {'label': 'Song Count', 'value': 'song_count'},
                            {'label': 'Genre Count', 'value': 'genre_count'},
                            {'label': 'Album Count', 'value': 'album_count'},
                            {'label': 'None', 'value': 'none'}
                        ],
                        value=None,  # Set default value to None
                        placeholder='Select a visualization',
                        style={'margin-bottom': '10px'}
                    ),
                    html.Div(id='dash-container7')
                ]),
                html.Div(className='col-md-3', children=[
                    dcc.Dropdown(
                        id='viz-dropdown8',
                        options=[
                            {'label': 'Artist Count', 'value': 'artist_count'},
                            {'label': 'Song Count', 'value': 'song_count'},
                            {'label': 'Genre Count', 'value': 'genre_count'},
                            {'label': 'Album Count', 'value': 'album_count'},
                            {'label': 'None', 'value': 'none'}
                        ],
                        value=None,  # Set default value to None
                        placeholder='Select a visualization',
                        style={'margin-bottom': '10px'}
                    ),
                    html.Div(id='dash-container8')
                ]),
            ]),
            html.Div(className='row', id='main', children=[
                html.Div(className='col-md-8', children=[
                    dcc.Dropdown(
                        id='viz-dropdown1',
                        options=[
                            {'label': 'Energy vs Loudness', 'value': 'energy_loudness'},
                            {'label': 'Popularity vs Loudness', 'value': 'popularity_loudness'},
                            {'label': 'Number of Songs per Year', 'value': 'songs_per_year'},
                            {'label': 'Top 10 Artists', 'value': 'top_10_artists'},
                            {'label': 'Top 10 Genres', 'value': 'genres'},
                            {'label': 'Correlation Heatmap Between Variables', 'value': 'heatmap'},
                            {'label': 'Popularity Distribution', 'value': 'popularity_histogram'},
                            {'label': 'Daneability vs Energy', 'value': 'danceability_energy'},
                            {'label': 'Popularity Over Time', 'value': 'popularity_over_time'},
                            {'label': 'Loudness by Genre', 'value': 'loudness_by_genre'},
                            {'label': 'None', 'value': 'none'}
                        ],
                        value=None,  # Set default value to None
                        placeholder='Select a visualization',
                        style={'margin-bottom': '10px'}
                    ),
                    html.Div(id='dash-container1')
                ]),
                html.Div(className='col-md-4', children=[
                    dcc.Dropdown(
                        id='viz-dropdown2',
                        options=[
                            {'label': 'Energy vs Loudness', 'value': 'energy_loudness'},
                            {'label': 'Popularity vs Loudness', 'value': 'popularity_loudness'},
                            {'label': 'Number of Songs per Year', 'value': 'songs_per_year'},
                            {'label': 'Top 10 Artists', 'value': 'top_10_artists'},
                            {'label': 'Top 10 Genres', 'value': 'genres'},
                            {'label': 'Correlation Heatmap Between Variables', 'value': 'heatmap'},
                            {'label': 'Popularity Distribution', 'value': 'popularity_histogram'},
                            {'label': 'Daneability vs Energy', 'value': 'danceability_energy'},
                            {'label': 'Popularity Over Time', 'value': 'popularity_over_time'},
                            {'label': 'Loudness by Genre', 'value': 'loudness_by_genre'},
                            {'label': 'None', 'value': 'none'}
                        ],
                        value=None,  # Set default value to None
                        placeholder='Select a visualization',
                        style={'margin-bottom': '10px'}
                    ),
                    html.Div(id='dash-container2'),
                ])
            ]),
            html.Div(className='row', children=[
                html.Div(className='col-md-6', children=[
                    dcc.Dropdown(
                        id='viz-dropdown3',
                        options=[
                            {'label': 'Energy vs Loudness', 'value': 'energy_loudness'},
                            {'label': 'Popularity vs Loudness', 'value': 'popularity_loudness'},
                            {'label': 'Number of Songs per Year', 'value': 'songs_per_year'},
                            {'label': 'Top 10 Artists', 'value': 'top_10_artists'},
                            {'label': 'Top 10 Genres', 'value': 'genres'},
                            {'label': 'Correlation Heatmap Between Variables', 'value': 'heatmap'},
                            {'label': 'Popularity Distribution', 'value': 'popularity_histogram'},
                            {'label': 'Daneability vs Energy', 'value': 'danceability_energy'},
                            {'label': 'Popularity Over Time', 'value': 'popularity_over_time'},
                            {'label': 'Loudness by Genre', 'value': 'loudness_by_genre'},
                            {'label': 'None', 'value': 'none'}
                        ],
                        value=None,  # Set default value to None
                        placeholder='Select a visualization',
                        style={'margin-bottom': '10px'}
                    ),
                    html.Div(id='dash-container3')
                ]),
                html.Div(className='col-md-6', children=[
                    dcc.Dropdown(
                        id='viz-dropdown4',
                        options=[
                            {'label': 'Energy vs Loudness', 'value': 'energy_loudness'},
                            {'label': 'Popularity vs Loudness', 'value': 'popularity_loudness'},
                            {'label': 'Number of Songs per Year', 'value': 'songs_per_year'},
                            {'label': 'Top 10 Artists', 'value': 'top_10_artists'},
                            {'label': 'Top 10 Genres', 'value': 'genres'},
                            {'label': 'Correlation Heatmap Between Variables', 'value': 'heatmap'},
                            {'label': 'Popularity Distribution', 'value': 'popularity_histogram'},
                            {'label': 'Daneability vs Energy', 'value': 'danceability_energy'},
                            {'label': 'Popularity Over Time', 'value': 'popularity_over_time'},
                            {'label': 'Loudness by Genre', 'value': 'loudness_by_genre'},
                            {'label': 'None', 'value': 'none'}
                        ],
                        value=None,  # Set default value to None
                        placeholder='Select a visualization',
                        style={'margin-bottom': '10px'}
                    ),
                    html.Div(id='dash-container4')
                ]),
            ])
        ]),
    ])
    
    @dash_app.callback(
        Output('flash-message', 'children'),
        Output('url', 'pathname'),
        State('text-input', 'value'),
        Input('viz-dropdown1', 'value'),
        Input('viz-dropdown2', 'value'),
        Input('viz-dropdown3', 'value'),
        Input('viz-dropdown4', 'value'),
        Input('viz-dropdown5', 'value'),
        Input('viz-dropdown6', 'value'),
        Input('viz-dropdown7', 'value'),
        Input('viz-dropdown8', 'value'),
        Input('save-button', 'n_clicks')
    )
    def save_dropdown_data(title, value1, value2, value3, value4, value5, value6, value7, value8, n_clicks):
        if n_clicks is not None and n_clicks > 0:
            fav_dash = UserFavoriteDashboards(
                dash_name=title, 
                kpi_1=value5,
                kpi_2=value6,
                kpi_3=value7,
                kpi_4=value8,
                viz_1=value1,
                viz_2=value2,
                viz_3=value3,
                viz_4=value4
            )
            db.session.add(fav_dash)
            db.session.commit()

            print(fav_dash)
            pathname = f'/dash/{fav_dash.id}'
            # flash('Dashboard Saved!', 'success')
            return 'Dashboard Saved!', pathname
        
        return dash.no_update

    dash_app.layout = layout
    return dash_app


def saved_dash_application(dash_id):
    # dashboards = UserFavoriteDashboards.query.filter_by(user_id=current_user.user_id).get(dash_id)
    
    # all_songs = Songs.query.filter_by(user_id=current_user.user_id).all()

    # energy_loudness = create_energy_loudness_plot(all_songs)
    # popularity_loudness = create_popularity_loudness_plot(all_songs)
    # songs_per_year = create_num_songs_per_year(all_songs)
    # top_10_artists = create_top_artists_plot(all_songs)
    # genres = create_genres_plot(all_songs)
    # heatmap = create_heatmap_plot(all_songs)
    # histo_popularity = create_histo_popularity(all_songs)
    # danceability_energy = create_danceability_energy_plot(all_songs)
    # popularity_over_time = create_populartity_over_time_plot(all_songs)
    # loudness_by_genre = create_loudness_by_genre_plot(all_songs)
    # artist_count = total_artists(all_songs)
    # song_count = total_songs(all_songs)
    # genre_count = total_genres(all_songs)
    # album_count = total_albums(all_songs)
    
    layout = html.Div([
        dcc.Location(id='url', refresh=True),
        html.Div(className='container-fluid', children=[
            html.Div(className='row', children=[
                html.Div(className='col-md-6', children=[
                    html.H1(dashboard.dash_name)
                ])
            ]),
            html.Div(className='row', children=[
                html.Div(className='col-md-3', children=[
                    dcc.Graph(figure=eval(dashboard.kpi_1) if dashboard.kpi_1 is not None else None)
                ]),
                html.Div(className='col-md-3', children=[
                    dcc.Graph(figure=eval(dashboard.kpi_2) if dashboard.kpi_2 is not None else None)
                ]),
                html.Div(className='col-md-3', children=[
                    dcc.Graph(figure=eval(dashboard.kpi_3) if dashboard.kpi_3 is not None else None)
                ]),
                html.Div(className='col-md-3', children=[
                    dcc.Graph(figure=eval(dashboard.kpi_4) if dashboard.kpi_4 is not None else None)
                ]),
            ]),
            html.Div(className='row', id='main', children=[
                html.Div(className='col-md-8', children=[
                    dcc.Graph(figure=eval(dashboard.viz_1) if dashboard.viz_1 is not None else None)
                ]),
                html.Div(className='col-md-4', children=[
                    dcc.Graph(figure=eval(dashboard.viz_2) if dashboard.viz_2 is not None else None)
                ])
            ]),
            html.Div(className='row', children=[
                html.Div(className='col-md-6', children=[
                    dcc.Graph(figure=eval(dashboard.viz_3) if dashboard.viz_3 is not None else None)
                ]),
                html.Div(className='col-md-6', children=[
                    dcc.Graph(figure=eval(dashboard.viz_4) if dashboard.viz_4 is not None else None)
                ]),
            ]),
        ]),
    ])
    
    dash_app.layout = layout
    return dash_app


@app.route('/user/profile', methods=["GET", "POST"])
@login_required
def profile():
    """Display current user's dashboards."""
    user_id = session[CURR_USER_KEY]
    dashboards = UserFavoriteDashboards.query.filter_by(user_id=user_id).all()
        
    return render_template('users/show.html', dashboards=dashboards)


@app.route('/user/profile/edit', methods=["GET", "POST"])
@login_required
def profile_edit():
    """Update profile for current user."""
    user = g.user
    form = UserEditForm(obj=user)
    user_id = session[CURR_USER_KEY]
    dashboards = UserFavoriteDashboards.query.filter_by(user_id=user_id).all()
    
    if form.is_submitted() and form.validate():
        if User.authenticate(user.username, form.password.data):
            user.first_name = form.first_name.data 
            user.last_name = form.last_name.data 
            user.email = form.email.data
            
            db.session.commit()
            flash('User updated!', 'success')
            return redirect('/dashboard')
        
        flash('Wrong password, please try again', 'danger')
        
    return render_template('/users/edit.html', user=user, form=form, dashboards=dashboards)
        
    
@app.route('/user/delete', methods=["GET","POST"])
@login_required
def delete_user():
    """Delete user."""
    
    user_id = g.user.user_id
    user = User.query.get_or_404(user_id)
    if user_id == session['_user_id']:  
        db.session.delete(user)
        db.session.commit()
        flash('User deleted', 'success')
        logout_user()  # Optional: Log out the user after deleting their account
        return redirect("/signup")
    else:
        flash('Access unauthorized.', 'danger')
        return redirect("/home")
    

