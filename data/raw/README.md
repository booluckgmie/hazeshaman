# Drop your IPU/API CSVs here

Hourly readings, any number of files, columns matched case-insensitively.

**Long format**
`datetime` (or `date` + `hour`, or `date` + `time`), `state` (or `negeri`), `api` (or `ipu`/`value`)

**Wide format**
`datetime` (or `date`+`hour`) and one column per state (Johor, Kedah, ... "Penang", "N. Sembilan", "KL", "Putrajaya", "Labuan" are normalised).

Station-level rows for the same state/hour are averaged. Gaps up to 3 h are interpolated.
Hourly resolution is required: the model compares announcement hours.

Then run `python -m hazeshaman.build` (CSV files here are git-ignored; keep private data out of the repo).
