#!/usr/bin/python
# -*- encoding: utf-8 -*-

# uvozimo bottle.py
from bottle import *

# uvozimo ustrezne podatke za povezavo
import auth_public as auth

#uvozimo paket, za datume
import datetime

# uvozimo psycopg2
import psycopg2, psycopg2.extensions, psycopg2.extras
psycopg2.extensions.register_type(psycopg2.extensions.UNICODE) # se znebimo problemov s šumniki

import hashlib # računanje MD5 kriptografski hash za gesla

# odkomentiraj, če želiš sporočila o napakah
debug(True)

secret = "to skrivnost je zelo tezko uganiti 1094107c907cw982982c42"

######################################################################
# Pomožne funkcije

def password_md5(s):
    """Vrni MD5 hash danega UTF-8 niza. Gesla vedno spravimo v bazo
       kodirana s to funkcijo."""
    h = hashlib.md5()
    h.update(s.encode('utf-8'))
    return h.hexdigest()

######################################################################

@get('/static/<filename:path>')
def static(filename):
    return static_file(filename, root='static')

@get('/')
def index():
    return template('zacetna_stran.html')

@get('/Login')
def login():
    return template('Login.html', napaka=None)

@post('/Login')
def login_post():
    print('login in')
    """Obdelaj izpolnjeno formo za prijavo"""
    # Uporabniško ime, ki ga je uporabnik vpisal v formo
    username = request.forms.username
    # Izračunamo MD5 has gesla, ki ga bomo spravili
    password = password_md5(request.forms.password)
    # Preverimo, ali se je uporabnik pravilno prijavil
    print(username)
    print(password)
    cur.execute("SELECT * FROM uporabnik WHERE username=%s AND password=%s", [username, password])
    if cur.fetchone() is None:
        print('ne obstaja')
        # Username in geslo se ne ujemata
        return template("login.html",
                               napaka="Uporabnik ne obstaja",
                               username=username)
    else:
        # Vse je v redu, nastavimo cookie in preusmerimo na glavno stran
        response.set_cookie('username', username, path='/', secret=secret)
        redirect("/")

@get('/Register')
def register():
    return template('Register.html')

@post("/Register")
def register_post():
    print('trying to register')
    """Registriraj novega uporabnika."""
    username = request.forms.username
    ime = request.forms.ime
    password1 = request.forms.password1
    password2 = request.forms.password2
    # Ali uporabnik že obstaja?
    cur.execute("SELECT 1 FROM uporabnik WHERE username=?", [username])
    if cur.fetchone():
        # Uporabnik že obstaja
        return template("Register.html",
                               username=username,
                               napaka='To uporabniško ime je že zavzeto')
    elif not password1 == password2:
        # Geslo se ne ujemata
        return template("Register.html",
                               username=username,
                               napaka='Gesli se ne ujemata')
    else:
        # Vse je v redu, vstavi novega uporabnika v bazo
        password = password_md5(password1)
        cur.execute("INSERT INTO uporabnik (username, password) VALUES (?, ?)",
                  (username, password))
        # Daj uporabniku cookie
        response.set_cookie('username', username, path='/', secret=secret)
        redirect("/")

@get('/Video')
def video():
    return template('Video.html')

@get('/tekmovalci')
def tekmovalci():
    cur.execute("SELECT * FROM tekmovalec ORDER BY priimek, ime")
    return template('tekmovalci.html', tekmovalci=cur)

@get('/sezone')
def sezone():
    return template('sezone.html')

@get('/tekme/:x/')
def tekme(x):
    cur.execute("SELECT id,kraj,datum,drzava,tip_tekme FROM tekma WHERE datum BETWEEN %s AND %s",
            [datetime.date(int(x)-1, 11, 1), datetime.date(int(x), 3, 31)])
    return template('tekme_sezona.html', x=x, tekme=cur)

@get('/dodaj_tekmovalca')
def dodaj_tekmovalca():
    return template('dodaj_tekmovalca.html', fis_code='', ime='', priimek='', drzava='', rojstvo='', klub='', smucke='', status='', napaka=None)

@post('/dodaj_tekmovalca')
def dodaj_tekmovalca_post():
    fis_code = request.forms.fis_code
    ime = request.forms.ime
    priimek = request.forms.priimek
    drzava = request.forms.drzava
    rojstvo = request.forms.rojstvo
    klub = request.forms.klub
    smucke = request.forms.smucke
    status = request.forms.status
    try:
        cur.execute("INSERT INTO tekmovalec (fis_code, ime, priimek, drzava, rojstvo, klub, smucke, status) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                    (fis_code, ime, priimek, drzava, rojstvo, klub, smucke, status))
        conn.commit()
    except Exception as ex:
        return template('dodaj_tekmovalca.html', fis_code=fis_code, ime=ime, priimek=priimek, drzava=drzava, rojstvo=rojstvo, klub=klub, smucke=smucke, status=status,
                        napaka = 'Zgodila se je napaka: %s' % ex)
    redirect("/")

######################################################################
# Glavni program

# priklopimo se na bazo
conn = psycopg2.connect(database=auth.db, host=auth.host, user=auth.user, password=auth.password)
conn.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT) # onemogočimo transakcije
cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor) 

# poženemo strežnik na portu 8080, glej http://localhost:8000/
run(host='localhost', port=8000, reloader=True)
