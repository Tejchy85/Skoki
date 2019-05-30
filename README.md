# Skoki
##Projekt pri predmetu Osnove podatkovnih baz na Fakulteti za matematiko in fiziko: Martin Dolenc, Petra Podlogar, Teja Škvarč

Na repozitoriju se nahaja enostavna spletna aplikacija, ki je namenjena pregledu rezultatov tekem, tekmovalcev, držav in njihovih uspehov med sezonami 2009 in 2019.

Če želite dostopati do spletne aplikacije, morate najprej sklonirati repozitorij in nato pognati datoteko main.py. Spletna aplikacija je dostopna na naslovu http://localhost:8000/ . 

Neprijavljeni uporabniki lahko dostopajo do tekem in rezultatov. Prav tako si lahko pogledajo seznam tekmovalcev in njihove podatke ter podatke o državah. Ne morejo pa dostopati do zanimivosti, te privilegije imajo samo prijavljeni obiskovalci. 
Prijavljeni obiskovalec ima možnost dodajanja priljubljenih tekmovalcev. 
Če se uporabnik registrira kot admin (za to potrebuje dodatno geslo - '1111') ali pa kasneje svoj račun nadgradi v administratorskega, ima omogočeno dodajanje novih tekem, držav in tekmovalcev. 

Primeri uporabniških imen ter gesel: 

(navadni uporabnik) <br />
upo. ime: navadni <br />
geslo: NaVaDnI

(administrator) <br />
upo. ime: admin <br />
geslo: AdMiN <br />
admin geslo: 1111


Prilagamo še sliko ER-diagrama, na podlagi katerega smo oblikovali našo podatkovno bazo.
![alt text](ER-diagram.png)
