import { describe, expect, it } from "vitest";

import {
  getLocalMemoryForDate,
  getLocalMemoryForLocation,
  getLocalMemoryRecords,
  getLocalMemorySecondaryForDate,
  getLocalMemorySummary,
} from "./localMemory";

const FUR_APPROVED_RECORD_IDS = [
  "memory-it-ready-0404-giani-stuparich-e-la-trieste-del-novecento",
  "memory-it-ready-0910-leonardo-zanier-poesia-ed-emigrazione",
  "memory-it-ready-0115-virgilio-giotti-e-la-poesia-di-trieste",
  "memory-it-ready-0317-bruno-pincherle-medicina-e-impegno-civile",
  "memory-it-ready-0125-ivan-trinko-e-la-cultura-della-benecia",
  "memory-it-ready-0928-mirko-basaldella-arte-friulana-del-novecento",
  "memory-it-ready-0329-tarcisio-petracco-e-l-universita-del-friuli",
  "memory-it-ready-0423-l-eccidio-di-via-ghega",
  "memory-it-ready-0531-la-strage-di-peteano",
  "memory-it-ready-0701-la-fucilazione-di-cercivento",
  "memory-it-ready-0403-l-eccidio-di-opicina",
  "memory-it-ready-0804-l-attentato-al-deposito-costiero-siot",
  "memory-it-ready-1012-l-assedio-di-trieste-del-1813",
  "memory-it-ready-0515-la-battaglia-di-tarvisio-del-1809",
  "memory-it-ready-1014-giuseppe-levi-scuola-di-scienza",
  "memory-it-ready-1230-sergio-doplicher-e-la-fisica-matematica",
  "memory-it-ready-0731-antonio-mario-radmilli-e-la-preistoria",
  "memory-it-ready-1130-richard-mollier-e-la-termodinamica",
  "memory-it-ready-0101-paolo-diacono-memoria-longobarda",
  "memory-it-ready-1103-le-giornate-di-trieste-del-1953",
  "memory-it-ready-0321-tarvisio-nelle-campagne-napoleoniche",
  "memory-it-ready-0429-opicina-negli-ultimi-giorni-di-guerra",
  "memory-it-ready-1204-francesco-caucig-e-la-gorizia-d-arte",
  "memory-it-ready-0706-giuseppe-tominz-ritratti-tra-gorizia-e-trieste",
  "memory-it-ready-0921-antonio-lasciac-architetto-goriziano",
  "memory-it-ready-1031-andrej-budal-cultura-slovena-a-gorizia",
  "memory-it-ready-0608-luciano-petech-studi-sull-asia",
  "memory-it-ready-0817-theodor-daubler-e-le-avanguardie",
  "memory-it-ready-0920-marij-kogoj-musica-di-confine",
];

const FUR_APPROVED_RECORD_IDS_WAVE_3 = [
  "memory-it-ready-0102-alessandro-de-stefani-scrittura-e-scena",
  "memory-it-ready-0131-domenico-schiavi-architettura-carnica",
  "memory-it-ready-0427-jacopo-stellini-filosofia-da-cividale",
  "memory-it-ready-0514-l-r-johannis-immaginazione-da-sacile",
  "memory-it-ready-0516-paolo-bozzi-e-la-scienza-del-vedere",
  "memory-it-ready-0726-giulio-krall-matematica-applicata",
  "memory-it-ready-0806-la-battaglia-di-doberdo",
  "memory-it-ready-0803-carlo-stuparich-scrittura-triestina",
  "memory-it-ready-0829-michelangelo-grigoletti-pittura-pordenonese",
  "memory-it-ready-0414-luigi-carnera-astronomia-triestina",
  "memory-it-ready-0813-fabio-conforto-e-la-geometria",
  "memory-it-ready-1122-david-maria-turoldo-voce-civile",
];

const FUR_APPROVED_RECORD_IDS_WAVE_4 = [
  "memory-it-ready-0108-bernardo-maria-de-rubeis-storia-da-cividale",
  "memory-it-ready-0216-ruggero-timeus-trieste-e-il-novecento",
  "memory-it-ready-1016-louis-toffoli-pittura-triestina-d-origine",
  "memory-it-ready-0226-alexander-kircher-mare-e-pittura",
  "memory-it-ready-0709-spiridon-gopcevic-astronomia-e-scrittura",
];

const FUR_APPROVED_RECORD_IDS_WAVE_5 = [
  "memory-it-ready-0509-la-riunione-adriatica-di-sicurta",
  "memory-it-ready-0903-karel-vladimir-truhlar-poesia-e-pensiero",
  "memory-it-ready-0728-guido-fink-sguardo-da-gorizia",
  "memory-it-ready-0529-giorgio-nicodemi-arte-e-musei",
  "memory-it-ready-0221-italo-tavolato-scrittura-triestina",
  "memory-it-ready-0218-giovanni-giuseppe-cosattini-pittura-udinese",
  "memory-it-ready-0420-ramiro-meng-forme-e-citta",
  "memory-it-ready-0621-luigi-comel-disegno-e-pittura",
];

const FUR_APPROVED_RECORD_IDS_WAVE_7 = [
  "memory-it-ready-0129-adelaide-ristori-il-teatro-da-cividale",
  "memory-it-ready-0717-leopoldo-metlicovitz-arte-e-manifesti",
  "memory-it-ready-0720-arduino-berlam-architettura-triestina",
  "memory-it-ready-0828-antonio-somma-parole-per-la-scena",
  "memory-it-ready-0303-arturo-rietti-ritratti-triestini",
  "memory-it-ready-0606-umberto-veruda-pittura-a-trieste",
  "memory-it-ready-0914-marcello-mascherini-scultura-e-scena",
  "memory-it-ready-0824-augusto-cernigoj-avanguardia-a-trieste",
  "memory-it-ready-0127-odorico-politi-pittura-udinese",
  "memory-it-ready-0227-marcello-d-olivo-progetto-e-paesaggio",
  "memory-it-ready-1220-teobaldo-ciconi-teatro-e-poesia",
  "memory-it-ready-1217-arturo-nathan-pittura-e-inquietudine",
];

const FUR_APPROVED_RECORD_IDS_WAVE_8 = [
  "memory-it-ready-1210-farfa-futurismo-da-trieste",
  "memory-it-ready-0407-bruno-croatto-pittura-e-incisione",
  "memory-it-ready-0920-carolus-cergoly-trieste-in-versi",
  "memory-it-ready-0301-carlo-marin-muggia-e-scrittura",
  "memory-it-ready-0214-bruno-giordano-sanzin-poesia-triestina",
  "memory-it-ready-0415-renzo-rosso-narrativa-triestina",
  "memory-it-ready-0816-ugo-mioni-libri-e-ragazzi",
  "memory-it-ready-1021-filippo-zamboni-poesia-e-risorgimento",
  "memory-it-ready-0924-enrico-nordio-forme-per-trieste",
  "memory-it-ready-1002-pierviviano-zecchini-san-vito-e-cultura",
];

const FUR_APPROVED_RECORD_IDS_WAVE_9 = [
  "memory-it-ready-0806-gorizia-e-la-sesta-battaglia-dell-isonzo",
  "memory-it-ready-1029-pozzuolo-del-friuli-battaglia-di-retroguardia",
  "memory-it-ready-0415-sacile-una-battaglia-napoleonica",
  "memory-it-ready-0401-aquileia-sotto-assedio",
  "memory-it-ready-0729-aquileia-nuovo-assedio-nella-storia-romana",
  "memory-it-ready-0316-valvasone-e-il-passaggio-napoleonico",
  "memory-it-ready-0523-le-battaglie-dell-isonzo",
  "memory-it-ready-0326-paolo-maurensig-narrativa-da-gorizia",
  "memory-it-ready-1207-gino-valle-progetto-e-architettura",
  "memory-it-ready-0120-luca-carlevarijs-vedute-e-pittura",
  "memory-it-ready-0124-gojmir-anton-kos-pittura-tra-confini",
  "memory-it-ready-0912-ermes-midena-architettura-friulana",
];

const FUR_APPROVED_RECORD_IDS_WAVE_10 = [
  "memory-it-ready-0719-aquileia-e-il-sacco-di-attila",
  "memory-it-ready-1227-pietro-zorutti-poesia-friulana",
  "memory-it-ready-0418-luigi-spazzapan-pittura-di-frontiera",
  "memory-it-ready-1007-armando-pizzinato-pittura-e-impegno",
  "memory-it-ready-1110-marco-salvador-medioevo-raccontato",
  "memory-it-ready-0311-miroslav-kosuta-poesia-slovena-da-trieste",
  "memory-it-ready-0616-giuseppe-bernardino-bison-pittura-da-palmanova",
  "memory-it-ready-0222-peter-butkovic-parole-di-confine",
  "memory-it-ready-0130-francesco-chiarottini-arte-da-cividale",
  "memory-it-ready-0228-antonio-rotta-pittura-da-gorizia",
  "memory-it-ready-1211-alfonso-canciani-scultura-dal-collio",
  "memory-it-ready-0802-viktor-sulcic-architettura-oltre-l-adriatico",
];

const FUR_APPROVED_RECORD_IDS_WAVE_11 = [
  "memory-it-ready-0122-luigi-loir-gorizia-e-l-illustrazione",
  "memory-it-ready-0111-guido-fulignot-ritratti-da-trieste",
  "memory-it-ready-0609-fabio-beltram-fisica-da-gorizia",
  "memory-it-ready-0103-roberto-car-e-la-fisica-computazionale",
  "memory-it-ready-0723-michele-vendruscolo-proteine-e-biofisica",
  "memory-it-ready-0220-vigilio-de-grassi-architettura-da-grado",
  "memory-it-ready-0202-iginio-montini-scultura-a-cividale",
  "memory-it-ready-0105-alberto-riccoboni-architettura-e-storia-dell-arte",
  "memory-it-ready-0831-enrico-de-cillia-pittura-e-carso",
  "memory-it-ready-1112-bruno-sacco-design-da-udine",
  "memory-it-ready-0601-doro-levi-archeologia-e-storia-dell-arte",
];

const FUR_APPROVED_RECORD_IDS_WAVE_12 = [
  "memory-it-ready-0117-carlo-marchesetti-archeologia-e-botanica-da-trieste",
  "memory-it-ready-0201-fausto-romitelli-musica-contemporanea-da-gorizia",
  "memory-it-ready-0203-giovanni-battista-benardelli-pittura-e-fotografia",
  "memory-it-ready-0207-ugo-morin-matematica-e-antifascismo",
  "memory-it-ready-0213-guido-horn-d-arturo-astronomia-da-trieste",
  "memory-it-ready-0320-bruno-cester-fisica-e-astronomia",
  "memory-it-ready-0505-alessandro-lustig-medicina-da-trieste",
  "memory-it-ready-0610-roberto-bazlen-libri-e-scoperte-editoriali",
  "memory-it-ready-0710-filosseno-luzzatto-studi-e-lingue",
  "memory-it-ready-0827-giacomo-ciamician-chimica-e-sole",
  "memory-it-ready-1030-giusto-fontanini-storia-e-archeologia",
  "memory-it-ready-1114-antonio-taramelli-archeologia-da-udine",
  "memory-it-ready-1126-ugo-cara-scultura-e-design-a-muggia",
  "memory-it-ready-0410-vittorio-cadel-poesia-e-pittura-da-fanna",
  "memory-it-ready-1013-bindo-chiurlo-critica-e-poesia",
];

const FUR_APPROVED_RECORD_IDS_WAVE_13 = [
  "memory-it-ready-0901-egidio-feruglio-geologia-ed-esplorazione",
  "memory-it-ready-0310-harry-bertoia-arte-e-design-da-arzene",
  "memory-it-ready-0417-giusto-gervasutti-e-l-alpinismo",
  "memory-it-ready-1008-giandomenico-picco-diplomazia-senza-armi",
  "memory-it-ready-1008-pietro-ellero-diritto-e-criminologia",
  "memory-it-ready-0328-giovanni-boaga-matematica-e-cartografia",
  "memory-it-ready-0730-livio-gratton-astrofisica-da-trieste",
  "memory-it-ready-1027-irene-di-spilimbergo-pittura-e-poesia",
  "memory-it-ready-0116-rodolfo-lipizer-violino-e-musica-da-gorizia",
  "memory-it-ready-1212-milko-kos-storia-tra-gorizia-e-il-mondo-sloveno",
  "memory-it-ready-0727-samuele-romanin-il-mestiere-dello-storico",
  "memory-it-ready-0525-ireneo-della-croce-cronache-di-trieste",
  "memory-it-ready-0528-vincenzo-joppi-libri-e-memoria-di-udine",
  "memory-it-ready-1128-costantino-dardi-architettura-e-progetto",
  "memory-it-ready-0722-maria-tore-barbina-una-voce-poetica",
];

const FUR_APPROVED_RECORD_IDS_WAVE_15 = [
  "memory-it-ready-0804-luigi-scrosoppi-educazione-e-cura-sociale",
  "memory-it-ready-0418-giovanni-battista-de-gasperi-geografia-e-grotte",
  "memory-it-ready-0920-ruggero-berlam-e-l-architettura-di-trieste",
  "memory-it-ready-0927-vittorio-vidali-antifascismo-e-conflitti-del-novecen",
  "memory-it-ready-0612-daniele-antonio-bertoli-alla-corte-imperiale",
  "memory-it-ready-1220-paolo-rumiz-viaggi-e-frontiere",
  "memory-it-ready-1119-giorgio-celiberti-arte-da-udine-all-europa",
  "memory-it-ready-0217-franco-vegliani-e-la-letteratura-di-frontiera",
];

const FUR_APPROVED_RECORD_IDS_WAVE_16 = [
  "memory-it-ready-0321-marcello-dudovich-e-l-arte-del-manifesto",
  "memory-it-ready-0412-giorgio-carmelich-e-il-futurismo-giuliano",
  "memory-it-ready-0616-lado-piscanc-poesia-dal-confine-orientale",
  "memory-it-ready-0121-nicolo-de-miniussi-da-trieste-a-waterloo",
  "memory-it-ready-0616-amalia-lydia-lalli-dal-friuli-alla-resistenza",
];

const FUR_APPROVED_RECORD_IDS_WAVE_17_PRE_WAVE_15 = [
  "memory-it-ready-0703-l-osservatore-triestino-e-la-storia-della-stampa",
  "memory-it-ready-1104-elettra-trieste-citta-della-scienza",
  "memory-it-ready-1216-la-cooperativa-lavoratori-uniti-e-i-diritti",
  "memory-it-ready-1026-il-ritorno-di-trieste-all-italia",
  "memory-it-ready-0628-gabriele-foschiatti-e-l-antifascismo-giuliano",
  "memory-it-ready-0708-edo-mihevc-architettura-e-confine",
  "memory-it-ready-0718-geppino-micheletti-il-medico-di-vergarolla",
  "memory-it-ready-0619-nasce-il-parco-zoo-punta-verde",
  "memory-it-ready-0516-giuseppe-caprin-storia-e-paesaggi-giuliani",
  "memory-it-ready-1130-pre-checo-placerean-e-la-lingua-friulana",
];

const FUR_APPROVED_RECORD_IDS_WAVE_17_AFTER_WAVE_15 = [
  "memory-it-ready-0910-il-litorale-adriatico-sotto-occupazione-tedesca",
];

const FUR_APPROVED_RECORD_IDS_WAVE_15_TAIL = [
  "memory-it-ready-0918-viktor-dankl-da-udine-ai-fronti-della-grande-guerra",
];

const FUR_APPROVED_RECORD_IDS_WAVE_18 = [
  "memory-it-ready-1204-gae-aulenti-architettura-senza-confini",
  "memory-it-ready-0418-ardito-desio-dal-friuli-al-k2",
  "memory-it-ready-1211-eugenio-curiel-scienza-e-resistenza",
  "memory-it-ready-1122-jacopo-pirona-e-il-vocabolario-friulano",
  "memory-it-ready-0726-carlo-sgorlon-il-friuli-nei-romanzi",
  "memory-it-ready-0311-salvatore-pincherle-e-l-analisi-moderna",
  "memory-it-ready-0410-victor-de-sabata-una-bacchetta-internazionale",
  "memory-it-ready-0828-enrico-peressutti-e-l-architettura-moderna",
  "memory-it-ready-0130-annibale-comessatti-geometria-da-udine",
  "memory-it-ready-0728-alberto-mazzucato-musica-e-insegnamento",
];

const FUR_APPROVED_RECORD_IDS_WAVE_19 = [
  "memory-it-ready-0814-giorgio-strehler-il-teatro-come-arte-pubblica",
  "memory-it-ready-1030-sergio-amidei-e-il-cinema-neorealista",
  "memory-it-ready-0905-getulio-alviani-luce-e-movimento",
  "memory-it-ready-0523-pietro-kandler-e-la-memoria-di-trieste",
  "memory-it-ready-1218-laura-mancinelli-il-medioevo-raccontato",
  "memory-it-ready-0422-carlo-caneva-e-la-stagione-coloniale-italiana",
];

const FUR_APPROVED_RECORD_IDS_WAVE_20 = [
  "memory-it-ready-0219-caterina-percoto-le-storie-del-friuli",
  "memory-it-ready-0328-ermes-di-colloredo-e-la-poesia-friulana",
  "memory-it-ready-0112-amedeo-giacomini-lingua-e-poesia",
  "memory-it-ready-1105-federico-tavan-la-voce-di-andreis",
  "memory-it-ready-0804-celso-macor-il-confine-come-incontro",
  "memory-it-ready-0211-pre-antoni-beline-scrivere-in-friulano",
  "memory-it-ready-0723-giuseppe-marchetti-e-la-cultura-friulana",
  "memory-it-ready-0612-margherita-hack-trieste-e-le-stelle",
  "memory-it-ready-0126-fulvio-tomizza-scrivere-il-confine",
  "memory-it-ready-0305-pasolini-casarsa-e-la-poesia-friulana",
];

const FUR_APPROVED_RECORD_IDS_WAVE_21 = [
  "memory-it-ready-0430-trieste-l-insurrezione-e-la-corsa-per-la-citta",
  "memory-it-ready-0306-l-atto-istitutivo-dell-universita-di-udine",
  "memory-it-ready-0524-la-consacrazione-del-cimitero-degli-invitti",
  "memory-it-ready-0808-nasce-l-universita-di-trieste",
  "memory-it-ready-1226-a-trieste-nascono-le-assicurazioni-generali",
  "memory-it-ready-0817-tina-modotti-fotografia-e-impegno-civile",
  "memory-it-ready-0212-irene-camber-il-primo-oro-della-scherma-italiana",
  "memory-it-ready-0923-gino-paoli-una-voce-della-canzone-d-autore",
  "memory-it-ready-0604-fedora-barbieri-la-voce-triestina-dell-opera",
  "memory-it-ready-0904-leo-castelli-e-l-arte-americana-del-dopoguerra",
  "memory-it-ready-0517-fausto-cleva-da-trieste-al-metropolitan",
  "memory-it-ready-0917-tullio-kezich-raccontare-il-cinema-italiano",
  "memory-it-ready-1123-sigmund-zois-scienza-e-cultura-dell-illuminismo",
  "memory-it-ready-0926-enzo-bearzot-il-friuli-campione-del-mondo",
  "memory-it-ready-1102-cesare-rubini-campione-in-due-sport",
];

const FUR_APPROVED_RECORD_IDS_WAVE_22 = [
  "memory-it-ready-0928-la-torbiera-cichinot-diventa-biotopo-regionale",
  "memory-it-ready-0918-l-inaugurazione-del-sacrario-di-redipuglia",
  "memory-it-ready-0227-i-mondiali-juniores-di-sci-sulle-montagne-friulane",
  "memory-it-ready-0923-gli-europei-di-pallavolo-arrivano-a-gorizia",
  "memory-it-ready-0527-trieste-ospita-il-mondiale-di-calcio-del-1934",
  "memory-it-ready-0131-il-mondiale-di-ciclocross-a-corva",
  "memory-it-ready-1018-la-prima-partita-allo-stadio-nereo-rocco",
  "memory-it-ready-1222-giorgio-oberweger-il-primo-podio-olimpico-italiano-n",
  "memory-it-ready-1019-mario-foschiani-e-la-resistenza-friulana",
];

const FUR_APPROVED_RECORD_IDS_WAVE_23 = [
  "memory-it-ready-0803-felice-venezian-e-l-irredentismo-triestino",
  "memory-it-ready-0712-silvio-marcuzzi-e-la-resistenza-nella-pianura-friula",
  "memory-it-ready-0902-giuseppe-revere-letteratura-e-risorgimento",
  "memory-it-ready-0701-alojzij-res-tra-cultura-italiana-e-slovena",
];

const FUR_APPROVED_RECORD_IDS_WAVE_24 = [
  "memory-it-ready-1022-camillo-castiglioni-e-l-industria-mitteleuropea",
  "memory-it-ready-0919-teho-teardo-musica-tra-cinema-e-teatro",
  "memory-it-ready-1116-rado-bordon-tra-poesia-e-traduzione",
  "memory-it-ready-1213-luciano-zani-e-la-ritirata-dal-fronte-russo",
  "memory-it-ready-0208-luigi-bevilacqua-sergente-del-genio",
];

const FUR_APPROVED_RECORD_IDS_WAVE_25 = [
  "memory-it-ready-0811-eduard-joseph-d-alton-tra-natura-e-archeologia",
  "memory-it-ready-0911-fabio-doplicher-tra-poesia-e-teatro",
  "memory-it-ready-0918-carlo-podrecca-patriota-e-storico-delle-valli-del-na",
  "memory-it-ready-1104-anton-kasutnik-tra-storia-e-teatro",
];

const FUR_APPROVED_RECORD_IDS_WAVE_26 = [
  "memory-it-ready-0418-alcide-paolini-tra-scrittura-ed-editoria",
  "memory-it-ready-0227-ugo-guarino-arte-e-liberta",
  "memory-it-ready-0321-mario-ceconi-scultura-del-novecento",
  "memory-it-ready-0816-fulvio-papi-filosofia-e-impegno-civile",
  "memory-it-ready-0818-demetrio-livaditi-e-la-ciarla",
];

const FUR_APPROVED_RECORD_IDS_WAVE_27 = [
  "memory-it-ready-0902-ferruccio-dardi-e-la-battaglia-di-el-qatara",
  "memory-it-ready-0906-francesco-maria-franceschinis-matematica-e-insegname",
  "memory-it-ready-0819-mario-rigutti-una-vita-dedicata-alle-stelle",
  "memory-it-ready-0921-edoardo-weiss-pioniere-della-psicoanalisi",
  "memory-it-ready-0728-davide-besso-e-il-periodico-di-matematica",
  "memory-it-ready-1028-nicolo-dallaporta-dalle-particelle-alle-galassie",
  "memory-it-ready-0301-nico-naldini-una-voce-autonoma-del-novecento",
];

const FUR_APPROVED_RECORD_IDS_WAVE_28 = [
  "memory-it-ready-0209-emilio-mattioni-e-l-architettura-del-friuli-moderno",
  "memory-it-ready-0318-edoardo-del-neri-tra-pittura-e-incisione",
  "memory-it-ready-0325-giuseppe-giacomo-battig-pittore-dell-ottocento-goriz",
  "memory-it-ready-0425-alberto-colantuoni-dal-teatro-al-premio-viareggio",
  "memory-it-ready-0527-giorgio-kirschner-e-la-grande-musica-corale",
  "memory-it-ready-1128-oscar-hermann-lamb-tra-trieste-e-la-secessione-vienn",
  "memory-it-ready-1031-dyalma-stultus-e-l-arte-triestina-del-novecento",
  "memory-it-ready-0620-antonio-mattioni-un-pioniere-del-volo-a-reazione",
  "memory-it-ready-1022-leone-morandini-arte-e-tutela-di-cividale",
];

const FUR_APPROVED_RECORD_IDS_WAVE_29 = [
  "memory-it-ready-0821-renato-ricamo-e-la-scuola-italiana-di-fisica-nuclear",
  "memory-it-ready-0616-edoardo-muller-una-vita-sui-podi-internazionali",
  "memory-it-ready-1122-davide-liani-musica-e-formazione-in-friuli",
  "memory-it-ready-0606-edvard-rusjan-pioniere-del-volo",
  "memory-it-ready-0221-emilio-comici-e-l-alpinismo-moderno",
  "memory-it-ready-0331-laura-conti-scienza-e-ambientalismo",
  "memory-it-ready-0103-corinna-ulcigrai-e-la-matematica-dei-sistemi-dinamic",
  "memory-it-ready-0203-giulio-gatti-casazza-dalla-scala-al-metropolitan",
  "memory-it-ready-0907-sergio-della-pergola-e-la-demografia-contemporanea",
  "memory-it-ready-0110-paul-henreid-da-trieste-a-casablanca",
  "memory-it-ready-0726-alessandro-trotter-pioniere-della-cecidologia",
  "memory-it-ready-1214-italico-brass-pittura-tra-gorizia-e-venezia",
  "memory-it-ready-0315-sasa-santel-pittura-e-musica-tra-due-culture",
  "memory-it-ready-0825-gino-parin-ritratti-dalla-trieste-europea",
  "memory-it-ready-0601-joze-pirjevec-storico-dei-balcani",
];

const FUR_APPROVED_RECORD_IDS_WAVE_30 = [
  "memory-it-ready-1120-rita-rosani-e-la-resistenza",
  "memory-it-ready-0531-dante-vaglieri-e-gli-scavi-di-ostia",
  "memory-it-ready-1112-marina-apollonio-oltre-il-cerchio",
  "memory-it-ready-0618-antonio-zanon-e-l-economia-del-friuli-moderno",
  "memory-it-ready-1026-cecilia-deganutti-infermiera-e-partigiana",
  "memory-it-ready-0927-sergio-stefanutti-e-l-aeronautica-sperimentale",
  "memory-it-ready-0813-ida-marcaria-sopravvissuta-ad-auschwitz",
  "memory-it-ready-0320-pinko-tomazic-e-l-antifascismo-sloveno-a-trieste",
  "memory-it-ready-1209-bruno-vasari-la-memoria-della-deportazione",
  "memory-it-ready-0425-gianni-widmer-pioniere-del-volo-adriatico",
  "memory-it-ready-1222-anna-maria-di-giorgio-e-la-fisiologia-dei-sensi",
  "memory-it-ready-0110-enrico-rocca-una-voce-tra-cultura-italiana-e-tedesca",
];

const FUR_APPROVED_RECORD_IDS_WAVE_31 = [
  "memory-it-ready-0623-ivan-grbec-e-la-musica-slovena-di-trieste",
  "memory-it-ready-1125-lucia-rodocanachi-la-traduttrice-rimasta-nell-ombra",
  "memory-it-ready-0102-riccardo-cassin-alpinismo-e-resistenza",
  "memory-it-ready-0509-roberto-malaroda-e-la-geologia-sul-campo",
  "memory-it-ready-0711-teddy-reno-da-trieste-alla-canzone-italiana",
  "memory-it-ready-0503-renato-balestra-e-l-alta-moda-italiana",
  "memory-it-ready-0515-francesco-carnelutti-e-la-scuola-del-diritto",
  "memory-it-ready-1221-moira-orfei-la-regina-del-circo",
  "memory-it-ready-0909-francesco-robortello-e-il-metodo-degli-umanisti",
  "memory-it-ready-0829-romilda-pantaleoni-la-prima-desdemona-di-verdi",
  "memory-it-ready-0305-alfred-jaell-pianista-triestino-sulle-scene-europee",
];

const FUR_APPROVED_RECORD_IDS_WAVE_32 = [
  "memory-it-ready-1223-olga-brunner-e-un-salotto-per-la-musica-europea",
  "memory-it-ready-1024-gianandrea-gropplero-dalla-resistenza-alla-cooperazi",
  "memory-it-ready-0526-roberto-damiani-e-la-cultura-civile-di-trieste",
  "memory-it-ready-1026-gianpaolo-tosel-e-le-inchieste-sulle-brigate-rosse",
  "memory-it-ready-0929-umberto-manfrin-il-segno-friulano-di-tiramolla",
  "memory-it-ready-0714-mario-maranzana-e-il-teatro-della-memoria-triestina",
];

const FUR_APPROVED_RECORD_IDS_WAVE_34 = [
  "memory-it-ready-0805-carla-gravina-dal-friuli-al-grande-cinema",
  "memory-it-ready-0808-mauro-maur-la-tromba-triestina-nel-mondo",
  "memory-it-ready-0411-gino-pancino-un-mondiale-nato-sulle-piste-friulane",
  "memory-it-ready-0615-lamberto-zannier-da-fagagna-alla-diplomazia-internaz",
  "memory-it-ready-0718-mara-navarria-dalla-bassa-friulana-all-oro-olimpico",
  "memory-it-ready-0620-giulia-rizzi-la-spada-udinese-d-oro-a-parigi",
];

const FUR_APPROVED_RECORD_IDS_WAVE_35 = [
  "memory-it-ready-0130-giacomo-galanda-da-udine-all-argento-olimpico",
  "memory-it-ready-0405-giacomo-gentilomo-dai-bozzetti-triestini-al-cinema-p",
  "memory-it-ready-0913-matej-cernic-da-savogna-all-argento-olimpico",
  "memory-it-ready-0514-elisa-togut-da-gorizia-al-tetto-del-mondo",
  "memory-it-ready-0718-michele-mian-da-gorizia-all-argento-olimpico",
  "memory-it-ready-0521-fulvia-franco-una-miss-per-la-trieste-del-1948",
  "memory-it-ready-0122-giovanni-micheletto-il-conte-di-sacile-tra-ciclismo-",
];

const FUR_APPROVED_RECORD_IDS_WAVE_36 = [
  "memory-it-ready-1022-piero-codia-dalla-triestina-nuoto-al-titolo-europeo",
  "memory-it-ready-0326-aldo-tarlao-da-grado-all-argento-olimpico",
  "memory-it-ready-0729-l-arena-di-pola-un-giornale-attraverso-l-esodo",
  "memory-it-ready-0507-salvatore-barzilai-da-trieste-al-governo-delle-terre",
];

const FUR_APPROVED_RECORD_IDS_WAVE_37 = [
  "memory-it-ready-0817-henrika-santel-arte-e-insegnamento-nella-gorizia-di-",
];

const FUR_APPROVED_RECORD_IDS_WAVE_38 = [
  "memory-it-ready-0531-luigi-gasparotto-da-sacile-alla-costituente",
];

const FUR_APPROVED_RECORD_IDS_WAVE_39 = [
  "memory-it-ready-0901-franco-gulli-violinista-da-trieste-al-mondo",
  "memory-it-ready-0502-leonardo-andervolti-e-la-difesa-del-1848",
  "memory-it-ready-0902-gabriella-gherbez-resistenza-e-diritti",
  "memory-it-ready-1202-elody-oblath-una-voce-letteraria-di-trieste",
];

const FUR_APPROVED_RECORD_IDS_WAVE_40 = [
  "memory-it-ready-0403-celso-costantini-dal-friuli-alla-cina",
  "memory-it-ready-0603-mirko-polic-e-il-teatro-musicale-sloveno",
  "memory-it-ready-0803-tiberio-deciani-e-le-radici-del-diritto-penale-moder",
  "memory-it-ready-0803-vittorio-ieralla-e-i-diritti-delle-persone-sorde",
  "memory-it-ready-1203-carlo-errera-e-la-storia-della-geografia",
  "memory-it-ready-0104-bruno-premiani-dal-disegno-politico-alla-doom-patrol",
  "memory-it-ready-0405-sergij-vilfan-e-la-storia-del-diritto",
  "memory-it-ready-0805-antonio-franconi-da-udine-alla-storia-del-circo",
];

const FUR_APPROVED_RECORD_IDS_WAVE_41 = [
  "memory-it-ready-0707-callisto-cosulich-e-la-critica-cinematografica",
  "memory-it-ready-0908-glauco-venier-dal-friuli-al-jazz-internazionale",
  "memory-it-ready-0312-emanuele-barison-dal-fumetto-friulano-alle-grandi-se",
  "memory-it-ready-0815-alberto-ascoli-e-la-ricerca-biomedica",
  "memory-it-ready-0915-enrico-terrinoni-traduttore-e-studioso-di-joyce",
  "memory-it-ready-1117-salomone-morpurgo-filologo-e-bibliotecario",
  "memory-it-ready-0721-avgusta-santel-arte-e-insegnamento-a-gorizia",
  "memory-it-ready-0922-elvio-guagnini-e-la-letteratura-di-confine",
  "memory-it-ready-0123-arnaldo-piutti-e-la-d-asparagina",
  "memory-it-ready-0624-romolo-amaseo-umanista-e-maestro-del-latino",
  "memory-it-ready-0327-tullio-padovani-e-il-diritto-penale",
  "memory-it-ready-1231-emilio-treves-e-la-grande-editoria-italiana",
];

const FUR_APPROVED_RECORD_IDS_WAVE_42 = [
  "memory-it-ready-0204-riccardo-luzzatto-dal-risorgimento-al-friuli",
  "memory-it-ready-0706-gino-beltrame-e-la-resistenza-friulana",
  "memory-it-ready-0706-carlo-sciarrelli-architetto-del-mare",
  "memory-it-ready-0706-bruno-widmar-filosofia-e-impegno-civile",
  "memory-it-ready-0706-gastone-canziani-e-la-psicologia-sperimentale",
  "memory-it-ready-0411-giusto-fegiz-e-la-lotta-alla-tubercolosi",
  "memory-it-ready-0511-luca-vendruscolo-dalla-scrittura-a-boris",
  "memory-it-ready-0114-mario-cubbino-e-il-fumetto-popolare-italiano",
  "memory-it-ready-0319-cesare-pagnini-e-la-storia-giuliana",
  "memory-it-ready-0325-basilio-brollo-e-i-primi-dizionari-della-lingua-cine",
  "memory-it-ready-1129-ferruccio-banissoni-e-lo-studio-delle-emozioni",
  "memory-it-ready-0330-alberto-fasulo-cinema-e-territorio",
];

const FUR_APPROVED_RECORD_IDS_WAVE_43 = [
  "memory-it-ready-1010-enrico-paolo-salem-tra-regime-e-leggi-razziali",
  "memory-it-ready-0128-francesca-clapcich-e-la-vela-oceanica",
  "memory-it-ready-0614-giovanna-botteri-dai-balcani-ai-grandi-conflitti",
  "memory-it-ready-0424-anna-maria-cecchi-e-il-nuoto-olimpico",
  "memory-it-ready-0421-laura-micheli-e-la-ginnastica-del-dopoguerra",
];

const FUR_APPROVED_RECORD_IDS_WAVE_44 = [
  "memory-it-ready-0805-giovanni-coccoluto-due-volte-campione-del-mondo",
  "memory-it-ready-0206-gianfranco-pieri-il-professore-del-basket",
  "memory-it-ready-0706-roberto-pangaro-e-il-primo-podio-mondiale-azzurro",
  "memory-it-ready-0906-ariella-reggio-e-la-nascita-della-contrada",
  "memory-it-ready-0906-martina-orzan-a-un-soffio-dal-podio-olimpico",
  "memory-it-ready-1106-donatella-bulfoni-pioniera-dell-atletica-friulana",
  "memory-it-ready-1106-giampiero-savio-e-il-bronzo-europeo-del-basket",
  "memory-it-ready-1207-giacomo-venezian-diritto-e-impegno-civile",
  "memory-it-ready-1207-giulio-de-vita-dal-fumetto-al-paff",
  "memory-it-ready-0208-giuseppe-kressevich-e-la-scuola-triestina-della-marc",
];

const FUR_APPROVED_RECORD_IDS_WAVE_45 = [
  "memory-it-ready-0609-italo-zannier-e-la-storia-della-fotografia",
  "memory-it-ready-0211-olinto-marinelli-geografia-ed-esplorazione",
  "memory-it-ready-1213-luigi-pio-tessitori-dal-friuli-all-india",
  "memory-it-ready-0615-elio-apih-e-la-storia-del-confine",
  "memory-it-ready-0117-vittorio-benussi-pioniere-della-psicologia-speriment",
  "memory-it-ready-1002-eugenio-boegan-e-il-mondo-sotterraneo-del-carso",
  "memory-it-ready-0212-ettore-fenderl-ingegno-tra-tecnica-e-scienza",
  "memory-it-ready-0826-enrico-maionica-e-l-archeologia-di-aquileia",
  "memory-it-ready-0713-alessandro-pizzorno-una-nuova-sociologia",
  "memory-it-ready-1219-graziana-pentich-tra-poesia-e-pittura",
  "memory-it-ready-0220-viktor-parma-e-la-nascita-dell-opera-slovena",
  "memory-it-ready-0828-geza-de-francovich-il-medioevo-tra-oriente-e-occiden",
];

const FUR_APPROVED_RECORD_IDS_WAVE_46 = [
  "memory-it-ready-0209-laura-coen-luzzatto-tradurre-e-custodire-la-musica",
  "memory-it-ready-0711-carlo-kunz-monete-e-memoria-dei-musei",
  "memory-it-ready-0713-attilio-tamaro-e-la-storia-politica-di-trieste",
  "memory-it-ready-0515-emilia-errera-letteratura-e-scuola",
  "memory-it-ready-0216-stojan-kuret-e-la-musica-corale-europea",
  "memory-it-ready-0616-giorgio-pilleri-dal-cervello-ai-cetacei",
  "memory-it-ready-0218-tiziana-lippiello-un-ponte-con-la-cina-classica",
  "memory-it-ready-0720-pietro-corsi-e-la-storia-delle-idee-scientifiche",
  "memory-it-ready-0820-vincenzo-manzini-e-il-diritto-penale-del-novecento",
  "memory-it-ready-0521-egle-becchi-e-la-storia-dell-infanzia",
  "memory-it-ready-0122-giampaolo-coral-trieste-nella-musica-nuova",
  "memory-it-ready-0826-amalia-popper-la-prima-voce-italiana-di-joyce",
  "memory-it-ready-0529-guido-goldschmiedt-il-chimico-che-decifro-la-papaver",
  "memory-it-ready-0928-ada-buffulini-la-resistenza-nel-lager",
  "memory-it-ready-0329-sergio-peresson-archi-per-i-grandi-del-novecento",
];

const FUR_APPROVED_RECORD_IDS_WAVE_47 = [
  "memory-it-ready-1102-marco-peresani-e-le-vite-dei-neanderthal",
  "memory-it-ready-0913-pompeo-caimo-medicina-e-libri-per-udine",
  "memory-it-ready-0205-andrea-segre-e-la-lotta-allo-spreco-alimentare",
  "memory-it-ready-1110-ottorino-bertolini-e-l-italia-dell-alto-medioevo",
  "memory-it-ready-0911-alessandro-perosa-e-i-testi-dell-umanesimo",
  "memory-it-ready-0828-augusto-de-brandis-collezioni-per-il-friuli",
  "memory-it-ready-1226-amedeo-herlitzka-e-la-fisiologia-sperimentale",
  "memory-it-ready-0628-enzo-cozzolino-e-una-nuova-idea-di-arrampicata",
  "memory-it-ready-0202-tiziana-weiss-alpinismo-e-conoscenza-della-montagna",
  "memory-it-ready-1219-armando-filiput-oro-europeo-e-primato-negli-ostacoli",
  "memory-it-ready-0831-cesare-nordio-dirigere-e-insegnare-la-musica",
];

const FUR_APPROVED_RECORD_IDS_WAVE_48 = [
  "memory-it-ready-0605-rodolfo-batagelj-e-il-sacrificio-sul-daniele-manin",
  "memory-it-ready-0317-stefano-zoff-un-titolo-mondiale-sul-ring",
  "memory-it-ready-0621-luigi-frausin-e-la-resistenza-a-trieste",
  "memory-it-ready-0721-attilio-basso-coraggio-nella-battaglia-di-cheren",
  "memory-it-ready-0824-arduino-forgiarini-e-il-dovere-sul-sommergibile-perl",
  "memory-it-ready-0331-germano-craighero-coraggio-in-servizio",
  "memory-it-ready-1005-francesco-arnaldi-e-i-classici-latini",
  "memory-it-ready-1017-orlando-dipiazza-e-la-musica-corale",
  "memory-it-ready-0106-paolo-camossi-campione-mondiale-nel-salto-triplo",
  "memory-it-ready-0905-silvio-furlani-e-la-biblioteca-della-camera",
  "memory-it-ready-1128-gian-giuseppe-liruti-e-la-storia-del-friuli",
];

const FUR_APPROVED_RECORD_IDS_WAVE_53 = [
  "memory-it-ready-0108-reno-bertoia-dal-friuli-alla-major-league-baseball",
];

const FUR_APPROVED_RECORD_IDS_WAVE_54 = [
  "memory-it-ready-0703-federico-flora-e-la-scienza-delle-finanze",
  "memory-it-ready-0803-federico-enriques-e-la-cultura-dei-libri",
  "memory-it-ready-0507-franco-devescovi-e-martin-mystere",
  "memory-it-ready-0901-ricciotti-lazzero-e-la-memoria-della-deportazione",
  "memory-it-ready-0711-bruno-dreossi-bronzo-olimpico-in-canoa",
];

const FUR_APPROVED_RECORD_IDS_WAVE_57 = [
  "memory-it-ready-1006-luciano-savio-e-lo-sviluppo-industriale-di-pordenone",
  "memory-it-ready-0308-gioacchino-rasponi-e-il-risorgimento",
  "memory-it-ready-0715-paolo-treu-ai-vertici-della-marina",
];

const FUR_APPROVED_RECORD_IDS_WAVE_60 = [
  "memory-it-ready-0107-le-nuove-province-nella-legislazione-italiana",
  "memory-it-ready-0109-nasce-il-movimento-friuli",
  "memory-it-ready-0113-pordenone-passa-sotto-le-truppe-austriache",
  "memory-it-ready-0118-la-provincia-di-gorizia-viene-soppressa",
  "memory-it-ready-0119-la-prima-assemblea-autonomista-del-dopoguerra",
  "memory-it-ready-0210-il-trattato-che-ridisegna-il-confine-orientale",
  "memory-it-ready-0215-lino-zanussi-e-la-pordenone-industriale",
  "memory-it-ready-0223-la-tutela-della-minoranza-slovena-diventa-legge",
  "memory-it-ready-0224-l-ultimo-convoglio-dalla-risiera",
  "memory-it-ready-0226-il-sistema-tavolare-nel-goriziano",
  "memory-it-ready-0302-mario-zafred-musica-tra-trieste-e-il-novecento",
  "memory-it-ready-0307-un-convoglio-da-trieste-verso-dachau",
  "memory-it-ready-0309-umberto-saba-poeta-di-trieste",
  "memory-it-ready-0313-nasce-l-istituto-per-la-storia-della-liberazione",
  "memory-it-ready-0314-marija-bernetic-antifascismo-e-diritti",
];

const FUR_APPROVED_RECORD_IDS_WAVE_61 = [
  "memory-it-ready-0318-trieste-diventa-porto-franco",
  "memory-it-ready-0322-il-friulano-diventa-lingua-riconosciuta",
  "memory-it-ready-0323-nasce-il-governo-provvisorio-di-udine",
  "memory-it-ready-0324-palmanova-caccia-gli-austriaci",
  "memory-it-ready-0406-la-guerra-investe-il-confine-orientale",
  "memory-it-ready-0408-la-medaglia-d-oro-a-virginia-tonelli",
  "memory-it-ready-0409-l-eccidio-delle-carceri-di-udine",
  "memory-it-ready-0412-l-assalto-al-castello-di-torre",
  "memory-it-ready-0413-la-linea-wilson-ridisegna-il-confine",
  "memory-it-ready-0416-la-battaglia-di-sacile",
  "memory-it-ready-0419-lo-statuto-dell-arlef",
  "memory-it-ready-0422-la-capitolazione-di-udine",
  "memory-it-ready-0428-il-cln-ordina-la-presa-del-potere",
  "memory-it-ready-0501-la-corsa-per-trieste",
  "memory-it-ready-0506-il-terremoto-del-friuli",
];

const FUR_APPROVED_RECORD_IDS_WAVE_62 = [
  "memory-it-ready-0608-nasce-l-orientalista-luciano-petech",
  "memory-it-ready-0625-nasce-lo-scultore-nino-franchina",
  "memory-it-ready-0702-gio-batta-morassi-e-la-liuteria",
  "memory-it-ready-0705-nasce-il-compositore-giulio-viozzi",
  "memory-it-ready-0801-aldo-visalberghi-e-la-scuola-democratica",
  "memory-it-ready-1109-nasce-il-poeta-mario-benedetti",
  "memory-it-ready-1201-amedeo-tommasi-tra-jazz-e-cinema",
  "memory-it-ready-1206-nasce-l-antifascista-anton-ukmar",
  "memory-it-ready-1218-nasce-l-economista-bonaldo-stringher",
  "memory-it-ready-1225-nasce-il-basso-bonaldo-giaiotti",
];

const FUR_APPROVED_RECORD_IDS_WAVE_63 = [
  "memory-it-ready-0513-girolamo-ortis-dal-friuli-al-romanzo-di-foscolo",
];

const FUR_APPROVED_RECORD_IDS_WAVE_64 = [
  "memory-it-ready-0519-il-riconoscimento-della-doc-friuli-latisana",
];

const FUR_APPROVED_RECORD_IDS_WAVE_65 = [
  "memory-it-ready-0520-la-prima-riunione-degli-alpini-per-la-ricostruzione",
  "memory-it-ready-0522-il-comune-di-gorizia-viene-commissariato",
  "memory-it-ready-0530-la-guerra-raggiunge-la-stazione-transalpina",
];

const FUR_APPROVED_RECORD_IDS_WAVE_66 = [
  "memory-it-ready-0508-a-gemona-si-traccia-la-linea-per-l-emergenza",
  "memory-it-ready-0510-il-primo-voto-della-regione-autonoma",
  "memory-it-ready-0512-finisce-la-repubblica-di-venezia",
  "memory-it-ready-0526-gorizia-sente-la-guerra-alle-porte",
];

const FUR_APPROVED_RECORD_IDS_WAVE_67 = [
  "memory-it-ready-0602-il-voto-repubblicano-non-raggiunge-tutto-il-confine",
  "memory-it-ready-0607-udine-passa-sotto-venezia",
  "memory-it-ready-0617-le-truppe-italiane-conquistano-plava",
  "memory-it-ready-0622-la-banda-civica-di-gorizia-viene-sciolta",
  "memory-it-ready-0626-gorizia-ordina-ai-civili-di-restare-in-casa",
  "memory-it-ready-0704-gorizia-entra-nelle-nuove-provincie",
];

const FUR_APPROVED_RECORD_IDS_WAVE_68 = [
  "memory-it-ready-0709-il-leone-di-san-marco-sul-portale-del-castello",
  "memory-it-ready-0724-il-bombardamento-colpisce-il-monastero-delle-orsolin",
  "memory-it-ready-0725-a-gorizia-arriva-la-notizia-della-crisi-con-la-serbi",
  "memory-it-ready-0809-gorizia-passa-sotto-il-controllo-italiano",
  "memory-it-ready-0812-l-armistizio-di-cormons-ridisegna-il-confine",
  "memory-it-ready-0823-caneva-si-arrende-a-venezia-dopo-l-assedio",
];

const FUR_APPROVED_RECORD_IDS_WAVE_69 = [
  "memory-it-ready-0916-dai-fogolars-nasce-l-idea-di-friuli-nel-mondo",
  "memory-it-ready-1003-il-trattato-di-vienna-porta-palmanova-nel-regno-d-it",
  "memory-it-ready-1011-venezia-ferma-l-esportazione-del-vino-da-pordenone",
  "memory-it-ready-1023-tina-jama-restituisce-un-raro-pugnale-di-rame",
  "memory-it-ready-1025-a-vienna-si-chiede-l-autodeterminazione-dei-friulani",
];

const FUR_APPROVED_RECORD_IDS_WAVE_70 = [
  "memory-it-ready-1101-un-elenco-racconta-chi-rimase-nella-gorizia-evacuata",
  "memory-it-ready-1107-il-municipio-di-gorizia-prepara-l-arrivo-dell-eserci",
  "memory-it-ready-1108-diaz-prende-il-comando-dopo-caporetto",
  "memory-it-ready-1113-dopo-caporetto-comincia-la-prima-battaglia-del-piave",
  "memory-it-ready-1118-gorizia-sotto-una-pioggia-di-proiettili",
  "memory-it-ready-1215-viene-approvato-lo-statuto-della-deputazione-di-stor",
];

const FUR_APPROVED_RECORD_IDS_WAVE_71 = [
  "memory-it-ready-0627-alla-costituente-si-afferma-il-nome-friuli-venezia-g",
  "memory-it-ready-0807-d-annunzio-vola-su-trieste-e-lancia-bandiere-e-volan",
];

const FUR_APPROVED_RECORD_IDS_WAVE_72 = [
  "memory-it-ready-1115-emilio-cravos-protesta-nella-gorizia-di-guerra",
  "memory-it-ready-1223-ungaretti-scrive-veglia-sul-san-michele",
];

const FUR_APPROVED_RECORD_IDS_WAVE_73 = [
  "memory-it-ready-1121-alojzij-res-racconta-gorizia-in-fiamme",
  "memory-it-ready-1205-i-goriziani-rifiutano-l-evacuazione-volontaria",
  "memory-it-ready-1224-natale-per-i-bambini-delle-orsoline",
];

const FUR_APPROVED_RECORD_IDS_WAVE_74 = [
  "memory-it-ready-1124-le-strade-deserte-di-gorizia",
  "memory-it-ready-1127-l-ospedale-femminile-diventa-militare",
];

const FUR_APPROVED_RECORD_IDS_WAVE_75 = [
  "memory-it-ready-0822-nino-paternolli-tra-le-rovine-della-tipografia",
  "memory-it-ready-0830-suor-camilla-resta-con-i-feriti",
  "memory-it-ready-0930-l-ora-legale-entra-in-vigore-a-gorizia",
  "memory-it-ready-1004-la-protesta-nel-campo-di-wagna",
];

const FUR_APPROVED_RECORD_IDS_WAVE_76 = [
  "memory-it-ready-0518-sei-bambini-delle-orsoline-partono-per-livorno",
  "memory-it-ready-0613-faidutti-difende-il-sussidio-dei-profughi-goriziani",
];

const FUR_APPROVED_RECORD_IDS_WAVE_77 = [
  "memory-it-ready-0630-la-bolla-che-ridisegna-le-diocesi-del-litorale",
  "memory-it-ready-0810-a-udine-la-grande-fiera-di-san-lorenzo",
  "memory-it-ready-0925-vietati-gli-schioppi-nascosti-sotto-i-mantelli",
  "memory-it-ready-1020-i-lagunari-nella-nuova-brigata-gorizia",
  "memory-it-ready-1228-gli-auguri-dei-bambini-di-casa-in-casa",
];

const FUR_APPROVED_RECORD_IDS_WAVE_78 = [
  "memory-it-ready-1208-a-gemona-l-immacolata-ricorda-un-grande-incendio",
  "memory-it-ready-1229-fabio-asquini-l-agricoltura-incontra-la-scienza",
];

const IT_APPROVED_PENDING_FUR_RECORD_IDS = [];

const SECONDARY_ENRICHMENT_WAVE_01_IDS = [
  "memory-secondary-0101-societa-minerva-1810",
  "memory-secondary-1005-ictp-inaugurazione-1964",
];

const readySource = {
  categories: {
    storia: { it: "Storia locale", fur: "Storie locâl" },
    cultura: { it: "Lingua e cultura", fur: "Lenghe e culture" },
  },
  records: [
    {
      id: "ready-exact",
      primaryUse: "discover",
      category: "storia",
      dateAnchors: ["07-03"],
      priority: 1,
      title: { it: "Evento verificato", fur: "Event verificât" },
      summary: { it: "Testo breve verificato.", fur: "Test curt verificât." },
      source: { label: "Fonte verificata", type: "verified_source" },
      editorialStatus: "ready_for_discover",
      languageStatus: { it: "approved", fur: "approved" },
      readyForUi: true,
    },
    {
      id: "ready-rotation-a",
      primaryUse: "discover",
      category: "cultura",
      dateAnchors: [],
      priority: 2,
      title: { it: "Rotazione A", fur: "pending_review" },
      summary: { it: "Prima pillola di rotazione.", fur: "pending_review" },
      source: { label: "Nota editoriale", type: "editorial_note" },
      editorialStatus: "ready_for_discover",
      languageStatus: { it: "approved", fur: "pending_review" },
      readyForUi: true,
    },
    {
      id: "ready-secondary",
      primaryUse: "discover",
      category: "cultura",
      dailyRole: "secondary",
      dateAnchors: ["07-03"],
      areas: ["pordenone"],
      priority: 2,
      title: { it: "Voce secondaria", fur: "Vôs secondarie" },
      summary: { it: "Nota breve da mostrare come voce secondaria.", fur: "Note curte di mostrâ come vôs secondarie." },
      source: { label: "Fonte verificata", type: "verified_source" },
      editorialStatus: "ready_for_discover",
      languageStatus: { it: "approved", fur: "approved" },
      readyForUi: true,
    },
    {
      id: "ready-secondary-trieste",
      primaryUse: "discover",
      category: "cultura",
      dailyRole: "secondary",
      dateAnchors: ["07-03"],
      areas: ["trieste"],
      priority: 3,
      title: { it: "Voce triestina", fur: "Vos triestine" },
      summary: { it: "Nota breve legata a Trieste.", fur: "Note curte leade a Triest." },
      source: { label: "Fonte verificata", type: "verified_source" },
      editorialStatus: "ready_for_discover",
      languageStatus: { it: "approved", fur: "approved" },
      readyForUi: true,
    },
  ],
};

describe("local memory discover archive", () => {
  it("summarizes the reviewed local memory records available to Scopri", () => {
    const summary = getLocalMemorySummary();

    expect(summary.totalRecords).toBe(581);
    expect(summary.sourceNeededRecords).toBe(0);
    expect(summary.sourceCandidateRecords).toBe(3);
    expect(summary.sourceVerifiedRecords).toBe(9);
    expect(summary.copyDraftItRecords).toBe(11);
    expect(summary.copyDraftFurRecords).toBe(0);
    expect(summary.approvedItRecords).toBe(567);
    expect(summary.approvedFurRecords).toBe(567);
    expect(summary.furHumanReviewNeededRecords).toBe(11);
    expect(summary.readyForDiscoverRecords).toBe(567);
    expect(summary.localityFocusReadyRecords).toBe(4);
    expect(summary.localityFocusProvinceCodes).toEqual(["GO", "PN", "TS", "UD"]);
    expect(getLocalMemoryForDate({ date: "2026-07-03" })).toMatchObject({
      id: "memory-draft-0703-aquileia-basilica",
      title: "Aquileia, mosaico sotto i passi",
      typeLabel: "Scoperte e archeologia",
    });
    expect(getLocalMemoryForDate({
      date: "2026-07-05",
      language: "fur",
    })).toMatchObject({
      id: "memory-it-ready-0705-nasce-il-compositore-giulio-viozzi",
      title: "Al nas il compositôr Giulio Viozzi",
      selectionKind: "exact_date",
    });
    expect(getLocalMemoryForDate({ date: "2026-06-11" })).toMatchObject({
      id: "memory-ostermann-san-barnaba-viti",
      title: "San Barnaba e la vendemmia",
      selectionKind: "exact_date",
    });
    expect(getLocalMemoryForDate({
      date: "2026-07-12",
      language: "fur",
    })).toMatchObject({
      id: "memory-ostermann-sant-ermacora-bufere",
      title: "Sant Ermacore, la setemane inquiete",
      selectionKind: "exact_date",
    });
  });

  it("selects an exact date record only when it is ready and sourced", () => {
    const card = getLocalMemoryForDate({
      date: "2026-07-03",
      language: "it",
      source: readySource,
    });

    expect(card).toMatchObject({
      id: "ready-exact",
      title: "Evento verificato",
      typeLabel: "Storia locale",
      seasonLabel: "3 luglio",
      selectionKind: "exact_date",
      sourceLabel: "Fonte verificata",
    });
  });

  it("formats daily memory dates for the active language without exposing internal keys", () => {
    expect(getLocalMemoryForDate({
      date: "2026-07-03",
      language: "it",
      source: readySource,
    })).toMatchObject({ seasonLabel: "3 luglio" });

    expect(getLocalMemoryForDate({
      date: "2026-07-03",
      language: "fur",
      source: readySource,
    })).toMatchObject({ seasonLabel: "3 di Lui" });
  });

  it("maps editorial category keys to readable labels", () => {
    const source = {
      categories: {
        scienza: { it: "Scienza e territorio", fur: "Science e teritori" },
      },
      records: [{
        id: "science-territory",
        primaryUse: "discover",
        category: "scienza_territorio",
        dateAnchors: ["07-04"],
        priority: 1,
        title: { it: "Una ricerca locale", fur: "Une ricercje locâl" },
        summary: { it: "Testo verificato.", fur: "Test verificât." },
        source: { label: "Fonte verificata", type: "verified_source" },
        editorialStatus: "ready_for_discover",
        languageStatus: { it: "approved", fur: "approved" },
        readyForUi: true,
      }],
    };

    expect(getLocalMemoryForDate({
      date: "2026-07-04",
      language: "it",
      source,
    })).toMatchObject({ typeLabel: "Scienza e territorio" });
    expect(getLocalMemoryForDate({
      date: "2026-07-04",
      language: "fur",
      source,
    })).toMatchObject({ typeLabel: "Science e teritori" });
  });

  it("keeps secondary memories separate from the main daily memory", () => {
    const mainCard = getLocalMemoryForDate({
      date: "2026-07-03",
      language: "it",
      source: readySource,
    });
    const secondaryCards = getLocalMemorySecondaryForDate({
      date: "2026-07-03",
      language: "it",
      location: { city: "Pordenone", region: "Friuli Venezia Giulia" },
      source: readySource,
    });

    expect(mainCard).toMatchObject({
      id: "ready-exact",
      dailyRole: "primary",
      selectionKind: "exact_date",
    });
    expect(secondaryCards).toEqual([
      expect.objectContaining({
        id: "ready-secondary",
        dailyRole: "secondary",
        selectionKind: "exact_date_secondary",
      }),
    ]);
  });

  it("filters secondary memories by active city or province", () => {
    expect(getLocalMemorySecondaryForDate({
      date: "2026-07-03",
      language: "it",
      location: { city: "Trieste", region: "Friuli Venezia Giulia" },
      source: readySource,
    })).toEqual([
      expect.objectContaining({ id: "ready-secondary-trieste" }),
    ]);

    expect(getLocalMemorySecondaryForDate({
      date: "2026-07-03",
      language: "it",
      location: { city: "Gorizia", region: "Friuli Venezia Giulia" },
      source: readySource,
    })).toEqual([]);
  });

  it("builds the locality focus with city, province, then FVG fallback", () => {
    const source = {
      categories: readySource.categories,
      records: [
        {
          ...readySource.records[0],
          id: "location-city",
          areas: ["cordenons", "pordenone", "friuli_venezia_giulia"],
          localityFocus: {
            temporal: "evergreen",
            targets: [{ scope: "municipality", istatCode: "093017" }],
          },
          title: { it: "Cordenons", fur: "Cordenons" },
        },
        {
          ...readySource.records[0],
          id: "location-province",
          areas: ["pordenone", "friuli_venezia_giulia"],
          localityFocus: {
            temporal: "evergreen",
            targets: [{ scope: "province", code: "PN" }],
          },
          title: { it: "Pordenonese", fur: "Pordenon" },
        },
        {
          ...readySource.records[0],
          id: "location-region",
          areas: ["friuli_venezia_giulia"],
          localityFocus: {
            temporal: "evergreen",
            targets: [{ scope: "region", code: "FVG" }],
          },
          title: { it: "Friuli Venezia Giulia", fur: "Friul Vignesie Julie" },
        },
      ],
    };

    expect(getLocalMemoryForLocation({
      date: "2026-07-11",
      language: "it",
      location: { city: "Cordenons" },
      source,
    })).toMatchObject({
      id: "location-city",
      locationLabel: "Cordenons",
      locationScope: "city",
      selectionKind: "location_focus",
      visualKind: "location",
    });

    expect(getLocalMemoryForLocation({
      date: "2026-07-11",
      excludeIds: ["location-city"],
      language: "it",
      location: { city: "Cordenons" },
      source,
    })).toMatchObject({
      id: "location-province",
      locationLabel: "PN · Pordenone",
      locationScope: "province",
    });

    expect(getLocalMemoryForLocation({
      date: "2026-07-11",
      excludeIds: ["location-city", "location-province"],
      language: "it",
      location: { city: "Cordenons" },
      source,
    })).toMatchObject({
      id: "location-region",
      locationLabel: "Friuli Venezia Giulia",
      locationScope: "region",
    });
  });

  it("keeps the locality focus stable for the same day and excludes used cards", () => {
    const source = {
      categories: readySource.categories,
      records: [
        {
          ...readySource.records[0],
          id: "location-a",
          areas: ["pordenone"],
          localityFocus: {
            temporal: "evergreen",
            targets: [{ scope: "province", code: "PN" }],
          },
        },
        {
          ...readySource.records[0],
          id: "location-b",
          areas: ["pordenone"],
          localityFocus: {
            temporal: "evergreen",
            targets: [{ scope: "province", code: "PN" }],
          },
        },
      ],
    };
    const options = {
      date: "2026-07-11",
      language: "it",
      location: { city: "Pordenone" },
      source,
    };
    const first = getLocalMemoryForLocation(options);
    const second = getLocalMemoryForLocation(options);

    expect(second.id).toBe(first.id);
    expect(getLocalMemoryForLocation({
      ...options,
      excludeIds: [first.id],
    }).id).not.toBe(first.id);
  });

  it("does not infer province scope from the legacy areas field", () => {
    const source = {
      categories: readySource.categories,
      records: [{
        ...readySource.records[0],
        id: "legacy-pordenone-area",
        areas: ["pordenone", "friuli_venezia_giulia"],
      }],
    };

    expect(getLocalMemoryForLocation({
      date: "2026-07-11",
      language: "it",
      location: { city: "Cordenons" },
      source,
    })).toBeNull();
  });

  it("falls back to a rotating Scopri pill when the date has no exact record", () => {
    const card = getLocalMemoryForDate({
      date: "2026-07-04",
      language: "it",
      source: readySource,
    });

    expect(card).toMatchObject({
      id: "ready-rotation-a",
      title: "Rotazione A",
      typeLabel: "Lingua e cultura",
      selectionKind: "rotation",
    });
  });

  it("hides local memory in FUR when FUR is not approved", () => {
    const card = getLocalMemoryForDate({
      date: "2026-07-04",
      language: "fur",
      source: readySource,
    });

    expect(card).toBeNull();
  });

  it("exposes records for editorial tooling without publishing them", () => {
    const records = getLocalMemoryRecords();

    expect(records.every((record) => record.primaryUse === "discover")).toBe(true);
    expect(records.filter((record) => record.readyForUi === true)).toHaveLength(567);
    expect(records.filter((record) => record.readyForUi === true).map((record) => record.id)).toEqual([
      "memory-draft-0703-aquileia-basilica",
      "memory-ostermann-san-barnaba-viti",
      "memory-ostermann-sant-ermacora-bufere",
      "memory-review-1219-italo-svevo",
      "memory-review-0402-alessandro-moissi",
      "memory-review-0331-carlo-rubbia",
      "memory-review-0504-giorgio-mainerio",
      "memory-review-0805-gino-de-finetti",
      "memory-source-aquileia-crocevia-popoli",
      "memory-source-aquileia-museo-archeologico",
      "memory-source-aquileia-unesco-181",
      "memory-copy-0818-gaetano-kanizsa",
      "memory-copy-0205-napoleone-cozzi",
      "memory-copy-1015-giovanni-da-udine",
      "memory-copy-0813-lella-vignelli",
      "memory-copy-0121-tito-maniacco",
      "memory-copy-0615-lojze-spacal",
      "memory-copy-0902-adalgiso-fior",
      "memory-copy-0603-giovanni-battista-bassi",
      "memory-copy-0504-lojzka-bratuz",
      "memory-copy-0429-valentin-stanic",
      "memory-copy-1005-giorgio-pressburger",
      "memory-copy-0120-luca-carlevarijs",
      "memory-copy-0820-enrico-rava",
      "memory-copy-0708-lelio-luttazzi",
      "memory-copy-0316-ernesto-nathan-rogers",
      "memory-copy-0409-stefan-kociancic",
      "memory-copy-0411-matteo-pertsch",
      "memory-copy-1111-giorgio-voghera",
      "memory-copy-1122-silvio-benco",
      "memory-copy-0225-eugenio-geiringer",
      "memory-copy-0410-claudio-magris",
      "memory-copy-0304-afro-basaldella",
      "memory-copy-1017-carlo-michelstaedter",
      "memory-backlog-0716-graziadio-ascoli",
      "memory-backlog-0414-tiziano-tessitori",
      "memory-backlog-0225-achille-tellini",
      "memory-backlog-0919-giuseppe-francescato",
      "memory-backlog-0714-scipio-slataper",
      "memory-backlog-0229-pietro-blaserna",
      "memory-copy-0629-biagio-marin",
      "memory-copy-0826-novella-cantarutti",
      "memory-copy-1001-pierluigi-cappello",
      "memory-copy-1007-giovanni-battista-brusin",
      "memory-history-1009-vajont",
      "memory-history-0426-assedio-osoppo",
      "memory-reviewpack-0713-antonio-zucchelli",
      "memory-reviewpack-0814-max-fabiani",
      "memory-reviewpack-0905-ludwig-boltzmann",
      ...FUR_APPROVED_RECORD_IDS,
      ...FUR_APPROVED_RECORD_IDS_WAVE_3,
      ...FUR_APPROVED_RECORD_IDS_WAVE_4,
      ...FUR_APPROVED_RECORD_IDS_WAVE_5,
      ...FUR_APPROVED_RECORD_IDS_WAVE_7,
      ...FUR_APPROVED_RECORD_IDS_WAVE_8,
      ...FUR_APPROVED_RECORD_IDS_WAVE_9,
      ...FUR_APPROVED_RECORD_IDS_WAVE_10,
      ...FUR_APPROVED_RECORD_IDS_WAVE_11,
      ...FUR_APPROVED_RECORD_IDS_WAVE_12,
      ...FUR_APPROVED_RECORD_IDS_WAVE_13,
      ...FUR_APPROVED_RECORD_IDS_WAVE_17_PRE_WAVE_15,
      ...FUR_APPROVED_RECORD_IDS_WAVE_15,
      ...FUR_APPROVED_RECORD_IDS_WAVE_17_AFTER_WAVE_15,
      ...FUR_APPROVED_RECORD_IDS_WAVE_15_TAIL,
      ...FUR_APPROVED_RECORD_IDS_WAVE_16,
      ...FUR_APPROVED_RECORD_IDS_WAVE_18,
      ...FUR_APPROVED_RECORD_IDS_WAVE_19,
      ...FUR_APPROVED_RECORD_IDS_WAVE_20,
      ...FUR_APPROVED_RECORD_IDS_WAVE_21,
      ...FUR_APPROVED_RECORD_IDS_WAVE_22,
      ...FUR_APPROVED_RECORD_IDS_WAVE_23,
      ...FUR_APPROVED_RECORD_IDS_WAVE_24,
      ...FUR_APPROVED_RECORD_IDS_WAVE_25,
      ...FUR_APPROVED_RECORD_IDS_WAVE_26,
      ...FUR_APPROVED_RECORD_IDS_WAVE_27,
      ...FUR_APPROVED_RECORD_IDS_WAVE_28,
      ...FUR_APPROVED_RECORD_IDS_WAVE_29,
      ...FUR_APPROVED_RECORD_IDS_WAVE_30,
      ...FUR_APPROVED_RECORD_IDS_WAVE_31,
      ...FUR_APPROVED_RECORD_IDS_WAVE_32,
      ...FUR_APPROVED_RECORD_IDS_WAVE_34,
      ...FUR_APPROVED_RECORD_IDS_WAVE_35,
      ...FUR_APPROVED_RECORD_IDS_WAVE_36,
      ...FUR_APPROVED_RECORD_IDS_WAVE_37,
      ...FUR_APPROVED_RECORD_IDS_WAVE_38,
      ...FUR_APPROVED_RECORD_IDS_WAVE_39,
      ...FUR_APPROVED_RECORD_IDS_WAVE_40,
      ...FUR_APPROVED_RECORD_IDS_WAVE_41,
      ...FUR_APPROVED_RECORD_IDS_WAVE_42,
      ...FUR_APPROVED_RECORD_IDS_WAVE_43,
      ...FUR_APPROVED_RECORD_IDS_WAVE_44,
      ...FUR_APPROVED_RECORD_IDS_WAVE_45,
      ...FUR_APPROVED_RECORD_IDS_WAVE_46,
      ...FUR_APPROVED_RECORD_IDS_WAVE_47,
      ...FUR_APPROVED_RECORD_IDS_WAVE_48,
      ...FUR_APPROVED_RECORD_IDS_WAVE_53,
      ...FUR_APPROVED_RECORD_IDS_WAVE_54,
      ...FUR_APPROVED_RECORD_IDS_WAVE_57,
      ...FUR_APPROVED_RECORD_IDS_WAVE_60,
      ...FUR_APPROVED_RECORD_IDS_WAVE_61,
      ...FUR_APPROVED_RECORD_IDS_WAVE_62,
      ...FUR_APPROVED_RECORD_IDS_WAVE_63,
      ...FUR_APPROVED_RECORD_IDS_WAVE_64,
      ...FUR_APPROVED_RECORD_IDS_WAVE_65,
      ...FUR_APPROVED_RECORD_IDS_WAVE_66,
      ...FUR_APPROVED_RECORD_IDS_WAVE_67,
      ...FUR_APPROVED_RECORD_IDS_WAVE_68,
      ...FUR_APPROVED_RECORD_IDS_WAVE_69,
      ...FUR_APPROVED_RECORD_IDS_WAVE_70,
      ...FUR_APPROVED_RECORD_IDS_WAVE_71,
      ...FUR_APPROVED_RECORD_IDS_WAVE_72,
      ...FUR_APPROVED_RECORD_IDS_WAVE_73,
      ...FUR_APPROVED_RECORD_IDS_WAVE_74,
      ...FUR_APPROVED_RECORD_IDS_WAVE_75,
      ...FUR_APPROVED_RECORD_IDS_WAVE_76,
      ...FUR_APPROVED_RECORD_IDS_WAVE_77,
      ...FUR_APPROVED_RECORD_IDS_WAVE_78,
      ...SECONDARY_ENRICHMENT_WAVE_01_IDS,
    ]);
    expect(records.filter((record) => record.editorialStatus === "source_verified").map((record) => record.id)).toEqual([
      "memory-copy-0616-stanislaus-joyce",
      "memory-copy-0507-gianni-bisiach",
      "memory-copy-0412-gillo-dorfles",
      "memory-copy-0705-flavio-paulin",
      "memory-copy-1013-marcello-de-stefano",
      "memory-copy-0318-eugenio-pilutti",
      "memory-copy-0706-alberto-spaini",
      "memory-copy-0709-aldo-stellita",
      "memory-copy-0325-giulio-camagni",
      ...IT_APPROVED_PENDING_FUR_RECORD_IDS,
    ]);
    expect(records.filter((record) => record.editorialStatus === "copy_candidate").map((record) => record.id)).toEqual([
      "memory-backlog-0530-boris-pahor",
      "memory-backlog-0205-julius-kugy",
    ]);
    expect(records.filter((record) => record.editorialStatus === "copy_candidate").every((record) => (
      record.readyForUi === false &&
      record.languageStatus.it === "copy_draft" &&
      record.languageStatus.fur === "human_review_needed" &&
      record.source.type === "daily_history_master_candidate"
    ))).toBe(true);
    expect(records.filter((record) => (
      record.editorialStatus === "source_verified" &&
      record.id.startsWith("memory-copy-")
    )).every((record) => (
      record.readyForUi === false &&
      record.languageStatus.it === "copy_draft" &&
      record.languageStatus.fur === "human_review_needed" &&
      record.source.type === "verified_source"
    ))).toBe(true);
    expect(records.filter((record) => (
      record.editorialStatus === "copy_candidate" &&
      record.title.fur !== "pending_review" &&
      record.summary.fur !== "pending_review"
    )).map((record) => record.id)).toEqual([]);
  });
});
