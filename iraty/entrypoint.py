import sys
import os
import io
import argparse
import tempfile
import markdown
import traceback
import shutil
from pathlib import Path

from domonic.dom import document
from domonic.html import html
from domonic.html import render
from omegaconf import OmegaConf

try:
    from html5print import HTMLBeautifier
except ImportError:
    have_beautifier = False
else:
    have_beautifier = True

import ipfshttpclient
from ipfshttpclient import client

from . import resolvers


def assert_v(version: str, minimum: str = '0.4.23',
             maximum: str = '0.15.0') -> None:
    # Don't really care which version you use
    pass


client.assert_version = assert_v


def convert(node, dom, parent=None):
    pn = parent if parent is not None else dom

    if isinstance(node, dict):
        for elem, n in node.items():
            if elem.startswith('_'):
                # Attribute
                pn.setAttribute(elem.replace('_', ''), n)
            else:
                tag = document.createElement(elem)

                if isinstance(n, str) and 0:
                    htmlized = markdown.markdown(n)
                    tag.innerText(htmlized)

                pn.appendChild(tag)

                convert(node[elem], dom, parent=tag)
    elif isinstance(node, list):
        for n in node:
            tag = document.createElement('span')
            pn.appendChild(tag)
            convert(n, dom, parent=tag)
    elif isinstance(node, str):
        tag = document.createElement('span')
        htmlized = markdown.markdown(node)
        tag.innerText(htmlized)
        pn.appendChild(tag)


class Iraty:
    def __init__(self, ipfs_client, args):
        self.iclient = ipfs_client
        self.args = args

    def ipfs_add(self, src):
        try:
            ret = self.iclient.add(src, cid_version=1,
                                   recursive=True)
            if isinstance(ret, list):
                entry = ret[-1]
            else:
                entry = ret

            return entry['Hash']
        except Exception as err:
            print(f'IPFS Error: {err}', file=sys.stderr)

    def output_dom(self, dom, dest: Path = None, fd=None):
        if dest:
            output = open(str(dest), 'wb')
        else:
            output = fd if fd else io.BytesIO()
        try:
            if have_beautifier:
                out = HTMLBeautifier.beautify(render(dom),
                                              int(self.args.htmlindent))
                if output is sys.stdout:
                    output.write(out)
                else:
                    output.write(out.encode())
            else:
                if output is sys.stdout:
                    output.write(f'{dom}')
                else:
                    output.write(f'{dom}'.encode())

            if output is not sys.stdout:
                output.seek(0, 0)
        except Exception:
            traceback.print_exc()
        else:
            return output

    def process_file(self, path: Path, output=False):
        dom = html()
        try:
            with open(str(path), 'rt') as fd:
                foc = OmegaConf.load(fd)

                convert(
                    OmegaConf.to_container(foc, resolve=True),
                    dom
                )
        except Exception:
            traceback.print_exc()
            return None

        if output:
            if self.args.ipfsout:
                out = self.output_dom(dom)
                cid = self.ipfs_add(out)
                if cid:
                    print(cid, file=sys.stdout)
            else:
                self.output_dom(dom, fd=sys.stdout)

        return dom

    def process_directory(self, path: Path):
        outd = tempfile.mkdtemp()
        try:
            for root, dirs, files in os.walk(str(path)):
                rr = root.replace(str(path), '').lstrip(os.sep)

                for file in files:
                    fp = Path(root).joinpath(file)
                    ddest = Path(outd).joinpath(rr)
                    ddest.mkdir(parents=True, exist_ok=True)

                    if fp.name.endswith('.yaml'):
                        dest = ddest.joinpath(file.replace('.yaml', '.html'))
                        dom = self.process_file(fp)

                        if dom:
                            self.output_dom(dom, dest=dest)
                    else:
                        # Copy other files
                        shutil.copy(fp, str(ddest))
        except Exception:
            traceback.print_exc()
        else:
            if self.args.ipfsout:
                cid = self.ipfs_add(outd)

                if cid:
                    print(cid, file=sys.stdout)
            else:
                print(outd, file=sys.stdout)


def iraty(args):
    if len(args.input) != 1:
        print('Invalid input arguments', file=sys.stderr)
        sys.exit(1)

    filein = args.input[0]

    try:
        iclient = ipfshttpclient.connect(args.ipfsmaddr)
    except Exception as err:
        # Should be fatal ?
        print(f'IPFS connection Error: {err}', file=sys.stderr)
    else:
        # Set global client
        resolvers.ipfs_client = iclient

    ira = Iraty(iclient, args)
    path = Path(filein)

    if not path.exists():
        print(f'{path} does not exist', file=sys.stderr)
        sys.exit(1)

    if path.is_file():
        ira.process_file(path, output=True)
    elif path.is_dir():
        ira.process_directory(path)


def run():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--ipfs-maddr',
        dest='ipfsmaddr',
        default='/dns/localhost/tcp/5001/http',
        help='IPFS daemon multiaddr')
    parser.add_argument(
        '--html-indent',
        dest='htmlindent',
        default=4,
        help='HTML indentation space count')
    parser.add_argument(
        '--ipfs',
        dest='ipfsout',
        action='store_true',
        default=False,
        help='Store HTML output to IPFS')

    parser.add_argument(nargs=1, dest='input')

    return iraty(parser.parse_args())
