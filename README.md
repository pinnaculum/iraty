# iraty

*iraty* is a Python tool to publish web (HTML) documents
using an easy templating syntax. Documents are written in YAML and can make use
of *resolvers* (special functions called by the
[YAML engine](https://github.com/omry/omegaconf)).

The tool is designed for the dweb, and the HTML documents produced can
easily be puslished to IPFS.

# Install

You only need python3. Install from the latest released wheel using pip:

```sh
pip install --user -U "https://gitlab.com/cipres/iraty/-/releases/1.0.0/downloads/iraty-1.0.0-py3-none-any.whl"
```

Or clone [the git repo](https://gitlab.com/cipres/iraty) and install it with:

```sh
git clone "https://gitlab.com/cipres/iraty.git" && cd iraty
pip install -e .
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
  - p:
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

Links (the *_* key sets the inner text of the DOM node):

```yaml
a:
  _href: "https://ipfs.io"
  _: "IPFS is the distributed web"
```

An image in base64 from an external IPFS file. HTML tag attributes must
start with *_*:

```yaml
img:
  _src: 'data:image/png;base64, ${cat64:QmUEd5oBhJJmb6WZWc7aHrPpcgF8ELEvcxHo6q4M8uWY5Q}'
```

# Resolvers

## cat

*cat* returns the contents (as a string) of an IPFS file or web resource.
The first and only argument is an IPFS path, an IPFS CID, or an HTTP/HTTPs URL.

```yaml
content: ${cat:QmeomffUNfmQy76CQGy9NdmqEnnHU9soCexBnGU3ezPHVH}

content: ${cat:https://gitlab.com/cipres/iraty/-/raw/master/README.md}
```

## cat64

*cat64* returns the contents in base64 of an IPFS file or web resource.
The first and only argument is an IPFS path, an IPFS CID, or an HTTP/HTTPs URL.

```yaml
content: ${cat64:QmeomffUNfmQy76CQGy9NdmqEnnHU9soCexBnGU3ezPHVH}
```

## csum_hex

*csum_hex* returns the checksum as an hexadecimal string for a given resource
and hashing algorithm.

The first argument is the algorithm, the second argument is the resource URL.
Use an algorithm from the following list:

```python
{'blake2s', 'sha3_224', 'sha512', 'blake2b', 'shake_256', 'sha256', 'sha1', 'sha3_256', 'md5', 'sha3_384', 'sha384', 'shake_128', 'sha3_512', 'sha224'}
```

Example:

```yaml
p: ${csum_hex:sha512,ipfs://bafkreihszin3nr7ja7ig3l7enb7fph6oo2zx4tutw5qfaiw2kltmzqtp2i}
```

## include

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



# Name origin

This tool is named after the succulent French (Basque) cheese called *Ossau-Iraty*.

# Donate

You can make a donation for this project
[here at Liberapay](https://liberapay.com/galacteek).

# Thanks

A big thanks to everyone involved with [OmegaConf](https://github.com/omry/omegaconf).
