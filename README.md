# Disagreement Without a Price: explorer

A [Vizro](https://github.com/mckinsey/vizro) dashboard over the data of the paper
[Disagreement Without a Price](https://ssrn.com/abstract=7016178): what different US fund houses
report for the same private company on the same date.

```bash
pip install -r requirements.txt
python app.py          # http://127.0.0.1:8050
python -m pytest -q    # checks the dashboard against the paper's numbers
```

The data are the paper's committed outputs, pinned in [`data/SOURCE.md`](data/SOURCE.md). Nothing is
re-estimated.
