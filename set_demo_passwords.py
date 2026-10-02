"""Set hashed passwords for the three fictional demo accounts."""
from getpass import getpass
from app import app, get_db
from werkzeug.security import generate_password_hash

if __name__ == '__main__':
    password = getpass('Choose a demo login password (at least 12 characters): ')
    if len(password) < 12:
        raise SystemExit('Use at least 12 characters.')
    with app.app_context():
        db = get_db()
        with db.cursor() as cursor:
            for email in ('alex@example.com', 'jordan@example.com', 'sam@example.com'):
                cursor.execute('UPDATE USER SET PasswordHash = %s WHERE Email = %s',
                               (generate_password_hash(password), email))
        db.commit()
    print('Demo passwords updated. Sign in as alex@example.com using your chosen password.')
