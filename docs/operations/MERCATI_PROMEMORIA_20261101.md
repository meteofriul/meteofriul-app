# Mercati: promemoria nel pannello ed email — 1 novembre 2026

## Stato operativo verificato

Il proprietario ha chiesto un avviso nel pannello e successivamente un
promemoria email inviato dal sistema Meteo Friûl. Destinatario indicato:
`info@meteofriul.it`, modificabile nel pannello. Nessun collegamento a calendari
esterni e nessuna email inviata.

La sezione **Scopri → Mercati e mercatini → Verifiche** è disponibile nel
pannello locale 5182. Mantiene una sola scheda/fonte visibile, con selettori e
impostazioni email richiudibili. La scheda di modifica del mercato conserva
gli spazi compatti precedenti. Il rendering reale nel browser resta da
osservare; moduli serviti HTTP 200, test di rendering statico e build superati.

Scadenza: primo lunedì del mese alle **09:00 Europe/Rome**, a partire dal
**2 novembre 2026**. Approfondimento ogni tre mesi da febbraio 2027. Le scadenze
non concluse restano visibili; se si salta un trimestre, il controllo più ampio
non viene perso. La chiusura richiede una nota di esito conservata nello storico
e non cambia verifiche, note, stato editoriale o pubblicazione dei mercati.

La coda comprende **98 schede** al momento della rilettura: usa i risultati
persistenti di ciascun mercato, conservando quelli non inclusi nell'ultimo
lotto automatico. Comprende anche i conflitti già annotati nelle schede.
Questi limiti non indicano necessariamente mercati cessati o dati errati.

## Email: destinatario salvato, invio ancora da attivare

In **Verifiche → Promemoria email** si possono cambiare il destinatario,
attivare/disattivare la richiesta del promemoria e leggere l'ultimo esito.
Il pannello distingue il salvataggio della preferenza dal collegamento
effettivo della casella mittente. Attualmente indica **invio da collegare**:
non sono disponibili credenziali SMTP e il task email non è registrato.

Il salvataggio iniziale autorizzato del destinatario ha portato l'archivio
amministrativo dalla revisione **5 alla 6**. Backup SQLite consistente prima
della modifica e confronto integrale successivo: mercati, edizioni, pratiche,
ledger automatico, note, catalogo pubblico e storico precedente invariati.
Restano **100 mercati, 219 edizioni, 59 pratiche**, revisione pubblica **0**.

I DNS pubblici del dominio indicano MX `mx.meteofriul.it` e SPF Aruba. È un
indizio del gestore, non una prova di accesso alla casella. Sono predisposti
i [parametri ufficiali Aruba](https://guide.aruba.it/hosting-e-domini/email/configurazione-posta/parametri-configurazione-posta),
SMTP TLS implicito su `smtps.aruba.it:465`; host e mittente possono essere
specificati al comando di configurazione. Nessun contatto SMTP reale eseguito.

Per collegare la casella, dal terminale PowerShell del workspace:

```powershell
.\scripts\configure-markets-reminder-email.ps1 -Configure
```

Il comando richiede la password direttamente nella console, verifica prima
il solo accesso SMTP e poi salva la credenziale protetta da Windows per lo
stesso utente/PC, sotto `.dev-logs/markets/email/` (ignorato da Git). Password
assente da sorgenti, argomenti del processo, rapporti, API e pannello; passa
soltanto nell'ambiente temporaneo del processo figlio. Un accesso SMTP fallito
non crea file né registra task. Una credenziale già esistente viene preservata.
La verifica della connessione non manda un'email di prova.

Solo dopo il collegamento viene registrato `MeteoFriul-MarketsReminder-Local`,
alle 09:00 e all'accesso Windows. Il processo è nascosto, richiede il PC acceso
e la sessione attiva, recupera una scadenza mancata all'avvio successivo.
Non è un invio cloud a PC spento. Il task di aggiornamento automatico delle
fonti delle 08:20 è già attivo e non è stato modificato.

## Invio e conservazione

Una email per periodo ancora da rivedere, con quantità di schede segnalate e
indicazioni per aprire Verifiche. Nessuna credenziale, nota privata o ricerca
completa viene inclusa. Il destinatario è letto dall'archivio al momento
dell'invio, non fissato nello script.

Una prenotazione transazionale persistente impedisce doppioni concorrenti.
Errori certi consentono un nuovo tentativo il giorno successivo, secondo il
giorno italiano. Una modifica al destinatario, una disattivazione o una
revisione conclusa prima dell'invio annullano il tentativo ancora in preparazione.
Un esito incerto dopo l'inizio dell'invio non viene ritentato automaticamente
nello stesso mese. L'accettazione SMTP non viene descritta come consegna
accertata nella casella.

Le preferenze e gli esiti vivono fuori dallo stato delle schede: i salvataggi
ordinari e il refresh non possono falsificarli o cancellarli. Mutazioni con
revisione attesa, ricevute idempotenti, autenticazione amministrativa dedicata
e risposta `no-store`. Le sole nuove route sono `POST /review-complete` e
`PUT /email-settings`, sotto `/api/admin/markets`.

## Verifiche

- **119 test backend PASS**, inclusi 7 per il promemoria e 20 per email,
  autorizzazione, concorrenza, retry, privacy e conservazione dei dati.
- **27 test mirati pannello PASS**, lint PASS, build in OS TEMP PASS (1956 moduli;
  consueto avviso chunk non bloccante).
- `compileall`, sintassi dei tre script PowerShell e controllo diff PASS.
- Consegna nel progetto esterno con guardia SHA-256 contro modifiche concorrenti
  e copie degli originali; API 8003 riavviata con verifica del processo.
- Rilettura autenticata: destinatario impostato, nessun mittente configurato,
  nessun esito di invio, prossimo promemoria 2 novembre 09:00, 98 schede.
- Credenziali SMTP, connessione reale, esecuzione del futuro task email e
  ricezione in casella restano da verificare dopo il collegamento.

Evidenze ignorate locali: `.tmp/markets-reminder-delivery-20261101.json`,
`.tmp/markets-email-delivery-20261101.json`,
`.tmp/markets-email-settings-receipt-20261101.json` e
`.tmp/markets-email-build-20261101.txt`.

Nessun commit, push, promozione a main, deploy, cambio di release, artefatto
Android/Web o pubblicazione applicativa. La pubblicazione Mercati resta bloccata.
