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

def is_admin(username):
    if username is not None:
        cur.execute("SELECT isadmin FROM uporabnik WHERE username=%s", [username])
        return cur.fetchone()[0]
    else:
        return False

def sezone():
    cur.execute("SELECT datum FROM tekma ORDER BY datum LIMIT 1")
    prva = cur.fetchone()[0]
    prva = prva.year
    cur.execute("SELECT datum FROM tekma ORDER BY datum DESC LIMIT 1")
    zadnja = cur.fetchone()[0]
    if zadnja.month in {11, 12}:
        zadnja = int(zadnja.year) + 1
    else:
        zadnja = int(zadnja.year)
    sezone = []
    for i in range(int(prva)+1,zadnja+1):
        sezone.append(i)
    return sezone

def najljubsi(username):
    if username==None:
        return []
    cur.execute("SELECT najljubsi_tekmovalci FROM uporabnik WHERE username = %s", [username])
    najljubsi = cur.fetchone()[0]
    if najljubsi == None:
        return []
    else:
        najljubsi = najljubsi.split(',')
        najljubsi = najljubsi[:-1]
        return list(map(int, najljubsi))


# Pomožne funkcije
######################################################################

@get('/static/<filename:path>')
def static(filename):
    return static_file(filename, root='static')

@get('/')
def index():
    username = get_user()
    admin = is_admin(username)
    sezone_seznam = sezone()
    sezona = sezone_seznam[-1]
    cur.execute("WITH umesna3 AS (WITH umesna2 AS (WITH umesna AS (SELECT id, ranki, fis_code FROM rezultat JOIN tekma USING (id) "
                "WHERE datum BETWEEN %s AND %s AND tip_tekme = 'posamicna' GROUP BY id, ranki, fis_code ORDER BY id,ranki)"
                "SELECT tocke,fis_code, count(*) AS stevilo FROM umesna JOIN tocke USING(ranki) GROUP BY tocke,fis_code)"
                "SELECT fis_code, sum(stevilo*tocke) AS sestevek FROM umesna2 GROUP BY fis_code)"
                "SELECT fis_code, ime, priimek, sestevek FROM umesna3 JOIN tekmovalec USING(fis_code) ORDER BY sestevek DESC",
                [datetime.date(int(sezona) - 1, 11, 1), datetime.date(int(sezona), 3, 31)])
    skupni_sestevek = cur.fetchall()
    return template('zacetna_stran.html', sezone=sezone_seznam, skupni_sestevek=skupni_sestevek, napakaO=None, username=username, admin=admin)

@post('/')
def postani_admin():
    username = get_user()
    adminPassword = request.forms.adminPassword
    password = request.forms.password

    #za začetno stran potrebuješ skupni seštevek:
    sezone_seznam = sezone()
    sezona = sezone_seznam[-1]
    cur.execute(
        "WITH umesna3 AS (WITH umesna2 AS (WITH umesna AS (SELECT id, ranki, fis_code FROM rezultat JOIN tekma USING (id) "
        "WHERE datum BETWEEN %s AND %s AND tip_tekme = 'posamicna' GROUP BY id, ranki, fis_code ORDER BY id,ranki)"
        "SELECT tocke,fis_code, count(*) AS stevilo FROM umesna JOIN tocke USING(ranki) GROUP BY tocke,fis_code)"
        "SELECT fis_code, sum(stevilo*tocke) AS sestevek FROM umesna2 GROUP BY fis_code)"
        "SELECT fis_code, ime, priimek, sestevek FROM umesna3 JOIN tekmovalec USING(fis_code) ORDER BY sestevek DESC",
        [datetime.date(int(sezona) - 1, 11, 1), datetime.date(int(sezona), 3, 31)])
    skupni_sestevek = cur.fetchall()

    if password == "":
        if adminPassword == adminGeslo:
            cur.execute("UPDATE uporabnik SET isadmin = True WHERE username=%s", [username])
            admin = is_admin(username)
            return template('zacetna_stran.html', skupni_sestevek=skupni_sestevek, sezone=sezone_seznam, napakaO=None, username=username, admin=admin)
        else:
            admin = is_admin(username)
            return template('zacetna_stran.html', skupni_sestevek=skupni_sestevek, sezone=sezone_seznam, napakaO="Vnesili ste napačno admin geslo.", username=username, admin=admin)
    else:
        cur.execute("SELECT password FROM uporabnik WHERE username=%s", [username])
        if cur.fetchone()[0] == password_md5(password):
            cur.execute("DELETE FROM uporabnik WHERE username=%s", [username])
            response.delete_cookie('username')
            return template('zacetna_stran.html', skupni_sestevek=skupni_sestevek, sezone=sezone_seznam, napakaO=None, username=None, admin=None)
        else:
            admin = is_admin(username)
            return template('zacetna_stran.html', skupni_sestevek=skupni_sestevek, sezone=sezone_seznam, napakaO="Vnesili ste napačno geslo.", username=username,
                            admin=admin)


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
                               napaka='To uporabniško ime je že zasedeno.')
    elif not password1 == password2:
        print('gesli se ne ujemata')
        # Geslo se ne ujemata
        return template("Register.html",
                               username=username,
                               napaka='Gesli se ne ujemata.')
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
                                napaka='Admin geslo ni pravilno.')
        else:
            print('ustvarimo navadnega uporabnika')

            password = password_md5(password1)
            cur.execute("INSERT INTO uporabnik (username, password, isadmin) VALUES (%s, %s, %s)",
                        (username, password, False))
            # Daj uporabniku cookie
            response.set_cookie('username', username, path='/', secret=secret)
            redirect("/")

@get('/tekmovalci')
def tekmovalci_get():
    username = get_user()
    admin = is_admin(username)
    cur.execute("SELECT * FROM tekmovalec ORDER BY priimek ASC")
    tekmovalci = cur.fetchall()
    moznosti = ['FIS code - padajoče', 'FIS code - naraščajoče', 'Status - od A do Ž', 'Status - od Ž do A',
                'Ime - od A do Ž', 'Ime - od Ž do A', 'Priimek - od A do Ž', 'Priimek - od Ž do A',
                'Država - od A do Ž', 'Država - od Ž do A', 'Rojstvo - starejši prej', 'Rojstvo - mlajši prej',
                'Klub - od A do Ž', 'Klub - od Ž do A', 'Smučke - od A do Ž', 'Smučke - od Ž do A']
    return template('tekmovalci.html', tekmovalci=tekmovalci, razvrscanje='Priimek - od A do Ž', moznosti=moznosti, sezone=sezone(), napakaO=None, napaka=None, username=username, admin=admin)

@post('/tekmovalci')
def tekmovalci_post():
    if (request.forms.adminPassword != "") or (request.forms.password != ""):
        postani_admin()

    search = request.forms.search.lower().replace('č', 'c').replace('š', 's').replace('ž', 'z')
    username = get_user()
    admin = is_admin(username)
    raz = request.forms.razvrscanje

    moznosti = ['FIS code - padajoče', 'FIS code - naraščajoče', 'Status - od A do Ž', 'Status - od Ž do A',
                'Ime - od A do Ž', 'Ime - od Ž do A', 'Priimek - od A do Ž', 'Priimek - od Ž do A',
                'Država - od A do Ž', 'Država - od Ž do A', 'Rojstvo - starejši prej', 'Rojstvo - mlajši prej',
                'Klub - od A do Ž', 'Klub - od Ž do A', 'Smučke - od A do Ž', 'Smučke - od Ž do A']

    sezR = raz.split('-')
    asc = ['naraščajoče', 'od A do Ž', 'starejši prej']

    if sezR == ['']:
        y = 'priimek ASC'
    elif sezR[1].strip() in asc:
        y = sezR[0].strip().replace(' ', '_').lower().replace('č', 'c').replace('š', 's').replace('ž', 'z') + ' ASC'
    else:
        y = sezR[0].strip().replace(' ', '_').lower().replace('č', 'c').replace('š', 's').replace('ž', 'z') + ' DESC'

    if search == "":
        cur.execute("SELECT * FROM tekmovalec ORDER BY " + y.replace('-', ' '))
        tekmovalci = cur.fetchall()
        return template('tekmovalci.html', tekmovalci=tekmovalci, razvrscanje=raz, moznosti=moznosti, sezone=sezone(), napakaO=None, napaka=None, username=username,
                        admin=admin)
    napaka = None
    head_list = ['status', 'ime', 'priimek', 'drzava', 'rojstvo', 'klub', 'smucke']
    sez = search.split(':')
    if len(sez) > 1:
        search = sez[1].strip()
        if sez[0].replace(' ', '') == 'fiscode':
            cur.execute("SELECT * FROM tekmovalec WHERE CAST(fis_code AS varchar(10)) LIKE %s" + "ORDER BY " + y.replace('-', ' '), ['%' + search + '%'])
        elif sez[0].strip() in head_list:
            cur.execute("SELECT * FROM tekmovalec WHERE LOWER(" + sez[0] + ") LIKE %s" + "ORDER BY " + y.replace('-', ' '), ['%' + search + '%'])
        else:
            napaka = "Neveljavno iskanje."
    else:
        cur.execute("SELECT * FROM tekmovalec WHERE CAST(fis_code AS varchar(10)) LIKE %s"
                    "OR LOWER(status) LIKE %s"
                    "OR LOWER(ime) LIKE %s"
                    "OR LOWER(priimek) LIKE %s"
                    "OR LOWER(drzava) LIKE %s"
                    "OR LOWER(rojstvo) LIKE %s"
                    "OR LOWER(klub) LIKE %s"
                    "OR LOWER(smucke) LIKE %s" + "ORDER BY " + y.replace('-', ' '),
                    8*['%' + search + '%'])
    tekmovalci = cur.fetchall()
    return template('tekmovalci.html', tekmovalci=tekmovalci, razvrscanje=raz, moznosti=moznosti, sezone=sezone(), napakaO=None, napaka=napaka, username=username, admin=admin)


@get('/tekmovalec/:x/')
def tekmovalec(x):
    username = get_user()
    admin = is_admin(username)
    cur.execute("SELECT * FROM tekmovalec WHERE fis_code = %s", [int(x)])
    tekmovalec = cur.fetchall()
    cur.execute("SELECT t.datum, t.kraj, t.drzava, t.tip_tekme, r.ranki FROM rezultat r JOIN tekmovalec ON r.fis_code = tekmovalec.fis_code JOIN tekma t ON r.id = t.id WHERE r.fis_code = %s GROUP BY t.id, r.fis_code, r.ranki ORDER BY t.datum DESC", [int(x)])
    tekme = cur.fetchall()
    moznosti = ['Datum - padajoče', 'Datum - naraščajoče', 'Kraj - od A do Ž', 'Kraj - od Ž do A',
                'Tip tekme - ekipne tekme prej', 'Tip tekme - posamične tekme prej', 'Rank - padajoče', 'Rank - naraščajoče']
    return template('tekmovalec.html', x=x, razvrscanje='Datum - padajoče', moznosti=moznosti, tekmovalec=tekmovalec, tekme=tekme, sezone=sezone(), najljubsi=najljubsi(username), napakaO=None, napaka=None, username=username, admin=admin)


@post('/tekmovalec/:x/')
def tekmovalec_post(x):
    if (request.forms.adminPassword != "") or (request.forms.password != ""):
        postani_admin()

    search = request.forms.search.lower().replace('č', 'c').replace('š', 's').replace('ž', 'z')
    username = get_user()
    admin = is_admin(username)
    cur.execute("SELECT * FROM tekmovalec WHERE fis_code = %s", [int(x)])
    tekmovalec = cur.fetchall()
    raz = request.forms.razvrscanje

    moznosti = ['Datum - padajoče', 'Datum - naraščajoče', 'Kraj - od A do Ž', 'Kraj - od Ž do A',
                'Tip tekme - ekipne tekme prej', 'Tip tekme - posamične tekme prej', 'Rank - padajoče', 'Rank - naraščajoče']

    sezR = raz.split('-')
    asc = ['naraščajoče', 'od A do Ž', 'ekipne tekme prej']

    slovar = {'rank': 'ranki'}

    if sezR == ['']:
        y = 'datum DESC'
    elif sezR[1].strip() in asc:
        z = sezR[0].strip().replace(' ', '_').lower().replace('č', 'c').replace('š', 's').replace('ž', 'z')
        if z in slovar:
            z = slovar.get(z)
        y = z + ' ASC'
    else:
        z = sezR[0].strip().replace(' ', '_').lower().replace('č', 'c').replace('š', 's').replace('ž', 'z')
        if z in slovar:
            z = slovar.get(z)
        y = z + ' DESC'

    if search == "":
        if 'ranki' in y:
            cur.execute(
                "SELECT t.datum, t.kraj, t.drzava, t.tip_tekme, r.ranki FROM rezultat r JOIN tekmovalec ON r.fis_code = tekmovalec.fis_code JOIN tekma t ON r.id = t.id WHERE r.fis_code = %s GROUP BY t.id, r.fis_code, r.ranki ORDER BY r." + y.replace(
                    '-', ' '), [int(x)])
        else:
            cur.execute(
                "SELECT t.datum, t.kraj, t.drzava, t.tip_tekme, r.ranki FROM rezultat r JOIN tekmovalec ON r.fis_code = tekmovalec.fis_code JOIN tekma t ON r.id = t.id WHERE r.fis_code = %s GROUP BY t.id, r.fis_code, r.ranki ORDER BY t." + y.replace(
                    '-', ' '), [int(x)])
        tekme = cur.fetchall()
        return template('tekmovalec.html', x=x, razvrscanje=raz, moznosti=moznosti, tekmovalec=tekmovalec, tekme=tekme, sezone=sezone(),
                        najljubsi=najljubsi(username), napakaO=None, napaka=None, username=username, admin=admin)

    napaka = None
    head_list = ['datum', 'kraj', 'drzava', 'tip_tekme', 'ranki']
    sez = search.split(':')
    sez[0] = sez[0].replace('č', 'c').replace('š', 's').replace('ž', 'z').strip()
    if sez[0] == 'rank':
        sez[0] = 'ranki'

    if len(sez) > 1:
        search = sez[1].strip()
        if sez[0].replace(' ', '') == 'tiptekme':
            cur.execute(
                "SELECT t.datum, t.kraj, t.drzava, t.tip_tekme, r.ranki FROM rezultat r JOIN tekmovalec ON r.fis_code = tekmovalec.fis_code JOIN tekma t ON r.id = t.id WHERE r.fis_code = %s AND CAST(t.tip_tekme AS varchar(10)) LIKE %s GROUP BY t.id, r.fis_code, r.ranki" + " ORDER BY " + y.replace(
                    '-', ' '), [int(x), '%' + search + '%'])
        elif sez[0].lower() == 'ranki':
            cur.execute(
                "SELECT t.datum, t.kraj, t.drzava, t.tip_tekme, r.ranki FROM rezultat r JOIN tekmovalec ON r.fis_code = tekmovalec.fis_code JOIN tekma t ON r.id = t.id WHERE r.fis_code = %s AND CAST(r.ranki AS varchar(10)) LIKE %s GROUP BY t.id, r.fis_code, r.ranki" + " ORDER BY " + y.replace(
                    '-', ' '), [int(x), '%' + search + '%'])
        elif sez[0] in ['kraj', 'drzava']:
            cur.execute(
                "SELECT t.datum, t.kraj, t.drzava, t.tip_tekme, r.ranki FROM rezultat r JOIN tekmovalec ON r.fis_code = tekmovalec.fis_code JOIN tekma t ON r.id = t.id WHERE r.fis_code = %s AND LOWER(t." +
                sez[0] + ") LIKE %s GROUP BY t.id, r.fis_code, r.ranki" + " ORDER BY " + y.replace('-',
                                                                                                                  ' '),
                [int(x), '%' + search + '%'])
        elif sez[0] in head_list:
            cur.execute(
                "SELECT t.datum, t.kraj, t.drzava, t.tip_tekme, r.ranki FROM rezultat r JOIN tekmovalec ON r.fis_code = tekmovalec.fis_code JOIN tekma t ON r.id = t.id WHERE r.fis_code = %s AND CAST(t." +
                sez[0] + " AS varchar(10)) LIKE %s GROUP BY t.id, r.fis_code, r.ranki" + " ORDER BY " + y.replace('-',
                                                                                                                  ' '),
                [int(x), '%' + search + '%'])
        else:
            napaka = "Neveljavno iskanje."
    else:
        cur.execute(
            "SELECT t.datum, t.kraj, t.drzava, t.tip_tekme, r.ranki FROM rezultat r JOIN tekmovalec ON r.fis_code = tekmovalec.fis_code JOIN tekma t ON r.id = t.id WHERE r.fis_code = %s AND (LOWER(tip_tekme) LIKE %s"
            "OR CAST(datum AS varchar(10)) LIKE %s"
            "OR LOWER(kraj) LIKE %s"
            "OR LOWER(t.drzava) LIKE %s"
            "OR CAST(ranki AS varchar(10)) LIKE %s)"
            "GROUP BY t.id, r.fis_code, r.ranki" + " ORDER BY " + y.replace('-', ' '),
            [int(x), '%' + search + '%', '%' + search + '%', '%' + search + '%', '%' + search + '%',
             '%' + search + '%'])
    tekme = cur.fetchall()
    return template('tekmovalec.html', x=x, razvrscanje=raz, moznosti=moznosti, tekmovalec=tekmovalec, tekme=tekme, sezone=sezone(),
                    najljubsi=najljubsi(username), napakaO=None, napaka=napaka, username=username, admin=admin)


@get('/tekme/:x/')
def tekme(x):
    username = get_user()
    admin = is_admin(username)
    cur.execute("SELECT id,kraj,datum,drzava,tip_tekme FROM tekma WHERE datum BETWEEN %s AND %s ORDER BY datum DESC",
                [datetime.date(int(x) - 1, 11, 1), datetime.date(int(x), 3, 31)])
    tekme = cur.fetchall()
    moznosti = ['ID - padajoče', 'ID - naraščajoče', 'Kraj - od A do Ž', 'Kraj - od Ž do A', 'Datum - starejši prej',
                'Datum - novejši prej', 'Država - od A do Ž', 'Država - od Ž do A', 'Tip tekme - ekipne tekme prej', 'Tip tekme - posamične tekme prej']
    return template('tekme_sezona.html', moznosti=moznosti, razvrscanje='Datum - novejši prej', sezone=sezone(), napakaO=None, x=x, tekme=tekme, username = username, admin=admin)

@post('/tekme/:x/')
def tekme_post(x):
    if (request.forms.adminPassword != "") or (request.forms.password != ""):
        postani_admin()

    moznosti = ['ID - padajoče', 'ID - naraščajoče', 'Kraj - od A do Ž', 'Kraj - od Ž do A', 'Datum - starejši prej',
                'Datum - novejši prej', 'Država - od A do Ž', 'Država - od Ž do A', 'Tip tekme - ekipne tekme prej',
                'Tip tekme - posamične tekme prej']

    search = request.forms.search.lower()
    username = get_user()
    admin = is_admin(username)

    raz = request.forms.razvrscanje

    sezR = raz.split('-')
    asc = ['naraščajoče', 'od A do Ž', 'starejši prej', 'ekipne tekme prej']

    if sezR[1].strip() in asc:
        z = sezR[0].strip().replace(' ', '_').lower().replace('č', 'c').replace('š', 's').replace('ž', 'z')
        if z == 'tip_tekme':
            z = '(tip_tekme, datum)'
        y = z + ' ASC'
    else:
        z = sezR[0].strip().replace(' ', '_').lower().replace('č', 'c').replace('š', 's').replace('ž', 'z')
        if z == 'tip_tekme':
            z = '(tip_tekme, datum)'
        y = z + ' DESC'

    print(y)

    cur.execute("SELECT id,kraj,datum,drzava,tip_tekme FROM tekma WHERE datum BETWEEN %s AND %s ORDER BY " + y.replace('-', ' '),
                [datetime.date(int(x) - 1, 11, 1), datetime.date(int(x), 3, 31)])
    tekme = cur.fetchall()

    return template('tekme_sezona.html', moznosti=moznosti, razvrscanje=raz, sezone=sezone(),
                    napakaO=None, x=x, tekme=tekme, username=username, admin=admin)

@get('/tekma/:x/')
def tekma(x):
    username = get_user()
    admin = is_admin(username)
    cur.execute("SELECT kraj, datum FROM tekma WHERE id = %s", [int(x)])
    kraj_datum = cur.fetchone()
    datumi = str(kraj_datum[1]).split('-')
    datum = datumi[2] + '.' + datumi[1] + '.' + datumi[0]
    cur.execute("SELECT tip_tekme FROM tekma WHERE id = %s LIMIT 1", [int(x)])
    if cur.fetchone()[0] == 'posamicna':
        ekipna = False
    else:
        ekipna = True
    cur.execute("SELECT serija FROM rezultat WHERE id = %s ORDER BY serija DESC LIMIT 1", [int(x)])
    serija = cur.fetchone()
    if serija is None:
        velikost = False
        serija_bool = True
        tekma = []
    else:
        velikost = True
        if serija[0] == 2:
            cur.execute("SELECT ranki,startna_stevilka,fis_code,ime,priimek,drzava,skoki1,tocke1,skoki2,tocke2,tocke,mesto_v_ekipi FROM dve_seriji WHERE id = %s ORDER BY ranki ASC",[int(x)])
            serija_bool = True
        else:
            cur.execute("SELECT ranki,startna_stevilka,fis_code,ime,priimek,drzava,tocke,mesto_v_ekipi FROM ena_serija WHERE id=%s ORDER BY ranki ASC",[int(x)])
            serija_bool = False
        tekma = cur.fetchall()

    moznosti = ['Rank - padajoče', 'Rank - naraščajoče']
    if ekipna:
        moznosti += ['Mesto v ekipi - padajoče', 'Mesto v ekipi - naraščajoče']
    else:
        moznosti += ['Startna številka - padajoče', 'Startna številka - naraščajoče']
    moznosti += ['FIS code - padajoče', 'FIS code - naraščajoče', 'Ime - od A do Ž', 'Ime - od Ž do A', 'Priimek - od A do Ž', 'Priimek - od Ž do A', 'Država - od A do Ž', 'Država - od Ž do A']
    if serija_bool:
        moznosti += ['1. skok - padajoče', '1. skok - naraščajoče', '1. točke - padajoče', '1. točke - naraščajoče', '2. skok - padajoče', '2. skok - naraščajoče', '2. točke - padajoče', '2. točke - naraščajoče']
        if not ekipna:
            moznosti += ['Skupne točke - padajoče', 'Skupne točke - naraščajoče']
    else:
        moznosti += ['Točke - padajoče', 'Točke - naraščajoče']

    return template('tekma.html', napakaO=None, razvrscanje='Ranki - naraščajoče', moznosti=moznosti, sezone=sezone(), x = x, tekma = tekma, velikost=velikost, kraj=kraj_datum[0], datum=datum, username = username, admin=admin, ekipna=ekipna, serija=serija_bool, napaka=None)


@post('/tekma/:x/')
def tekma_post(x):
    if (request.forms.adminPassword != "") or (request.forms.password != ""):
        postani_admin()

    search = request.forms.search.lower()
    username = get_user()
    admin = is_admin(username)
    napaka = None

    raz = request.forms.razvrscanje

    sezR = raz.split('-')
    asc = ['naraščajoče', 'od A do Ž']

    if len(sezR) < 2:
        sezR = ['rank', 'naraščajoče']

    slovar = {'1._skok': 'skoki1', '2._skok': 'skoki2', '1._tocke': 'tocke1', '2._tocke': 'tocke2', 'rank': 'ranki'}

    if sezR[1].strip() in asc:
        z = sezR[0].strip().replace(' ', '_').lower().replace('č', 'c').replace('š', 's').replace('ž', 'z')
        if z in slovar:
            z = slovar.get(z)
        y = z + ' ASC'
    else:
        z = sezR[0].strip().replace(' ', '_').lower().replace('č', 'c').replace('š', 's').replace('ž', 'z')
        if z in slovar:
            z = slovar.get(z)
        y = z + ' DESC'

    cur.execute("SELECT kraj, datum FROM tekma WHERE id = %s", [int(x)])
    kraj_datum = cur.fetchone()
    datumi = str(kraj_datum[1]).split('-')
    datum = datumi[2] + '.' + datumi[1] + '.' + datumi[0]
    cur.execute("SELECT tip_tekme FROM tekma WHERE id = %s LIMIT 1", [int(x)])
    if cur.fetchone()[0] == 'posamicna':
        ekipna = False
    else:
        ekipna = True
    cur.execute("SELECT serija FROM rezultat WHERE id = %s ORDER BY serija DESC LIMIT 1", [int(x)])
    serija = cur.fetchone()
    if serija is None:
        velikost = False
        serija_bool = True
        head_list = ['ranki', 'startna_stevilka', 'fis_code', 'skoki1', 'tocke1', 'skoki2', 'tocke2', 'tocke',
                     'mesto_v_ekipi']
        string = 'dve_seriji'
    else:
        velikost = True
        if serija[0] == 2:
            serija_bool = True
            head_list = ['ranki', 'startna_stevilka', 'fis_code', 'skoki1', 'tocke1', 'skoki2', 'tocke2', 'tocke', 'mesto_v_ekipi']
            string = 'dve_seriji'
        else:
            serija_bool = False
            head_list = ['ranki', 'startna_stevilka', 'fis_code', 'tocke', 'mesto_v_ekipi']
            string = 'ena_serija'

    moznosti = ['Rank - padajoče', 'Rank - naraščajoče']
    if ekipna:
        moznosti += ['Mesto v ekipi - padajoče', 'Mesto v ekipi - naraščajoče']
    else:
        moznosti += ['Startna številka - padajoče', 'Startna številka - naraščajoče']
    moznosti += ['Fis code - padajoče', 'Fis code - naraščajoče', 'Ime - od A do Ž', 'Ime - od Ž do A',
                 'Priimek - od A do Ž', 'Priimek - od Ž do A', 'Država - od A do Ž', 'Država - od Ž do A']
    if serija_bool:
        moznosti += ['1. skok - padajoče', '1. skok - naraščajoče', '1. točke - padajoče', '1. točke - naraščajoče',
                     '2. skok - padajoče', '2. skok - naraščajoče', '2. točke - padajoče', '2. točke - naraščajoče']
        if not ekipna:
            moznosti += ['Skupne točke - padajoče', 'Skupne točke - naraščajoče']
    else:
        moznosti += ['Točke - padajoče', 'Točke - naraščajoče']

    text_list = ['ime', 'priimek', 'drzava']
    sez = search.split(':')
    sez[0] = sez[0].replace('č', 'c').replace('š', 's').replace('ž', 'z')
    sez[0] = sez[0].strip().replace(' ', '_')
    if sez[0] == 'rank':
        sez[0] = 'ranki'

    if len(sez) > 1:
        if sez[0] in head_list:
            cur.execute("SELECT " + ','.join(head_list[:3]) + ',' + ','.join(text_list) + ',' + ','.join(head_list[3:]) + ' FROM ' + string + " WHERE id = %s AND CAST(" + sez[0] + " AS varchar(10)) LIKE %s" + "ORDER BY " + y.replace('-', ' '),
            [int(x)] + ['%' + sez[1].strip() + '%'])
        elif sez[0] in text_list:
            cur.execute("SELECT " + ','.join(head_list[:3]) + ',' + ','.join(text_list) + ',' + ','.join(head_list[3:]) + ' FROM ' + string + " WHERE id = %s AND LOWER(" + sez[0] + ") LIKE %s" + "ORDER BY " + y.replace('-', ' '),
            [int(x)] + ['%' + sez[1].strip() + '%'])
        else:
            napaka = "Neveljavno iskanje."
    else:
        cur.execute("SELECT " + ','.join(head_list[:3]) + ',' + ','.join(text_list) + ',' + ','.join(head_list[3:]) + ' FROM ' + string + " WHERE id = %s AND (CAST("
                    + ' AS varchar(10)) LIKE %s OR CAST('.join(head_list) + " AS varchar(10)) LIKE %s"
                    + " OR LOWER(" + ') LIKE %s OR LOWER('.join(text_list) + ") LIKE %s)" + "ORDER BY " + y.replace('-', ' '),
                    [int(x)] + (len(head_list) + len(text_list)) * ['%' + search + '%'])
    tekma = cur.fetchall()
    return template('tekma.html', razvrscanje=raz, moznosti=moznosti, velikost=velikost, napakaO=None, x=x, tekma=tekma, kraj=kraj_datum[0], datum=datum, username=username,
                    admin=admin, ekipna=ekipna, serija=serija_bool, sezone=sezone(), napaka=napaka)


@get('/drzave')
def drzave():
    username = get_user()
    admin = is_admin(username)
    cur.execute("SELECT kratica,ime FROM drzava ORDER BY kratica")
    drzave = cur.fetchall()
    return template('drzave.html', sezone=sezone(), napakaO=None, drzave=drzave,username=username,admin=admin)


@get('/drzava/:x')
def drzava(x):
    username = get_user()
    cur.execute("SELECT ime FROM drzava WHERE kratica=%s",[x])
    ime = cur.fetchone()[0]
    admin = is_admin(username)
    cur.execute("SELECT * FROM tekmovalec WHERE drzava=%s ORDER BY priimek,ime",[x])
    tekmovalci=cur.fetchall()

    cur.execute("SELECT id FROM tekma WHERE tip_tekme = 'ekipna' AND datum <= date('now') ORDER BY datum DESC LIMIT 1")
    id = cur.fetchone()[0]
    cur.execute("SELECT kraj FROM tekma WHERE tekma.id=%s",[int(id)])
    kraj = cur.fetchone()[0]
    cur.execute("SELECT datum FROM tekma WHERE tekma.id=%s",[int(id)])
    datum = cur.fetchone()[0]
    datumi = str(datum).split('-')
    datum = datumi[2] + '.' + datumi[1] + '.' + datumi[0]
    cur.execute(
        "SELECT r1.ranki, r1.startna_stevilka, t.fis_code, t.ime, t.priimek, t.drzava, r1.skoki AS skoki1, r1.tocke AS tocke1, r2.skoki AS skoki2, r2.tocke AS tocke2, r1.mesto_v_ekipi "
        "FROM rezultat r1 JOIN rezultat r2 ON r1.id = r2.id AND r1.fis_code = r2.fis_code AND r1.serija < r2.serija JOIN tekmovalec t ON r1.fis_code = t.fis_code "
        "WHERE r1.id=%s ORDER BY r1.ranki, r1.mesto_v_ekipi ASC",[int(id)])
    tekma=cur.fetchall()

    cur.execute(
        "WITH zdruzena AS (SELECT * FROM rezultat JOIN tekma ON rezultat.id = tekma.id WHERE rezultat.drzava = %s) "
        "SELECT ranki, count(*) AS stevilo FROM zdruzena WHERE tip_tekme <> 'ekipna' GROUP BY ranki ORDER BY ranki",[x])
    mesta = cur.fetchall()

    if mesta == []:
        prazna = True
    else:
        prazna = False

    return template('drzava.html', sezone=sezone(), prva=sezone()[0], zadnja=sezone()[-1], napakaO=None, prazna=prazna, x=x, ime=ime,tekmovalci=tekmovalci,kraj=kraj,datum=datum, tekma=tekma, serija=True, ekipna=True, mesta=mesta, username = username, admin=admin )


@get('/zadnja_tekma')
def zadnja_tekma():
    cur.execute("SELECT id FROM tekma WHERE datum <= date('now') ORDER BY datum DESC LIMIT 1")
    id = cur.fetchone()[0]
    return tekma(id)

@post('/zadnja_tekma')
def zadnja_tekma_post():
    cur.execute("SELECT id FROM tekma WHERE datum <= date('now') ORDER BY datum DESC LIMIT 1")
    id = cur.fetchone()[0]
    return tekma_post(id)

@get('/dodaj_drzavo')
def dodaj_drzavo():
    username = get_user()
    admin = is_admin(username)
    return template('dodaj_drzavo.html',kratica='',ime='', sezone=sezone(), napakaO=None, napaka=None,username=username,admin=admin)


@post('/dodaj_drzavo')
def dodaj_drzavo_post():
    if (request.forms.adminPassword != "") or (request.forms.password != ""):
        postani_admin()

    username = get_user()
    admin=is_admin(username)
    kratica = request.forms.kratica
    ime = request.forms.ime

    try:
        cur.execute("INSERT INTO drzava (kratica,ime) VALUES (%s,%s)",[kratica,ime])
        conn.commit()
    except Exception as ex:
        return template('dodaj_drzavo.html',kratica=kratica,ime=ime,napakaO=None,napaka='Zgodila se je napaka: %s'% ex, sezone=sezone(), username=username, admin=admin)
    redirect("/")

@get('/dodaj_tekmovalca')
def dodaj_tekmovalca():
    username = get_user()
    admin = is_admin(username)
    cur.execute("SELECT kratica,ime FROM drzava ORDER BY kratica ASC")
    drzave = cur.fetchall()
    return template('dodaj_tekmovalca.html', fis_code='', ime='', priimek='', drzave=drzave, rojstvo='', klub='',
                        smucke='', status='', sezone=sezone(), napakaO=None, napaka=None, username=username, admin=admin)


@post('/dodaj_tekmovalca')
def dodaj_tekmovalca_post():
    if (request.forms.adminPassword != "") or (request.forms.password != ""):
        postani_admin()

    username = get_user()
    admin = is_admin(username)
    cur.execute("SELECT kratica,ime FROM drzava ORDER BY kratica ASC")
    drzave = cur.fetchall()
    fis_code = request.forms.fis_code
    ime = request.forms.ime
    priimek = request.forms.priimek
    drzava = request.forms.drzava
    vse = drzava.split('-')
    drzava = vse[0].strip()
    rojstvo = request.forms.rojstvo
    klub = request.forms.klub
    smucke = request.forms.smucke
    status = request.forms.status
    try:
        cur.execute("INSERT INTO tekmovalec (fis_code, ime, priimek, drzava, rojstvo, klub, smucke, status) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                    (fis_code, ime, priimek, drzava, rojstvo, klub, smucke, status))
        conn.commit()
    except Exception as ex:
        return template('dodaj_tekmovalca.html', sezone=sezone(), napakaO=None, fis_code=fis_code, ime=ime, priimek=priimek, drzave=drzave, rojstvo=rojstvo, klub=klub, smucke=smucke, status=status,
                        napaka = 'Zgodila se je napaka: %s' % ex, username=username, admin=admin)
    redirect("/tekmovalec/{}/".format(fis_code))


@get('/uredi_tekmovalca/:x/')
def uredi_tekmovalca(x):
    username = get_user()
    admin = is_admin(username)
    cur.execute("SELECT kratica,ime FROM drzava ORDER BY kratica ASC")
    drzave = cur.fetchall()
    cur.execute("SELECT d.ime FROM drzava AS d JOIN tekmovalec ON (tekmovalec.drzava = d.kratica) WHERE fis_code = %s", [int(x)])
    ime_drzave = cur.fetchone()[0]
    cur.execute("SELECT * FROM tekmovalec WHERE fis_code = %s", [int(x)])
    podatki = cur.fetchone()
    return template('uredi_tekmovalca.html', ime_drzave=ime_drzave, fis_code=x, status=podatki[1], ime=podatki[2], priimek=podatki[3], drzava=podatki[4], drzave=drzave, rojstvo=podatki[5], klub=podatki[6],
                        smucke=podatki[7], x=x, sezone=sezone(), napakaO=None, napaka=None, username=username, admin=admin)


@post('/uredi_tekmovalca/:x/')
def uredi_tekmovalca_post(x):
    if (request.forms.adminPassword != "") or (request.forms.password != ""):
        postani_admin()

    username = get_user()
    admin = is_admin(username)
    cur.execute("SELECT kratica,ime FROM drzava ORDER BY kratica ASC")
    drzave = cur.fetchall()
    cur.execute("SELECT d.ime FROM drzava AS d JOIN tekmovalec ON (tekmovalec.drzava = d.kratica) WHERE fis_code = %s",
                [int(x)])
    ime_drzave = cur.fetchone()[0]
    status=request.forms.status
    ime=request.forms.ime
    priimek=request.forms.priimek
    drzava = request.forms.drzava
    vse = drzava.split('-')
    drzava = vse[0].strip()
    rojstvo=request.forms.rojstvo
    klub=request.forms.klub
    smucke=request.forms.smucke
    try:
        cur.execute("UPDATE tekmovalec SET status=%s,drzava=%s, rojstvo=%s,klub=%s,smucke=%s WHERE fis_code=%s",
                    [status,drzava,rojstvo,klub,smucke,x])
        conn.commit()
    except Exception as ex:
        return template('uredi_tekmovalca.html', ime_drzave=ime_drzave, fis_code=x, status=status, ime=ime, priimek=priimek, drzava=drzava, drzave=drzave, rojstvo=rojstvo, klub=klub,
                        smucke=smucke, x=x, sezone=sezone(), napakaO=None, napaka = 'Zgodila se je napaka: %s' % ex, username=username, admin=admin)
    redirect("/tekmovalec/{}/".format(x))


@get('/dodaj_tekmo')
def dodaj_tekmo():
    username = get_user()
    admin = is_admin(username)
    cur.execute("SELECT kratica,ime FROM drzava ORDER BY kratica ASC")
    drzave = cur.fetchall()
    return template('dodaj_tekmo.html', sezone=sezone(), napakaO=None, id='', kraj='', drzave=drzave, datum='', tip_tekme='', napaka=None, username = username, admin=admin)


@post('/dodaj_tekmo')
def dodaj_tekmo_post():
    if (request.forms.adminPassword != "") or (request.forms.password != ""):
        postani_admin()

    username = get_user()
    admin = is_admin(username)
    cur.execute("SELECT kratica,ime FROM drzava ORDER BY kratica ASC")
    drzave = cur.fetchall()
    id = request.forms.id
    kraj = request.forms.kraj
    drzava = request.forms.drzava
    vse = drzava.split('-')
    drzava = vse[0].strip()
    datum = request.forms.datum
    tip_tekme = request.forms.tip_tekme
    try:
        cur.execute("INSERT INTO tekma (id, kraj, datum, drzava, tip_tekme) VALUES (%s, %s, %s, %s, %s)",
                    (id, kraj, datum, drzava, tip_tekme))
        conn.commit()
    except Exception as ex:
        return template('dodaj_tekmo.html', id=id, kraj=kraj, datum=datum, drzave=drzave, tip_tekme=tip_tekme, napakaO=None,
                        napaka = 'Zgodila se je napaka: %s' % ex, sezone=sezone(), username = username, admin=admin)
    zakljuci = request.forms.zakljuci
    if zakljuci == "ne":
        redirect("/dodaj_rezultat/{}/".format(id))
    else:
        redirect("/tekma/{}/".format(id))


@get('/dodaj_rezultat/:x/')
def dodaj_rezultat(x):
    username = get_user()
    admin = is_admin(username)
    cur.execute("SELECT kraj FROM tekma WHERE id = %s", [int(x)])
    kraj = cur.fetchone()[0]
    cur.execute("SELECT datum FROM tekma WHERE id = %s", [int(x)])
    datum = cur.fetchone()[0]
    cur.execute("SELECT kratica,ime FROM drzava ORDER BY kratica ASC")
    drzave=cur.fetchall()
    cur.execute("SELECT fis_code,ime,priimek FROM tekmovalec ORDER BY priimek,ime")
    vsi_tekmovalci = cur.fetchall()
    cur.execute("SELECT tip_tekme FROM tekma WHERE id = %s", [int(x)])
    if cur.fetchone()[0] == 'posamicna':
        ekipna = False
    else:
        ekipna = True
    if not ekipna:
        return template('dodaj_rezultat.html', napakaO=None, x=x, id=x, kraj=kraj, datum=datum, ranki='', startna_stevilka='', fis_code='', drzava='',
                        skoki1='', tocke1='', skoki2='', tocke2='', drzave=drzave, vsi_tekmovalci=vsi_tekmovalci, ekipna=ekipna,
                        sezone=sezone(), napaka=None, username=username, admin=admin)
    else:
        return template('dodaj_rezultat.html', napakaO=None, x=x, id=x, kraj=kraj, datum=datum, ranki='',
                        fis_code1='', fis_code2='', fis_code3='', fis_code4='',
                        skoki11='', tocke11='', skoki21='', tocke21='',
                        skoki12='', tocke12='', skoki22='', tocke22='',
                        skoki13='', tocke13='', skoki23='', tocke23='',
                        skoki14='', tocke14='', skoki24='', tocke24='',
                        drzava='', drzave=drzave, vsi_tekmovalci=vsi_tekmovalci, ekipna=ekipna,
                        sezone=sezone(), napaka=None, username=username, admin=admin)


@post('/dodaj_rezultat/:x/')
def dodaj_tekmo_post(x):
    if (request.forms.adminPassword != "") or (request.forms.password != ""):
        postani_admin()

    username = get_user()
    admin = is_admin(username)
    cur.execute("SELECT kraj FROM tekma WHERE id = %s", [int(x)])
    kraj = cur.fetchone()[0]
    cur.execute("SELECT datum FROM tekma WHERE id = %s", [int(x)])
    datum = cur.fetchone()[0]
    cur.execute("SELECT kratica,ime FROM drzava ORDER BY kratica ASC")
    drzave = cur.fetchall()
    cur.execute("SELECT fis_code,ime,priimek FROM tekmovalec ORDER BY priimek,ime")
    vsi_tekmovalci = cur.fetchall()
    cur.execute("SELECT tip_tekme FROM tekma WHERE id = %s", [int(x)])
    if cur.fetchone()[0] == 'posamicna':
        ekipna = False
    else:
        ekipna = True
    ranki = request.forms.ranki
    if not ekipna:
        startna_stevilka = request.forms.startna_stevilka
        fis_code = request.forms.fis_code.split(' ')[0]
    else:
        fis_code1 = request.forms.fis_code1.split(' ')[0]
        fis_code2 = request.forms.fis_code2.split(' ')[0]
        fis_code3 = request.forms.fis_code3.split(' ')[0]
        fis_code4 = request.forms.fis_code4.split(' ')[0]
    drzava = request.forms.drzava
    vse = drzava.split('-')
    drzava = vse[0].strip()
    if not ekipna:
        skoki1 = request.forms.skoki1
        tocke1 = request.forms.tocke1
        skoki2 = request.forms.skoki2
        tocke2 = request.forms.tocke2
    else:
        skoki11 = request.forms.skoki11
        tocke11 = request.forms.tocke11
        skoki21 = request.forms.skoki21
        tocke21 = request.forms.tocke21
        skoki12 = request.forms.skoki12
        tocke12 = request.forms.tocke12
        skoki22 = request.forms.skoki22
        tocke22 = request.forms.tocke22
        skoki13 = request.forms.skoki13
        tocke13 = request.forms.tocke13
        skoki23 = request.forms.skoki23
        tocke23 = request.forms.tocke23
        skoki14 = request.forms.skoki14
        tocke14 = request.forms.tocke14
        skoki24 = request.forms.skoki24
        tocke24 = request.forms.tocke24
    try:
        if ekipna:
            cur.execute("INSERT INTO rezultat (id, ranki, startna_stevilka, fis_code, drzava, skoki, tocke, serija, mesto_v_ekipi) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                        (x, ranki, 0, fis_code1, drzava, skoki11, tocke11, 1, 1))
            conn.commit()
            if skoki21 and tocke21:
                cur.execute("INSERT INTO rezultat (id, ranki, startna_stevilka, fis_code, drzava, skoki, tocke, serija, mesto_v_ekipi) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                            (x, ranki, 0, fis_code1, drzava, skoki21, tocke21, 2, 1))
                conn.commit()
            else:
                cur.execute("INSERT INTO rezultat (id, ranki, startna_stevilka, fis_code, drzava, skoki, tocke, serija, mesto_v_ekipi) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                            (x, ranki, 0, fis_code1, drzava, 0, 0, 2, 1))
                conn.commit()

            cur.execute("INSERT INTO rezultat (id, ranki, startna_stevilka, fis_code, drzava, skoki, tocke, serija, mesto_v_ekipi) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                        (x, ranki, 0, fis_code2, drzava, skoki12, tocke12, 1, 2))
            conn.commit()
            if skoki22 and tocke22:
                cur.execute("INSERT INTO rezultat (id, ranki, startna_stevilka, fis_code, drzava, skoki, tocke, serija, mesto_v_ekipi) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                            (x, ranki, 0, fis_code2, drzava, skoki22, tocke22, 2, 2))
                conn.commit()
            else:
                cur.execute("INSERT INTO rezultat (id, ranki, startna_stevilka, fis_code, drzava, skoki, tocke, serija, mesto_v_ekipi) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                            (x, ranki, 0, fis_code2, drzava, 0, 0, 2, 2))
                conn.commit()

            cur.execute("INSERT INTO rezultat (id, ranki, startna_stevilka, fis_code, drzava, skoki, tocke, serija, mesto_v_ekipi) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                        (x, ranki, 0, fis_code3, drzava, skoki13, tocke13, 1, 3))
            conn.commit()
            if skoki23 and tocke23:
                cur.execute("INSERT INTO rezultat (id, ranki, startna_stevilka, fis_code, drzava, skoki, tocke, serija, mesto_v_ekipi) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                            (x, ranki, 0, fis_code3, drzava, skoki23, tocke23, 2, 3))
                conn.commit()
            else:
                cur.execute("INSERT INTO rezultat (id, ranki, startna_stevilka, fis_code, drzava, skoki, tocke, serija, mesto_v_ekipi) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                            (x, ranki, 0, fis_code3, drzava, 0, 0, 2, 3))
                conn.commit()

            cur.execute("INSERT INTO rezultat (id, ranki, startna_stevilka, fis_code, drzava, skoki, tocke, serija, mesto_v_ekipi) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                        (x, ranki, 0, fis_code4, drzava, skoki14, tocke14, 1, 4))
            conn.commit()
            if skoki24 and tocke24:
                cur.execute("INSERT INTO rezultat (id, ranki, startna_stevilka, fis_code, drzava, skoki, tocke, serija, mesto_v_ekipi) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                            (x, ranki, 0, fis_code4, drzava, skoki24, tocke24, 2, 4))
                conn.commit()
            else:
                cur.execute("INSERT INTO rezultat (id, ranki, startna_stevilka, fis_code, drzava, skoki, tocke, serija, mesto_v_ekipi) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                            (x, ranki, 0, fis_code4, drzava, 0, 0, 2, 4))
                conn.commit()

        else:
            cur.execute("INSERT INTO rezultat (id, ranki, startna_stevilka, fis_code, drzava, skoki, tocke, serija, mesto_v_ekipi) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                        (x, ranki, startna_stevilka, fis_code, drzava, skoki1, tocke1, 1, 0))
            conn.commit()
            if skoki2 and tocke2:
                cur.execute("INSERT INTO rezultat (id, ranki, startna_stevilka, fis_code, drzava, skoki, tocke, serija, mesto_v_ekipi) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                            (x, ranki, startna_stevilka, fis_code, drzava, skoki2, tocke2, 2, 0))
                conn.commit()
            else:
                cur.execute(
                    "INSERT INTO rezultat (id, ranki, startna_stevilka, fis_code, drzava, skoki, tocke, serija, mesto_v_ekipi) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                    (x, ranki, startna_stevilka, fis_code, drzava, 0, 0, 2, 0))
                conn.commit()
    except Exception as ex:
        if not ekipna:
            return template('dodaj_rezultat.html', sezone=sezone(), napakaO=None, x=x, id=x, kraj=kraj, datum=datum, ranki=ranki,
                            startna_stevilka=startna_stevilka, fis_code=fis_code,
                            drzava=drzava, skoki1=skoki1, tocke1=tocke1, skoki2=skoki2, tocke2=tocke2, drzave=drzave,
                            vsi_tekmovalci=vsi_tekmovalci, ekipna=ekipna,
                            napaka='Zgodila se je napaka: %s' % ex, username=username, admin=admin)
        else:
            return template('dodaj_rezultat.html', sezone=sezone(), napakaO=None, x=x, id=x, kraj=kraj, datum=datum, ranki=ranki,
                            fis_code1=fis_code1, fis_code2=fis_code2, fis_code3=fis_code3, fis_code4=fis_code4, drzava=drzava,
                            skoki11=skoki11, tocke11=tocke11, skoki21=skoki21, tocke21=tocke21,
                            skoki12=skoki12, tocke12=tocke12, skoki22=skoki22, tocke22=tocke22,
                            skoki13=skoki13, tocke13=tocke13, skoki23=skoki23, tocke23=tocke23,
                            skoki14=skoki14, tocke14=tocke14, skoki24=skoki24, tocke24=tocke24,
                            drzave=drzave, vsi_tekmovalci=vsi_tekmovalci, ekipna=ekipna,
                            napaka='Zgodila se je napaka: %s' % ex, username=username, admin=admin)
    zakljuci = request.forms.zakljuci
    if zakljuci == "ne":
        redirect("/dodaj_rezultat/{}/".format(x))
    else:
        redirect("/tekma/{}/".format(x))


@get('/zanimivosti/:x')
def zanimivosti(x):
    username=get_user()
    admin=is_admin(username)
    cur.execute("SELECT * FROM drzava ORDER BY kratica")
    drzave = cur.fetchall()
    cur.execute("SELECT fis_code,ime,priimek FROM tekmovalec ORDER BY priimek,ime")
    vsi_tekmovalci = cur.fetchall()
    return template('zanimivosti.html',sezone=sezone(),drzave=drzave,drzava='',sezona1='',sezona2='',ime1='',ime2='',ime3='',zacetna='',koncna='',izbrana=False,napaka=None, zanimivost=int(x),
                    username=username,admin=admin,napakaO=None,izpis=False,tekmovalci=cur,vsi_tekmovalci=vsi_tekmovalci,tekme_boljsi=cur,
                    tekmovalci_dolzina=cur, ranki=cur, dolzina='',skupni_sestevek=cur)


@post('/zanimivosti/1')
def zanimivosti_post_1():
    if (request.forms.adminPassword != "") or (request.forms.password != ""):
        postani_admin()

    username=get_user()
    admin=is_admin(username)
    cur.execute("SELECT * FROM drzava ORDER BY kratica")
    drzave = cur.fetchall()
    drzava = request.forms.drzava
    sezona1= request.forms.sezona1
    sezona2= request.forms.sezona2
    cur.execute("WITH tek AS (WITH zdruzena AS (SELECT * FROM tekmovalec JOIN drzava ON tekmovalec.drzava = drzava.kratica JOIN rezultat USING (fis_code) JOIN tekma USING (id))"
                "SELECT fis_code FROM zdruzena WHERE kratica=%s AND datum BETWEEN %s AND %s GROUP BY fis_code) SELECT * FROM tek JOIN tekmovalec USING (fis_code)",[drzava, datetime.date(int(sezona1) - 1, 11, 1), datetime.date(int(sezona2), 3, 31)])
    tekmovalci_drzave = cur.fetchall()
    return template('zanimivosti.html',sezone=sezone(),drzave=drzave,drzava=drzava,sezona1=sezona1,sezona2=sezona2,izbrana=True,napaka=None,tekmovalci=tekmovalci_drzave, zanimivost=1,
                    username=username,admin=admin,napakaO=None,izpis=True,vsi_tekmovalci=cur,tekme_boljsi=cur,tekmovalci_dolzina=cur,dolzina='',
                    ranki=cur,skupni_sestevek=cur)


@post('/zanimivosti/2')
def zanimivosti_post_2():
    if (request.forms.adminPassword != "") or (request.forms.password != ""):
        postani_admin()

    username=get_user()
    admin=is_admin(username)
    cur.execute("SELECT fis_code,ime,priimek FROM tekmovalec ORDER BY priimek,ime")
    vsi_tekmovalci = cur.fetchall()
    tekmovalec1 = request.forms.tekmovalec1
    tekmovalec2 = request.forms.tekmovalec2
    id_1 = int(tekmovalec1.split('-')[0])
    print(id_1)
    id_2 = int(tekmovalec2.split('-')[0])
    cur.execute("with boljsi as ("
                "  with oba as ("
                "    select id, count(id) as oba from tekma"
                "    join rezultat using (id)"
                "    where (fis_code = %s or fis_code = %s) and (serija = 1 or serija = 3)"
                "    group by id"
                "  )"
                "  select id, min(ranki) as ranki from tekma"
                "  join oba using (id)"
                "  join rezultat using (id)"
                "  where oba = 2 and (fis_code = %s or fis_code = %s) and (serija = 1 or serija = 3)"
                "  group by id"
                ")"
                " select id, kraj, datum, t.drzava, tip_tekme, ime, priimek from tekma t"
                " join boljsi using(id)"
                " join rezultat using(ranki, id)"
                " join tekmovalec using(fis_code)"
                " where (serija = 1 or serija = 3) and (fis_code = %s or fis_code = %s)", 3 * [id_1, id_2])
    tekme_boljsi = cur.fetchall()
    ime1 = tekmovalec1.split('-')[1]
    ime2 = tekmovalec2.split('-')[1]
    return template('zanimivosti.html', tekmovalec1=tekmovalec1, tekmovalec2=tekmovalec2, id_1=id_1, id_2=id_2, ime1=ime1, ime2=ime2, izbrana=True, tekme_boljsi=tekme_boljsi, vsi_tekmovalci=vsi_tekmovalci, izpis=True,
                    sezone=cur, drzave=cur, napaka=None, napakaO=None, tekmovalci=cur, zanimivost=2, username=username, admin=admin,
                    tekmovalci_dolzina=cur,dolzina='',ranki=cur,skupni_sestevek=cur)


@post('/zanimivosti/3')
def zanimivosti_post_3():
    if (request.forms.adminPassword != "") or (request.forms.password != ""):
        postani_admin()

    username = get_user()
    admin = is_admin(username)
    dolzina = request.forms.dolzina
    cur.execute("WITH umesna AS (SELECT fis_code, count(*) AS stevilo FROM rezultat WHERE skoki >= %s GROUP BY fis_code)"
                "SELECT fis_code, status, ime, priimek, drzava, rojstvo, klub, smucke, stevilo FROM umesna "
                "JOIN tekmovalec USING (fis_code) ORDER BY stevilo DESC",[float(dolzina)])
    tekmovalci_dolzina = cur.fetchall()
    return template('zanimivosti.html', tekmovalci_dolzina=tekmovalci_dolzina, dolzina=dolzina, tekme_boljsi=cur, vsi_tekmovalci=cur, izpis=True,
                    sezone=cur, drzave=cur, napaka=None, napakaO=None, tekmovalci=cur, zanimivost=3, username=username,
                    admin=admin,ranki=cur,skupni_sestevek=cur)


@post('/zanimivosti/4')
def zanimivosti_post_4():
    if (request.forms.adminPassword != "") or (request.forms.password != ""):
        postani_admin()

    username = get_user()
    admin = is_admin(username)
    cur.execute("SELECT fis_code,ime,priimek FROM tekmovalec ORDER BY priimek,ime")
    vsi_tekmovalci = cur.fetchall()
    tekmovalec = request.forms.tekmovalec
    zacetna = request.forms.sezona41
    koncna = request.forms.sezona42
    cur.execute("WITH umesna AS (SELECT id,ranki FROM rezultat JOIN tekma USING (id) "
                "WHERE fis_code=%s AND datum BETWEEN %s AND %s GROUP BY id,ranki)"
                "SELECT ranki,count(*) FROM umesna GROUP BY ranki ORDER BY ranki",[int(tekmovalec.split(' - ')[0]),
                                                                                   datetime.date(int(zacetna) - 1, 11, 1),
                                                                                   datetime.date(int(koncna), 3, 31)])
    ranki=cur.fetchall()
    ime3 = tekmovalec.split('-')[1]
    id = int(tekmovalec.split('-')[0])
    return template('zanimivosti.html',tekmovalec=tekmovalec,id=id,ime3=ime3,zacetna=zacetna,koncna=koncna,izbrana=True,ranki=ranki,izpis=True,zanimivost=4,napaka=None,napakaO=None,admin=admin,username=username,
                    tekmovalci_dolzina=cur,dolzina='',tekme_boljsi=cur,vsi_tekmovalci=vsi_tekmovalci,sezone=sezone(),drzave=cur,tekmovalci=cur,skupni_sestevek=cur)

@post('/zanimivosti/5')
def zanimivosti_post_5():
    if (request.forms.adminPassword != "") or (request.forms.password != ""):
        postani_admin()

    username = get_user()
    admin = is_admin(username)
    sezona = request.forms.sezona_skupni
    cur.execute("WITH umesna3 AS (WITH umesna2 AS (WITH umesna AS (SELECT id, ranki, fis_code FROM rezultat JOIN tekma USING (id) "
                "WHERE datum BETWEEN %s AND %s AND tip_tekme = 'posamicna' GROUP BY id, ranki, fis_code ORDER BY id,ranki)"
                "SELECT tocke,fis_code, count(*) AS stevilo FROM umesna JOIN tocke USING(ranki) GROUP BY tocke,fis_code)"
                "SELECT fis_code, sum(stevilo*tocke) AS sestevek FROM umesna2 GROUP BY fis_code)"
                "SELECT fis_code, ime, priimek, sestevek FROM umesna3 JOIN tekmovalec USING(fis_code) ORDER BY sestevek DESC",
                [datetime.date(int(sezona) - 1, 11, 1), datetime.date(int(sezona), 3, 31)])
    skupni_sestevek = cur.fetchall()
    return template('zanimivosti.html',sezona=sezona,izbrana=True,skupni_sestevek=skupni_sestevek,sezone=sezone(),izpis=True,zanimivost=5,napaka=None,
                    napakaO=None,admin=admin,username=username,ranki=cur,tekmovalci_dolzina=cur,dolzina='',tekme_boljsi=cur,
                    vsi_tekmovalci=cur,drzave=cur,tekmovalci=cur)

@get('/najljubsi')
def najljubsi_get(napaka=None):
    username = get_user()
    admin = is_admin(username)

    cur.execute("SELECT fis_code,ime,priimek FROM tekmovalec ORDER BY priimek,ime")
    vsi_tekmovalci = cur.fetchall()

    list_najljubsih = najljubsi(username)

    if list_najljubsih == []:
        napaka = 'Nimate še dodanih najljubših tekmovalcev.'
        izrisi = False
        cur.execute("SELECT * FROM tekmovalec")
    else:
        stringFC = ','.join(map(str,list_najljubsih))
        cur.execute("SELECT * FROM tekmovalec WHERE fis_code IN (" + stringFC + ")")
        izrisi = True
    tekmovalci = cur.fetchall()
    return template('najljubsi.html', tekmovalci=tekmovalci, sezone=sezone(), izrisi = izrisi, napakaO=None, napaka=napaka, username=username,
                    admin=admin, vsi_tekmovalci=vsi_tekmovalci)


@post('/najljubsi')
def najljubsi_post():
    dodaj = request.forms.tekmovalec
    if dodaj != '':
        dodaj = dodaj.split('-')
        dodaj = int(dodaj[0])
        cur.execute("SELECT * FROM tekmovalec WHERE fis_code = %s", [dodaj])
        try:
            if len(cur.fetchone()) > 0:
                username = get_user()
                stringFC = najljubsi(username)
                if dodaj not in stringFC:
                    if stringFC != []:
                        cur.execute("UPDATE uporabnik SET najljubsi_tekmovalci = %s WHERE username = %s",
                                    [','.join(map(str, stringFC)) + ',' + str(dodaj) + ',', username])
                    else:
                        cur.execute("UPDATE uporabnik SET najljubsi_tekmovalci = %s WHERE username = %s", [str(dodaj) + ',', username])
                    napaka = 'Tekmovalec je bil uspešno dodan med najljubše'
                else:
                    napaka = 'Ta tekmovalec je že med tvojimi priljubljenimi.'
        except:
            napaka = 'Ne obstaja tekmovalec s to fis kodo'
    else:
        napaka = 'Izberite tekmovalca.'

    najljubsi_get(napaka)
    redirect('/najljubsi')

@post('/dodaj/:x/')
def dodaj(x):
    x = int(x)
    username = get_user()
    dodaj = request.forms.dodaj
    naj = najljubsi(username)
    if dodaj == "ne":
        i = naj.index(x)
        naj.pop(i)
        if len(naj)==0:
            cur.execute("UPDATE uporabnik SET najljubsi_tekmovalci = NULL WHERE username=%s",[username])
        else:
            naj_str = ','.join(map(str,naj)) + ','
            cur.execute("UPDATE uporabnik SET najljubsi_tekmovalci = %s WHERE username = %s", [naj_str, username])
    else:
        if len(naj)==0:
            naj_str = str(x) + ','
        else:
            naj_str = ','.join(map(str,naj)) + ',' + str(x) + ','
        cur.execute("UPDATE uporabnik SET najljubsi_tekmovalci = %s WHERE username = %s", [naj_str, username])
    redirect("/tekmovalec/{}/".format(x))


######################################################################
# Glavni program

# priklopimo se na bazo
conn = psycopg2.connect(database=auth.db, host=auth.host, user=auth.user, password=auth.password)
conn.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT) # onemogočimo transakcije
cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor) 

# poženemo strežnik na portu 8080, glej http://localhost:8000/
run(host='localhost', port=8000, reloader=True)
