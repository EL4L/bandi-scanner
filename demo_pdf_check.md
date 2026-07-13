# Verifica estrazione PDF demo

Generato chiamando direttamente `extract_text_from_pdf()` e `extract_bando_data()`. Nessun dato è stato salvato nel database.

## Complesso.pdf

- Caratteri estratti e analizzati integralmente: 206141
- Soglia per singola chiamata: 250000

```json
{
  "bando": {
    "titolo": "Nuovo Fondo Futuro (NFF) - Annualità 2025",
    "ente": "Regione Lazio",
    "data_pubblicazione": "2026-04-16",
    "data_scadenza": null,
    "codici_ateco_ammessi": [],
    "attivita_ammesse": [
      "Acquisto di arredi, impianti, macchinari e attrezzature nuovi",
      "Acquisto di mezzi targati come beni strumentali",
      "Investimenti per sicurezza nei luoghi di lavoro",
      "Investimenti per riduzione impatto ambientale",
      "Acquisto di brevetti e brevetti",
      "Realizzazione di sistema di qualità e certificazioni",
      "Ricerca e sviluppo",
      "Realizzazione sito web",
      "Acquisto di software per esigenze produttive e gestionali",
      "Opere per adeguamento funzionale e ristrutturazione della sede operativa",
      "Altre spese connesse alla realizzazione del progetto"
    ],
    "ateco_aperto_a_tutti": false,
    "regioni_ammesse": [
      "Lazio"
    ],
    "dimensione_impresa": {
      "micro": true,
      "piccola": false,
      "media": false,
      "grande": false
    },
    "fatturato_max": 2000000,
    "numero_dipendenti_min": null,
    "numero_dipendenti_max": 10,
    "contributo_max": null,
    "percentuale_fondo_perduto": {
      "micro": null,
      "piccola": null,
      "media": null,
      "default": null
    },
    "modalita_presentazione": "sportello",
    "tipo_agevolazione": [
      "finanziamento_agevolato"
    ],
    "cumulabilita": "I finanziamenti agevolati sono erogati in applicazione del Reg. UE N. 2831/2023 della Commissione del 13 dicembre 2023 relativo all'applicazione degli articoli 107 e 108 del trattato sul funzionamento dell'Unione Europea agli aiuti «de minimis» alle imprese, che prevede, tra l'altro, che gli Stati membri non possono concedere più di 300.000,00 euro di aiuti De Minimis nell'arco di tre anni a un'Impresa Unica.",
    "spese_ammissibili": [
      "Acquisto di arredi, impianti, macchinari e attrezzature nuovi di fabbrica",
      "Acquisto di mezzi targati solo se beni strumentali",
      "Investimenti per sicurezza nei luoghi di lavoro",
      "Investimenti per riduzione impatto ambientale",
      "Acquisto di brevetti, realizzazione di sistema di qualità, certificazione di qualità",
      "Ricerca e sviluppo",
      "Realizzazione sito web",
      "Acquisto di software per esigenze produttive e gestionali",
      "Opere per adeguamento funzionale e ristrutturazione della sede operativa",
      "Altre spese connesse al progetto"
    ],
    "link_fonte_ufficiale": "https://www.farelazio.it",
    "note_esclusioni": {
      "lista_testuale": "Sono escluse le società di capitali diverse da quelle ammesse. Non sono ammissibili Microimprese con operatori specializzati nel sostegno finanziario (Business Angels, investitori istituzionali). Esclusi investimenti legati a produzione, trasformazione, trasporto, distribuzione, stoccaggio o combustione di combustibili fossili (eccetto risorse POC 14-20 e regionali). Esclusioni di attività economiche per DNSH: tabacco, gioco d'azzardo, armi, pornografia, energia nucleare, attività che violano diritti umani, clonazione umana, ricerca con animali vivi, sviluppo immobiliare, attività finanziarie, smantellamento nucleare, estrazione mineraria, carbone, petrolio, gas, discariche, TMB, inceneritori (con eccezioni specifiche).",
      "sezioni_ateco_escluse": [],
      "attivita_vietate": [
        "Tabacco e bevande alcoliche distillate",
        "Armi e munizioni",
        "Gioco d'azzardo e case da gioco",
        "Pornografia e commercio sessuale",
        "Energia nucleare",
        "Attività che violano diritti umani",
        "Clonazione umana",
        "Ricerca con animali vivi",
        "Sviluppo immobiliare",
        "Attività finanziarie",
        "Estrazione mineraria e combustibili fossili",
        "Discariche",
        "Impianti TMB",
        "Inceneritori"
      ]
    },
    "spesa_minima_ammissibile": 5000,
    "spesa_massima_ammissibile": null,
    "anzianita_impresa": {
      "mesi_minimi_dalla_costituzione": null,
      "mesi_massimi_dalla_costituzione": 36
    },
    "forme_giuridiche_ammesse": [
      "Liberi Professionisti",
      "Ditte individuali",
      "Società in nome collettivo (S.n.c.)",
      "Società in accomandita semplice (S.a.s.)",
      "Società cooperative",
      "Società a responsabilità limitata (S.r.l)",
      "Società a responsabilità limitata semplificata (S.r.l.s.)"
    ],
    "agevolazioni": [
      {
        "tipo": "finanziamento_agevolato",
        "importo_min": 5000,
        "importo_max": 25000,
        "percentuale": null,
        "tasso_interesse_percentuale": 0,
        "durata_mesi": 72,
        "preammortamento_mesi": 12,
        "abbuono_rate": 12,
        "percentuali_per_dimensione": {
          "micro": null,
          "piccola": null,
          "media": null,
          "default": null
        },
        "rimborso_richiesto": true,
        "tasso_descrizione": "Tasso zero",
        "descrizione": "Prestito a tasso zero erogato a valere sul NFF, con possibilità di abbuono delle ultime 12 rate per beneficiari in regola con i pagamenti",
        "condizioni": [
          "Assenza di garanzie richieste",
          "Rimborso a rata mensile costante posticipata",
          "Tasso di mora del 2% annuo in caso di ritardato pagamento",
          "Nessun altro costo aggiuntivo (spese di istruttoria, commissioni, penali)"
        ],
        "fonti": [
          {
            "campo": "agevolazioni[0].tasso_interesse_percentuale",
            "pagina": 6,
            "testo": "tasso di interesse: zero",
            "certezza": "alta"
          },
          {
            "campo": "agevolazioni[0].importo_max",
            "pagina": 6,
            "testo": "importo massimo: 25.000,00 euro",
            "certezza": "alta"
          },
          {
            "campo": "agevolazioni[0].durata_mesi",
            "pagina": 6,
            "testo": "periodo di rimborso del prestito: 72 mesi, incluso preammortamento",
            "certezza": "alta"
          },
          {
            "campo": "agevolazioni[0].preammortamento_mesi",
            "pagina": 6,
            "testo": "preammortamento: 12 (sempre previsto)",
            "certezza": "alta"
          }
        ]
      }
    ],
    "fonti": [
      {
        "campo": "titolo",
        "pagina": 1,
        "testo": "AVVISO A VALERE SUL NUOVO FONDO FUTURO (PROGRAMMA REGIONALE FESR LAZIO 2021-2027) - APERTURA DEI TERMINI PER LA PRESENTAZIONE DELLE DOMANDE DI AGEVOLAZIONE",
        "certezza": "alta"
      },
      {
        "campo": "ente",
        "pagina": 1,
        "testo": "Banca Nazionale del Lavoro SpA",
        "certezza": "alta"
      },
      {
        "campo": "data_pubblicazione",
        "pagina": 1,
        "testo": "16/04/2026 - BOLLETTINO UFFICIALE DELLA REGIONE LAZIO - N. 31",
        "certezza": "alta"
      },
      {
        "campo": "regioni_ammesse",
        "pagina": 5,
        "testo": "devono avere una Sede Operativa nel Lazio",
        "certezza": "alta"
      },
      {
        "campo": "dimensione_impresa",
        "pagina": 4,
        "testo": "ha l'obiettivo di sostenere le Microimprese in fase di avviamento",
        "certezza": "alta"
      },
      {
        "campo": "anzianita_impresa",
        "pagina": 5,
        "testo": "devono essere costituende o costituite da non più di 36 mesi",
        "certezza": "alta"
      },
      {
        "campo": "spesa_minima_ammissibile",
        "pagina": 4,
        "testo": "Il valore del Progetto presentato a valere sul presente Avviso deve essere almeno pari a euro 5.000,00",
        "certezza": "alta"
      },
      {
        "campo": "modalita_presentazione",
        "pagina": 8,
        "testo": "Lo sportello è accessibile per la compilazione e la firma delle Domande a partire dalle ore 10 del 7 maggio 2026. La protocollazione delle Domande, che definisce l'ordine cronologico delle richieste, è consentita a partire dalle ore 10 dell'11 maggio 2026. Lo sportello resta aperto fino al raggiungimento di un volume di richieste pari alla dotazione dell'Avviso",
        "certezza": "alta"
      }
    ],
    "copertura_estrazione": {
      "caratteri_totali": 206141,
      "caratteri_analizzati": 206141,
      "numero_blocchi": 1,
      "completa": true
    },
    "urgenza": null
  }
}
```

## esclusioni.pdf

- Caratteri estratti e analizzati integralmente: 123600
- Soglia per singola chiamata: 250000

```json
{
  "bando": {
    "titolo": "Donne e Impresa 2026",
    "ente": "Regione Lazio",
    "data_pubblicazione": "2026-04-07",
    "data_scadenza": "2026-06-10",
    "codici_ateco_ammessi": [],
    "attivita_ammesse": [
      "Acquisto beni strumentali",
      "Adozione di nuovi applicativi software, infrastrutture o piattaforme informatiche",
      "Adozione di nuovi sistemi di Digital Commerce & Engagement"
    ],
    "ateco_aperto_a_tutti": false,
    "regioni_ammesse": [
      "Lazio"
    ],
    "dimensione_impresa": {
      "micro": true,
      "piccola": true,
      "media": true,
      "grande": false
    },
    "fatturato_max": 50000000,
    "numero_dipendenti_min": null,
    "numero_dipendenti_max": null,
    "contributo_max": 100000,
    "percentuale_fondo_perduto": {
      "micro": null,
      "piccola": null,
      "media": null,
      "default": null
    },
    "modalita_presentazione": "graduatoria",
    "tipo_agevolazione": [
      "fondo_perduto"
    ],
    "cumulabilita": "Il contributo riconosciuto per l’adozione di nuovi sistemi di Digital Commerce & Engagement non è compatibile con nessun altro Aiuto o sostegno pubblico, compresi quelli previsti dagli avvisi Voucher Digitalizzazione, concesso per la realizzazione del medesimo intervento o avente ad oggetto i costi indicati nell’appendice 4 rientranti nella definizione della somma forfettaria riconosciuta ai sensi degli artt. 53 (1) (c) e 94 del RDC.",
    "spese_ammissibili": [
      "Beni strumentali",
      "Software e piattaforme informatiche"
    ],
    "link_fonte_ufficiale": "https://www.lazioinnova.it",
    "note_esclusioni": {
      "lista_testuale": "Sono escluse le attività economiche dei settori finanziario e assicurativo (Sez. K) e delle attività immobiliari (Sez. L), nonché attività connesse a tabacco, gioco d'azzardo, commercio sessuale, attività nucleari, e altre attività vietate elencate nell'Appendice 1. Inoltre, non sono ammissibili le PMI Femminili che hanno già ricevuto contributo dal precedente Avviso 'Donne e Impresa' 2025, salvo esito non noto. Riserva di 300.000 euro per l'Area Alessandrino-Quarticciolo (Municipio V di Roma).",
      "sezioni_ateco_escluse": [
        "Sez. K",
        "Sez. L"
      ],
      "attivita_vietate": [
        "tabacco",
        "gioco d'azzardo",
        "commercio sessuale",
        "attività nucleari"
      ]
    },
    "spesa_minima_ammissibile": 25000,
    "spesa_massima_ammissibile": null,
    "anzianita_impresa": {
      "mesi_minimi_dalla_costituzione": null,
      "mesi_massimi_dalla_costituzione": null
    },
    "forme_giuridiche_ammesse": [
      "lavoratrice autonoma",
      "impresa individuale",
      "società cooperativa",
      "società di persone",
      "studio associato",
      "società di capitali"
    ],
    "agevolazioni": [
      {
        "tipo": "fondo_perduto",
        "importo_min": null,
        "importo_max": 100000,
        "percentuale": null,
        "tasso_interesse_percentuale": null,
        "durata_mesi": null,
        "preammortamento_mesi": null,
        "abbuono_rate": null,
        "percentuali_per_dimensione": {
          "micro": null,
          "piccola": null,
          "media": null,
          "default": null
        },
        "rimborso_richiesto": false,
        "tasso_descrizione": null,
        "descrizione": "Contributo a fondo perduto per progetti di sviluppo, ampliamento, ristrutturazione o ammodernamento di PMI femminili, con percentuale scelta tra 50% e 70% delle spese ammissibili.",
        "condizioni": [],
        "fonti": [
          {
            "campo": "agevolazioni[0].importo_max",
            "pagina": 6,
            "testo": "Il contributo concedibile a un singolo Progetto e a una singola PMI Femminile non può superare 100.000,00 euro",
            "certezza": "alta"
          },
          {
            "campo": "agevolazioni[0].percentuale",
            "pagina": 6,
            "testo": "nella percentuale indicata dall’Impresa Proponente ... che deve essere compresa fra il 50% e il 70%",
            "certezza": "alta"
          }
        ]
      },
      {
        "tipo": "fondo_perduto",
        "importo_min": null,
        "importo_max": 4954.8,
        "percentuale": null,
        "tasso_interesse_percentuale": null,
        "durata_mesi": null,
        "preammortamento_mesi": null,
        "abbuono_rate": null,
        "percentuali_per_dimensione": {
          "micro": null,
          "piccola": null,
          "media": null,
          "default": null
        },
        "rimborso_richiesto": false,
        "tasso_descrizione": null,
        "descrizione": "Contributo forfettario per l'adozione di nuovi sistemi di Digital Commerce & Engagement.",
        "condizioni": [],
        "fonti": [
          {
            "campo": "agevolazioni[1].importo_max",
            "pagina": 6,
            "testo": "un importo facoltativo pari a 4.954,80 euro per l’adozione di nuovi sistemi di Digital Commerce & Engagement",
            "certezza": "alta"
          }
        ]
      }
    ],
    "fonti": [
      {
        "campo": "data_pubblicazione",
        "pagina": 1,
        "testo": "07/04/2026 - BOLLETTINO UFFICIALE DELLA REGIONE LAZIO - N. 28",
        "certezza": "alta"
      },
      {
        "campo": "data_scadenza",
        "pagina": 13,
        "testo": "entro le ore 17:00 del 10 giugno 2026",
        "certezza": "alta"
      },
      {
        "campo": "ateco_aperto_a_tutti",
        "pagina": 25,
        "testo": "Non sono ammissibili alle agevolazioni di cui al presente Avviso le attività economiche del settore finanziario e assicurativo (Sez. K ATECO), delle attività immobiliari (Sez. L ATECO)",
        "certezza": "alta"
      },
      {
        "campo": "dimensione_impresa",
        "pagina": 4,
        "testo": "I Beneficiari ... sono le Imprese Femminili, in forma singola, che ... sono PMI",
        "certezza": "alta"
      },
      {
        "campo": "contributo_max",
        "pagina": 6,
        "testo": "Il contributo concedibile a un singolo Progetto e a una singola PMI Femminile non può superare 100.000,00 euro",
        "certezza": "alta"
      },
      {
        "campo": "spesa_minima_ammissibile",
        "pagina": 3,
        "testo": "Spese Ammissibili da Rendicontare ... non inferiori a 25.000,00 euro",
        "certezza": "alta"
      }
    ],
    "copertura_estrazione": {
      "caratteri_totali": 123600,
      "caratteri_analizzati": 123600,
      "numero_blocchi": 1,
      "completa": true
    },
    "urgenza": "scaduto"
  }
}
```
