# INCIDENT LOG - MLPG Project
Registro degli errori tecnici e dei bug riscontrati durante lo sviluppo.

## [15 Maggio 2026] - Configurazione Ambiente
- **Stato:** Setup iniziale completato.
- **Note:** Pronto per la Fase 1 (Building).

## [15 Maggio 2026] - Errori riscontrati durante lo sviluppo
- **Errore:** Modello Gemini non supportato inizialmente usato `gemini-1.5-flash`.
  - **Soluzione:** Aggiornato a `models/gemini-2.5-flash` in `src/generator.py`.
- **Errore:** Risposte AI con testo extra o blocchi markdown impedivano il parsing JSON.
  - **Soluzione:** Aggiunta logica di pulizia JSON in `valuta_risposta()` e `genera_spiegazione_alternativa()`.
- **Errore:** Il tutor doveva fermarsi e spiegare meglio quando l'utente non capiva, ma non c'era una fine empatica.
  - **Soluzione:** Implementata funzione `genera_saluto_finale()` e aggiornato il flusso in `src/main.py`.
- **Errore:** La conclusione finale era poco chiara e non separava correttamente livello, punti di forza e note.
  - **Soluzione:** Ristrutturato il riepilogo in `src/main.py` con sezioni distinte.
- **Errore:** Bug di indentazione su `main.py` durante la gestione della conferma sulla comprensione.
  - **Soluzione:** Corretto il blocco `if continua ...` e rivisto il ciclo di comprensione.

## [19 Maggio 2026] - Miglioramento gestione confusione intermedio/avanzato
- **Errore:** La gestione della confusione non era sufficientemente mirata per utenti di livello intermedio o avanzato.
  - **Soluzione:** Estesa `genera_spiegazione_alternativa()` per utilizzare il livello utente e generare output strutturato con spiegazione semplificata, esempio pratico e passaggi consigliati.
- **Errore:** La domanda di chiarimento era troppo generica.
  - **Soluzione:** Aggiornato `main.py` per chiedere l’area precisa di confusione e passare questo dettaglio al prompt dell’AI.

## [19 Maggio 2026] - Estensione interfacce web
- **Errore:** L’applicazione era limitata al terminale e non offriva una UI grafica accessibile.
  - **Soluzione:** Creati `app.py` (Flask), `streamlit_app.py` (Streamlit) e l’interfaccia HTML in `templates/index.html`.
- **Errore:** La versione web non era supportata da `requirements.txt`.
  - **Soluzione:** Aggiornato `requirements.txt` con `flask` e `streamlit`.

---
*Esempio di inserimento futuro:*
- **Errore:** L'AI non rispetta il limite delle 150 parole.
- **Soluzione:** Modificato il System Prompt aggiungendo un vincolo più stringente.