# iraty

*iraty* is a Python tool to publish web (HTML) documents
using an easy syntax. Documents are written in YAML and can make use
of *resolvers* (special functions called by the YAML engine).

Any text in the document is assumed to be markdown. The tool is designed
for the dweb (the resulting HTML documents can easily be puslished to IPFS).

# Usage

You need python3. Clone this repo and install with:

```sh
python setup.py build install
```

Or install from wheel:

```sh
pip install https://gitlab.com/cipres/iraty/-/releases/continuous-master/downloads/iraty-1.0.0-py3-none-any.whl
```

Convert and print a document to stdout with:

```sh
iraty document.yaml
```

Convert and import a document to IPFS (the CID is printed on the console):

```sh
iraty --ipfs document.yaml

iraty --ipfs document.yaml|ipfs cat
```

# Examples

A div with some markdown that includes a remote IPFS file, with an image:

```yaml
body:
  div:
  - >
    # Hello

    File contents .. ${cat:QmeomffUNfmQy76CQGy9NdmqEnnHU9soCexBnGU3ezPHVH}

  - p:
    # h1

    Second paragraph

  - img:
      _src: 'https://example.com/someimage.png'
```

Tables:

```yaml
- table:
  - tr:
    - td: One
    - td: Two
  - tr:
    - td: Three
    - td: Four
```

An image in base64 from an external IPFS file. HTML tag attributes must
start with *_*:

```yaml
img:
  _src: 'data:image/png;base64, ${cat64:QmUEd5oBhJJmb6WZWc7aHrPpcgF8ELEvcxHo6q4M8uWY5Q}'
```

## resolvers

### ipfs_cat

*ipfs_cat* (or just *cat*) returns the contents (as string) of an IPFS file.
The first and only argument is an IPFS path or CID.

```yaml
content: ${cat:QmeomffUNfmQy76CQGy9NdmqEnnHU9soCexBnGU3ezPHVH}
```

### ipfs_cat64

*ipfs_cat64* (or just *cat64*) returns the contents in base64 of an IPFS file.
The first and only argument is an IPFS path or CID.

```yaml
content: ${cat64:QmeomffUNfmQy76CQGy9NdmqEnnHU9soCexBnGU3ezPHVH}
```

# Name origin

This tool is named after the succulent French (Basque) cheese called *Ossau-Iraty*.
