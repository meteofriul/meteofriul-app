# Handoff privacy e Data Safety per Territorio

Stato: **gate riaperto dalla reputazione pseudonima: privacy pubblica, Data Safety e TTL cloud da aggiornare prima della distribuzione ufficiale**
Data decisione: 18 settembre 2026
Perimetro: segnalazioni UGC di Territorio, privacy IT/FUR e dichiarazione Google
Play Data Safety. Questo documento non autorizza modifiche a Play Console,
generazione AAB o pubblicazione della landing.

## 1. Esito del confronto landing

Le sorgenti della landing sono nel repository separato identificato come
`meteofriul-landing`, non richiesto dal runtime di questa app:

- `public/privacy/index.html`;
- `public/fur/privacy/index.html`.

Le pagine pubbliche verificate in sola lettura sono:

- `https://meteofriul.it/privacy/`;
- `https://meteofriul.it/fur/privacy/`.

Il 25 agosto entrambe le pagine pubbliche sono state rilette direttamente via
HTTPS senza cache: espongono il nuovo contratto Territorio in italiano e
friulano. Le sorgenti del 25 agosto rimuovono inoltre i riferimenti a digest,
log ed email automatiche di moderazione, che non sono trattamenti attivi della
prima beta e non richiedono job, scheduler, policy Monitoring o canali email.

| Tema | Pagina pubblica corrente | Stato |
| --- | --- | --- |
| Identificazione antiabuso | `client_id` casuale locale, chiavi pseudonime backend e normale trattamento tecnico di rete separato | conforme |
| Dato pubblico | fenomeno predefinito, Comune/zona canonica, orario e scadenza; mai GPS preciso | conforme |
| Fonte pseudonima | chiave opaca a rotazione giornaliera, resa nell'app come alias | conforme |
| Azioni degli utenti | conferma, smentita, flag categoriale e blocco locale della fonte | conforme |
| Sicurezza community | hide locale immediato, scadenza automatica e intervento globale manuale eventuale | conforme |
| Retention | orizzonti effimeri gia' pubblicati; nuovo ledger reputazione a 365 giorni non ancora pubblicato | **da aggiornare** |
| Responsabile tecnico | Google Cloud/Firebase per backend, Firestore e App Check | conforme |
| Friulano | contratto aggiornato e pubblicato; l'italiano resta il testo di riferimento | conforme per la beta; ulteriori affinamenti linguistici restano editoriali |

L'indirizzo IP puo' essere trattato nei normali log di rete e sicurezza dei
fornitori, come gia' dichiarato nella sezione generale della privacy. Non va
pero' attribuita al runtime UGC una combinazione `IP + ID installazione` che il
codice corrente non esegue.

## 2. Dati UGC da dichiarare

La privacy IT/FUR deve elencare in modo comprensibile:

- il fenomeno scelto fra le otto categorie chiuse;
- il Comune/zona canonica, l'orario di invio e la scadenza del report;
- l'uso transitorio delle coordinate precise per verificare FVG, distanza e
  Comune; nel report viene memorizzato il centro canonico del Comune, non il fix
  GPS dell'utente, e non viene creata una cronologia degli spostamenti;
- un `client_id` casuale creato e conservato localmente, trasmesso nelle sole
  mutazioni, e le chiavi/hash pseudonimi scoped derivati dal backend, usati per
  proprieta' temporanea del report, cooldown, deduplicazione, conferme, flag,
  antiabuso e blocchi
  amministrativi eventuali; non e' un account o una registrazione pubblica del
  dispositivo, ma resta un identificatore pseudonimo da dichiarare;
- una chiave pubblica opaca della fonte che ruota per finestre giornaliere e
  viene trasformata localmente in un alias; non sono pubblicati identificativo
  di installazione, hash interno, nome, e-mail o account;
- conferme e smentite del fenomeno;
- flag con motivo chiuso `inaccurate`, `duplicate` o `misuse` e relativo target;
- eventuali decisioni manuali temporanee di hide o blocco fonte;
- punti convalidati, rango e riferimenti di episodio hashati conservati in un
  ledger privato pseudonimo; nessun punto e' pubblico e nessun `client_id`
  grezzo viene scritto nel ledger;
- assenza di recupero o trasferimento del rango: cancellando il `client_id`
  locale o cambiando installazione il vecchio ledger non e' piu' raggiungibile
  dall'utente e non viene collegato alla nuova identita', ma resta soggetto
  alla propria scadenza TTL sul backend;
- blocchi di contenuto/fonte scelti dall'utente, conservati soltanto sul suo
  dispositivo e non inviati al backend.

Prima dell'invio l'interfaccia deve continuare a spiegare che fenomeno e Comune
saranno visibili agli altri utenti per circa un'ora. Google Cloud e Firebase
operano come fornitori/responsabili tecnici per backend, Firestore e App Check;
i dati non sono usati per pubblicita', vendita o profilazione.

## 3. Retention da riportare senza semplificazioni fuorvianti

| Dato | Orizzonte applicativo |
| --- | ---: |
| report pubblico e collegamento interno alla fonte | 60 minuti |
| cooldown per installazione/fonte | 45 minuti |
| conferme e smentite | fino alla scadenza dell'ultimo report attivo del gruppo; ogni report dura 60 minuti e un report successivo nello stesso bucket orario puo' estendere il documento, comunque non oltre due ore dall'inizio del bucket |
| flag e snapshot privato del target | 24 ore dal flag |
| stato tecnico aggregato del flag e dell'eventuale intervento manuale | 24 ore dall'ultimo flag |
| blocco amministrativo della fonte | 24 ore |
| contatori tecnici di rate limit | durata della finestra piu' margine tecnico, massimo 2 ore |
| riepilogo reputazione | 365 giorni dall'ultimo invio, convalida o revoca dell'installazione; include il totale reale degli invii accettati e alla scadenza e' ignorato subito dal servizio |
| singola assegnazione reputazione | 365 giorni dalla convalida o revoca del relativo episodio; alla scadenza non blocca una nuova idempotenza |
| blocchi locali sul dispositivo | fino alla rotazione giornaliera, massimo 24 ore |

Ogni documento Firestore deve avere `expires_at_timestamp` e una policy TTL
`ACTIVE`. Allo scadere il dato viene escluso subito dal servizio; la rimozione
fisica eseguita da Firestore e' asincrona e puo' avvenire successivamente. La
privacy non deve promettere cancellazione fisica istantanea. Il gate resta
rosso fino a read-back cloud, controllo dei documenti correnti e campione reale
degli orizzonti.

La collection `community_moderation_digest_state` e il relativo codice possono
restare come contingenza dormiente, con policy TTL a 48 ore, ma non vengono
prodotti dal flusso ordinario della prima beta e non vanno descritti come
trattamento attivo. Non sono richiesti ne' attivi job, scheduler, evento
`community_moderation_digest_ready`, canale Monitoring o email automatiche di
moderazione. Prima di una futura attivazione serviranno una nuova decisione e
l'aggiornamento preventivo di privacy, Data Safety, retention dei log e del
canale di consegna.

## 4. Mappatura prudenziale Google Play Data Safety

La compilazione finale spetta al titolare, ma non deve omettere i dati
pseudonimi solo perche' non esiste un account.

| Categoria Play | Dato/uso | Raccolto | Condiviso pubblicamente |
| --- | --- | --- | --- |
| Posizione precisa | fix trasmesso al backend e usato transitoriamente per convalida e Comune | si, opzionale/effimero, funzionalita' | no |
| Posizione approssimativa | Comune/zona canonica del report | si, opzionale, funzionalita' | si, per azione esplicita dell'utente |
| Altri contenuti generati dagli utenti | fenomeno predefinito, orario e scadenza | si, opzionale, funzionalita' | si, per azione esplicita dell'utente |
| Attivita' nell'app / altre azioni | conferme, smentite e flag | si, opzionale, funzionalita' e sicurezza | no |
| ID dispositivo o altri ID | `client_id` pseudonimo e hash derivati, incluso il ledger privato di rango; nessun registro pubblico del dispositivo | si, opzionale, funzionalita', sicurezza e prevenzione abusi | no |

Google Cloud/Firebase tratta i dati per conto del titolare. L'eventuale
eccezione Data Safety per il service provider non elimina l'obbligo di
dichiarare la raccolta. I blocchi che restano soltanto nel dispositivo non sono
raccolti dal progetto.

## 5. Stato linguistico FUR

La versione friulana aggiornata e' pubblica e collegata alla versione italiana,
che resta il testo di riferimento. Un ulteriore controllo linguistico umano e'
raccomandato come manutenzione editoriale, ma non modifica il trattamento, il
contratto tecnico o il contenuto informativo necessario alla prima beta.

Nel copy tecnico corrente richiedono controllo almeno:

- `Lineis guide community`;
- `par chei altris utents`;
- `gjavadis o platadis blocant la font anonime`;
- `rinovament zornalîr`.

Sono note di affinamento editoriale futuro, non blocker tecnici del rilascio.

## 6. Gate di consegna landing

Prima dell'AAB devono essere completati e verificati tutti i punti:

- [x] preparare le sorgenti IT/FUR aggiornate nel repository landing separato;
- [x] non descrivere digest, log o email automatiche di moderazione come
  trattamenti attivi della prima beta;
- [x] descrivere il `client_id` locale e gli hash server-side come pseudonimi,
  senza promettere l'assenza totale di identificatori;
- [x] approvare editorialmente il testo italiano di riferimento;
- [x] pubblicare la traduzione friulana, mantenendo l'italiano come riferimento;
- [x] aggiornare data/versione dell'informativa al 25 agosto 2026;
- [x] pubblicare entrambe le pagine;
- [x] confrontare via HTTPS le pagine pubbliche senza cache;
- [x] verificare che l'app apra le URL aggiornate;
- [ ] aggiornare e ripubblicare privacy IT/FUR con finalita', dati e retention
  del rango pseudonimo, poi verificarle via HTTPS senza cache;
- [ ] riportare la stessa mappatura nella Data Safety di Play Console;
- [ ] attivare e verificare le policy TTL di `community_reputation` e
  `community_reputation_awards`, poi rigenerare l'evidenza LIVE a dieci
  collection, distinta dal gate outbox push.
