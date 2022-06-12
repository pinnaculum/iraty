# iraty

*iraty* is a Python tool to easily create and publish static websites
using a simple template syntax. Documents are written in YAML and can make use
of *resolvers* (special functions called by the
[YAML engine](https://github.com/omry/omegaconf)).

This tool is designed with the distributed web in mind (but you can run it in
a *standalone* mode), and the HTML documents produced can
easily be puslished to IPFS. Because YAML enforces indentation, the structure
of your documents is easy to read and this lets you concentrate on the content.
A collection of *classless* CSS themes is provided to make styling easy.

*If you think that using bits of YAML to create websites is insane and totally
stupid, you'll feel right at home here.*

# Install

You only need python3. Install from the latest released wheel using pip:

```sh
pip install --user -U "https://gitlab.com/cipres/iraty/-/releases/1.1.0/downloads/iraty-1.1.0-py3-none-any.whl"
```

Or clone [the git repo](https://gitlab.com/cipres/iraty) and install it with:

```sh
git clone "https://gitlab.com/cipres/iraty.git" && cd iraty
pip install -e .
```

There's also a docker image (see [how to run it with docker](#docker)):

```sh
sudo docker pull registry.gitlab.com/cipres/iraty:latest
```

# Usage

The following commands are supported:

* **run**: generate the website
* **ipfs-deploy**: same as **run**, but always imports to IPFS
* **node-config** (or **nc**): configure an IPFS node (the default node is *local*)
* **serve**: generate the website and serve it over HTTP
* **list-resolvers**: list all available resolvers and their documentation
* **list-themes**: list all available themes

The **run** command accepts a directory or single file. YAML files (files with
the *.yaml* or *.yml* extension) inside the source directory will be converted.
The output directory path by default is **public**
(use **-o** to set another output directory).
If you use **--ipfs** or **-i**, the website will be imported to IPFS and
the CID of the root IPFS directory is printed to stdout.
Use **--theme** or **-t** to change the theme (the default theme is
*mercury*, use **-t null** to use no theme).

```sh
iraty run site
iraty --theme=sakura-dark -o html run site

iraty --ipfs run site
iraty --ipfs run site|ipfs ls
```

Create a new config for an IPFS node with the **node-config** command
(this will open your *EDITOR*), and specify the node you want to use
with **--node**. The default IPFS node configuration is called *local*.
You will be asked if you want to register the remote pinning
services listed in the config.

```sh
iraty node-config ripfs1
iraty --node=ripfs1 ipfs-deploy site
```

If you want to serve the website over HTTP on your machine, use
**serve**, and set the HTTP port with **--port** (the default is TCP port: *8000*).

```sh
iraty --port 9000 serve site
```

If you want to force the use of a specific IPFS node (will soon be
deprecated by **--node** and **node-config**):

```sh
iraty --ipfs-maddr '/dns/localhost/tcp/5051/http' ipfs-deploy site
```

*Remote pinning* is supported via the **--pin-remote** (or **--pr**) switch.
Specify the name of the remote pinning service registered on your go-ipfs node
with **-rps** (otherwise it will use the *default RPS* specified in the node's
configuration):

```sh
iraty -i --pin-remote run site
iraty --pr --rps=pinata2 ipfs-deploy site
```

You can also publish your website to an IPNS key (if you use **--ipns-name**
it will lookup a key with that name and create it if necessary, if you use
**--ipns-id** you need to pass the *Id* of an existing key):

```sh
iraty --ipns-name=my-dwebsite ipfs-deploy site
iraty --ipns-id=k51qzi5uqu5dkdol6lzkg0q7jaiv2r252ir9t5z8xbheg6g4vzd6lk2ydibe5y ipfs-deploy site
```

*iraty* caches the configuration for your site in a file called **.iraty.yaml**.
To reuse the last saved configuration, use **-r** or **--restore** (all
other config arguments will be ignored):

```sh
iraty -r run site
iraty --restore serve site
```

You can also pass a file. Convert and print a document to stdout with:

```sh
iraty run document.yaml
iraty -t sakura-dark run document.yaml
```

Convert and import a document to IPFS (the CID is printed on the console):

```sh
iraty -i run document.yaml
iraty -i run document.yaml|ipfs cat
```

Layouts are supported, look at the *block* resolver's documentation below and
checkout [the layout example](https://gitlab.com/cipres/iraty/-/tree/master/examples/layout).

# Docker

The only difference with Docker is that you have to create a volume (here we
generate the site from *$HOME/site* to *$HOME/public*):

```sh
sudo docker run -v $HOME:/h -t registry.gitlab.com/cipres/iraty:latest -o /h/public run /h/site
```

# Examples

Take a look [at the examples](https://gitlab.com/cipres/iraty/-/tree/master/examples).

A div with some markdown that includes an embedded IPFS file, with an image:

```yaml
body:
  div:
  - p: |-
      # Hello

      File contents .. ${cat:QmeomffUNfmQy76CQGy9NdmqEnnHU9soCexBnGU3ezPHVH}

  - p: |-
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

Embedding a [jinja2 template](https://gitlab.com/cipres/iraty/-/tree/master/examples/jinja):

```yaml
body:
  # Jinja template from string (passing variables)
  - jinja:
      template: |-
        <div>

        {% for i in range(num) %}
          <p>Iteration: {{ i }}</p>
        {% endfor %}

        </div>
      with:
        num: 5
```

An image in base64 from an external IPFS file. HTML tag attributes must
start with *_*:

```yaml
img:
  _src: 'data:image/png;base64, ${cat64:QmUEd5oBhJJmb6WZWc7aHrPpcgF8ELEvcxHo6q4M8uWY5Q}'
```

# Resolvers

## block

Declares a block. This is used inside a layout file called **.layout.yaml**.
This allows you to define a general layout for your website and not
have to declare the document structure over and over again.

**.layout.yaml**:

```yaml
div: ${block:b1}
```

Your templates can then declare the block that will be replaced inside
the layout.

**section.yaml**:

```yaml
block_b1:
  p:
    The contents of block *b1*
```

*Note*: There is no safe-check on whether a block has already been defined or
not. Only the first matching block will be substituted.

## dtnow_iso

Returns the current date and time.

```yaml
p: Current date and time ${dtnow_iso:}
```


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
Several *classless* CSS stylesheets are included in the repository:

- [classlesscss](https://github.com/emareg/classlesscss)
- [sakura](https://github.com/oxalorg/sakura)
- [MercuryCSS](https://github.com/wmeredith/MercuryCSS)
- [water.css](https://github.com/kognise/water.css)
