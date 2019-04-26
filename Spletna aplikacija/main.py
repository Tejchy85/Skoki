#!/usr/bin/python
# -*- encoding: utf-8 -*-

# uvozimo bottle.py
from bottle import *

# uvozimo ustrezne podatke za povezavo
import auth_public as auth

# uvozimo psycopg2
import psycopg2, psycopg2.extensions, psycopg2.extras
psycopg2.extensions.register_type(psycopg2.extensions.UNICODE) # se znebimo problemov s šumniki

# odkomentiraj, če želiš sporočila o napakah
# debug(True)

@get('/static/<filename:path>')
def static(filename):
    return static_file(filename, root='static')

@get('/')  #začetna stran, seznam tekma, tekmovalci, drzaca, zanimivosti, dodaj tekmo
def index():
    return template('zacetna_stran.html')

@get('/tekme/:x/') #x bo v tem primeru sezona, recimo 2018
def tekme(x):
    cur.execute("SELECT * FROM tekma WHERE datum > %s ORDER BY znesek, id", [int(x)]) #tu je še treba ta select pravilno zapisat
    return template('transakcije.html', x=x, tekma=cur)

@get('/dodaj_transakcijo')
def dodaj_transakcijo():
    return template('dodaj_transakcijo.html', znesek='', racun='', opis='', napaka=None)

@post('/dodaj_transakcijo')
def dodaj_transakcijo_post():
    znesek = request.forms.znesek
    racun = request.forms.racun
    opis = request.forms.opis
    try:
        cur.execute("INSERT INTO transakcija (znesek, racun, opis) VALUES (%s, %s, %s)",
                    (znesek, racun, opis))
        conn.commit()
    except Exception as ex:
        return template('dodaj_transakcijo.html', znesek=znesek, racun=racun, opis=opis,
                        napaka = 'Zgodila se je napaka: %s' % ex)
    redirect("/")

######################################################################
# Glavni program

# priklopimo se na bazo
conn = psycopg2.connect(database=auth.db, host=auth.host, user=auth.user, password=auth.password)
conn.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT) # onemogočimo transakcije
cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor) 

# poženemo strežnik na portu 8080, glej http://localhost:8000/
run(host='localhost', port=8000)