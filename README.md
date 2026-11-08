# Epson print and scan API

A container that exposes printing and scanning over HTTP for Epson printers on the network. It runs CUPS with the Epson ESC/P-R driver, SANE's `scanimage`, and a FastAPI service. The printer's IP address is passed on each request. The host must be x86_64 Linux.

Scanning and printing were tested with an Epson L3250 from Docker Desktop on Windows, using driver 1.8.8. Driver 1.8.10, included here, has been tested against a simulated printer only. Other Epson models are untested.

This project is not affiliated with or endorsed by Seiko Epson Corporation.

## Layout

| Path | Contents |
|---|---|
| `driver/` | Epson's ESC/P-R printer driver: the `.deb` used by the build and its matching source package |
| `source/epson_api/domain/` | Business rules and data, with no framework or system dependencies |
| `source/epson_api/application/` | Scan, print and status services, and the interfaces they rely on |
| `source/epson_api/infrastructure/` | Adapters for SANE, CUPS, IPP and the Epson driver files |
| `source/epson_api/api/` | FastAPI routes, request schemas and error mapping |
| `source/tests/` | Automated tests, which use fakes and need no printer |
| `samples/` | Example HTTP requests for the VS Code REST Client extension |
| `entrypoint.sh` | Starts CUPS and the API |

## Run

```sh
echo "API_KEY=$(openssl rand -hex 32)" > .env
docker build -t epson-api .
docker network create printing
docker run -d --name epson-api --restart unless-stopped \
  --env-file .env --network printing -p 127.0.0.1:8000:8000 epson-api
```

Other containers on the `printing` network reach it at `http://epson-api:8000`. The `-p` option publishes it to the host only. Remove it if only containers need access.

| Setting in `.env` | Default | Purpose |
|---|---|---|
| `API_KEY` | required | Value callers send in the `X-API-Key` header |
| `ALLOWED_IPS` | `*` (all clients) | Client addresses allowed to call the API, as comma-separated IPs or CIDR ranges, for example `192.168.0.10,172.18.0.0/16`. Other clients get `403` |
| `SCAN_TIMEOUT` | `600` | Seconds before a scan is abandoned |
| `MAX_UPLOAD_MB` | `50` | Largest file accepted for printing |

After editing `.env`, remove the container and run it again.

`ALLOWED_IPS` checks the address the container sees and applies to every endpoint, including `/openapi.json`. Other containers appear with their Docker network address. Requests through a published port may appear with the Docker gateway address, as they do on Docker Desktop, so check `docker logs epson-api` to see which address to allow. Forwarded-address headers are ignored. An invalid entry stops the container at startup.

## API

Every request needs the `X-API-Key` header. `printer_ip` must be a private LAN IPv4 address. Interactive documentation is at `/docs`.

### Scan

```sh
curl -H "X-API-Key: $API_KEY" -H "Content-Type: application/json" \
  -d '{"printer_ip":"192.168.0.64","resolution":300,"format":"pdf","paper_size":"A4"}' \
  -o scan.pdf --max-time 600 http://localhost:8000/scan
```

| Field | Values | Default |
|---|---|---|
| `printer_ip` | IPv4 address | required |
| `resolution` | `75`, `150`, `300`, `600`, `1200` | `300` |
| `mode` | `Color`, `Gray`, `Lineart` | `Color` |
| `format` | `png`, `jpeg`, `tiff`, `pdf` | `png` |
| `paper_size` | `full`, `A4`, `A5`, `B5`, `Letter`, `custom` | `full` |
| `width_mm`, `height_mm` | Numbers, required with `custom` and rejected otherwise | none |

Paper sizes in millimetres:

| `paper_size` | Width × height |
|---|---|
| `full` | The whole flatbed, 215.9 × 297.18 on the L3250 |
| `A4` | 210 × 297 |
| `A5` | 148 × 210 |
| `B5` (ISO) | 176 × 250 |
| `Letter` | 215.9 × 279.4 |
| `custom` | `width_mm` × `height_mm`, up to the flatbed size |

The scan area starts at the scanner's top-left corner, so place the original against that corner or it will be cropped. Larger sizes such as Legal and A3 don't fit the flatbed and aren't available.

Custom size example:

```json
{"printer_ip": "192.168.0.64", "paper_size": "custom", "width_mm": 100, "height_mm": 150}
```

The response is the scanned file. A 600 dpi full-flatbed colour PNG takes about 3 minutes and is around 50 MB, so set a long client timeout.

| Status | Meaning |
|---|---|
| `409` | A scan is already running on that IP |
| `422` | Invalid field, or a size that doesn't fit the flatbed |
| `502` | The scanner reported an error |
| `504` | The scan passed `SCAN_TIMEOUT` |

### Print

```sh
curl -H "X-API-Key: $API_KEY" -F file=@document.pdf -F printer_ip=192.168.0.64 \
  -F paper_type=PLAIN -F quality=HIGH -F ink=MONO -F page_ranges=1-3 http://localhost:8000/print
```

The first print to an IP creates its queue, using `socket://<ip>:9100`. A successful response means CUPS accepted the job, not that the page has printed.

| Field | Values | Default |
|---|---|---|
| `file` | See supported files below | required |
| `printer_ip` | IPv4 address | required |
| `model` | Epson model name from an installed driver file, as in `Epson-<model>-*.ppd.gz` | `L3250_Series` |
| `copies` | `1` to `99` | `1` |
| `paper_type` | See paper and quality below | `PLAIN` |
| `quality` | `HIGH`, `NORMAL`, `DRAFT` | `NORMAL` |
| `ink` | `COLOR`, `MONO` | `COLOR` |
| `page_size` | See page sizes below | `A4` |
| `brightness` | `-25` to `25` | `0` |
| `contrast` | `-25` to `25` | `0` |
| `saturation` | `-25` to `25` | `0` |
| `page_ranges` | `all`, or a list such as `1-3,5,8-` | `all` |
| `orientation` | `auto`, `portrait`, `landscape`, `reverse_landscape`, `reverse_portrait` | `auto` (the document's own) |
| `number_up` | Pages per sheet: `1`, `2`, `4`, `6`, `9`, `16` | `1` |
| `fit_to_page` | `true`, `false` | `false` |

Paper and quality for the L3250:

| `paper_type` | Paper | `quality` values |
|---|---|---|
| `PLAIN` | Plain paper | `HIGH`, `NORMAL` |
| `SFINE` | Epson Photo Quality Ink Jet | `HIGH`, `NORMAL` |
| `PMMATT` | Epson Matte | `HIGH`, `NORMAL` |
| `PLATINA` | Epson Ultra Glossy | `HIGH`, `NORMAL` |
| `PMPHOTO` | Epson Premium Glossy | `HIGH`, `NORMAL`, `DRAFT` |
| `PSGLOS` | Epson Premium Semigloss | `HIGH`, `NORMAL`, `DRAFT` |
| `LCPP` | Photo Paper Glossy | `HIGH`, `NORMAL`, `DRAFT` |
| `ENV` | Envelope | `HIGH`, `NORMAL` |

Quality names come from the driver. On papers with `DRAFT`, the driver labels `HIGH` as Photo RPM, `NORMAL` as High and `DRAFT` as Standard. On the other photo papers `HIGH` may be Photo RPM or High, depending on the paper.

Page sizes for the L3250: `A4`, `A5`, `A6`, `B5`, `B6`, `Letter`, `Legal`, `16K`, `8x10`, `L`, `2L`, `TL`, `INDEX5`, `4X6FULL`, `T4X6FULL`, `4X7`, `T4X7`, `Postcard`, `TPostcard`, `ENV10`, `EnvDL`, `ENVC6`.

`paper_type`, `quality`, `page_size` and the adjustments are checked against the selected model's driver. A combination it doesn't offer, such as `PLAIN` with `DRAFT`, returns `422`. The driver has no double-sided option.

Supported files, identified by their content: PDF, PostScript, plain text (including CSV), PNG, JPEG, TIFF, GIF, BMP, PNM and SVG. Anything else, including HTML, RTF and Office documents, returns `415`, so convert those to PDF first.

| Status | Meaning |
|---|---|
| `413` | File is larger than `MAX_UPLOAD_MB` |
| `415` | Unsupported or empty file |
| `422` | Invalid field, or an option the driver doesn't offer |
| `502` | CUPS refused the job |

### Status

```sh
curl -H "X-API-Key: $API_KEY" "http://localhost:8000/status?printer_ip=192.168.0.64"
```

Example response:

```json
{
  "printer": {
    "reachable": true,
    "printer-state": "idle",
    "printer-state-reasons": ["none"],
    "printer-is-accepting-jobs": true,
    "printer-make-and-model": "EPSON L3250 Series"
  },
  "queue": {
    "name": "epson-192-168-0-64",
    "printer-state": "idle",
    "printer-state-reasons": ["none"],
    "printer-is-accepting-jobs": true,
    "jobs": [
      {"job-id": 3, "job-name": "a.pdf", "job-state": "pending", "job-state-reasons": ["none"]}
    ]
  },
  "scanner": {"device": "epsonds:net:192.168.0.64", "busy": false, "reachable": true}
}
```

Field names and values follow the IPP standard (RFC 8011), so any printer that speaks IPP at `/ipp/print` reports the same way.

| Section | Source | Notes |
|---|---|---|
| `printer` | The printer itself, over IPP | `printer-state` is `idle`, `processing` or `stopped`. `printer-state-reasons` lists problems such as `media-empty-error`, or `none` |
| `queue` | CUPS, over IPP | `name` and the state fields are `null` until the first print to that IP creates the queue |
| `queue.jobs` | CUPS, over IPP | Unfinished jobs only. `job-state` is `pending`, `pending-held`, `processing` or `processing-stopped`. `job-id` is the final number in the `job_id` that `/print` returns |
| `scanner` | Port check and the scan lock | `reachable` is `null` while a scan is running |

If the printer can't be reached, `printer.reachable` is `false` and its state fields are `null`. During a scan, `printer.reachable` is `null` and the printer isn't queried. `printer-make-and-model`, `printer-alert-description` and the `marker-*` ink fields appear only when the printer reports them. The L3250 doesn't report ink levels.

## Other Epson drivers

The build installs every `.deb` in `driver/`, and the API finds model files at `/opt/<driver>/ppds/**/Epson-<model>-*.ppd.gz`. To use another Epson Linux driver, add its amd64 `.deb` to `driver/`, rebuild, and pass the model name in `model`. Keep only one version of each driver, and only `L3250_Series` on driver 1.8.8 has been tested on real hardware. A driver that needs extra system libraries must also have them added to the `Dockerfile`. If you publish a driver, follow its licence. Scanning doesn't use this folder.

## Docker Hub

Pushing a version tag such as `v1.0.0` runs the checks, then publishes the image as `<username>/epson-print-scan-api` with the tags `1.0.0` and `latest`. Set the repository secrets `DOCKERHUB_USERNAME` and `DOCKERHUB_TOKEN` first, using a Docker Hub access token.

## OpenAPI

The full specification is in [`openapi.json`](openapi.json), and a running server also provides it at `/openapi.json` without an API key, with interactive documentation at `/docs`. It describes every field, response and error, so AI agents and code generators can use it directly. After changing the API, regenerate the file with `uv run --directory source python -m epson_api.openapi_export`.

## Sample requests

`samples/requests.http` has ready-made requests for each endpoint. Set `@apiKey` and `@printerIp` at the top of the file, then send them with the [REST Client](https://marketplace.visualstudio.com/items?itemName=humao.rest-client) extension for VS Code. These requests use your real printer.

## Development

```sh
uv run --directory source ruff format
uv run --directory source ruff check
uv run --directory source mypy
uv run --directory source pytest
```

To run the format, lint and type checks before each commit, install the git hooks once with `uv run --directory source pre-commit install`. GitHub Actions runs all of these on every push to `main` and every pull request.

## Updating dependencies

```sh
uv lock --upgrade --directory source
```

## Troubleshooting

- If `/scan` returns `502` with "Error during device I/O" just after the printer is switched on, wait a minute and try again.
- API and startup log: `docker logs epson-api`
- CUPS log: `docker exec epson-api tail -n 50 /var/log/cups/error_log`
- Queues: `docker exec epson-api lpstat -t`
- Direct scan, bypassing the API: `docker exec epson-api scanimage -d "epsonds:net:192.168.0.64" --format png --mode=Color --resolution=600 > scan.png`

## Source code for the Docker image

The Docker image contains open-source software under its own licences, including GPL software. Licence notices are in `/usr/share/doc/<package>/copyright` inside the image, and the Epson driver's licence is `/opt/epson-inkjet-printer-escpr/doc/COPYING`.

| Component | Source |
|---|---|
| Epson ESC/P-R driver 1.8.10-1 | [`driver/epson-inkjet-printer-escpr-1.8.10-1.src.rpm`](driver/epson-inkjet-printer-escpr-1.8.10-1.src.rpm) in this repository |
| Debian packages | [sources.debian.org](https://sources.debian.org/), with exact past versions at [snapshot.debian.org](https://snapshot.debian.org/) |
| Python packages | [PyPI](https://pypi.org/), at the versions pinned in [`source/uv.lock`](source/uv.lock) |

To see the exact Debian package versions in an image, run `docker run --rm --entrypoint dpkg-query <image> -W`.

## License

The code in this repository is released under the [MIT License](LICENSE).

The files in `driver/` are not covered by the MIT License. They are the Epson Inkjet Printer Driver (ESC/P-R) for Linux, version 1.8.10-1, copyright Seiko Epson Corporation, licensed under the GNU General Public License version 2. The license text is the `COPYING` file inside each package, and the complete source is `driver/epson-inkjet-printer-escpr-1.8.10-1.src.rpm`. Newer versions are available from [Epson's Linux driver site](http://download.ebz.epson.net/dsc/search/01/search/?OSC=LX).

## Credits

Created by Nilay Joshi, built with [Claude Code](https://claude.com/claude-code) (Claude Opus 5.5) by Anthropic.
