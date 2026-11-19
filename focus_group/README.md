# Expert evaluation (focus group)

| File | Content |
|---|---|
| `items.csv` | The 24 Likert statements (in Spanish, as presented to the experts), the criterion each one belongs to, and whether it is reverse-coded |
| `responses_anonymized.csv` | One row per expert (E1–E4): years of experience and the answer to each statement (1 = strongly disagree … 5 = strongly agree, as answered, not reversed) |
| `compute_stats.py` | Recomputes Table "Descriptive statistics of the expert evaluation" of the paper → `summary.csv` |

```bash
python compute_stats.py
```

The questionnaire received five submissions; one was a test submission (non-informative answers
in every free-text field) and is not included. Names, e-mails, timestamps, free-text profiles and
the answers to the open questions were removed to protect the participants' identity. All four
experts gave informed consent to participate and to the anonymous use of their responses.
