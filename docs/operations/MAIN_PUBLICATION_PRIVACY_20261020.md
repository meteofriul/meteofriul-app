# Main: preparazione della pubblicazione, 20 ottobre 2026

Il primo push è stato bloccato dal controllo privacy locale prima di aggiornare
GitHub. Il nome del profilo Windows compariva in tre copie di evidenze:
helper archiviato ICON, log di una prova locale e attestazione API.

È stato sostituito da `LOCAL_USER` nei soli commit non ancora pubblicati.
Gli inventari delle copie archiviate sono aggiornati; gli hash originali
degli artefatti eseguiti restano riferimenti storici. Nessuna attestazione
di esecuzione è stata rigenerata o dichiarata nuovamente riuscita.

La base già pubblicata `6bd4216964ad81f7dcd20d478cde7b0db5ba442c` e tutta la sua cronologia sono invariate.
Autori, date, messaggi e struttura dei commit locali sono conservati.
Un riferimento esclusivamente locale conserva la cronologia originale.
Il successivo push resta un fast-forward e usa il controllo privacy originale.

Codice applicativo, test, configurazioni di runtime e pipeline sono identici
al candidato `b54fcde7e8bb8d6ba8d5533e9c1ecabd7a479e49` verificato con 183 test ICON. Cambiano soltanto i tre
file di evidenza, i relativi inventari e questa nota. Non occorre ripetere
i test del codice per la sola redazione delle evidenze; la CI remota sarà
verificata sul commit effettivamente pubblicato.

## Identità dei commit locali aggiornate

I riferimenti precedenti nei verbali e negli artefatti descrivono le prove
effettivamente eseguite prima della redazione. Questa corrispondenza permette
di ritrovare il codice equivalente nella cronologia pubblicabile.

| Prima | Dopo redazione |
| --- | --- |
| `9ef1410e` | `cb99d783` |
| `c8aa724d` | `0c8e017e` |
| `54c8c916` | `51bb8fd8` |
| `aa8a89c4` | `9c77d2e6` |
| `73b44310` | `50b1d85a` |
| `520caa9a` | `01a97ae3` |
| `b54fcde7` | `46004cae` |

Il controllo sulla corsa ICON reale resta incompleto; nessuna AAB,
installazione, distribuzione o attivazione degli invii fa parte di questo push.

## Correzione del test emersa nella CI della PR

Il primo run CI della PR 8 (`39479702733`) ha rilevato un'aspettativa obsoleta
in `communityDarkPalette.test.js`: attendeva il cuore rosa, mentre la ricevuta
approvata usa già una spunta verde. Il test viene allineato allo stile approvato
e il controllo del contrasto legge ora i colori effettivi della spunta dal CSS.
Non cambia alcun componente, stile o comportamento dell'app.

Verifica locale: 51 test passati in `communityDarkPalette.test.js` e
`LiveView.webcamCarousel.test.jsx`, tramite `npm test --` e caricamento nativo
della configurazione. Dipendenze già presenti riutilizzate; nessuna installazione.
La CI viene rieseguita sul commit aggiornato prima del merge.
