# Mercati: commit, backup e copia remota — 1 novembre 2026

Il proprietario ha autorizzato commit, backup dell'archivio, push dei rami
di lavoro e completamento dei gitignore. Le modifiche Mercati sono salvate
nei due repository; non è stata effettuata alcuna promozione o pubblicazione.

## Sorgenti salvati e verificati sul remoto

| Repository | Ramo | Commit funzionale |
| --- | --- | --- |
| App/backend | `codex/mercati-integration-20261028` | [`f0e28d7c`](https://github.com/meteofriul/meteofriul-app/commit/f0e28d7ccba079225e093c85526dd6a2a18944e3) |
| Pannello | `codex/markets-management-20261030` | [`fe4768f`](https://github.com/meteofriul/meteofriul-inserzioni/commit/fe4768ff60f297183a56e50c477dc2e9660d5dea) |

Entrambi i push sono riusciti e gli hash sono stati riletti con `ls-remote`.
Il ramo del pannello ha ora l'upstream e working tree pulito. Nel repository
app sono rimasti fuori dal commit i precedenti lavori del raggio nelle
Impostazioni e i relativi documenti, oltre ai resoconti ICON e dell'audit job.
Le sezioni dei documenti condivisi sono state inserite selettivamente
nell'indice, lasciando intatti i contenuti estranei nel working tree.
Il commit che contiene questo verbale registra separatamente il checkpoint.

Nessuna PR aperta sul ramo app al controllo successivo al push. I trigger
esistenti non avviano la CI per un normale push su `codex/**`; non è stata
richiesta una corsa remota. Il pannello non contiene workflow Actions.
Nessun merge a main, deploy, nuova build Android o pubblicazione Web.

## Backup locale separato da Git

Directory: `.dev-logs/markets/backups/checkpoint-20261101T143044Z/`.
Contiene 77 file modificati/non tracciati nei due progetti con manifest SHA-256,
compresi i lavori lasciati fuori dai commit Mercati, e una copia SQLite ottenuta
tramite API di backup consistente. Non contiene la credenziale amministrativa
né password SMTP. È una copia sullo stesso PC, non un backup del database su
GitHub o su un dispositivo esterno.

- Revisione amministrativa **6**, revisione pubblica **0**.
- **100 mercati, 219 edizioni e 59 pratiche**.
- `PRAGMA quick_check` e checksum del payload: PASS.
- SHA-256 copia SQLite:
  `643b7f3985b2fa67e773d79f463ec8cb474cbd5785452c084ac10b2e68c613a8`.

Il backup conserva anche preferenze dei promemoria e storico delle revisioni;
non effettua modifiche alle schede e non sostituisce l'archivio operativo.

## Esclusioni e controlli privacy

I due `.gitignore` escludono database SQLite e relativi journal WAL/SHM,
copie `.db`, file del token locale, credenziali Windows XML/CLIXML, configurazione
SMTP locale, file `.env`, log, cache e cartelle temporanee. Nel pannello sono
state aggiunte le esclusioni locali che mancavano. Gli esempi `.env.example`
restano versionabili. Non sono stati cancellati file locali o chiavi.

Undici percorsi campione privati per ciascun repository risultano ignorati;
il token amministrativo effettivo non compare nei file dei commit. I log
storici di verifica già intenzionalmente versionati nell'app restano conservati
e non fanno parte di questo salvataggio. Non sono stati aggiunti database,
backup, token o credenziali ai repository.

Il pre-push privacy esterno dell'app è rimasto attivo e il push ha superato
il controllo. La scansione della cronologia del pannello (50 commit) ha
segnalato un solo valore: la chiave Firebase della configurazione browser in
un commit già presente in `origin/main`, non modificata da questo lavoro.
È il caso di [configurazione client pubblica documentato da Firebase](https://firebase.google.com/docs/projects/api-keys);
nessuna nuova credenziale privata rilevata. Nessuna eccezione aggiunta ai guard
e nessuna riscrittura della cronologia.

## Verifiche e attività ancora aperte

- Pannello: **194/194 test PASS**, 33 file, Node 22.17.1, configurazione nativa,
  due worker; lint PASS. 106 file sorgente/asset/config corrispondono alla copia
  verificata. Regole Storage non modificate e test con emulatori non ripetuti.
- Backend: mantenuta la prova **119/119 PASS** del passaggio precedente;
  nessuna successiva modifica del codice applicativo durante questo checkpoint.
- Ultima build pannello PASS a codice invariato; diff check e pulizia del
  workspace canonico PASS. Nessuna nuova prova visiva del promemoria.
- Destinatario email salvato e modificabile; collegamento SMTP e task email
  ancora da configurare, nessuna email inviata.
- GitHub ha riportato due avvisi Dependabot sul ramo predefinito dell'app
  (uno alto, uno moderato). Non sono stati analizzati o risolti in questo
  salvataggio; nessuna dipendenza modificata.

Le precedenti frasi «non committato / nessun push» nei verbali del 31 ottobre
e del 1 novembre descrivono le rispettive finestre storiche e sono superate,
per il solo lavoro Mercati qui elencato, da questo checkpoint.
