from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'my-super-secret-key-for-mx-fantasy-league-2025')

# Simple in-memory storage
users = {
    'test': generate_password_hash('password'),
    'test2': generate_password_hash('password')
}

@app.route('/')
def index():
    if 'username' not in session:
        return redirect(url_for('login'))
    
    return render_template('index.html', username=session['username'])

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'username' in session:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        username = request.form.get('username', '')
        password = request.form.get('password', '')
        
        if username in users and check_password_hash(users[username], password):
            session['username'] = username
            return redirect(url_for('index'))
        
        flash('Felaktigt användarnamn eller lösenord', 'error')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/register')
def register():
    return f"""
    <h1>Registrering</h1>
    <p>För att registrera dig, kontakta administratören.</p>
    <p><a href="/login">Tillbaka till inloggning</a></p>
    """

@app.route('/admin')
def admin():
    if 'username' not in session or session['username'] != 'test':
        flash('Du har inte behörighet att komma åt denna sida', 'error')
        return redirect(url_for('index'))
    
    return f"""
    <h1>Admin Panel</h1>
    <p>Välkommen, {session['username']}!</p>
    <p>Detta är admin-sidan.</p>
    <p><a href="/">Tillbaka till huvudsidan</a></p>
    <p><a href="/logout">Logga ut</a></p>
    """

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
