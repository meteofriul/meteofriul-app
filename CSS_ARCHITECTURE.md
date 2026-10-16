# Meteo Friul UI 3.0.0 - CSS Architecture

Data: 2026-06-21
Stato: regola operativa

## Obiettivo

La UI 3.0.0 non deve crescere con sovrascrizioni progressive. Ogni stile deve avere una casa chiara, un livello di cascade chiaro e un motivo chiaro.

## Regola principale

```text
token -> base -> layout -> componenti -> feature
```

Mai:

```text
feature nuova -> override globale -> altro override -> !important
```

## Cascade layers

Il frontend usa questi layer CSS:

```css
@layer reset, tokens, base, layout, components, features, utilities;
```

Ordine previsto:

| Layer | Uso |
| --- | --- |
| `tokens` | colori, tipografia, spaziatura, ombre, motion |
| `base` | reset leggero, `html`, `body`, elementi nativi |
| `layout` | AppShell, header, bottom nav, pagine |
| `components` | AppButton, AppCard, AppBadge, AppTabs, stati comuni |
| `features` | CSS specifico di Home, Bollettino, Territorio, Eventi, Scopri |
| `utilities` | solo utility piccole e documentate |

## Regole non negoziabili

- Non creare un nuovo `App.css`.
- Non importare `App.css` dalla app attuale.
- Non aggiungere CSS definitivo in fondo a un file esistente.
- Non usare `!important` salvo ponte temporaneo documentato.
- Non usare selettori lunghi per vincere conflitti.
- Non far dipendere una tab dal CSS di un'altra tab.
- Non creare card dentro card senza necessita reale.
- Non usare colori hardcoded nei componenti quando esiste un token.

## Naming

Classi condivise:

```text
mf-*
```

Classi feature:

```text
mf-home-*
mf-bulletin-*
mf-live-*
mf-events-*
mf-discover-*
```

Classi temporanee laboratorio:

```text
mf-lab-*
```

Le classi `mf-lab-*` devono essere eliminate o sostituite quando una schermata viene promossa.

## Dove mettere il CSS

| Tipo stile | File |
| --- | --- |
| Colori | `frontend/src/ui/tokens/colors.css` |
| Tipografia | `frontend/src/ui/tokens/typography.css` |
| Spaziature/raggi | `frontend/src/ui/tokens/spacing.css` |
| Ombre | `frontend/src/ui/tokens/shadows.css` |
| Motion | `frontend/src/ui/tokens/motion.css` |
| Reset/base | `frontend/src/ui/base.css` |
| Componenti condivisi | `frontend/src/ui/components/components.css` |
| Layout shell | `frontend/src/ui/layout/layout.css` |
| Laboratorio temporaneo | `frontend/src/features/lab/lab.css` |
| Feature definitive | `frontend/src/features/<feature>/<feature>.css` |

## Processo per nuove modifiche

1. Prima cercare se esiste un token o componente.
2. Se manca un valore ricorrente, aggiungere token.
3. Se manca un pattern UI ricorrente, aggiungere variante componente.
4. Se lo stile vale solo per una tab, metterlo nel CSS della feature.
5. Se serve un override, fermarsi e capire quale ownership e' sbagliata.

## Prima di approvare

- Il componente usa token.
- Il CSS vive nel file giusto.
- Nessun selettore dipende da markup fragile.
- Nessuna regola globale e' stata aggiunta per sistemare un caso locale.
- Build e lint passano.
- Mobile stretto leggibile.
