# Mercati: 59 bozze salvate nell'archivio locale

Il 30 ottobre 2026, su richiesta del proprietario di collegarsi e proseguire
direttamente, il coordinatore ha utilizzato l'API del pannello sulla porta 5182
per preparare e salvare il lotto reale. Non è una simulazione su un database
temporaneo e non è una pubblicazione online.

- Archivio SQLite locale: revisione amministrativa da **0 a 1**.
- **59 pratiche preparate e collegate alle rispettive bozze**: 13 più complete,
  46 con verifiche residue, tutte con `publicationReady=false`.
- **19 aggiornamenti** mantengono gli ID esistenti; **40 nuove bozze** portano
  l'archivio a 100 identità uniche. Le 60 identità iniziali sono conservate.
- Le 176 date già archiviate restano identiche. Le bozze nuove aggiungono
  37 date proposte, per 213 date amministrative. Le proposte relative alle
  schede già esistenti restano da riconciliare con il calendario, senza
  sostituirlo automaticamente o duplicare le edizioni.
- La revisione pubblica resta **0**: confronto integrale dello snapshot prima
  e dopo riuscito, con 53 schede e 161 date pubbliche invariate.
- Fonti, limiti, classificazione 13/46 e altre evidenze delle 59 pratiche sono
  stati confrontati dopo il salvataggio e conservati.

Il pannello ora mostra **Apri bozza preparata** per le pratiche lavorate.
Riaprirle restituisce la bozza salvata, preservando le successive correzioni
editoriali anziché riapplicare la proposta iniziale. Anche il normale salvataggio
di una scheda aggiorna lo stato e il collegamento della sua pratica.

Sono stati usati gli helper reali del pannello, la validazione del server e un
solo salvataggio atomico con revisione attesa, motivo e ID dell'operazione.
I file prima/dopo e la richiesta, senza credenziale, rimangono nell'area locale
ignorata `.dev-logs/markets/preparation-20261030/`; il server conserva anche lo
storico della revisione. L'evidenza condivisibile è nel
[riepilogo JSON](evidence/MERCATI_BOZZE_PREPARATE_20261030.json).

Verifica pannello: **165 test in 29 file PASS**, comprese le regressioni su
riapertura senza sovrascrittura e collegamento della pratica. Il browser di
automazione continua a restituire `The browser access host is unavailable`:
non è stata attestata l'interazione visiva con la pagina aperta dall'utente.
Il raggio resta nel ramo separato; codice e dati online, Web distribuita,
Android, permessi Firebase e Firestore remoto non sono stati modificati.
