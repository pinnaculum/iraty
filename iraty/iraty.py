import sys
import os
import os.path
import io
import inspect
import re
import traceback
import shutil
import functools
import http.server
import socketserver
import pkg_resources
import subprocess
from pathlib import Path
from typing import Union, IO
from urllib.parse import urlparse

from domonic.dom import document
from domonic.html import *  # noqa
from omegaconf import OmegaConf
from omegaconf import DictConfig
from omegaconf.basecontainer import BaseContainer
from jinja2 import Environment, FileSystemLoader, select_autoescape

import markdown
from markdown.extensions.toc import TocExtension

from .config import node_get_config
from .config import node_configure
from .config import node_configure_default

from .omega import shove

try:
    from html5print import HTMLBeautifier
except ImportError:
    have_beautifier = False
else:
    have_beautifier = True


import ipfshttpclient
from ipfshttpclient import client
from ipfshttpclient.exceptions import ErrorResponse

from . import resolvers
from . import appdirs
from . import i18n


def is_str(obj):
    return isinstance(obj, str)


def is_intfloat(obj):
    return isinstance(obj, int) or isinstance(obj, float)


def assert_v(version: str, minimum: str = '0.4.23',
             maximum: str = '0.15.0') -> None:
    # Ignore go-ipfs version number (we only use a small subset of the API)
    pass


client.assert_version = assert_v
md = markdown.Markdown(extensions=[TocExtension(permalink=True)])


def relative(path: Path, dirp: Path):
    return os.path.relpath(str(path), start=str(dirp))


def http_serve(directory: Path, port=8000):
    """
    Serve via HTTP the specified directory on the given TCP port
    """

    Handler = functools.partial(
        http.server.SimpleHTTPRequestHandler,
        directory=str(directory)
    )

    with socketserver.TCPServer(("", port), Handler) as httpd:
        print(f'Serving via HTTP at: http://localhost:{port}', file=sys.stdout)

        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            httpd.shutdown()
            httpd.server_close()
        except OSError as err:
            print(str(err), file=sys.stderr)


def handle_textnode(dom, pn, text: str, lang=None):
    def toke(tokens):
        # Recursively process tokens from the markdown toc extension
        for token in tokens:
            dom._toc.links.append({
                'tag': f'h{token["level"]}',
                'name': token['name'],
                'link': f'#{token["id"]}'
            })

            if len(token['children']) > 0:
                toke(token['children'])

    if pn.tagName in ['p', 'span']:
        html = md.convert(text)

        # Process toc tokens
        toke(md.toc_tokens)

        pn.innerText(html)
    else:
        pn.innerText(text)


jenv = Environment(autoescape=select_autoescape())

assets_root = Path(pkg_resources.resource_filename(
    'iraty.assets',
    ''
))


def section_id(content: str):
    san = ''.join(re.split('[^a-zA-Z0-9\\s]*', content.lower()))
    san = re.sub('\\s+', '-', san)
    return san, f'#{san}'


def convert_post(dom, parentNode, node, tagn, content):
    if tagn in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6'] and isinstance(content, str):
        name, link = section_id(content)

        # Add permalink
        node.appendChild(a('¶', _href=link))

        dom._toc.links.append({
            'tag': tagn,
            'name': content,
            'link': link
        })


def create_element(pn, tag, content, lang=None):
    parent = pn

    if tag in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6'] and is_str(content):
        # Create section
        name, link = section_id(content)
        sec = section(_id=name)
        pn.appendChild(sec)
        parent = sec

    elem = document.createElement(tag)
    parent.appendChild(elem)
    return elem


dots = ['.' * x for x in range(1, 4)]


def convert(ira, node, dom, destdir: Path, parent=None, lang=None):
    pn = parent if parent is not None else dom
    rel_destdir = relative(destdir, ira.outdirp)

    if isinstance(node, dict):
        for tagn, value in node.items():
            if len(tagn) > 1 and tagn.startswith('_') and \
                    (is_str(value) or is_intfloat(value)):
                # Attribute
                attr = re.sub('_', '', tagn, count=1)
                aattrs = ['href_auto', 'src_auto']

                if attr in aattrs:
                    url = urlparse(value)

                    if not url.scheme:
                        comps = rel_destdir.split('/')

                        hrefl = relative(value, comps[0] if comps else '')
                        pn.setAttribute(attr.replace('_auto', ''), hrefl)
                    else:
                        pn.setAttribute(attr, value)
                else:
                    pn.setAttribute(attr, value)
            elif tagn in dots or pn.tagName in dots:
                # in situ
                convert(ira, value, dom, destdir, parent=pn)
                continue
            elif tagn == '_' and is_str(value):
                # Tag text contents
                handle_textnode(dom, pn, value, lang=lang)
            elif tagn == 'jinja':
                args = {}

                if is_str(value):
                    tmpl = jenv.from_string(value)
                elif isinstance(value, dict):
                    args = value.get('with', {})
                    tpath = value.get('from')
                    template = value.get('template')

                    if is_str(tpath):
                        tmpl = jenv.get_template(tpath)
                    elif is_str(template):
                        tmpl = jenv.from_string(template)

                if tmpl:
                    args.update({'langs': ira.site_langs})
                    pn.appendChild(
                        document.createTextNode(tmpl.render(**args))
                    )
            else:
                elem = create_element(pn, tagn, value, lang=lang)

                convert(ira, node[tagn], dom, destdir, parent=elem, lang=lang)

                convert_post(dom, pn, elem, tagn, value)
    elif isinstance(node, list):
        [convert(ira, subn, dom, destdir, parent=pn, lang=lang) for subn in node]
    elif isinstance(node, str):
        handle_textnode(dom, pn, node, lang=lang)


class IratySiteConfig:
    """
    Holds the configuration for an iraty website
    """

    def __init__(self, cfg_path, args):
        self.path = cfg_path
        self.args = args
        self._oc = {}

    @property
    def c(self):
        return self._oc

    def exists(self):
        return self.path.is_file()

    def init(self):
        if self.exists() and self.args.restore_config:
            try:
                with open(self.path, 'rt') as fd:
                    self._oc = OmegaConf.load(fd)

                # Basic check
                for attr in ['icf_version', 'theme',
                             'output_path', 'ipfs_output',
                             'ipfs_maddr', 'ipfs_rps_name',
                             'http_serve_port']:
                    if attr not in self.c:
                        raise ValueError(f'Attribute {attr} missing from '
                                         f'config file {self.path}')
            except Exception:
                self._oc = self.from_args()
                self.sync()
        else:
            # Not restoring config, use from command-line args
            self._oc = self.from_args()
            self.sync()

    def from_args(self):
        return OmegaConf.create({
            'icf_version': 1,
            'theme': self.args.theme,
            'output_path': self.args.outdir,
            'ipfs_output': self.args.ipfsout,
            'ipfs_maddr': self.args.ipfsmaddr,
            'ipfs_rps_name': self.args.rps_name,
            'http_serve_port': self.args.httpport,
            'language_default': self.args.lang_default_iso639
        })

    def sync(self):
        with open(self.path, 'wt') as fd:
            OmegaConf.save(self.c, fd)


def dom_find(dom, tag: str):
    found = []
    for node in dom.iter():
        if node.name == tag:
            found.append(node)
    return found


class TOC:
    def __init__(self):
        self.links = []


class Iraty:
    def __init__(self,
                 command,
                 input_path,
                 ipfs_client,
                 ipfs_node_cfg,
                 args):
        self.command = command
        self.iclient = ipfs_client
        self.ipfs_node_cfg = ipfs_node_cfg
        self.args = args
        self.input_path = input_path

        if self.input_path.is_dir():
            cfgpath = self.input_path.joinpath('.iraty.yaml')
        else:
            cfgpath = Path(os.getcwd()).joinpath('.iraty.yaml')

        self.sitecfg = IratySiteConfig(cfgpath, self.args)
        self.sitecfg.init()

        self.outdirp = Path(self.sitecfg.c.output_path)
        self.lang_default = i18n.lang_get(self.sitecfg.c.language_default)
        self.site_langs = []

    def start(self):
        if os.getenv('HOME') == str(self.outdirp):
            raise Exception('Not using HOME as output, dude')

        self.outdirp.mkdir(parents=True, exist_ok=True)

        if self.sitecfg.exists() and self.args.purge:
            for root, dirs, files in os.walk(self.outdirp):
                for file in files:
                    # Only purge html/css files
                    if file.endswith('.html') or file.endswith('.css'):
                        os.unlink(os.path.join(root, file))

        for iso639 in self.args.langs.split(','):
            lang = i18n.lang_get(iso639)

            if lang and lang not in self.site_langs:
                self.site_langs.append(lang)

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

    def ipfs_pinremote(self, service, cid):
        try:
            resp = self.iclient.pinremote.add(service, cid)
            assert resp['Status'] == 'pinned'
        except ErrorResponse as err:
            print(f'Pin to remote error: {err}', file=sys.stderr)
            return False
        except Exception as err:
            print(f'Unknown Error: {err}', file=sys.stderr)
            return False
        else:
            return True

    def output_dom(self, dom, dest: Path = None, fd=None):
        tocdefs = dom_find(dom, 'toc')

        for tocn in tocdefs:
            depth = int(tocn.depth)

            if depth in range(1, 7):
                atags = [f'h{d}' for d in range(1, depth + 1)]
            elif depth == 0:
                atags = [f'h{d}' for d in range(1, 7)]

            title = h3(tocn.title)
            top = div(title)

            ulel = ul()
            top.appendChild(ulel)

            for tocl in dom._toc.links:
                if tocl['tag'] not in atags:
                    continue

                link = a(tocl['name'], _href=tocl['link'])
                e = li(link)

                # TODO: use levels and not tags, this is boring
                if tocl['tag'] == 'h1':
                    e.setAttribute(
                        'style', 'text-indent: -15px; list-style: none;')
                elif tocl['tag'] in ['h2', 'h3', 'h4', 'h5', 'h6']:
                    level = int(tocl['tag'].replace('h', ''))
                    margin = level * 10

                    e.setAttribute(
                        'style',
                        f'margin-left: {margin}px; list-style: position;')

                ulel.appendChild(e)

            tocn.parentNode.replaceChild(top, tocn)

        if dest:
            output = open(str(dest), 'wb')
        else:
            output = fd if fd else io.BytesIO()
        try:
            if have_beautifier and 0:
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

    def process_file(self,
                     source: Union[Path, IO, DictConfig],
                     destdir_root: Path = None,
                     i18n_out=True,
                     basename=None,
                     output=False):
        lang = None
        dom = html()
        dom._toc = TOC()

        try:
            theme_name = os.path.basename(self.sitecfg.c.theme)
            themedp = Path(pkg_resources.resource_filename(
                'iraty.themes',
                self.sitecfg.c.theme
            ))

            destdir = destdir_root

            if destdir:
                destdir.mkdir(parents=True, exist_ok=True)

            if isinstance(source, Path) and source.is_file():
                basename, lang = i18n.language_target(source)

                with open(source, 'rt') as fd:
                    foc = OmegaConf.load(fd)
            elif isinstance(source, io.StringIO):
                with open(source, 'rt') as fd:
                    foc = OmegaConf.load(fd)
            elif isinstance(source, DictConfig):
                foc = source
            else:
                raise Exception(f'Invalid source input: {source}')

            if theme_name != 'null' and themedp.is_dir():
                dest = self.outdirp.joinpath(f'{theme_name}.css')

                if not dest.is_file():
                    # Copy the theme's main CSS
                    shutil.copy(
                        str(themedp.joinpath(f'{theme_name}.css')),
                        str(self.outdirp)
                    )

                # Compute the CSS's relative path to the root output dir
                if destdir_root:
                    css_relp = os.path.relpath(
                        str(dest), start=str(destdir))
                else:
                    css_relp = f'{theme_name}.css'

                # Reference the CSS in <head>
                css_link = {
                    'link': {
                        '_rel': 'stylesheet',
                        '_type': 'text/css',
                        '_href': css_relp
                    }
                }

                utf8_meta = {
                    'meta': {
                        '_content': 'text/html; charset=utf-8',
                        '_http-equiv': 'Content-Type',
                    }
                }

                head = foc.get('head')
                if not head:
                    foc['head'] = {}
                    head = foc['head']

                shove(head, css_link)
                shove(head, utf8_meta)

                sel_outp = self.outdirp.joinpath('lang-selector.css')
                sel_relpath = os.path.relpath(str(sel_outp), start=str(destdir))

                sel_css_link = {
                    'link': {
                        '_rel': 'stylesheet',
                        '_type': 'text/css',
                        '_href': sel_relpath
                    }
                }

                if len(self.site_langs) > 1:
                    shove(foc.get('head'), sel_css_link)

                    shove(foc.get('body'), {
                        '.': '${lang_selector:}'
                    }, pos='first')

            convert(
                self,
                OmegaConf.to_container(foc, resolve=True),
                dom,
                destdir,
                lang=lang
            )
        except Exception:
            traceback.print_exc()
            return None, None, None

        if output:
            cid = None

            if self.sitecfg.c.ipfs_output or self.command == 'ipfs-deploy':
                out = self.output_dom(dom)
                cid = self.ipfs_add(out)

                if cid:
                    rps = self.get_target_rps()
                    if rps and self.args.pintoremote:
                        # Pin to remote service
                        self.ipfs_pinremote(rps, cid)

                    print(cid, file=sys.stdout)
            else:
                self.output_dom(dom, fd=sys.stdout)

            if cid:
                self.ipns_publish(cid)

        destp = destdir.joinpath(f'{basename}.html')
        return dom, lang, destp

    def get_target_rps(self):
        rps = self.ipfs_node_cfg.get('ipfs_rps_default')

        if is_str(rps):
            return rps
        elif self.sitecfg.c.ipfs_rps_name:
            return self.sitecfg.c.ipfs_rps_name

    def find_closest_layout(self, fp: Path, root: Path):
        """
        Find the closest .layout.yaml file (hierarchy-wise) to
        the file referenced by fp.
        """
        current = fp.parent
        dirs = [current]

        while current != root:
            current = current.parent
            dirs.append(current)

        for dir in dirs:
            layoutp = dir.joinpath('.layout.yaml')

            if layoutp.is_file():
                # TODO: check that this is a valid yaml
                return layoutp

    def process_directory(self, path: Path):
        # Copy necessary assets
        css_langsel = assets_root.joinpath('lang-selector.css')

        if css_langsel.is_file():
            shutil.copy(css_langsel, self.outdirp)

        target_langs = []

        try:
            for root, dirs, files in os.walk(path):
                rr = root.replace(str(path), '').lstrip(os.sep)

                for file in files:
                    fp = Path(root).joinpath(file)
                    layoutp = self.find_closest_layout(fp, path)

                    ddest_def = self.outdirp.joinpath(rr)
                    ddest_def.mkdir(parents=True, exist_ok=True)

                    if fp.name.startswith('.'):
                        # Ignore dot files (reserved)
                        continue

                    dom_layout, blocks = None, []
                    if layoutp:
                        # Parse the layout
                        dom_layout, lang, _ = self.process_file(layoutp,
                                                                destdir_root=ddest_def)

                        if dom_layout:
                            # Parse declared blocks

                            for node in dom_layout.iter():
                                if node.name.startswith('block_'):
                                    blocks.append(node)

                    def findblock(name):
                        for blk in blocks:
                            if blk.name == name:
                                return blk

                    if fp.name.endswith('.yaml') or fp.name.endswith('.yml'):
                        basename, lang = i18n.language_target(fp)
                        if lang and lang not in target_langs:
                            target_langs.append(lang)

                        if lang:
                            ddest = self.outdirp.joinpath(lang.pt1).joinpath(rr)
                            ddest.mkdir(parents=True, exist_ok=True)

                        else:
                            ddest = ddest_def

                        dom, _lang, dest = self.process_file(fp, destdir_root=ddest)

                        if dom_layout and len(blocks) > 0:
                            for node in dom.iter():
                                if node.name.startswith('block_'):
                                    blk = findblock(node.name)

                                    if blk is None or blk.parentNode is None:
                                        continue

                                    # Replace the node
                                    blk.parentNode.replaceChild(
                                        node.firstChild, blk)

                        dom_target = dom_layout if dom_layout else dom

                        if not dom_target:
                            raise Exception('Empty DOM')

                        self.output_dom(dom_target, dest=dest)
                    else:
                        if fp.suffix not in ['.jinja2', '.yaml']:
                            # Copy other files
                            shutil.copy(fp, str(ddest_def))

            if target_langs:
                # At least one target language. Write the main index to redirect
                # to the default language

                redir = OmegaConf.create({
                    'head': {
                        'meta': [{
                            '_http-equiv': 'Refresh',
                            '_content': f'0; url={self.lang_default.pt1}/'
                        }]
                    }
                })

                dom, _l, dest = self.process_file(
                    redir, destdir_root=self.outdirp,
                    basename='index',
                    i18n_out=False
                )

                self.output_dom(dom, dest=dest)
        except Exception:
            traceback.print_exc()
            return 1
        else:
            cid = None

            if self.sitecfg.c.ipfs_output or self.command == 'ipfs-deploy':
                cid = self.ipfs_add(str(self.outdirp))

                if cid:
                    rps = self.get_target_rps()
                    if rps and self.args.pintoremote:
                        # Pin to remote service
                        if self.ipfs_pinremote(rps, cid):
                            print(cid, file=sys.stdout)
                    else:
                        print(cid, file=sys.stdout)
            else:
                if self.args.httpserve or self.command == 'serve':
                    return http_serve(self.outdirp,
                                      port=self.sitecfg.c.http_serve_port)
                else:
                    for root, dirs, files in os.walk(str(self.outdirp)):
                        for file in files:
                            print(os.path.join(root, file), file=sys.stdout)

            if cid:
                self.ipns_publish(cid)

        return 0

    def ipns_genkey(self, name: str, type: str = 'ed25519'):
        return self.iclient.key.gen(name, type)

    def ipns_publish(self, cid):
        pk_id = None
        kn = self.args.ipns_key_name
        kid = self.args.ipns_key_id

        if not kn and not kid:
            return

        res = self.iclient.key.list()

        if res and 'Keys' in res:
            for key in res['Keys']:
                name = key.get('Name')
                _id = key.get('Id')

                if (kn and name == kn) or (kid and kid == _id):
                    pk_id = _id
                    break
        else:
            raise Exception('Cannot list IPNS keys')

        if not pk_id and kn:
            key = self.ipns_genkey(kn)
            pk_id = key['Id']
        elif pk_id:
            # Publish
            for att in range(0, 3):
                try:
                    resp = self.iclient.name.publish(cid, key=pk_id)
                    key = resp['Name']

                    print(f'/ipns/{key}', file=sys.stdout)
                    break
                except Exception as err:
                    print(f'Error publishing to {pk_id}: {err}', file=sys.stderr)
        else:
            raise Exception('Inexistent key. Please specify a key name with --ipns-name')


def list_themes():
    themes_root = pkg_resources.resource_filename(
        'iraty.themes',
        ''
    )
    for root, dirs, files in os.walk(str(themes_root)):
        for dir in dirs:
            if dir.startswith('_'):
                continue

            if root == themes_root:
                print(dir)
            else:
                print('/'.join([os.path.basename(root), dir]))


def _get_resolver_docstring(name: str):
    try:
        fn = getattr(resolvers, name)
        return inspect.getfullargspec(fn)[0], fn.__doc__
    except AttributeError:
        return None, None


def list_resolvers():
    help = ''

    for name, rslv in BaseContainer._resolvers.items():
        sig, doc = _get_resolver_docstring(name)

        if doc:
            if sig:
                argl = ','.join(list(sig))
                help += f'=> {name}({argl}):\n {doc}\n'
            else:
                help += f'=> {name}: {doc}\n'

    if shutil.which('less'):
        p = subprocess.Popen(['less'], stdin=subprocess.PIPE)
        p.communicate(input=help.encode())
    else:
        print(help)


def lint(args):
    from .config import default_lint_config
    try:
        from yamllint import linter
        from yamllint.config import YamlLintConfig
    except ImportError:
        print('The yamllint library is missing', file=sys.stderr)
        return 1

    cfg = YamlLintConfig(default_lint_config)
    errc = 0

    for root, dirs, files in os.walk(Path(args.input[0])):
        for file in files:
            if not file.endswith('.yaml') or file == '.iraty.yaml':
                continue

            fp = Path(root).joinpath(file)

            with open(fp, 'rt') as fd:
                errs = linter.run(fd, cfg)

                for err in errs:
                    print(f'({fp}): {err}', file=sys.stderr)

                    errc += 1

    return 0 if errc == 0 else 2


def iraty(args):
    config_dir = Path(appdirs.user_config_dir('iraty'))
    config_dir.mkdir(parents=True, exist_ok=True)
    nodes_config_dir = config_dir.joinpath('ipfs-nodes')
    nodes_config_dir.mkdir(parents=True, exist_ok=True)

    node_configure_default(config_dir, nodes_config_dir)

    command = args.cmd.pop()

    if command == 'list-themes':
        list_themes()
        sys.exit(0)

    elif command == 'list-resolvers':
        list_resolvers()
        sys.exit(0)

    elif command == 'lint':
        sys.exit(lint(args))

    elif command in ['node-config', 'nc']:
        cfg = node_configure(args, config_dir, nodes_config_dir)

        if not cfg:
            print('Error configuring node', file=sys.stderr)
            sys.exit(1)

        print('Connect to IPFS node and register '
              'remote pinning services ? [y/n]')

        resp = sys.stdin.readline().strip()

        if resp.lower() == 'y':
            # Register configured pinning services
            try:
                count = 0
                ic = ipfshttpclient.connect(cfg.ipfs_api_maddr)

                services = ic.pinremote.service_ls()
                csrvs = [c['Service'] for c in services['RemoteServices']]

                for name, rpsc in cfg.ipfs_rps_cfg.items():
                    ep, key = rpsc.get('endpoint'), rpsc.get('key')

                    if is_str(key) and name not in csrvs:
                        print(f'=> Adding RPS: {name} (endpoint: {ep})')

                        ic.pinremote.service_add(
                            name, ep, key
                        )

                        count += 1

                print(f'=> Registered {count} service(s)')
            except Exception as err:
                print(f'Error configuring remote pinning: {err}',
                      file=sys.stderr)
                sys.exit(1)

        sys.exit(0)

    if len(args.input) != 1:
        print('Invalid input arguments', file=sys.stderr)
        sys.exit(1)

    ncp, node_cfg = node_get_config(nodes_config_dir, args.ipfs_node)

    if not node_cfg:
        print(f'Unconfigured IPFS node: {args.ipfs_node}', file=sys.stderr)
        sys.exit(1)

    filein = args.input[0]

    try:
        maddr = args.ipfsmaddr if args.ipfsmaddr else node_cfg.ipfs_api_maddr
        iclient = ipfshttpclient.connect(maddr)
    except Exception as err:
        # Should be fatal ?
        iclient = None
        print(f'IPFS connection Error: {err}', file=sys.stderr)
    else:
        # Set global client
        resolvers.ipfs_client = iclient

    input_path = Path(filein)
    ira = Iraty(command, input_path, iclient, node_cfg, args)
    ira.start()

    if not input_path.exists():
        print(f'{input_path} does not exist', file=sys.stderr)
        sys.exit(1)

    if input_path.is_file():
        resolvers.root_input_path = input_path.parent
        jenv.loader = FileSystemLoader(str(input_path.parent))
        _dom, _l, _p = ira.process_file(input_path, destdir_root=Path('.'), output=True)
        sys.exit(0 if _dom else 1)
    elif input_path.is_dir():
        resolvers.root_input_path = input_path
        jenv.loader = FileSystemLoader([
            str(input_path),
            str(input_path.joinpath('templates')),
            str(assets_root.joinpath('jinja2')),
        ])

        sys.exit(ira.process_directory(input_path))
