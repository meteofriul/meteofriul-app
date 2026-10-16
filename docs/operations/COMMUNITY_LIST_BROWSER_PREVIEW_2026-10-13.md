# Elenco unico: anteprima browser — 13 ottobre 2026

Richiesta del proprietario: mantenere la UX precedente e mostrare un solo elenco
scorrevole delle ultime 48 ore, senza aggiungere pulsanti. Proposta visiva sul
ramo `codex/community-reports-simplification`, non implementazione dello storico.

Aprire `http://127.0.0.1:5174/community-list-preview.html` con il pilot canonico
avviato tramite `scripts/start-local-weather-pilot.ps1 -CommunityPilot`, quindi
Meteo → Tempo reale. Si riutilizzano App, mappa, pannello, righe e dettaglio reali.
La pagina parte dalla mappa come l'app precedente. Aprendo Segnalazioni compare
il pannello compatto con una sola riga; premendo il titolo «Recenti» si alza
l'elenco e premendolo ancora si riduce. La maniglia permette di alzarlo o
abbassarlo trascinando, con le altezze già usate dall'app. Sono nascosti i due
selettori Recenti/Storico; resta la dicitura «Ultime 48 ore». Scorrimento diretto
dell'elenco espanso senza «Carica altro».

Le segnalazioni attive provengono dalla TEST locale; le otto righe passate sono
esempi in memoria, dalla più recente a quella di 47 ore e 55 minuti prima.
Scadute e sostituite sono prive di azioni. Nessuna scrittura di questi esempi
nel database. Il caricamento automatico delle vere pagine dello storico resta
da implementare dopo la valutazione dell'anteprima. I controlli esistenti
dell'app rimangono quelli della TEST locale.

Attivazione limitata a Vite DEV, host loopback e percorso dell'anteprima.
L'entry non fa parte degli input della build. La pagina normale `/` e le APK
conservano l'interfaccia corrente. Nessuna installazione su telefono per questa
anteprima; nessun aggiornamento di main, GitHub, Play o produzione.

Verifiche nel browser: lista scorsa fino al messaggio finale delle 48 ore,
apertura e chiusura del dettaglio attivo con le azioni precedenti, pulsante
Segnala visibile anche nella finestra 1280 × 720. Test di integrazione del
pannello e lettura segnalazioni: 56 PASS. Schermata locale in
`.tmp/community-list-preview/elenco-unico.jpg`.

Correzione successiva richiesta dal proprietario: verificati nel browser anche
avvio sulla mappa, apertura compatta con una sola riga, espansione e riduzione
premendo «Recenti», trascinamento della maniglia in entrambe le direzioni.
Ripetuti i 56 test, tutti PASS. Schermate aggiornate `compatto.jpg` e
`espanso.jpg` nella stessa cartella locale; anteprima lasciata compatta.

La build Android verticale avviata prima della richiesta di anteprima è
terminata: candidata `881c0eba67bc601eb41cc902c2e02d6e5187f335`, SHA-256
`b07f51fc7e0b67de99dd7285530ec68133d430f2d64f199530d45c349ec68eb3`.
Questa nuova APK non è ancora installata o verificata a runtime: il lavoro
successivo si è concentrato sull'anteprima browser richiesta dal proprietario.

## Punto di ripresa — sessione chiusa il 13 ottobre

Il proprietario ha chiesto di fermarsi e continuare il 14 ottobre. Ultima
modifica verificata: `a2376a6f`, pannello compatto, «Recenti» per espanderlo,
maniglia per alzarlo e abbassarlo. Tutto salvato in commit locali del ramo
segnalazioni; main resta `5a68de5dc1607105f921d4d2b731170f1a8a0446`.

Alla ripresa: valutare questa anteprima e collegare l'elenco ai veri dati delle
48 ore se confermata la soluzione. Resta inoltre da installare e collaudare la
candidata Android verticale sopra identificata; il collaudo precedente del
telefono è in `COMMUNITY_REPORTS_PHONE_TEST_2026-10-13.md`. Non considerare
completati il runtime della nuova candidata, R8 minificato o il riscontro su
dispositivo fisico Android 15 del contrasto dei tre tasti.

Chiusura verificata: scheda di anteprima chiusa; servizi locali sulle porte
5174, 8002, 8781 e 8783 arrestati; server ADB 5037/5038 e daemon Gradle fermati.
Nessun emulatore era ancora in esecuzione. Nessuna delle porte TEST controllate
resta in ascolto. Database `.dev-logs/community-pilot/state.sqlite3` conservato,
`PRAGMA quick_check` restituisce `ok`. APK e schermate locali conservate.
Nessuna operazione su main, GitHub, Play o servizi cloud.

## Ripresa del 14 ottobre

Pilot riavviato con `scripts/start-local-weather-pilot.ps1 -CommunityPilot
-WeatherTestNow 2026-09-04T12:00:00Z`, database Community conservato. Riaperta
`community-list-preview.html`, sul pannello Segnalazioni compatto.

Con tutte le segnalazioni reali del giorno precedente scadute, la classe del
pannello vuoto riduceva l'altezza anche in presenza della prima riga di esempio
dello storico, tagliandola. Corretto il calcolo per considerare anche le righe
passate dell'anteprima. Nessuna variazione alla pagina normale o alle APK.
Verificati visivamente riga completa, pulsante Segnala e apertura/riduzione con
«Recenti» anche senza segnalazioni attive. Test del pannello: 56 PASS.
Schermata `.tmp/community-list-preview/compatto-2026-10-14.jpg`.

Il collegamento dell'elenco unico ai dati reali delle 48 ore e le prove Android
pendenti descritte sopra restano da completare.

Su richiesta del proprietario, assottigliata la riga «Recenti · Ultime 48 ore»
nella sola anteprima: altezza da 44 a 28 px, distanza dalla lista da 9 a 5 px,
pannello compatto da 260 a 240 px. Recuperati 20 px per la mappa mantenendo
intera la prima scheda e invariato il pulsante Segnala. Verificati nel browser
a 588 × 902 apertura e riduzione premendo «Recenti»; lasciato il pannello
compatto. Schermata `.tmp/community-list-preview/compatto-sottile-2026-10-14.jpg`.
Verifica visiva e `git diff --check`; nessuna nuova build Android.

Secondo affinamento richiesto sul pannello intero: altezza compatta da 240 a
216 px, spazi interni ridotti e prima scheda da 68 a 60 px. Le tab conservano
44 px di area verticale, il pulsante Segnala resta alto 48 px e i caratteri
non cambiano dimensione. A 588 × 902 verificati assenza di tagli, apertura con
«Recenti» e chiusura dalla maniglia. Intervento limitato al CSS dell'anteprima.
Schermata `.tmp/community-list-preview/pannello-compatto-2026-10-14.jpg`.

## Integrazione approvata nella TEST — 14 ottobre

Il proprietario ha approvato il pannello compatto e il collegamento alle vere
segnalazioni delle ultime 48 ore. Il prototipo è ora sostituito dalla vera app
TEST, mantenendo apertura con «Recenti», maniglia e misure approvate; nessuna
riga di esempio. Integrata anche la candidata Eventi `f7fe8e96` con un backend
locale dedicato. Main e produzione invariati.

Il [resoconto di integrazione](COMMUNITY_EVENTS_TEST_INTEGRATION_2026-10-14.md)
registra commit, nuova APK, collaudo browser, raccolta reale Eventi, evidenze e
verifiche Android ancora pendenti. Le precedenti note sul prototipo descrivono
le fasi storiche, non lo stato attuale.
