"""Flask flow checks using real SQL through an isolated SQLite adapter."""
import os
import re
import sqlite3
import sys
from pathlib import Path
from datetime import date, datetime
from decimal import Decimal
import pytest
from werkzeug.security import generate_password_hash

os.environ['SECRET_KEY'] = 'isolated-test-secret-never-used-for-running-app'
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import app as module

class Cursor:
    def __init__(self, db):
        self.db = db
        self.raw = db.raw.cursor()
    def execute(self, sql, params=()):
        if self.db.fail_hotel and 'INSERT INTO HOTEL' in sql:
            raise RuntimeError('Simulated detail insert failure')
        self.raw.execute(sql.replace('%s', '?'), tuple(str(x) if isinstance(x, Decimal) else x for x in params))
    @property
    def lastrowid(self):
        return self.raw.lastrowid
    def convert(self, row):
        if row is None:
            return None
        result = dict(row)
        for key in ('StartDate', 'EndDate', 'BookingDate', 'CheckInDate', 'CheckOutDate'):
            if result.get(key):
                result[key] = date.fromisoformat(result[key])
        for key in ('DepartureTime', 'ArrivalTime'):
            if result.get(key):
                result[key] = datetime.fromisoformat(result[key])
        return result
    def fetchone(self):
        return self.convert(self.raw.fetchone())
    def fetchall(self):
        return [self.convert(x) for x in self.raw.fetchall()]
    def close(self):
        self.raw.close()
    def __enter__(self):
        return self
    def __exit__(self, *args):
        self.close()

class Database:
    fail_hotel = False
    def __init__(self):
        self.raw = sqlite3.connect(':memory:')
        self.raw.row_factory = sqlite3.Row
        self.raw.execute('PRAGMA foreign_keys=ON')
        text = (Path(module.__file__).parent / 'seed_data.sql').read_text()
        text = text[text.index('CREATE TABLE USER'):]
        text = text.replace('INT AUTO_INCREMENT PRIMARY KEY', 'INTEGER PRIMARY KEY AUTOINCREMENT')
        text = re.sub(r'ENUM\([^)]*\)', 'TEXT', text)
        self.raw.executescript(text)
        self.raw.execute('UPDATE USER SET PasswordHash=?', (generate_password_hash('CorrectDemoPassword!'),))
        self.raw.commit()
    def cursor(self):
        return Cursor(self)
    def commit(self):
        self.raw.commit()
    def rollback(self):
        self.raw.rollback()
    def close(self):
        # Preserve the test fixture; emulate a real connection close rolling back uncommitted writes.
        self.raw.rollback()

@pytest.fixture
def environment(monkeypatch):
    db = Database()
    module.app.config.update(TESTING=True, WTF_CSRF_ENABLED=True)
    def connection():
        module.g.db = db
        return db
    monkeypatch.setattr(module, 'get_db', connection)
    yield module.app.test_client(), db
    db.raw.close()

def csrf(client, path='/login'):
    html = client.get(path).get_data(as_text=True)
    return re.search(r'name="csrf_token" value="([^"]+)"', html).group(1)

def signin(client, email='alex@example.com', password='CorrectDemoPassword!'):
    return client.post('/login', data={'email': email, 'password': password, 'csrf_token': csrf(client)})

def hotel_data(client, **extra):
    data = dict(trip_id='1', booking_type='Hotel', hotel_name='Demo Hotel', location='London',
                checkin_date='2026-06-01', checkout_date='2026-06-04', price_per_night='150.25',
                csrf_token=csrf(client, '/booking?trip_id=1'))
    data.update(extra)
    return data

def test_login_checks_hash_and_renders_dashboard(environment):
    client, db = environment
    assert b'Invalid email or password' in signin(client, password='pass123').data
    assert signin(client).status_code == 302
    assert b'Summer Europe Trip' in client.get('/dashboard').data

def test_csrf_and_logout(environment):
    client, db = environment
    assert client.post('/login', data={'email':'alex@example.com', 'password':'CorrectDemoPassword!'}).status_code == 400
    signin(client)
    assert client.get('/logout').status_code == 405
    token = csrf(client, '/dashboard')
    assert client.post('/logout', data={'csrf_token':token}).status_code == 302
    assert client.get('/dashboard').status_code == 302

def test_other_users_cannot_access_or_write_trip(environment):
    client, db = environment
    signin(client, email='jordan@example.com')
    assert client.get('/booking?trip_id=1').status_code == 404
    assert client.get('/confirmation/1').status_code == 404
    token = csrf(client, '/booking')
    assert client.post('/booking', data={'trip_id':'1', 'booking_type':'Hotel', 'csrf_token':token}).status_code == 404
    assert db.raw.execute('SELECT count(*) FROM BOOKING').fetchone()[0] == 2

def test_trip_creation_and_destination_lookup(environment):
    client, db = environment
    signin(client)
    assert client.get('/visa-info/5').json[0]['VisaType'] == 'Demo visa information'
    data=dict(trip_name='Paris Weekend', destination_id='5', start_date='2026-11-01', end_date='2026-11-04', status='Planning', csrf_token=csrf(client, '/create-trip'))
    response=client.post('/create-trip', data=data)
    assert response.status_code == 302
    assert db.raw.execute("SELECT count(*) FROM TRIP WHERE TripName='Paris Weekend'").fetchone()[0] == 1

@pytest.mark.parametrize('start,end,destination', [('invalid','2026-11-04','5'), ('2026-11-04','2026-11-01','5'), ('2026-11-01','2026-11-04','999')])
def test_invalid_trip_data_does_not_write(environment, start, end, destination):
    client, db = environment
    signin(client)
    response = client.post('/create-trip', data=dict(trip_name='Invalid', destination_id=destination, start_date=start, end_date=end, status='Planning', csrf_token=csrf(client, '/create-trip')))
    assert response.status_code == 200
    assert db.raw.execute('SELECT count(*) FROM TRIP').fetchone()[0] == 3

def test_hotel_booking_exact_total_and_confirmation(environment):
    client, db = environment
    signin(client)
    response=client.post('/booking', data=hotel_data(client))
    assert response.status_code == 302
    assert Decimal(str(db.raw.execute('SELECT TotalPrice FROM BOOKING ORDER BY BookingID DESC LIMIT 1').fetchone()[0])) == Decimal('450.75')
    assert b'450.75' in client.get(response.location).data

@pytest.mark.parametrize('price', ['NaN','Infinity','-1','0','abc','1.001'])
def test_invalid_prices_do_not_write(environment, price):
    client, db = environment
    signin(client)
    assert client.post('/booking', data=hotel_data(client, price_per_night=price)).status_code == 200
    assert db.raw.execute('SELECT count(*) FROM BOOKING').fetchone()[0] == 2

def test_invalid_hotel_dates_do_not_crash(environment):
    client, db = environment
    signin(client)
    assert client.post('/booking', data=hotel_data(client, checkin_date='not-a-date')).status_code == 200
    assert db.raw.execute('SELECT count(*) FROM BOOKING').fetchone()[0] == 2

def test_detail_failure_rolls_back_parent_booking(environment):
    client, db = environment
    signin(client)
    data = hotel_data(client)
    db.fail_hotel = True
    with pytest.raises(RuntimeError, match='Simulated'):
        client.post('/booking', data=data)
    assert db.raw.execute('SELECT count(*) FROM BOOKING').fetchone()[0] == 2

def test_flight_booking_and_time_validation(environment):
    client, db = environment
    signin(client)
    data=dict(trip_id='1', booking_type='Flight', airline='Demo Air', departure_city='Dubai', arrival_city='London', departure_time='2026-06-01T08:00', arrival_time='2026-06-01T12:30', price='850.00', csrf_token=csrf(client, '/booking?trip_id=1'))
    response=client.post('/booking', data=data)
    assert response.status_code == 302
    assert b'Demo Air' in client.get(response.location).data
    data['arrival_time']='2026-05-31T12:30'
    data['csrf_token']=csrf(client, '/booking?trip_id=1')
    assert client.post('/booking', data=data).status_code == 200
    assert db.raw.execute('SELECT count(*) FROM BOOKING').fetchone()[0] == 3
