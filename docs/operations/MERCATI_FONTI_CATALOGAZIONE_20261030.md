# Mercati: fonti e catalogazione del 30 ottobre 2026

Seguito nello stesso giorno: [ricognizione dei 215 comuni](MERCATI_RICOGNIZIONE_COMUNI_20261030.md)
e [contratto proposto per la gestione dal pannello](MERCATI_GESTIONE_PANNELLO_CONTRATTO_20261030.md).
I numeri sotto descrivono questo primo lotto e non il registro territoriale successivo.

Proseguimento della [ricerca del 29 ottobre](MERCATI_COPERTURA_RICERCA_20261029.md)
sul ramo `codex/mercati-integration-20261028`. Base di questo lotto `3f4fbbbb`,
dopo l'allineamento al `main` verificato `e3527f73`: comprende la correzione
tipografica Home e il prerequisito di avvio locale CAMS.

Il [registro delle fonti in JSON](evidence/MERCATI_FONTI_20261030.json) conserva
URL, autore, tipo, pubblicazione quando comprovata, consultazione, accesso,
passaggio pertinente, limiti e collegamenti alle schede. Non viene consumato
dall'app. La ricerca non modifica il catalogo pubblico né approva nuovo copy.

## Risultato del lotto

| Misura | Esito |
|---|---:|
| Fonti catalogate | 51 |
| Fonti con passaggi pertinenti letti | 41 |
| Fonti consultabili soltanto nell'indice | 6 |
| Fonti non acquisite, tentativo documentato | 4 |
| Schede di ricerca approfondite | 44 |
| Riprese dai 74 candidati del 29 ottobre | 24 |
| Riferite a schede già presenti nel JSON applicativo, anche escluse | 9 |
| Nuove candidature di identità/sede | 11 |

Stato delle 44 schede: **10 pronte alla revisione editoriale, 24 da confermare,
9 con conflitti e 1 soltanto storica**. Una scheda pronta alla revisione può
ancora avere orari assenti o avvertenze: non significa approvata per l'app.
Le 11 nuove candidature non sono altrettanti mercati attivi accertati e possono
richiedere deduplicazione. Il registro è un approfondimento selettivo, non la
conversione completa delle 74 candidature precedenti né un censimento regionale.

Sono registrate **22 coppie scheda/data esplicite**: 19 dal 30 ottobre in poi e
3 trascorse. Le 19 future comprendono date in conflitto o da qualificare; non
sono un lotto importabile automaticamente. Fra tutte le date: 17 pubblicate,
1 anticipata, 1 provvisoria e 3 storiche. La qualifica della singola data è
separata da quella dell'intera scheda.

## Riscontri che cambiano la coda di lavoro

### Edizioni puntuali e variazioni

| ID | Riscontro documentato | Limite o azione |
|---|---|---|
| M024, Riuso Udine | La [pagina live PromoTurismoFVG][riuso] annuncia l'anticipo dal 05/12 al **28/11/2026**; UNPLI elenca anche 07/11 | UNPLI conserva 05/12 e l'incoerenza storica su aprile. Valutare la correzione puntuale senza sanare tutta la serie |
| M025, Aviano | [UNPLI][aviano]: **01/11/2026** | Il sito della Pro Loco non è stato acquisito; nessuna data di dicembre dedotta |
| M029, Venzone | [PromoTurismoFVG][venzone]: **08/11/2026**, 08–17, centro storico, anche con maltempo | Candidata alla rivalutazione della singola edizione; non calendario annuale |
| M034, Gemona | [UNPLI][gemona]: **01/11 e 06/12/2026** | Non trasferire la serie 2025 nel 2026; orario non acquisito |
| M037, Sacellum | [Pro Sacile][sacile]: **22/11 e 27/12/2026** | Possibili variazioni della disposizione; **27/12 espressamente modificabile** per esigenze comunali |
| M040, Udine Antiqua | [UNPLI][antiqua]: **15/11 e 20/12/2026** | Le due date future sono leggibili; resta il conflitto storico su aprile |
| M050, Ponterosso usato | [PromoTurismoFVG][ponterosso-usato] corrobora **22/11/2026**, 08:30–tramonto; Discover Trieste elenca anche 27/12 | Non applicare «ultima domenica» a novembre. Sede dettagliata e apertura 08:30 sono della sola edizione 22/11; possibile sospensione per maltempo |
| M027, Cervignano | [Comunicazione della Pro Loco][cervignano] riferibile al 2026 dai metadati | Conferma novembre alla prima domenica, ma nessuna data completa dell'edizione nel testo: `explicit_dates` resta vuoto |

Le **sette date mancanti sulle quattro schede pubbliche** individuate ieri
(M025, M034, M037, M040) sono state ricontrollate. La loro assenza nel runtime
resta invariata: questo lotto prepara fonti e decisioni, non le inserisce.

### Abituali UD/PN

- **Fontanafredda (UP20 / UP-N01):** letta la [pagina comunale del mercato
  cittadino][fontanafredda], giovedì in piazzale San Luca. L'agricolo ha una
  procedura distinta: mercoledì nel bando 2025 contro giovedì nella copia
  regolamentare 2017. Il nuovo PDF collegato non è stato acquisito. Non
  sommare i giorni in una falsa doppia ricorrenza; avvio e continuità da verificare.
- **Cordenons (UP21):** la [delibera 62/2026][cordenons] conferma venerdì e
  piazza della Vittoria, modificando l'assetto 2025. Allegato nuovo non acquisito:
  gli orari 08–13 del testo precedente rimangono storici.
- **Casarsa (UP27):** la [pagina comunale del servizio rifiuti][casarsa]
  distingue mercato 08–13 e sosta vietata 07–14:30; sede piazza Italia/via XXIV
  Maggio. Informazione non datata, da riscontrare per il 2026. San Giovanni
  (UP28) conserva giorno regolamentare ma manca ancora sede puntuale.
- **Moggio (UP15):** il regolamento distingue vendita 08–13 e presenza
  operatori dalle 07. **Pertegada (UP08)** ha vendita 08–13 nella disciplina,
  ma sede e attualità non sono completate. **Tarcento (UP09)** resta senza
  PDF leggibile. Le vecchie norme non provano lo svolgimento di oggi.
- **Tarvisio (UP12):** l'indice dell'app ufficiale espone 07:30 nel calendario
  e 08:00 nel titolo. Anno non esplicito nell'estratto: nessuna data ISO
  aggiunta e nessun arbitraggio dell'orario.
- **Torre e Sacro Cuore (UP29/UP30):** pagina legacy di Torre con slug errato
  e avviso senza anno; affidamento Sacro Cuore documentato solo fino a fine
  2025. Continuità corrente da trovare, senza dedurre chiusure.

### Trieste e Gorizia

- Il [regolamento comunale di Trieste 2025][trieste-reg] e le relative
  [schede cartografiche][trieste-map] aiutano a riconoscere le sedi rionali.
  Sono prove di localizzazione, non un calendario di aperture. Foraggi e via
  dei Mille richiedono ancora riconciliazione; l'assenza da un elenco non
  certifica la cessazione.
- Per **TS09**, l'[avviso ufficiale del Comune][trieste-avviso] documenta il
  trasferimento temporaneo dal 03/06/2026 in piazza Ponterosso, lato Fontana.
  È una decorrenza di sede, non un'edizione. Termine e successivi spostamenti
  da verificare. **TS09 non è M050**, il mercatino dell'usato.
- Il [mensile Coldiretti di settembre, pubblicato il 13/10][coldiretti], p. 30,
  conferma **GO06, coperto di Gorizia**, mar 15–19 e gio/sab 08:30–13 in via
  IX Agosto 4/b. È distinto dal comunale in corso Verdi.
- Lo stesso mensile lascia da riconciliare **GO03 Monfalcone** (07:30–12
  contro 08–13 nella directory), **GO07 Gradisca Unità** (ven 08–13 contro
  08:30–13 e testo mar/gio), **TS10/TS11 San Giacomo/Goldoni** (sabati alterni
  08–13 contro riquadro 08–14). Non è disponibile una sequenza delle sedi.
- **M021**, Campagna Amica di piazza Vittorio Veneto, riceve un riscontro
  recente sul martedì 08–13. **GT-N01** riguarda invece l'Associazione
  Mercatino Agricolo con date di sabato: la sede comune non basta per unire
  le due identità.

## Le 11 nuove candidature

| ID ricerca | Comune e identità | Prova acquisita / prossima azione |
|---|---|---|
| UP-N01 | Fontanafredda, contadino | Bando e versioni normative discordanti; leggere nuovo regolamento ed esito procedura |
| UP-N02 | Tolmezzo, contadino | Pro Loco: lunedì mattina, piazza Centa; conferma corrente e orario mancanti |
| UP-N03 | Rivignano Teor, settimanale | [Bando 2026][rivignano]: lunedì, via Umberto I/piazza Tarabane; pronto alla revisione, orario assente e riassetto previsto da ricontrollare |
| UP-N04 | San Giorgio di Nogaro, settimanale | Regolamento storico: sabato; 07–14 sono limiti legali, non orario effettivo |
| UP-N05 | Tolmezzo, Fiera dei Santi | [Avviso comunale del 29/10][tolmezzo]: **02/11/2026, 08–20**, centro; singola fiera, distinta dall'ordinario e dal contadino |
| N-P01 | Prata di Pordenone, Santa Lucia | [Regolamento Pro Loco 2026][prata]: **13/12/2026**, piazza dell'Indipendenza e Libertà dei Popoli; pronto alla revisione, orario assente |
| N-P02 | Ovaro, Marcjât di San Martin | [PromoTurismoFVG][ovaro]: **11/11/2026**, chiesa S. Martino; qualificare le bancarelle oltre ai chioschi e alla musica |
| N-P03 | Vito d'Asio, Natale | Fonte di un'attività collaterale cita 06/12; il programma del mercato manca: nessuna data importabile |
| N-P04 | Aquileia d'inverno | Fonte territoriale riferita a **08/12/2025**, non 2026: solo pista storica |
| GT-N01 | Trieste, agricolo Associazione Mercatino Agricolo | [Ottobre][ts-agri-ott], [novembre][ts-agri-nov], [dicembre EN][ts-agri-dic]: future **31/10, 14/11, 28/11, 12/12/2026**, 08–14; conservate anche 3 e 17 ottobre trascorsi |
| GT-N02 | Gradisca, Campagna Amica via Regina Elena | Mensile recente: mar 08–13; chiarire autonomia rispetto all'ordinario GO01 prima di creare una scheda |

## Regole di catalogazione e prosecuzione

1. `verified_fields` significa **letto nella fonte**, con limiti e data della
   fonte; non significa automaticamente attuale. `null` e liste vuote
   conservano le lacune. Giorni della settimana in formato ISO, lunedì 1 e
   domenica 7; nessuna data generata da ricorrenze, alternanze o intervalli.
2. Ogni data completa ha `date_evidence` con fonte e qualifica. Pubblicazione,
   adozione del documento, aggiornamento del sito, consultazione, decorrenza
   di trasferimento e appuntamento restano concetti distinti.
3. Le copie indicizzate possono essere precedenti alla risposta live: caso
   M024 documentato nel registro. I recuperi HTTP pubblici riusciti sono
   indicati; un tentativo fallito non viene presentato come lettura.
4. Per gli allegati PDF sono stati letti i passaggi pertinenti; tabelle e
   pagine sensibili controllate visivamente dove indicato. Il registro pinna
   gli hash di due PDF acquisiti dal coordinatore. Originali, HTML e render
   rimangono scratch locali ignorati, non vengono redistribuiti nel repository.
5. Prima revisione: sette date mancanti, Venzone, anticipo Riuso e nuove fiere
   documentate. Poi risolvere identità/sedi, orari e deroghe degli abituali;
   acquisire programmi 2027 senza estendere il limite del catalogo.

Restano aperti i limiti applicativi già descritti il 29 ottobre: eccezioni
festive, stagionalità/alternanza, sede per edizione, proiezione oltre il
31/12/2026. Restano inoltre la prova visiva Mercati e la revisione friulana.
L'accesso alla revisione editoriale non aggira questi controlli.

## Verifica della consegna

Coordinatore: unico autore del registro canonico e di questo dossier;
`scopri`: ricerca UD/PN; `eventi`: periodici/stagionali; `build_verifica`:
audit indipendente della documentazione. Le fonti non rilette dal verificatore
non vengono presentate come doppia verifica sul Web.

Audit documentale PASS: ID unici, relazioni bidirezionali, date ISO e relative
qualifiche, conteggi, sette date ancora assenti dal runtime, 22 reference
Markdown e sette link locali validi. I due hash PDF corrispondono ai file
consultati. Nessuna modifica a frontend, backend, scripts o experiments dalla
base di questo lotto; diff staged pulito. Guard del workspace canonico PASS
dopo lo staging: 4026 file tracciati, senza nuovi output generati o segreti.

Questo lotto cambia soltanto documentazione e registro di ricerca. Il catalogo
rimane di 53 schede pubbliche e 7 escluse, con SHA-256
`dce63d9d521ccfd9f593de9143f0ff0649220a0a15c09135ecf902290fecbafb`.
Nessun test applicativo, lint o build rieseguito per queste modifiche documentali;
le prove del 28 ottobre rimangono evidenza storica.

Nessun contatto con organizzatori, nuovo job, deployment, pacchetto Android o
pubblicazione Web. AAB 300038 e Web distribuita invariati. Nessuna promozione
del ramo Mercati a `main` in questo lotto.

[riuso]: https://www.turismofvg.it/eventi/mercatino-del-riuso-474444
[aviano]: https://prolocoregionefvg.it/eventi-delle-associate/anticamente-mercatino-dellantiquariato-ad-aviano-8/
[venzone]: https://www.turismofvg.it/eventi/mercanti-nel-borgo-antigae-e-a-vencon-478654
[gemona]: https://prolocoregionefvg.it/eventi-delle-associate/mercatino-delle-pulci-e-del-libro-usato/
[sacile]: https://www.prosacile.it/antiquariato
[antiqua]: https://prolocoregionefvg.it/eventi-delle-associate/udine-antiqua-3/
[ponterosso-usato]: https://www.turismofvg.it/eventi/mercatino-di-ponterosso-478821?LangSetCMS=it
[cervignano]: https://www.prolococervignanofvg.it/comunicazione-importante-mercatino-dellusato-della-prima-domenica-del-mese/
[fontanafredda]: https://www.comune.fontanafredda.pn.it/vivere-il-comune/territorio/mercato/
[cordenons]: https://sac4.halleysac.it/c093017/zf/index.php/atti-amministrativi/delibere/dettaglio/atto/G9mpBd0TUWT0-A
[casarsa]: https://www.trasparenzatari.it/trasparenzatari/?comune=b940
[trieste-reg]: https://amministrazionetrasparente.comune.trieste.it/wp-content/uploads/2025/12/Reg_Commercio_AAPP_DC_43_2025.pdf
[trieste-map]: https://amministrazionetrasparente.comune.trieste.it/wp-content/uploads/2025/12/ALL.03-SCHEDE-AREE-MERCATALI.pdf
[trieste-avviso]: https://t.me/s/comunetrieste?before=5373
[coldiretti]: https://friuliveneziagiulia.coldiretti.it/wp-content/uploads/2026/10/coltivatore-friulano_settembre-2026.pdf
[rivignano]: https://www.comune.rivignanoteor.ud.it/media/files/030188/attachment/bando_definitivo_posteggi_liberi_mercato_2026-signed_6BvgMv1.pdf
[tolmezzo]: https://www.comune.tolmezzo.ud.it/novita/fiera-dei-santi-2026/
[prata]: https://www.prolocosantaluciaprata.it/files/FESTA-DI-SANTA-LUCIA-2026_regolamento-hobbisti.pdf
[ovaro]: https://www.turismofvg.it/eventi/marcjat-di-san-martin-467592
[ts-agri-ott]: https://www.turismofvg.it/eventi/mercatino-agricolo-in-piazza-vittorio-veneto-480978?LangSetCMS=it
[ts-agri-nov]: https://www.turismofvg.it/eventi/mercatino-agricolo-in-piazza-vittorio-veneto-480982?LangSetCMS=it
[ts-agri-dic]: https://www.turismofvg.it/events/farmers-market-in-piazza-vittorio-veneto-480985
