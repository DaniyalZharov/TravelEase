from flask import Flask, render_template, request, redirect, url_for, session, abort, jsonify, g
import pymysql
import pymysql.cursors
from datetime import date, datetime
from functools import wraps
from decimal import Decimal, InvalidOperation
from pathlib import Path
import os
from dotenv import load_dotenv
from flask_wtf.csrf import CSRFProtect
from werkzeug.security import check_password_hash

app = Flask(__name__)
load_dotenv(Path(__file__).with_name('.env'))
app.secret_key = os.environ.get('SECRET_KEY')
if not app.secret_key or app.secret_key == 'replace-with-a-random-secret':
    raise RuntimeError('Set SECRET_KEY in .env. See README.md for setup.')
app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Lax',
                  SESSION_COOKIE_SECURE=os.getenv('COOKIE_SECURE', 'false').lower() == 'true')
CSRFProtect(app)

# -------------------------------------------------------
# Database Connection
# -------------------------------------------------------
def get_db():
    if 'db' not in g:
        g.db = pymysql.connect(
            host=os.getenv('DB_HOST', '127.0.0.1'),
            port=int(os.getenv('DB_PORT', '3306')),
            user=os.getenv('DB_USER', 'travelease_app'),
            password=os.getenv('DB_PASSWORD', ''),
            database=os.getenv('DB_NAME', 'TravelEaseDemo'),
            charset='utf8mb4',
            cursorclass=pymysql.cursors.DictCursor
        )
    return g.db

@app.teardown_appcontext
def close_db(exception=None):
    db = g.pop('db', None)
    if db is not None:
        if exception is not None:
            db.rollback()
        db.close()
    
def parse_date_range(start, end, label, errors, datetime_values=False):
    parser = datetime.fromisoformat if datetime_values else date.fromisoformat
    try:
        first, last = parser(start), parser(end)
        if datetime_values and (first.tzinfo is not None or last.tzinfo is not None):
            raise ValueError('Use local date and time values without time-zone offsets.')
        if last <= first:
            errors.append(f'{label}: end must be after start.')
        return first, last
    except (ValueError, TypeError):
        errors.append(f'{label}: enter valid dates.')
        return None, None

def parse_price(value, label, errors):
    try:
        amount = Decimal(value)
        if not amount.is_finite() or amount <= 0 or amount > Decimal('99999999.99'):
            raise ValueError
        if amount != amount.quantize(Decimal('0.01')):
            raise ValueError
        return amount
    except (InvalidOperation, ValueError, TypeError):
        errors.append(f'{label}: enter a positive amount with at most two decimal places.')
        return None

# -------------------------------------------------------
# Login required decorator
# -------------------------------------------------------
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

# -------------------------------------------------------
# Login
# -------------------------------------------------------
@app.route('/', methods=['GET', 'POST'])
@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))

    error = None

    if request.method == 'POST':
        email    = request.form.get('email', '').strip()
        password = request.form.get('password', '')

        if not email or not password:
            error = 'Email and password are required.'
        else:
            db = get_db()
            cursor = db.cursor()
            cursor.execute("SELECT * FROM USER WHERE Email = %s", (email,))
            user = cursor.fetchone()
            cursor.close()

            if user and user.get('PasswordHash') and check_password_hash(user['PasswordHash'], password):
                session.clear()
                session['user_id']   = user['UserID']
                session['user_name'] = user['Name']
                return redirect(url_for('dashboard'))
            else:
                error = 'Invalid email or password.'

    return render_template('login.html', error=error)

# -------------------------------------------------------
# Logout
# -------------------------------------------------------
@app.route('/logout', methods=['POST'])
def logout():
    session.clear()
    return redirect(url_for('login'))

# -------------------------------------------------------
# Dashboard
# -------------------------------------------------------
@app.route('/dashboard')
@login_required
def dashboard():
    db = get_db()
    cursor = db.cursor()

    user_id = session['user_id']

    cursor.execute("SELECT * FROM USER WHERE UserID = %s", (user_id,))
    user = cursor.fetchone()

    cursor.execute("""
        SELECT t.TripID, t.TripName, t.StartDate, t.EndDate, t.Status,
               d.City, c.CountryName,
               COUNT(b.BookingID) as BookingCount
        FROM TRIP t
        JOIN DESTINATION d ON t.DestinationID = d.DestinationID
        JOIN COUNTRY c ON d.CountryCode = c.CountryCode
        LEFT JOIN BOOKING b ON b.TripID = t.TripID
        WHERE t.UserID = %s
        GROUP BY t.TripID, t.TripName, t.StartDate, t.EndDate, t.Status, d.City, c.CountryName
        ORDER BY t.StartDate ASC
    """, (user_id,))
    trips = cursor.fetchall()

    cursor.close()

    return render_template('dashboard.html',
                           user=user,
                           trips=trips,
                           today=date.today().strftime('%d-%b-%Y').upper())

# -------------------------------------------------------
# Trip Creation Form
# -------------------------------------------------------
@app.route('/create-trip', methods=['GET', 'POST'])
@login_required
def create_trip():
    db = get_db()
    cursor = db.cursor()
    errors = []
    user_id = session['user_id']

    cursor.execute("""
        SELECT d.DestinationID, d.City, c.CountryName
        FROM DESTINATION d
        JOIN COUNTRY c ON d.CountryCode = c.CountryCode
        ORDER BY c.CountryName, d.City
    """)
    destinations = cursor.fetchall()

    if request.method == 'POST':
        trip_name  = request.form.get('trip_name', '').strip()
        dest_id    = request.form.get('destination_id', '').strip()
        start_date = request.form.get('start_date', '').strip()
        end_date   = request.form.get('end_date', '').strip()
        status     = request.form.get('status', 'Planning').strip()

        if not trip_name:  errors.append('Trip Name is required.')
        if not dest_id:    errors.append('Destination is required.')
        if not start_date: errors.append('Start Date is required.')
        if not end_date:   errors.append('End Date is required.')
        if start_date and end_date:
            parse_date_range(start_date, end_date, 'Travel dates', errors)
        if trip_name and len(trip_name) > 100:
            errors.append('Trip Name must be at most 100 characters.')
        if dest_id not in {str(d['DestinationID']) for d in destinations}:
            errors.append('Select a valid destination.')
        if status not in ['Planning', 'Confirmed', 'Completed']:
            errors.append('Invalid status value.')

        if not errors:
            cursor.execute("""
                INSERT INTO TRIP (TripName, StartDate, EndDate, Status, UserID, DestinationID)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (trip_name, start_date, end_date, status, user_id, dest_id))
            db.commit()
            trip_id = cursor.lastrowid
            cursor.close()
            return redirect(url_for('booking', trip_id=trip_id))

    cursor.close()
    return render_template('trip_form.html',
                           destinations=destinations,
                           errors=errors,
                           today=date.today().strftime('%d-%b-%Y').upper())

# -------------------------------------------------------
# Booking Form
# -------------------------------------------------------
@app.route('/booking', methods=['GET', 'POST'])
@login_required
def booking():
    db = get_db()
    cursor = db.cursor()
    errors = []
    user_id = session['user_id']

    trip_id = request.form.get('trip_id') if request.method == 'POST' else request.args.get('trip_id')

    cursor.execute("""
        SELECT t.TripID, t.TripName, d.City, c.CountryName
        FROM TRIP t
        JOIN DESTINATION d ON t.DestinationID = d.DestinationID
        JOIN COUNTRY c ON d.CountryCode = c.CountryCode
        WHERE t.UserID = %s
        ORDER BY t.StartDate DESC
    """, (user_id,))
    trips = cursor.fetchall()

    selected_trip = None
    if trip_id:
        cursor.execute("""
            SELECT t.TripID, t.TripName, d.City, c.CountryName
            FROM TRIP t
            JOIN DESTINATION d ON t.DestinationID = d.DestinationID
            JOIN COUNTRY c ON d.CountryCode = c.CountryCode
            WHERE t.TripID = %s AND t.UserID = %s
        """, (trip_id, user_id))
        selected_trip = cursor.fetchone()
        if not selected_trip:
            abort(404)

    if request.method == 'POST':
        trip_id      = request.form.get('trip_id', '').strip()
        booking_type = request.form.get('booking_type', '').strip()
        booking_date = date.today().isoformat()

        if not trip_id or not selected_trip:
            errors.append('Select one of your trips.')
        if booking_type not in ['Flight', 'Hotel']:
            errors.append('Booking Type must be Flight or Hotel.')

        if booking_type == 'Flight':
            airline  = request.form.get('airline', '').strip()
            dep_city = request.form.get('departure_city', '').strip()
            arr_city = request.form.get('arrival_city', '').strip()
            dep_time = request.form.get('departure_time', '').strip()
            arr_time = request.form.get('arrival_time', '').strip()
            price    = request.form.get('price', '').strip()

            if not airline:  errors.append('Airline is required.')
            if not dep_city: errors.append('Departure City is required.')
            if not arr_city: errors.append('Arrival City is required.')
            if not dep_time: errors.append('Departure Time is required.')
            if not arr_time: errors.append('Arrival Time is required.')
            if dep_city and arr_city and dep_city.lower() == arr_city.lower():
                errors.append('Departure and Arrival cities cannot be the same.')
            price = parse_price(price, 'Price', errors)
            if dep_time and arr_time:
                parse_date_range(dep_time, arr_time, 'Flight times', errors, True)
            for label, value in [('Airline', airline), ('Departure city', dep_city), ('Arrival city', arr_city)]:
                if len(value) > 100:
                    errors.append(f'{label} must be at most 100 characters.')

            if not errors:
                cursor.execute("""
                    INSERT INTO BOOKING (BookingType, BookingDate, Status, TotalPrice, TripID)
                    VALUES (%s, %s, %s, %s, %s)
                """, (booking_type, booking_date, 'Confirmed', price, trip_id))
                booking_id = cursor.lastrowid

                cursor.execute("""
                    INSERT INTO FLIGHT (Airline, DepartureCity, ArrivalCity, DepartureTime, ArrivalTime, Price, BookingID)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (airline, dep_city, arr_city, dep_time, arr_time, price, booking_id))
                db.commit()
                cursor.close()
                return redirect(url_for('confirmation', booking_id=booking_id))

        elif booking_type == 'Hotel':
            hotel_name  = request.form.get('hotel_name', '').strip()
            location    = request.form.get('location', '').strip()
            checkin     = request.form.get('checkin_date', '').strip()
            checkout    = request.form.get('checkout_date', '').strip()
            price_night = request.form.get('price_per_night', '').strip()

            if not hotel_name: errors.append('Hotel Name is required.')
            if not location:   errors.append('Location is required.')
            if not checkin:    errors.append('Check-in Date is required.')
            if not checkout:   errors.append('Check-out Date is required.')
            ci, co = parse_date_range(checkin, checkout, 'Hotel dates', errors)
            price_night = parse_price(price_night, 'Price per night', errors)
            for label, value in [('Hotel name', hotel_name), ('Location', location)]:
                if len(value) > 100:
                    errors.append(f'{label} must be at most 100 characters.')
            if ci and co and price_night is not None and price_night * (co - ci).days > Decimal('99999999.99'):
                errors.append('Hotel total exceeds the supported price range.')

            if not errors:
                nights = (co - ci).days
                total  = price_night * nights

                cursor.execute("""
                    INSERT INTO BOOKING (BookingType, BookingDate, Status, TotalPrice, TripID)
                    VALUES (%s, %s, %s, %s, %s)
                """, (booking_type, booking_date, 'Confirmed', total, trip_id))
                booking_id = cursor.lastrowid

                cursor.execute("""
                    INSERT INTO HOTEL (HotelName, Location, CheckInDate, CheckOutDate, PricePerNight, BookingID)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (hotel_name, location, checkin, checkout, price_night, booking_id))
                db.commit()
                cursor.close()
                return redirect(url_for('confirmation', booking_id=booking_id))

    cursor.close()
    return render_template('booking_form.html',
                           trips=trips,
                           selected_trip=selected_trip,
                           trip_id=trip_id,
                           errors=errors,
                           today=date.today().strftime('%d-%b-%Y').upper())

# -------------------------------------------------------
# Booking Confirmation Report
# -------------------------------------------------------
@app.route('/confirmation/<int:booking_id>')
@login_required
def confirmation(booking_id):
    db = get_db()
    cursor = db.cursor()

    cursor.execute("""
        SELECT
            b.BookingID, b.BookingType, b.BookingDate, b.Status, b.TotalPrice,
            t.TripID, t.TripName, t.StartDate, t.EndDate,
            d.City, c.CountryName, c.CountryCode,
            u.UserID, u.Name, u.Nationality
        FROM BOOKING b
        JOIN TRIP t        ON b.TripID        = t.TripID
        JOIN DESTINATION d ON t.DestinationID = d.DestinationID
        JOIN COUNTRY c     ON d.CountryCode   = c.CountryCode
        JOIN USER u        ON t.UserID        = u.UserID
        WHERE b.BookingID = %s AND t.UserID = %s
    """, (booking_id, session['user_id']))
    booking = cursor.fetchone()

    if not booking:
        cursor.close()
        return "Booking not found.", 404

    flight = None
    hotel  = None

    if booking['BookingType'] == 'Flight':
        cursor.execute("SELECT * FROM FLIGHT WHERE BookingID = %s", (booking_id,))
        flight = cursor.fetchone()
    elif booking['BookingType'] == 'Hotel':
        cursor.execute("SELECT * FROM HOTEL WHERE BookingID = %s", (booking_id,))
        hotel = cursor.fetchone()

    cursor.execute("""
        SELECT VisaType, Requirements, ProcessingTime
        FROM VISAREQUIREMENT
        WHERE CountryCode = %s
    """, (booking['CountryCode'],))
    visa_requirements = cursor.fetchall()

    cursor.close()

    return render_template('confirmation.html',
                           booking=booking,
                           flight=flight,
                           hotel=hotel,
                           visa_requirements=visa_requirements,
                           today=date.today().strftime('%d-%b-%Y').upper())

@app.get('/visa-info/<int:destination_id>')
@login_required
def visa_info(destination_id):
    cursor = get_db().cursor()
    cursor.execute("""SELECT v.VisaType, v.Requirements, v.ProcessingTime
                      FROM VISAREQUIREMENT v JOIN DESTINATION d
                      ON d.CountryCode = v.CountryCode WHERE d.DestinationID = %s""",
                   (destination_id,))
    rows = cursor.fetchall()
    cursor.close()
    return jsonify(rows)

# -------------------------------------------------------
# Run
# -------------------------------------------------------
if __name__ == '__main__':
    app.run(debug=os.getenv('FLASK_DEBUG', 'false').lower() == 'true',
            host='127.0.0.1', port=int(os.getenv('PORT', '5000')))
