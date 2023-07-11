# Tests that a user can successfully sign up with valid input data.
def test_signup_success(self):
    with app.test_client() as client:
        response = client.post(
            '/signup',
            data={
                'first_name': 'John',
                'last_name': 'Doe',
                'email': 'johndoe@example.com',
                'username': 'johndoe',
                'password': 'password'
            }
        )
        assert response.status_code == 302
        assert response.location == 'http://localhost/home'


# Tests that a user is redirected to the home page after successfully signing up.
def test_signup_redirects_to_home_on_success(self):
    with app.test_client() as client:
        response = client.post(
            '/signup',
            data={
                'first_name': 'John',
                'last_name': 'Doe',
                'email': 'johndoe@example.com',
                'username': 'johndoe',
                'password': 'password'
            }
        )
        assert response.status_code == 302
        assert response.headers['Location'] == 'http://localhost/home'


# Tests that the page_not_found function renders the 404.html template
def test_page_not_found_template_rendered(self):
    with app.test_request_context('/unknown_route'):
        response = page_not_found(404)
        assert response[0].status_code == 404
        assert b'404 - Page Not Found' in response[0].data
        assert b'The page you are looking for does not exist.' in response[0].data
        assert b'Go back to the homepage' in response[0].data


# Tests that page_not_found returns a 404 status code
def test_return_404_status_code(self):
    with app.test_request_context():
        response = page_not_found(Exception())
        assert response[1] == 404

