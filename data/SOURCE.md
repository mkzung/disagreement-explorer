# Where these files come from

Copied unchanged from [mkzung/unicorn-valuation-disagreement](https://github.com/mkzung/unicorn-valuation-disagreement)
at commit `1ae7a595701baad04a0d17f522e6402153e21c77` (7 Oct 2026), directory `data/`.

| File | Built there by | SHA-256 |
| --- | --- | --- |
| `population_cells.csv` | `src/population.py` | `742fe431e36c75ed44e071c9e013ee8566c806c4143e4bfa1115537366bdf8f1` |
| `company_classification.csv` | `src/company_class.py` | `0483e7104c37107fe49c2683a203cbfb51453e5b30553f30c0a930d7d071b6a1` |
| `ipo_validation.csv` | hand-collected, scored by `src/validation.py` | `4f64c6a1c6dda8c07f62ec1b095964f6ea351897a245455765cc1e1c35bca37a` |

`tests/test_app.py` checks each hash, so a changed copy fails the suite. To refresh, copy the
files from a newer commit, then update this table and the hashes in the test together.
