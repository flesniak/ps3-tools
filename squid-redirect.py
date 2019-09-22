#!/usr/bin/env python3
## -*- coding: utf-8 -*-

import os
import logging
import sys
import re
import json
from collections import namedtuple, ChainMap

SquidRequest = namedtuple('SquidRequest', ('channel_id', 'url', 'ident'))
# If `url_rewrite_extras` are used, SquidRequest needs modifying
# Default extras: "%>a/%>A %un %>rm myip=%la myport=%lp" -> ip/fqdn ident method [urlgroup] kv-pair

log = logging.getLogger(__name__)

VERSION = '0.0'


# Utils ------------------------------------------------------------------------

def _postmortem(func, *args, **kwargs):
    import traceback
    import pdb
    import sys
    try:
        return func(*args, **kwargs)
    except Exception:
        type, value, tb = sys.exc_info()
        traceback.print_exc()
        pdb.post_mortem(tb)


def load_data(*sources):
    """
    Normalize sources from `python_dict`, `json_string` or `json_filename` -> `python_dict`

    >>> load_data({'a': 1}, '{"b": 2}') == {'a': 1, 'b': 2}
    True
    """
    def _open_source(source):
        assert source
        if isinstance(source, dict):
            return source
        if isinstance(source, str) and source.startswith('{') and source.endswith('}'):
            return json.loads(source)
        if os.path.exists(source):
            with open(source) as filehandle:
                return json.load(filehandle)

    return dict(ChainMap(*map(_open_source, sources)))


# Squid Request Processing ----------------------------------------------------

def process_squid_request(request_line, rewrite_rules={}, redirect_rules={}, **args):
    """
    Reference:
        http://www.squid-cache.org/Doc/config/url_rewrite_program/
        https://wiki.squid-cache.org/Features/Redirectors

    >>> rules = {
    ...     'rewrite_rules': {
    ...         'www\.site\.com': 'www.test.com',
    ...         '/my/path': '/my/test_path',
    ...     },
    ...     'redirect_rules': {
    ...         'www\.notreal\.com': 'www.real.com',
    ...     }
    ... }
    >>> process_squid_request('0 http://www.google.com/ -', **rules)
    '0 ERR'
    >>> process_squid_request('1 http://www.site.com/my/path.json?test=yes -', **rules)
    '1 OK rewrite-url="http://www.test.com/my/path.json?test=yes"'
    >>> process_squid_request('2 http://www.notreal.com/data?test=yes -', **rules)
    '2 OK status=301 url="http://www.real.com/data?test=yes"'
    """
    def _replace_url(url, rules, template):
        for regex, replacement in rules.items():
            if re.search(regex, url):
                return template.format(url=re.sub(regex, replacement, url))

    def _lookup_response(url):
        try:
            return next(filter(None, (
                _replace_url(url, rewrite_rules, 'rewrite-url="{url}"'),
                _replace_url(url, redirect_rules, 'status=301 url="{url}"'),
            )))
        except StopIteration:
            return None

    try:
        request = SquidRequest(*map(lambda text: text.strip(), request_line.split(' ')))
    except TypeError as ex:
        log.debug(f'unable to process: {request_line}')
        #return f'{request.channel_id} BH message="{ex}"'
        # TODO: channel_id required in response
        return 'BH'
    response = _lookup_response(request.url)
    if response:
        return f'{request.channel_id} OK {response}'
    return f'{request.channel_id} ERR'


def process_input_output_handlers(input_handle=sys.stdin, output_handle=sys.stdout, **args):
    log.debug(f'start: {__file__} {args}')
    while True:
        request_line = input_handle.readline()
        if not request_line or not request_line.strip():
            break
        log.debug(f'request: {request_line}')
        response = process_squid_request(request_line, **args)
        log.debug(f'response: {response}')
        output_handle.write(f'{response}\n')
        output_handle.flush()
    log.debug(f'end: {__file__}')



# Commandline -----------------------------------------------------------------

def get_args():
    import argparse
    parser = argparse.ArgumentParser(
        description=f'''
        Example Useage:
            python3 {__file__}
        Tests:
            pytest --doctest-modules {__file__}
        ''',
        epilog=''' ''',
        formatter_class=argparse.RawTextHelpFormatter,
    )

    parser.add_argument('--rewrite', nargs='+', help='json filename or string with key:value to rewrite', default=())
    parser.add_argument('--redirect', nargs='+', help='json filename or string with key:value to redirect', default=())

    parser.add_argument('--logfile', action='store', help='debug data logfile to write. Details start,stop,request,response')
    parser.add_argument('--postmortem', action='store_true', help='Automatically drop into pdb shell on exception. Used for debuging')
    parser.add_argument('--version', action='version', version=VERSION)

    args = vars(parser.parse_args())
    return args


if __name__ == "__main__":
    args = get_args()
    if args['logfile']:
        logging.basicConfig(filename=args['logfile'], level=logging.DEBUG)

    def main(**args):
        process_input_output_handlers(
            **{
                f'{arg}_rules': load_data(*args.get(arg))
                for arg in ('rewrite', 'redirect')
            },
            **args,
        )

    if args.get('postmortem'):
        _postmortem(main, **args)
    else:
        main(**args)
