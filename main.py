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
adminGeslo = "1111"

######################################################################
# Pomožne funkcije

def password_md5(s):
    """Vrni MD5 hash danega UTF-8 niza. Gesla vedno spravimo v bazo
       kodirana s to funkcijo."""
    h = hashlib.md5()
    h.update(s.encode('utf-8'))
    return h.hexdigest()

def get_user():
    """Poglej cookie in ugotovi, kdo je prijavljeni uporabnik,
       vrni njegov username in ime. Če ni prijavljen, presumeri
       na stran za prijavo ali vrni None (advisno od auto_login).
    """
    # Dobimo username iz piškotka
    username = request.get_cookie('username', secret=secret)
    print(username)
    # Preverimo, ali ta uporabnik obstaja
    if username is not None:
        cur.execute("SELECT username FROM uporabnik WHERE username=%s", [username])
        r = cur.fetchone()
        if r is not None:
            # uporabnik obstaja, vrnemo njegove podatke
            return username
    # Če pridemo do sem, uporabnik ni prijavljen, naredimo redirect
    else:
        return None

######################################################################

@get('/static/<filename:path>')
def static(filename):
    return static_file(filename, root='static')

@get('/')
def index():
    return template('zacetna_stran.html', username = get_user())

@get('/Login')
def login():
    return template('Login.html', napaka=None)

@post('/Login')
def login_post():
    """Obdelaj izpolnjeno formo za prijavo"""
    # Uporabniško ime, ki ga je uporabnik vpisal v formo
    username = request.forms.username
    # Izračunamo MD5 has gesla, ki ga bomo spravili
    password = password_md5(request.forms.password)
    # Preverimo, ali se je uporabnik pravilno prijavil
    cur.execute("SELECT * FROM uporabnik WHERE username=%s AND password=%s", [username, password])
    if cur.fetchone() is None:
        # Username in geslo se ne ujemata
        return template("Login.html",
                               napaka="Uporabnik ne obstaja",
                               username=username)
    else:
        # Vse je v redu, nastavimo cookie in preusmerimo na glavno stran
        response.set_cookie('username', username, path='/', secret=secret)
        redirect("/")

@get("/Logout")
def logout():
    """Pobriši cookie in preusmeri na login."""
    response.delete_cookie('username')
    redirect('/')

@get('/Register')
def register():
    return template('Register.html', username=None, napaka=None)

@post("/Register")
def register_post():
    print('trying to register')
    """Registriraj novega uporabnika."""
    username = request.forms.username
    password1 = request.forms.password1
    password2 = request.forms.password2
    adminPassword = request.forms.adminPassword
    adminCheck = request.forms.adminCheckbox
    # Ali uporabnik že obstaja?
    cur.execute("SELECT * FROM uporabnik WHERE username=%s", [username])
    if cur.fetchone():
        print('ime že zasedeno')
        # Uporabnik že obstaja
        return template("Register.html",
                               username=username,
                               napaka='To uporabniško ime je že zavzeto')
    elif not password1 == password2:
        print('gesli se ne ujemata')
        # Geslo se ne ujemata
        return template("Register.html",
                               username=username,
                               napaka='Gesli se ne ujemata')
    else:
        # Vse je v redu, vstavi novega uporabnika v bazo
        print('ustvarjamo novega uporabnika')

        if adminCheck == "kot admin":
            if adminPassword == adminGeslo:
                print('dodaj admina')

                password = password_md5(password1)
                cur.execute("INSERT INTO uporabnik (username, password, isadmin) VALUES (%s, %s, %s)",
                            (username, password, True))
                # Daj uporabniku cookie
                response.set_cookie('username', username, path='/', secret=secret)
                redirect("/")
            else:
                return template("Register.html",
                                username=username,
                                napaka='Admin geslo ni pravilno')
        else:
            print('ustvarimo navadnega uporabnika')

            password = password_md5(password1)
            cur.execute("INSERT INTO uporabnik (username, password, isadmin) VALUES (%s, %s, %s)",
                        (username, password, False))
            # Daj uporabniku cookie
            response.set_cookie('username', username, path='/', secret=secret)
            redirect("/")


@get('/Video')
def video():
    return template('Video.html')

@get('/tekmovalci')
def tekmovalci():
    username = get_user()
    cur.execute("SELECT * FROM tekmovalec ORDER BY priimek, ime")
    return template('tekmovalci.html', tekmovalci=cur, napaka=None, username = username)

@get('/sezone')
def sezone():
    username = get_user()
    return template('sezone.html', username = username)

@get('/tekme/:x/')
def tekme(x):
    username = get_user()
    cur.execute("SELECT id,kraj,datum,drzava,tip_tekme FROM tekma WHERE datum BETWEEN %s AND %s ORDER BY datum",
            [datetime.date(int(x)-1, 11, 1), datetime.date(int(x), 3, 31)])
    return template('tekme_sezona.html', x=x, tekme=cur, username = username)

@get('/tekma/:x/')
def tekma(x):
    username = get_user()
    cur.execute("SELECT r.ranki, r.startna_stevilka, r.fis_code, t.ime, t.priimek, r.drzava, r.skoki, r.tocke, r.serija, r.mesto_v_ekipi FROM rezultat r LEFT JOIN tekmovalec t ON r.fis_code = t.fis_code WHERE id=%s ORDER BY ranki ASC",[int(x)])
    return template('tekma.html',x = x, tekma = cur, username = username)

@get('/zadnja_tekma')
def zadnja_tekma():
    username = get_user()
    cur.execute("WITH zadnja AS (SELECT id FROM tekma WHERE datum <= date('now') ORDER BY datum DESC LIMIT 1) SELECT r.ranki, r.startna_stevilka, r.fis_code, t.ime, t.priimek, r.drzava, r.skoki, r.tocke, r.serija, r.mesto_v_ekipi FROM rezultat r LEFT JOIN tekmovalec t ON r.fis_code = t.fis_code WHERE r.id IN (SELECT id FROM zadnja) ORDER BY ranki ASC")
    return template('zadnja_tekma.html', tekma=cur, username = username)

@get('/dodaj_tekmovalca')
def dodaj_tekmovalca():
    username = get_user()
    cur.execute("SELECT isadmin FROM uporabnik WHERE username=%s", [username])
    if username is None:
        cur.execute("SELECT * FROM tekmovalec ORDER BY priimek, ime")
        return template("tekmovalci.html", tekmovalci=cur, napaka="Niste prijavljeni", username=username)
    elif not cur.fetchone()[0]:
        # Ni admin
        cur.execute("SELECT * FROM tekmovalec ORDER BY priimek, ime")
        return template("tekmovalci.html", tekmovalci=cur, napaka="Uporabnik ni admin", username=username)
    else:
        return template('dodaj_tekmovalca.html', fis_code='', ime='', priimek='', drzava='', rojstvo='', klub='',
                        smucke='', status='', napaka=None, username=username)

@post('/dodaj_tekmovalca')
def dodaj_tekmovalca_post():
    username = get_user()
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
                        napaka = 'Zgodila se je napaka: %s' % ex, username = username)
    redirect("/")

@get('/dodaj_tekmo')
def dodaj_tekmo():
    username = get_user()
    return template('dodaj_tekmo.html', id='', kraj='', drzava='', datum='', tip_tekme='', napaka=None, username = username)

@post('/dodaj_tekmo')
def dodaj_tekmo_post():
    username = get_user()
    id = request.forms.id
    kraj = request.forms.kraj
    drzava = request.forms.drzava
    datum = request.forms.datum
    tip_tekme = request.forms.tip_tekme
    try:
        cur.execute("INSERT INTO tekma (id, kraj, datum, drzava, tip_tekme) VALUES (%s, %s, %s, %s, %s)",
                    (id, kraj, datum, drzava, tip_tekme))
        conn.commit()
    except Exception as ex:
        return template('dodaj_tekmo.html', id=id, kraj=kraj, datum=datum, drzava=drzava, tip_tekme=tip_tekme,
                        napaka = 'Zgodila se je napaka: %s' % ex, username = username)
    redirect("/")

######################################################################
# Glavni program

# priklopimo se na bazo
conn = psycopg2.connect(database=auth.db, host=auth.host, user=auth.user, password=auth.password)
conn.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT) # onemogočimo transakcije
cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor) 

# poženemo strežnik na portu 8080, glej http://localhost:8000/
run(host='localhost', port=8000, reloader=True)
