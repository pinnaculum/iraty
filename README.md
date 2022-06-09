# iraty

*iraty* is a Python tool to publish web (HTML) documents
using an easy templating syntax. Documents are written in YAML and can make use
of *resolvers* (special functions called by the YAML engine).

The tool is designed for the dweb, and the HTML documents produced can
easily be puslished to IPFS.

# Install

You only need python3. Install from the latest released wheel using pip:

```sh
pip install --user -U "https://gitlab.com/cipres/iraty/-/releases/continuous-master/downloads/iraty-1.0.0-py3-none-any.whl"
```

Or clone [the git repo](https://gitlab.com/cipres/iraty) and install it with:

```sh
git clone "https://gitlab.com/cipres/iraty.git" && cd iraty
python setup.py build install
```

# Usage

Convert and print a document to stdout with:

```sh
iraty document.yaml
```

Convert and import a document to IPFS (the CID is printed on the console):

```sh
iraty --ipfs document.yaml

iraty --ipfs document.yaml|ipfs cat
```

If you want to use a specific IPFS node (default is *localhost*, port *5001*):

```sh
iraty --ipfs --ipfs-maddr '/dns/localhost/tcp/5051/http' document.yaml
```

*Remote pinning* is supported via the **--pin-remote** (or **-pr**) switch.
Specify the name of the remote pinning service registered on your go-ipfs node:

```sh
iraty --ipfs --pin-remote=pinata document.yaml
```

*iraty* can also process directories. YAML files (files with the *.yaml*
or *.yml* extension) will be converted. The output folder hierarchy will match the
input folder hierarchy. The output directory path, or the CID of the
root IPFS directory (if you use *--ipfs*) is printed to stdout:

```sh
iraty srcdir

iraty --ipfs srcdir

iraty --ipfs srcdir|ipfs ls
```

# Examples

A div with some markdown that includes an embedded IPFS file, with an image:

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

### include

*include* allows you to embed another (yaml) template in the DOM. The
specified path is relative to the root directory being processed, or relative
to the directory containing the processed file:

```yaml
head: ${include:.head.yml}
```

The structure of the *.head.yml* template will go inside the *head* DOM element.
However if you don't want to use a subtag, and just need the specified template
to be included *in situ*, just use the *.* operator:

```yaml
.: ${include:.head.yml}
```

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
